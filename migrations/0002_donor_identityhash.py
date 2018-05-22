# -*- coding: utf-8 -*-
# Generated by Django 1.9.13 on 2018-05-22 20:27
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tracker', '0001_squashed_0039_upgrade_to_19'),
    ]

    operations = [
        migrations.AddField(
            model_name='donor',
            name='identityhash',
            field=models.CharField(max_length=64, null=True, unique=True, verbose_name=b'Email Hash'),
        ),
    ]
