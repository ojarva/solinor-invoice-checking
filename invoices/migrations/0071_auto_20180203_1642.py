# Generated by Django 2.0 on 2018-02-03 14:42

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0070_tenkfuser_updated_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='hourentry',
            name='created_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='hourentry',
            name='updated_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='hourentry',
            name='upstream_id',
            field=models.IntegerField(blank=True, null=True, unique=True),
        ),
    ]
