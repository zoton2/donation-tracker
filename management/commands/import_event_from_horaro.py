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
        parser.add_argument('-e', '--event', help='name of horaro event to import', required=True, default="esa/2018-winter")

    def handle(self, *args, **options):
        super(Command, self).handle(*args, **options)

        url = "https://horaro.org/" + options["event"] + ".json?named=true"
        data = json.loads(urllib.urlopen(url).read())

        raw_runs = data['schedule']['items']
        runs = map( get_run, range(1,len(raw_runs)+1), raw_runs )
        print(map((lambda r: r.order), runs))

def get_run(order, json_run):
    name = ""
    name_match = re.match("\[(.*)\]\((.*)\)", json_run['data'][0], flags=re.U or re.S)
    if name_match:
        name = name_match.group(1)
        
    start_time = dateutil.parser.parse(json_run['scheduled'])
    run_duration = timedelta(seconds=json_run['length_t'])

    run = models.SpeedRun(
        name = name,
        console = json_run['data'][2],
        starttime = start_time,
        endtime = start_time+run_duration,
        order = order,
        run_time = json_run['length_t']*1000,
        setup_time = 10*60*1000,
        category = json_run['data'][3],
    )
    run.save()

    raw_runners = (json_run['data'][1]).split(',')
    for raw_runner in raw_runners:
        runner_match = re.match("\[(.*)\]\((.*)\)", raw_runner, flags=re.U or re.S)
        if runner_match:
            runner_name = runner_match.group(1)
            runner_stream = runner_match.group(2)
            runner = get_runner(runner_name, runner_stream)

            if runner != None:
                run.runners.add(runner)
                run.save()

    return run

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