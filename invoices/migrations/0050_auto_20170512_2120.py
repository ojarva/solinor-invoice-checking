# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2017-05-12 21:20
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0049_amazoninvoicerow_invoice_month'),
    ]

    operations = [
        migrations.AlterField(
            model_name='amazoninvoicerow',
            name='total_cost',
            field=models.FloatField(blank=True, null=True),
        ),
    ]
