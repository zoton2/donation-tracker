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
    help = 'Remove all private data about one or all users.'

    def add_arguments(self, parser):
        parser.add_argument('-a', '--all', help='Remove data for all users.', action='store_true', default=False)
        parser.add_argument('-u', '--user', help='Email of donor to clear data.')
        parser.add_argument('-d', '--dry-run', help='Run the command, but do not modify the database', action='store_true')

    def handle(self, *args, **options):
        super(Command, self).handle(*args, **options)
        if options["all"]:
        	users = models.Donor.objects.all()
        else:
        	users = models.Donor.objects.filter(email=options["user"])

        for usr in users:
        	if usr.anonymized:
        		continue
        		
        	print("Scrubbing: ", usr.firstname, ' ', usr.lastname, '(', usr.email ,')')
        	if not options['dry_run']:
        		usr.identityhash = usr.calculate_hash()
        		usr.gdpr_scrub()