from tracker.models import *
import filters
from django.db.models import Count,Sum,Max,Avg,Q
from django.core.urlresolvers import reverse
from decimal import Decimal
import simplejson
import random
import gdata.spreadsheet.service
import settings
import datetime
import dateutil.parser
import operator
import re
import pytz

# Adapted from http://djangosnippets.org/snippets/1474/

def admin_url(obj):
  return reverse("admin:%s_%s_change" % (obj._meta.app_label, obj._meta.object_name.lower()), args=(obj.pk,), current_app=obj._meta.app_label)

def get_referer_site(request):
  origin = request.META.get('HTTP_ORIGIN', None)
  if origin != None:
    return re.sub('^https?:\/\/', '', origin)
  else:
    return None

def get_event(event):
  if event:
    if re.match('^\d+$', event):
      event = int(event)
      return Event.objects.get(id=event)
    else:
      eventSet = Event.objects.filter(short=event)
      if eventSet.exists():
        return eventSet[0]
      else:
        raise Http404
  e = Event()
  e.id = ''
  e.name = 'All Events'
  return e

# Parses a 'natural language' list, i.e. seperated by commas, semi-colons, and 'and's
def natural_list_parse(s):
  result = []
  tokens = [s]
  seperators = [',',';','&','+',' and ',' or ', ' and/or ', ' vs. ']
  for sep in seperators:
    newtokens = []
    for token in tokens:
      while len(token) > 0:
        before, found, after = token.partition(sep)
        newtokens.append(before)
        token = after
    tokens = newtokens
  return list(filter(lambda x: len(x) > 0, map(lambda x: x.strip(), tokens)))

def request_params(request):
  if request.method == 'GET':
    return request.GET
  elif request.method == 'POST':
    return request.POST
  else:
    raise Exception("No request parameters associated with this request method.")

def draw_prize(prize, seed=None):
  eligible = prize.eligible_donors()
  if prize.maxed_winners():
    if prize.maxwinners == 1:
      return False, { "error" : "Prize: " + prize.name + " already has a winner." }
    else:
      return False, { "error" : "Prize: " + prize.name + " already has the maximum number of winners allowed." }
  if not eligible:
    return False, { "error" : "Prize: " + prize.name + " has no eligible donors." }
  else:
    rand = None
    try:
      rand = random.Random(seed)
    except TypeError: # not sure how this could happen but hey
      return False, {'error': 'Seed parameter was unhashable'}
    psum = reduce(lambda a,b: a+b['weight'], eligible, 0.0)
    result = rand.random() * psum
    ret = {'sum': psum, 'result': result}
    for d in eligible:
      if result < d['weight']:
        try:
          winRecord = PrizeWinner.objects.create(prize=prize, winner=Donor.objects.get(pk=d['donor']))
          ret['winner'] = winRecord.winner.id
          winRecord.save()
        except Exception as e:
          return False, { "error" : "Error drawing prize: " + prize.name + ", " + str(e) }
        return True, ret
      result -= d['weight']
    return False, {"error" : "Prize drawing algorithm failed." }

_1ToManyBidsAggregateFilter = Q(bids__donation__transactionstate='COMPLETED')
_1ToManyDonationAggregateFilter = Q(donation__transactionstate='COMPLETED')
DonationBidAggregateFilter = _1ToManyDonationAggregateFilter
DonorAggregateFilter = _1ToManyDonationAggregateFilter
EventAggregateFilter = _1ToManyDonationAggregateFilter
PrizeWinnersFilter = Q(prizewinner__acceptstate='ACCEPTED') | Q(prizewinner__acceptstate='PENDING')

# http://stackoverflow.com/questions/5722767/django-mptt-get-descendants-for-a-list-of-nodes
def get_tree_queryset_descendants(model, nodes, include_self=False):
  if not nodes:
    return nodes
  filters = []
  for n in nodes:
    lft, rght = n.lft, n.rght
    if include_self:
      lft -=1
      rght += 1
    filters.append(Q(tree_id=n.tree_id, lft__gt=lft, rght__lt=rght))
  q = reduce(operator.or_, filters)
  return model.objects.filter(q).order_by(*model._meta.ordering)

# http://stackoverflow.com/questions/6471354/efficient-function-to-retrieve-a-queryset-of-ancestors-of-an-mptt-queryset
def get_tree_queryset_ancestors(model, nodes):
  tree_list = {}
  query = Q()
  for node in nodes:
    if node.tree_id not in tree_list:
      tree_list[node.tree_id] = []
    parent =  node.parent.pk if node.parent is not None else None,
    if parent not in tree_list[node.tree_id]:
      tree_list[node.tree_id].append(parent)
      query |= Q(lft__lt=node.lft, rght__gt=node.rght, tree_id=node.tree_id)
    return model.objects.filter(query).order_by(*model._meta.ordering)

def get_tree_queryset_all(model, nodes):
  filters = []
  for node in nodes:
    filters.append(Q(tree_id=node.tree_id))
  q = reduce(operator.or_, filters)
  return model.objects.filter(q).order_by(*model._meta.ordering)

ModelAnnotations = {
  'event'        : { 'amount': Sum('donation__amount', only=EventAggregateFilter), 'count': Count('donation', only=EventAggregateFilter), 'max': Max('donation__amount', only=EventAggregateFilter), 'avg': Avg('donation__amount', only=EventAggregateFilter) },
  'prize' : { 'numwinners': Count('winners', only=PrizeWinnersFilter), },
}

def parse_gdoc_cell_title(title):
  digit = re.search("\d", title)
  if not digit:
    return None
  letters = title[:digit.start()]
  digits = title[digit.start():]
  columnIdx = 0
  for letter in letters:
    if not re.match("[A-Z]", letter):
      return None
    columnIdx *= 26
    columnIdx += ord(letter) - ord('A')
  rowIdx = int(digits) - 1
  return columnIdx, rowIdx

def parse_gdoc_cell_headers(cells):
  headers = {}
  for cell in cells.entry:
    col,row = parse_gdoc_cell_title(cell.title.text)
    if row > 0:
      break
    while len(headers) < col:
      headers.append(None)
    headers[col] = cell.content.text.strip().lower()
  return headers

def make_empty_row(headers):
  row = {}
  for col in headers:
    row[headers[col]] = ''
  return row

def parse_gdoc_cells_as_list(cells):
  headers = parse_gdoc_cell_headers(cells)
  currentRowId = 0
  currentRow = make_empty_row(headers)
  rows = []
  for cell in cells.entry:
    col,row = parse_gdoc_cell_title(cell.title.text)
    if row == 0:
      continue
    if row != currentRowId and currentRowId != 0:
      rows.append(currentRow)
      currentRow = make_empty_row(headers)
    currentRowId = row
    if col in headers:
      currentRow[headers[col]] = cell.content.text
  if currentRowId != 0:
    rows.append(currentRow)
  return rows

def find_people(people_list):
  result = []
  for person in people_list:
      try:
        d = Donor.objects.get(alias__iequals=person)
        result.append(d)
      except:
        pass
  return result

class MarathonSpreadSheetEntry:
    def __init__(self, name, time, estimate, runners=None, commentators=None, comments=None):
      self.gamename = name
      self.starttime = time
      self.endtime = estimate
      self.runners = runners or ''; # find_people(runners)
      self.commentators = commentators or ''; # find_people(commentators)
      self.comments = comments or ''
    def __unicode__(self):
      return self.gamename
    def __repr__(self):
      return u"MarathonSpreadSheetEntry('%s','%s','%s','%s','%s','%s')" % (self.starttime,
        self.gamename, self.runners, self.endtime, self.commentators, self.comments)



def parse_row_entry(event, rowEntries):
  estimatedTimeDelta = datetime.timedelta()
  postGameSetup = datetime.timedelta()
  comments = ''
  commentators = ''
  if rowEntries[event.scheduledatetimefield]:
    startTime = dateutil.parser.parse(rowEntries[event.scheduledatetimefield])
  else:
    return None
  gameName = rowEntries[event.schedulegamefield].strip()

  canonicalGameNameForm = gameName.lower()

  if not canonicalGameNameForm or canonicalGameNameForm in ['start', 'end', 'finale', 'total:'] or 'setup' in canonicalGameNameForm:
    return None

  runners = rowEntries[event.schedulerunnersfield]; # natural_list_parse(rowEntries[event.schedulerunnersfield])
  if event.scheduleestimatefield and rowEntries[event.scheduleestimatefield]:
    toks = rowEntries[event.scheduleestimatefield].split(":")
    if len(toks) == 3:
      estimatedTimeDelta = datetime.timedelta(hours=int(toks[0]), minutes=int(toks[1]), seconds=int(toks[2]))
  # I'm not sure what should be done with the post-game set-up field...
  if event.schedulesetupfield:
    if rowEntries[event.schedulesetupfield]:
      toks = rowEntries[event.schedulesetupfield].split(":")
      if len(toks) == 3:
        postGameSetup = datetime.timedelta(hours=int(toks[0]), minutes=int(toks[1]), seconds=int(toks[2]))
  if event.schedulecommentatorsfield:
    commentators = rowEntries[event.schedulecommentatorsfield] # natural_list_parse(rowEntries[event.schedulecommentatorsfield])
  if event.schedulecommentsfield:
    comments = rowEntries[event.schedulecommentsfield]
  estimatedTime = startTime + estimatedTimeDelta
  # Convert the times into UTC
  timezone = pytz.timezone(event.scheduletimezone)
  startTime = timezone.localize(startTime)
  estimatedTime = timezone.localize(estimatedTime)
  ret = MarathonSpreadSheetEntry(gameName, startTime, estimatedTime+postGameSetup, runners, commentators, comments)
  return ret


def prizecmp(a,b):
  # if both prizes are run-linked, sort them that way
  if a.startrun and b.startrun:
    return cmp(a.startrun.starttime,b.startrun.starttime) or cmp(a.endrun.endtime,b.endrun.endtime) or cmp(a.name,b.name)
  # else if they're both time-linked, sort them that way
  if a.starttime and b.starttime:
    return cmp(a.starttime,b.starttime) or cmp(a.endtime,b.endtime) or cmp(a.name,b.name)
  # run-linked prizes are listed after time-linked and non-linked
  if a.startrun and not b.startrun:
    return 1
  if b.startrun and not a.startrun:
    return -1
  # time-linked prizes are listed after non-linked
  if a.starttime and not b.starttime:
    return 1
  if b.starttime and not a.starttime:
    return -1
  # sort by category or name as a fallback
  return cmp(a.category,b.category) or cmp(a.name,b.name)

def merge_schedule_list(event, scheduleList):
  try:
    runs = filter(lambda r: r != None, map(lambda x: parse_row_entry(event, x), scheduleList))
  except KeyError, k:
    raise Exception('KeyError, \'%s\' make sure the column names are correct' % k.args[0])
  existingruns = dict(map(lambda r: (r.name.lower(),r),SpeedRun.objects.filter(event=event)))

  scheduleRunNames = set()
  addedRuns = []

  for run in runs:
    uniqueGameName = run.gamename.lower()
    if uniqueGameName in scheduleRunNames:
      raise Exception('Merged schedule has two runs with the same name \'%s\'' % uniqueGameName)
    scheduleRunNames.add(uniqueGameName)
    if uniqueGameName in existingruns.keys():
      r = existingruns[uniqueGameName]
    else:
      r = SpeedRun(name=run.gamename, event=event, description=run.comments)
      addedRuns.append(r)
    r.name = run.gamename
    r.deprecated_runners = run.runners
    #for runner in run.runners:
    #  r.runners.add(runner)
    r.starttime = run.starttime
    r.endtime = run.endtime
    r.save()

  removedRuns = []
  
  for existingRunName, existingRun in existingruns.items():
    if existingRunName not in scheduleRunNames:
      removedRuns.append(existingRun) 

  # Eventually we may want to have something that asks for user descisions regarding runs added/removed
  # from the schdule, for now, we take the schedule as cannon
  for run in removedRuns:
    run.delete()

  prizes = sorted(Prize.objects.filter(event=event),cmp=prizecmp)
  return len(runs)

def merge_schedule_gdoc(event):
  # This is required by the gdoc api to identify the name of the application making the request, but it can basically be any string
  PROGRAM_NAME = "sda-webtracker"
  spreadsheetService = gdata.spreadsheet.service.SpreadsheetsService()
  spreadsheetService.ClientLogin(settings.GDOC_USERNAME, settings.GDOC_PASSWORD)
  cellFeed = spreadsheetService.GetCellsFeed(key=event.scheduleid)
  return merge_schedule_list(event, parse_gdoc_cells_as_list(cellFeed))

EVENT_SELECT = 'admin-event'

def get_selected_event(request):
  evId = request.session.get(EVENT_SELECT, None)
  if evId:
    return Event.objects.get(pk=evId)
  else:
    return None

def set_selected_event(request, event):
  if event:
    request.session[EVENT_SELECT] = event.id
  else:
    request.session[EVENT_SELECT] = None

