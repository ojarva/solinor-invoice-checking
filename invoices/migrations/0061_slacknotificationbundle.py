# Generated by Django 2.0 on 2017-12-26 10:49

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoices', '0060_auto_20170522_1919'),
    ]

    operations = [
        migrations.CreateModel(
            name='SlackNotificationBundle',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('notification_type', models.CharField(max_length=50)),
                ('sent_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
    ]
