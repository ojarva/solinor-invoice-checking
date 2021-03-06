"""
Listen to `request-refresh` redis pubsub, and process 10000ft hour entry updates, and send Slack notifications.

Multiple simultaneous requests are queued, but executed one by one.

Never run more than one instance of this command - pubsub will deliver requests to each instance, and you will have some surprising behaviour out of the system.
"""
import datetime
import json
import logging

import redis
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from flex_hours.utils import send_flex_saldo_notifications
from invoices.models import DataUpdate, SlackNotificationBundle
from invoices.slack import send_unapproved_hours_notifications, send_unsubmitted_hours_notifications
from invoices.syncing.tenkfeet import HourEntryUpdate, refresh_invoice_stats


def update_10kf_data(logger, data, redis_instance):
    now = timezone.now()
    if not data.get("force", False):
        try:
            latest_run = DataUpdate.objects.exclude(finished_at=None).latest("finished_at")
            if now - latest_run.finished_at < datetime.timedelta(seconds=10):
                logger.info("Last hour entry update finished recently. Skipping this data update.")
                latest_run.aborted = True
                latest_run.save()
                return
        except DataUpdate.DoesNotExist:
            pass
    update_obj = DataUpdate.objects.filter(started_at=None).filter(aborted=False)
    obj_count = update_obj.count()
    if obj_count > 1:
        update_obj.update(aborted=True)
        update_obj = update_obj[obj_count - 1]
    else:
        update_obj = DataUpdate()
    DataUpdate.objects.filter(aborted=False).filter(finished_at=None).update(aborted=True)
    update_obj.aborted = False
    update_obj.started_at = timezone.now()
    update_obj.save()
    start_date = datetime.datetime.strptime(data["start_date"], "%Y-%m-%d").date()
    end_date = datetime.datetime.strptime(data["end_date"], "%Y-%m-%d").date()
    logger.info("Updating hour entries.")
    update_obj.started_at = timezone.now()
    hour_entry_update = HourEntryUpdate(start_date, end_date)
    _, _, updated_entries_count = hour_entry_update.update()
    logger.info("Hour entry update done.")
    if updated_entries_count > 0:
        logger.info("Update invoice statistics.")
        refresh_invoice_stats(start_date, end_date)
        logger.info("Invoice statistics updated.")
    else:
        logger.info("No entries were updated - skipped updating invoice statistics")
    update_obj.finished_at = timezone.now()
    update_obj.aborted = False
    update_obj.save()
    redis_instance.set("last-data-update", str(timezone.now()))


def time_since_last_slack_notification(notification_type):
    try:
        last_notification = SlackNotificationBundle.objects.filter(notification_type=notification_type).latest()
    except SlackNotificationBundle.DoesNotExist:
        return datetime.timedelta(days=365)
    return timezone.now() - last_notification.sent_at


def slack_unapproved_notifications(logger, data):
    if time_since_last_slack_notification("unapproved") < datetime.timedelta(hours=12):
        logger.error("Skip sending unapproved slack notifications - last notification sent too recently.")
    today = datetime.date.today()
    if "start_date" not in data:
        end_date = today - datetime.timedelta(today.isoweekday())
        start_date = end_date - datetime.timedelta(days=60)
    else:
        start_date = datetime.datetime.strptime(data["start_date"], "%Y-%m-%d").date()
        end_date = datetime.datetime.strptime(data["end_date"], "%Y-%m-%d").date()
    send_unapproved_hours_notifications(start_date, end_date)


def slack_flex_saldo_notifications(logger):
    if time_since_last_slack_notification("flex") < datetime.timedelta(hours=12):
        logger.error("Skip sending flex saldo notifications - last notification sent too recently.")
    today = datetime.date.today()
    send_flex_saldo_notifications(today.year, today.month)


def slack_unsubmitted_notifications(logger, data):
    if time_since_last_slack_notification("unsubmitted") < datetime.timedelta(hours=12):
        logger.error("Skip sending unsubmitted slack notifications - last notification sent too recently.")
    today = datetime.date.today()
    if "start_date" not in data:
        end_date = today - datetime.timedelta(today.isoweekday())
        start_date = end_date - datetime.timedelta(days=60)
    else:
        start_date = datetime.datetime.strptime(data["start_date"], "%Y-%m-%d").date()
        end_date = datetime.datetime.strptime(data["end_date"], "%Y-%m-%d").date()
    send_unsubmitted_hours_notifications(start_date, end_date)


class Command(BaseCommand):
    help = "Run background worker to import hour entries from 10000ft, and to send slack notifications. NEVER RUN MORE THAN ONE INSTANCE OF THIS COMMAND SIMULTANEOUSLY."

    def handle(self, *args, **options):
        logger = logging.getLogger(__name__)  # pylint: disable=invalid-name

        redis_instance = redis.from_url(settings.REDIS)
        pubsub = redis_instance.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe("request-refresh")
        for entry in pubsub.listen():
            logger.info("Received %s from redis queue", entry)
            data = json.loads(entry["data"])
            if data["type"] == "data-update":
                update_10kf_data(logger, data, redis_instance)
            elif data["type"] == "slack-unsubmitted-notification":
                slack_unsubmitted_notifications(logger, data)
            elif data["type"] == "slack-unapproved-notification":
                slack_unapproved_notifications(logger, data)
            elif data["type"] == "slack-flex-saldo-notification":
                slack_flex_saldo_notifications(logger)
            else:
                logger.error("Unhandled data: %s", entry)
