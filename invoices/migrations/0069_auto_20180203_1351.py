# Generated by Django 2.0 on 2018-02-03 11:51

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0068_event'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tenkfuser',
            name='email',
            field=models.CharField(blank=True, max_length=100, null=True, unique=True),
        ),
    ]