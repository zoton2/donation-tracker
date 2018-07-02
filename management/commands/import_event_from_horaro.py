from django.core.management.base import BaseCommand, CommandError

import settings
import urllib, json
import re
import dateutil.parser
from datetime import datetime, timedelta

import tracker.models as models
import tracker.viewutil as viewutil
import tracker.prizemail as prizemail
import tracker.commandutil as commandutil

class Command(commandutil.TrackerCommand):
    help = 'Import event from horaro'

    def add_arguments(self, parser):
        parser.add_argument('-he', '--horaro', help='name of horaro event to import', required=True, default="esa/2018-winter")
        parser.add_argument('-e', '--event', help='name of event to import to', required=False, default="")

    def handle(self, *args, **options):
        super(Command, self).handle(*args, **options)

        url = "https://horaro.org/" + options["horaro"] + ".json?named=true"
        data = json.loads(urllib.urlopen(url).read())
        event = models.event.LatestEvent()
        try:
            event = models.Event.objects.get(short=options["event"])
        except models.Event.DoesNotExist:
            event = models.event.LatestEvent()

        raw_runs = data['schedule']['items']
        base_setup_time = (data['schedule']['setup_t']) * 1000
        setup_time = 0
        order=0
        for raw_run in raw_runs:
            order += 1
            get_run(event, order, raw_run, setup_time)
            options = raw_run['options']
            if options != None:
                setup_time = parse_duration(options['setup'] or "0m").seconds * 1000
            else:
                setup_time = base_setup_time

def get_run(event, order, json_run, setup_time = 0):
    name = ""
    name_match = re.match(r"^\[?(.*)\]?\(?(.*)?\)?", json_run['data'][0], flags=re.U or re.S)
    if name_match:
        name = name_match.group(1)

    category = json_run['data'][3]
    print(name, category)

    run = None
    try:
        run = models.SpeedRun.objects.get(name=name, category=category, event=event)
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
        run.console = json_run['data'][2]
        run.run_time = json_run['length_t']*1000
        run.setup_time = setup_time
        run.save()

        raw_runners = (json_run['data'][1]).split(',')
        for raw_runner in raw_runners:
            runner_match = re.match("\[?(.*)\]?\(?(.*)?\)?", raw_runner, flags=re.U or re.S)
            if runner_match:
                runner_name = runner_match.group(1)
                runner_stream = runner_match.group(2)
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