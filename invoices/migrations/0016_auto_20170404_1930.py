# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2017-04-04 19:30
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0015_auto_20170404_1708'),
    ]

    operations = [
        migrations.AddField(
            model_name='comments',
            name='checked_changes_last_month',
            field=models.NullBooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='comments',
            name='checked',
            field=models.NullBooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='comments',
            name='checked_bill_rates_ok',
            field=models.NullBooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='comments',
            name='checked_non_billable_ok',
            field=models.NullBooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='comments',
            name='checked_phases_ok',
            field=models.NullBooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='comments',
            name='user',
            field=models.TextField(default='', max_length=100),
            preserve_default=False,
        ),
    ]
