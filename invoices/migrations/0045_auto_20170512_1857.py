# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2017-05-12 18:57
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0044_auto_20170512_1856'),
    ]

    operations = [
        migrations.AlterField(
            model_name='amazoninvoicerow',
            name='usage_quantity',
            field=models.FloatField(blank=True, null=True),
        ),
    ]
