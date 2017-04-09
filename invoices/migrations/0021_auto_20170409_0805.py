# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2017-04-09 08:05
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0020_auto_20170407_1238'),
    ]

    operations = [
        migrations.AddField(
            model_name='comments',
            name='invoice_number',
            field=models.IntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='comments',
            name='invoice_sent_to_customer',
            field=models.BooleanField(default=False),
        ),
    ]