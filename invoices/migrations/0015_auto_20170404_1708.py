# -*- coding: utf-8 -*-
# Generated by Django 1.9.7 on 2017-04-04 17:08
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0014_invoice_tags'),
    ]

    operations = [
        migrations.AlterField(
            model_name='hourentry',
            name='notes',
            field=models.CharField(max_length=1000, null=True),
        ),
        migrations.AlterField(
            model_name='invoice',
            name='has_comments',
            field=models.NullBooleanField(choices=[(None, 'Unknown'), (True, 'Yes'), (False, 'No')], default=False),
        ),
        migrations.AlterField(
            model_name='invoice',
            name='is_approved',
            field=models.NullBooleanField(choices=[(None, 'Unknown'), (True, 'Yes'), (False, 'No')], default=False),
        ),
    ]
