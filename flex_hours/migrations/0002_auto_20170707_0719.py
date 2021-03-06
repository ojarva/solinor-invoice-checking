# -*- coding: utf-8 -*-
# Generated by Django 1.11.1 on 2017-07-07 07:19
from __future__ import unicode_literals

import datetime
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0060_auto_20170522_1919'),
        ('flex_hours', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='FlexTimeCorrection',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('adjust_by', models.DecimalField(decimal_places=2, max_digits=6)),
                ('set_to', models.DecimalField(decimal_places=2, max_digits=6)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='invoices.FeetUser')),
            ],
        ),
        migrations.CreateModel(
            name='PublicHoliday',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('date', models.DateField()),
            ],
        ),
        migrations.AddField(
            model_name='workcontract',
            name='end_date',
            field=models.DateField(default=datetime.date(2017, 7, 7)),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='workcontract',
            name='flex_enabled',
            field=models.BooleanField(default=False),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='workcontract',
            name='start_date',
            field=models.DateField(default=datetime.date(2017, 7, 7)),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='workcontract',
            name='worktime_percent',
            field=models.IntegerField(blank=True, null=True),
        ),
    ]
