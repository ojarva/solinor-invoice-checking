# Generated by Django 2.0 on 2018-01-21 14:48

from django.db import migrations, models
import flex_hours.models


class Migration(migrations.Migration):

    dependencies = [
        ('flex_hours', '0003_auto_20170707_0818'),
    ]

    operations = [
        migrations.AlterField(
            model_name='workcontract',
            name='worktime_percent',
            field=models.IntegerField(default=100, validators=[flex_hours.models.validate_percent_field]),
        ),
    ]
