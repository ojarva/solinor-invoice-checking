import datetime
import hashlib
import json
import logging
from collections import defaultdict

from django.conf import settings
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_date as parse_date_django

from flex_hours.models import PublicHoliday
from invoices.invoice_utils import calculate_entry_stats, get_aws_entries
from invoices.models import HourEntry, HourEntryChecksum, Invoice, Project, TenkfUser, is_phase_billable
from invoices.slack import send_slack_notification
from invoices.tenkfeet_api import TenkFeetApi

logger = logging.getLogger(__name__)  # pylint: disable=invalid-name
tenkfeet_api = TenkFeetApi(settings.TENKFEET_AUTH)  # pylint: disable=invalid-name

STATS_FIELDS = [
    "incorrect_entries_count",
    "billable_incorrect_price_count",
    "non_billable_hours_count",
    "non_phase_specific_count",
    "not_approved_hours_count",
    "empty_descriptions_count",
]


def daterange(start_date, end_date):
    for n in range(int((end_date - start_date).days)):
        yield start_date + datetime.timedelta(n)


def get_weekend_hours_per_user(start_date, end_date, incurred_hours_threshold):
    holidays_list = PublicHoliday.objects.filter(date__gte=start_date).filter(date__lte=end_date)
    holidays = {item.date: item.name for item in holidays_list}
    hour_markings = HourEntry.objects.filter(date__gte=start_date).filter(date__lte=end_date).filter(Q(date__week_day=1) | Q(date__week_day=7)).order_by("user_m", "date").values("user_m", "date").annotate(sum_hours=Sum("incurred_hours")).filter(sum_hours__gte=incurred_hours_threshold)


def get_overly_long_days_per_user(start_date, end_date, incurred_hours_threshold):
    hour_markings = HourEntry.objects.filter(date__gte=start_date).filter(date__lte=end_date).order_by("user_m", "date").values("user_m", "date").annotate(sum_hours=Sum("incurred_hours")).filter(sum_hours__gte=incurred_hours_threshold)


def parse_date(date):
    if date:
        return parse_date_django(date)


def parse_float(data):
    try:
        return float(data)
    except TypeError:
        return 0


def update_users():
    logger.info("Updating users")
    tenkfeet_users = tenkfeet_api.fetch_users()
    total_updated = 0
    for user in tenkfeet_users:
        user_email = user["email"].lower()
        user_fields = {
            "user_id": user["id"],
            "first_name": user["first_name"],
            "last_name": user["last_name"],
            "archived": user["archived"],
            "display_name": user["display_name"],
            "email": user_email,
            "billable": user["billable"],
            "hire_date": user["hire_date"],
            "termination_date": user["termination_date"],
            "mobile_phone": user["mobile_phone"],
            "invitation_pending": user["invitation_pending"],
            "billability_target": user["billability_target"],
            "created_at": user["created_at"],
            "archived_at": user["archived_at"],
            "thumbnail": user["thumbnail"],
        }
        user_obj, _ = TenkfUser.objects.update_or_create(guid=user["guid"], defaults=user_fields)
        updated_objects = HourEntry.objects.filter(user_email__iexact=user_email).filter(user_m=None).update(user_m=user_obj)
        logger.debug("Updated %s to %s entries", user_email, updated_objects)
        total_updated += updated_objects
    logger.info("Updated %s hour entries and %s users", total_updated, len(tenkfeet_users))


def update_projects():
    logger.info("Updating projects")
    tenkfeet_projects = tenkfeet_api.fetch_projects()
    projects = []
    for project in tenkfeet_projects:
        project_fields = {
            "project_id": project["id"],
            "project_state": project["project_state"],
            "client": project["client"],
            "name": project["name"],
            "parent_id": project["parent_id"],
            "phase_name": project["phase_name"],
            "archived": project["archived"],
            "created_at": project["created_at"],
            "archived_at": project["archived_at"],
            "description": project["description"],
            "starts_at": project["starts_at"],
            "ends_at": project["ends_at"],
        }
        project_obj, created = Project.objects.update_or_create(guid=project["guid"],
                                                                defaults=project_fields)
        user_cache = {}

        for tag in project["tags"]["data"]:
            tag_value = tag["value"]
            if tag_value in user_cache:
                matching_users = user_cache[tag_value]
            else:
                try:
                    first_name, last_name = tag_value.split(" ", 1)
                except ValueError:
                    logger.info("Invalid tag: %s for %s", tag, project["id"])
                matching_users = TenkfUser.objects.filter(first_name=first_name, last_name=last_name)
                logger.debug("Matched %s to tag %s; first_name=%s, last_name=%s", matching_users, tag, first_name, last_name)
                user_cache[tag_value] = matching_users

            project_obj.admin_users.clear()
            for matching_user in matching_users:
                project_obj.admin_users.add(matching_user)
        project_obj.save()
        projects.append(project_obj)
        if created:
            send_slack_notification(project_obj)
    logger.info("Finished updating projects (n=%s)", len(projects))
    for invoice in Invoice.objects.filter(project_m=None):
        for project in projects:
            if project.name == invoice.project and project.client == invoice.client:
                logger.info("Updating invoice %s with project %s", invoice, project)
                invoice.project_m = project
                invoice.save()
                break


def get_projects():
    projects_data = {}
    for project in Project.objects.all():
        projects_data[project.project_id] = project
    return projects_data


def get_invoices():
    invoices_data = {}
    for invoice in Invoice.objects.all():
        invoice_key = u"%s-%s %s - %s" % (invoice.year, invoice.month, invoice.client, invoice.project)
        invoices_data[invoice_key] = invoice
    return invoices_data


def get_users():
    users = {}
    for user in TenkfUser.objects.all():
        users[user.email] = user
    return users


class HourEntryUpdate(object):
    def __init__(self, start_date, end_date):
        self.logger = logging.getLogger(__name__)
        self.invoices_data = get_invoices()
        self.projects_data = get_projects()
        self.user_data = get_users()
        self.start_date = start_date
        self.end_date = end_date
        self.first_entry = datetime.date(2100, 1, 1)
        self.last_entry = datetime.date(1970, 1, 1)

    def update_range(self, date):
        self.last_entry = max(self.last_entry, date)
        self.first_entry = min(self.first_entry, date)

    def match_project(self, project_id):
        return self.projects_data.get(project_id, None)

    def match_invoice(self, data):
        invoice_key = u"%s-%s %s - %s" % (data["date"].year, data["date"].month, data["client"], data["project"])
        invoice = self.invoices_data.get(invoice_key)
        if invoice:
            logger.debug("Invoice already exists: %s", invoice_key)
            if invoice.tags != data["project_tags"]:
                invoice.tags = data["project_tags"]
                invoice.save()
            return invoice
        else:
            logger.info("Creating a new invoice: %s", invoice_key)
            invoice, _ = Invoice.objects.update_or_create(year=data["date"].year, month=data["date"].month, client=data["client"], project=data["project"], defaults={"tags": data["project_tags"]})
            self.invoices_data[invoice_key] = invoice
            return invoice

    def match_user(self, email):
        return self.user_data.get(email)

    def update(self):
        self.logger.info("Starting hour entry update: %s - %s", self.start_date, self.end_date)
        now = timezone.now()
        tenkfeet_entries = tenkfeet_api.fetch_hour_entries(self.start_date, self.end_date)
        entries = []

        per_date_data = defaultdict(lambda: {"items": [], "sha256": hashlib.sha256()})

        for entry in tenkfeet_entries:
            if parse_float(entry[8]) in (0, None):  # incurred_hours
                logger.debug("Skipping hour entry with 0 incurred hours: %s", entry)
                continue
            entry_date = parse_date(entry[40])

            per_date_data[entry_date]["sha256"].update(json.dumps(entry).encode())
            per_date_data[entry_date]["items"].append(entry)

        dates = list(daterange(self.start_date, self.end_date))
        checksums = {k.date: k.sha256 for k in HourEntryChecksum.objects.filter(date__in=dates)}

        delete_days = []
        for date in dates:
            if date not in per_date_data:
                logger.info("No entries for %s - delete all existing entries.", date)
                delete_days.append(date)
                continue
            sha256 = per_date_data[date]["sha256"].hexdigest()
            if checksums.get(date) != sha256:
                logger.info("Something changed for %s", date)

                for entry in per_date_data[date]["items"]:
                    entry_date = parse_date(entry[40])
                    data = {
                        "date": entry_date,
                        "user_id": int(entry[0]),
                        "user_name": entry[1],
                        "client": entry[6],
                        "project": entry[3],
                        "incurred_hours": parse_float(entry[8]),
                        "incurred_money": parse_float(entry[11]),
                        "category": entry[14],
                        "notes": entry[15],
                        "entry_type": entry[17],
                        "discipline": entry[18],
                        "role": entry[19],
                        "bill_rate": parse_float(entry[28]),
                        "leave_type": entry[16],
                        "phase_name": entry[31],
                        "billable": entry[21] in ("1", 1),
                        "approved": entry[52] == "Approved",
                        "status": entry[52],
                        "user_email": entry[29].lower(),
                        "project_tags": entry[34],
                        "last_updated_at": now,
                        "calculated_is_billable": is_phase_billable(entry[31], entry[3]),
                    }

                    assert data["date"].year > 2000
                    assert data["date"].year < 2050
                    assert data["bill_rate"] >= 0
                    assert data["incurred_money"] >= 0
                    assert data["incurred_hours"] >= 0

                    self.update_range(entry_date)

                    try:
                        project_id = int(entry[32])
                        data["project_m"] = self.match_project(project_id)
                    except (ValueError, TypeError):
                        pass

                    data["invoice"] = self.match_invoice(data)
                    data["user_m"] = self.match_user(data["user_email"])
                    hour_entry = HourEntry(**data)
                    hour_entry.update_calculated_fields()
                    entries.append(hour_entry)
                    delete_days.append(entry_date)

                item, created = HourEntryChecksum.objects.update_or_create(date=date, defaults={"sha256": sha256})
                if not created:
                    item.sha256 = sha256
                    item.save()
            else:
                logger.info("Nothing was changed for %s - skip updating", date)

        logger.info("Processed all 10k entries. Inserting %s entries to database.", len(entries))
        # Note: this does not call .save() for entries.
        with transaction.atomic():
            HourEntry.objects.bulk_create(entries)
            logger.info("All 10k entries added: %s.", len(entries))
            logger.info("Deleting old 10k entries.")
            deleted_entries, _ = HourEntry.objects.filter(date__gte=self.first_entry, date__lte=self.last_entry, date__in=delete_days, last_updated_at__lt=now).delete()
            logger.info("All old 10k entries deleted: %s.", deleted_entries)
        return (self.first_entry, self.last_entry)


def refresh_stats(start_date, end_date):
    if start_date and end_date:
        if start_date.year == end_date.year:
            invoices = Invoice.objects.filter(year__gte=start_date.year, year__lte=end_date.year, month__gte=start_date.month, month__lte=end_date.month)
        else:
            invoices_1 = Invoice.objects.filter(year=start_date.year, month__gte=start_date.month)
            invoices_2 = Invoice.objects.filter(year=end_date.year, month__lte=end_date.month)
            invoices = [invoice for invoice in invoices_1]
            invoices.extend([invoice for invoice in invoices_2])
        logger.info("Updating statistics for invoices between %s and %s: %s invoices", start_date, end_date, len(invoices))
    else:
        logger.info("Updating statistics for all invoices")
        invoices = Invoice.objects.all()
    for invoice in invoices:
        entries = HourEntry.objects.filter(invoice=invoice).filter(incurred_hours__gt=0)
        aws_entries = None
        if invoice.project_m:
            aws_accounts = invoice.project_m.amazon_account.all()
            aws_entries = get_aws_entries(aws_accounts, invoice.month_start_date, invoice.month_end_date)
        stats = calculate_entry_stats(entries, invoice.get_fixed_invoice_rows(), aws_entries)
        for field in STATS_FIELDS:
            setattr(invoice, field, stats[field])

        invoice.incurred_money = sum([row["incurred_money"] for row in stats["total_rows"].values() if "incurred_money" in row])
        invoice.incurred_hours = sum([row["incurred_hours"] for row in stats["total_rows"].values() if "incurred_hours" in row])
        invoice.incurred_billable_hours = stats["total_rows"]["hours"]["incurred_billable_hours"]
        if invoice.incurred_hours > 0:
            invoice.billable_percentage = invoice.incurred_billable_hours / invoice.incurred_hours
        else:
            invoice.billable_percentage = 0
        if stats["total_rows"]["hours"]["incurred_hours"] > 0:
            invoice.bill_rate_avg = stats["total_rows"]["hours"]["incurred_money"] / stats["total_rows"]["hours"]["incurred_hours"]
        else:
            invoice.bill_rate_avg = 0
        invoice.save()
        logger.debug("Updated statistics for %s", invoice)
