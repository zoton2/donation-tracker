from django.core.management.base import BaseCommand, CommandError
from bs4 import BeautifulSoup
from markdown import markdown

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
        parser.add_argument('-he', '--horaro', help='name of horaro event to import', required=True, default="")
        parser.add_argument('-e', '--event', help='name of event to import to', required=True, default="")
        parser.add_argument('-rc', '--runnercol', help='column name for runners', required=False, default="Player(s)")
        parser.add_argument('-gc', '--gamecol', help='column name for games', required=False, default="Game")
        parser.add_argument('-cc', '--categorycol', help='column name for categorys', required=False, default="Category")
        parser.add_argument('-pc', '--platformcol', help='column name for platforms', required=False, default="Platform")
        parser.add_argument('-s', '--safe', help="Don't delete anything", action='store_true')

    def handle(self, *args, **options):
        super(Command, self).handle(*args, **options)

        url = "https://horaro.org/" + options["horaro"] + ".json?named=true"
        data = json.loads(urllib.urlopen(url).read())
        event = models.Event.objects.get(short=options["event"])

        #Remove any existing order to prevent duplicate orders and so we can delete all the unordered ones afterwards.
        models.SpeedRun.objects.filter(event=event.id).update(order=None)

        raw_runs = data['schedule']['items']
        base_setup_time = (data['schedule']['setup_t']) * 1000

        columns = get_columns(data['schedule'])

        order=0
        for (raw_run, peek) in setup_peek(raw_runs):
            order += 1
            setup_time = base_setup_time
            if peek is not None and 'options' in peek and peek['options'] is not None and 'setup' in peek['options']:
                setup_time = parse_duration(peek['options']['setup']).seconds * 1000

            get_run(event, columns, order, raw_run, options, setup_time)

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
    return columns

def get_run(event, columns, order, json_run, options, setup_time = 0):
    name = strip_markdown(json_run['data'][columns[options["gamecol"]]])[:64] #Truncate becuase DB limitation
    category = json_run['data'][columns[options["categorycol"]]] or "N/A"
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
        if options["platformcol"] in columns and json_run['data'][columns[options["platformcol"]]]:
            run.console = json_run['data'][columns[options["platformcol"]]]
        run.run_time = json_run['length_t']*1000
        run.setup_time = setup_time
        
        run.save()

        if json_run['data'][columns[options["runnercol"]]]:
            runner_column = strip_markdown(json_run['data'][columns[options["runnercol"]]])
            raw_runners = runner_column.replace(' vs. ', ', ').split(', ')
            for raw_runner in raw_runners:
                runner_name = raw_runner
                runner = get_runner(runner_name)
                if runner != None:
                    run.runners.add(runner)
                    run.save()

        return run
    return None

def get_runner(name):
    try:
        return models.Runner.objects.get(name=name)

    except models.Runner.DoesNotExist: 
        runner = models.Runner(
            name = name,
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

def strip_markdown(str):
    html = markdown(str)
    text = ''.join(BeautifulSoup(html).findAll(text=True))
    return text