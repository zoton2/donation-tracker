from django.core.management.base import BaseCommand, CommandError

import settings
import urllib, json
import re
import dateutil.parser
from datetime import datetime, timedelta
from itertools import izip_longest, tee

import tracker.models as models
import tracker.viewutil as viewutil
import tracker.prizemail as prizemail
import tracker.commandutil as commandutil

class Command(commandutil.TrackerCommand):
    help = 'Import event from horaro'

    def add_arguments(self, parser):
        parser.add_argument('-he', '--horaro', help='name of horaro event to import', required=True, default="esa/2018-winter")
        parser.add_argument('-e', '--event', help='name of event to import to', required=False, default="")
        parser.add_argument('-s', '--safe', help="Don't delete anything", action='store_true')
        parser.add_argument('-l', '--linked', help="Horaro entries have links attached", action='store_true')

    def handle(self, *args, **options):
        super(Command, self).handle(*args, **options)

        url = "https://horaro.org/" + options["horaro"] + ".json?named=true"
        data = json.loads(urllib.urlopen(url).read())
        event = models.event.LatestEvent()
        try:
            event = models.Event.objects.get(short=options["event"])
        except models.Event.DoesNotExist:
            event = models.event.LatestEvent()

        #Remove any existing order to prevent duplicate orders and so we can delete all the unordered ones afterwards.
        models.SpeedRun.objects.filter(event=event.id).update(order=None)

        raw_runs = data['schedule']['items']
        base_setup_time = (data['schedule']['setup_t']) * 1000

        columns = get_columns(data['schedule'])

        order=0
        for (raw_run, peek) in setup_peek(raw_runs):
            order += 1
            setup_time = base_setup_time
            if peek != None and 'options' in peek and 'setup' in peek['options']:
                setup_time = parse_duration(peek['options']['setup']).seconds * 1000

            get_run(event, columns, order, raw_run, setup_time)

        if options["safe"]:
            print("Would have deleted:")
            for run in models.SpeedRun.objects.filter(event=event.id,order=None):
                print(run.name, run.category)
        else:
            print("Deleting {0} runs".format(models.SpeedRun.objects.filter(event=event.id,order=None).count()))
            #Clear out any old runs that still linger, which means they are deleted from Horaro.
            models.SpeedRun.objects.filter(event=event.id,order=None).delete()


def get_columns(schedule):
    columns = dict()
    for id, col in enumerate(schedule["columns"]):
        columns[col] = id
    if not "Player(s)" in columns and "Runner(s)" in columns:
         columns["Player(s)"] = columns["Runner(s)"]
    if not "Player(s)" in columns and "Runner" in columns:
         columns["Player(s)"] = columns["Runner"]

    return columns
            
offline_id = 1

def get_run(event, columns, order, json_run, setup_time = 0):
    name = json_run['data'][columns["Game"]]
    if name[0] == '[':
        name_match = re.match(r"^\[(.*)\]\((.*)\)?", name, flags=re.U or re.S)
        if name_match:
            name = name_match.group(1)

    if name == "OFFLINE":
        global offline_id
        name = "OFFLINE {0}".format(offline_id)
        offline_id += 1

    name = name[:64] #Truncate becuase DB limitation

    category = json_run['data'][columns["Category"]] or "Sleep%"
    print(name, category)

    run = None
    try:
        run = models.SpeedRun.objects.get(name__iexact=name, category__iexact=category, event=event)
    except models.SpeedRun.DoesNotExist:
        run = models.SpeedRun(
            name = name,
            category = category,
            event = event,
        )

    if run != None:
        start_time = dateutil.parser.parse(json_run['scheduled'])
        run_duration = timedelta(seconds=json_run['length_t'])

        run.order = order
        run.starttime = start_time
        run.endtime = start_time+run_duration
        if "Platform" in columns:
            run.console = json_run['data'][columns["Platform"]]
        else:
            run.console = "N/A"

        run.run_time = json_run['length_t']*1000
        run.setup_time = setup_time
        
        run.save()

        if json_run['data'][columns["Player(s)"]]:
            runner_column = json_run['data'][columns["Player(s)"]]
            if runner_column[0] == '[':
                #ESA mode
                raw_runners = re.findall(r"\[([^ \[\]]*)\]\(([^ \(\)]*)\)", runner_column)

                #if len(raw_runners) < 1:
                #    raw_runners = (json_run['data'][1]).replace("vs.", ',').split(',')

                for raw_runner in raw_runners:
                    runner_name = raw_runner[0]
                    runner_stream = raw_runner[1]
                    runner = get_runner(runner_name, runner_stream)
                    if runner != None:
                        run.runners.add(runner)
                        run.save()
            elif event.short.startswith('uksg'):
                #UKSG mode
                raw_runners = runner_column.split("&")
                raw_runner_streams = json_run['data'][columns["Twitch Username(s)"]].split('&')
                for (raw_runner,raw_twitch) in zip(raw_runners, raw_runner_streams):
                    runner_name = raw_runner.strip()
                    runner_stream = "https://twitch.tv/" + raw_twitch.strip()
                    runner = get_runner(runner_name, runner_stream)
                    if runner != None:
                        run.runners.add(runner)
                        run.save()

        return run
    return None

def get_runner(name, stream):
    try:
        return models.Runner.objects.get(name=name)

    except models.Runner.DoesNotExist: 
        runner = models.Runner(
            name = name,
            stream = stream,
            donor = get_donor(name)
        )
        runner.save()

        return runner
    return None

def get_donor(name):
    try: 
        return models.Donor.objects.get(alias=name)
    except models.Donor.DoesNotExist:
        return None

def parse_duration(duration):
    num = int(duration[:-1])
    if duration.endswith('s'):
        return timedelta(seconds=num)
    elif duration.endswith('m'):
        return timedelta(minutes=num)
    elif duration.endswith('h'):
        return timedelta(hours=num)
    elif duration.endswith('d'):
        return timedelta(days=num)

def setup_peek(raw_runs):
    iterator, peeker = tee(iter(raw_runs))
    next(peeker)
    return izip_longest(iterator, peeker, fillvalue=None)