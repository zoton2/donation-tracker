# -*- coding: utf-8 -*-
# Generated by Django 1.9.13 on 2018-01-18 09:19
from __future__ import unicode_literals

from django.db import migrations, models
import tracker.validators


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0038_add_donation_indices'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='credentialsmodel',
            name='id',
        ),
        migrations.RemoveField(
            model_name='flowmodel',
            name='id',
        ),
        migrations.AlterModelOptions(
            name='userprofile',
            options={'permissions': (('show_rendertime', 'Can view page render times'), ('show_queries', 'Can view database queries'), ('can_search', 'Can use search url')), 'verbose_name': 'User Profile'},
        ),
        migrations.RemoveField(
            model_name='event',
            name='schedulecommentatorsfield',
        ),
        migrations.RemoveField(
            model_name='event',
            name='schedulecommentsfield',
        ),
        migrations.RemoveField(
            model_name='event',
            name='scheduledatetimefield',
        ),
        migrations.RemoveField(
            model_name='event',
            name='scheduleestimatefield',
        ),
        migrations.RemoveField(
            model_name='event',
            name='schedulegamefield',
        ),
        migrations.RemoveField(
            model_name='event',
            name='schedulerunnersfield',
        ),
        migrations.RemoveField(
            model_name='event',
            name='schedulesetupfield',
        ),
        migrations.RemoveField(
            model_name='event',
            name='scheduletimezone',
        ),
        migrations.AlterField(
            model_name='donationbid',
            name='amount',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=20, validators=[tracker.validators.positive, tracker.validators.nonzero]),
        ),
        migrations.AlterField(
            model_name='event',
            name='scheduleid',
            field=models.CharField(blank=True, editable=False, max_length=128, null=True, unique=True, verbose_name=b'Schedule ID (LEGACY)'),
        ),
        migrations.DeleteModel(
            name='CredentialsModel',
        ),
        migrations.DeleteModel(
            name='FlowModel',
        ),
    ]
