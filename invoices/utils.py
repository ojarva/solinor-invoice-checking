import datetime
import hashlib
import json
import logging
from collections import defaultdict

from django.conf import settings
from django.db import transaction
from django.db.models import Q, Sum
from django.db.utils import IntegrityError
from django.utils import timezone
from django.utils.dateparse import parse_date as parse_date_django
from django.utils.dateparse import parse_datetime as parse_datetime_django

from flex_hours.models import PublicHoliday
from invoices.invoice_utils import calculate_entry_stats, get_aws_entries
from invoices.models import Event, HourEntry, HourEntryChecksum, Invoice, Project, TenkfUser, is_phase_billable
from invoices.slack import send_new_project_to_slack
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
    for n in range(int((end_date - start_date).days) + 1):
        yield start_date + datetime.timedelta(n)


def get_weekend_hours_per_user(start_date, end_date, incurred_hours_threshold):
    holidays_list = PublicHoliday.objects.filter(date__gte=start_date).filter(date__lte=end_date)
    holidays = {item.date: item.name for item in holidays_list}
    hour_markings = HourEntry.objects.filter(date__gte=start_date).filter(date__lte=end_date).filter(Q(date__week_day=1) | Q(date__week_day=7)).order_by("user_m", "date").values("user_m", "date").annotate(sum_hours=Sum("incurred_hours")).filter(sum_hours__gte=incurred_hours_threshold)


def get_overly_long_days_per_user(start_date, end_date, incurred_hours_threshold):
    hour_markings = HourEntry.objects.filter(date__gte=start_date).filter(date__lte=end_date).order_by("user_m", "date").values("user_m", "date").annotate(sum_hours=Sum("incurred_hours")).filter(sum_hours__gte=incurred_hours_threshold)


def parse_date(timestamp):
    if timestamp:
        return parse_date_django(timestamp)


def parse_datetime(timestamp):
    if timestamp:
        return parse_datetime_django(timestamp)


def parse_float(data):
    try:
        return float(data)
    except TypeError:
        return 0


def sync_10000ft_users():
    logger.info("Updating users")
    tenkfeet_users = tenkfeet_api.fetch_users()
    updated_hour_entries = updated_users = created_users = 0
    all_users = {str(user["guid"]): user["updated_at"] for user in TenkfUser.objects.values("guid", "updated_at")}
    for user in tenkfeet_users:
        if not user["email"]:
            continue
        user_email = user["email"]
        updated_at = user["updated_at"]

        if user["guid"] in all_users:
            if all_users[user["guid"]] == updated_at:
                logger.info("Skip updating %s (%s) - update timestamp matches", user["email"], user["guid"])
                continue
        logger.info("%s - %s - %s", user["guid"], all_users.get(user["guid"]), user["updated_at"])

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
            "updated_at": user["updated_at"],
            "thumbnail": user["thumbnail"],
        }
        # TODO: always ensure non-archived user is added to the DB
        try:
            user_obj, created = TenkfUser.objects.update_or_create(guid=user["guid"], defaults=user_fields)
            if created:
                created_users += 1
            else:
                updated_users += 1
        except IntegrityError:
            logger.info("Unable to update %s - duplicate email", user_email)
            continue
        updated_objects = HourEntry.objects.filter(user_email__iexact=user_email).filter(user_m=None).update(user_m=user_obj)
        logger.debug("Updated %s to %s entries", user_email, updated_objects)
        updated_hour_entries += updated_objects
    logger.info("Got %s users from 10000ft, updated %s users, created %s users, linked %s hour entries", len(tenkfeet_users), updated_users, created_users, updated_hour_entries)
    Event(event_type="sync_10000ft_users", succeeded=True, message="Got {} users from 10000ft, updated {} users, created {} users, linked {} hour entries".format(len(tenkfeet_users), updated_users, created_users, updated_hour_entries)).save()


def sync_10000ft_projects():
    logger.info("Updating projects")
    tenkfeet_projects = tenkfeet_api.fetch_projects()
    projects = []
    created_count = 0
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
                matching_users = TenkfUser.objects.filter(first_name=first_name, last_name=last_name).filter(archived=False)
                logger.debug("Matched %s to tag %s; first_name=%s, last_name=%s", matching_users, tag, first_name, last_name)
                user_cache[tag_value] = matching_users

            project_obj.admin_users.clear()
            for matching_user in matching_users:
                project_obj.admin_users.add(matching_user)
        project_obj.save()
        projects.append(project_obj)
        if created:
            created_count += 1
            send_new_project_to_slack(project_obj)
    logger.info("Finished updating projects (n=%s)", len(projects))
    linked_invoices = 0
    for invoice in Invoice.objects.filter(project_m=None):
        for project in projects:
            if project.name == invoice.project and project.client == invoice.client and invoice.project_m != project:
                logger.info("Updating invoice %s with project %s", invoice, project)
                linked_invoices += 1
                invoice.project_m = project
                invoice.save()
                break
    Event(event_type="sync_10000ft_projects", succeeded=True, message="Updated {} projects, created {} projects and linked {} invoices to projects".format(len(projects), created_count, linked_invoices)).save()


def get_projects():
    return {project.project_id: project for project in Project.objects.all()}


def get_invoices():
    return {"{}-{} {} - {}".format(invoice.year, invoice.month, invoice.client, invoice.project): invoice for invoice in Invoice.objects.all()}


def get_users():
    return {user.email: user for user in TenkfUser.objects.all()}


def parse_upstream_id(id):
    # 108957-2018-01-20-865336-717868858
    if not id:
        return
    return id.split("-")[-1]


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
        invoice_key = "{}-{} {} - {}".format(data["date"].year, data["date"].month, data["client"], data["project"])
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

    def update_10000ft_api_hours(self, date):
        upstream_hours = tenkfeet_api.fetch_api_hour_entries(date, date)
        print(upstream_hours)
        stored_hours = HourEntry.objects.filter(date=date).select_related("project_m")
        for upstream_entry in upstream_hours:
            if upstream_entry["hours"] == 0:
                continue
            upstream_date = parse_date(upstream_entry["date"])
            for stored_entry in stored_hours:
                if stored_entry.date != upstream_date:
                    continue
                if stored_entry.user_id != upstream_entry["user_id"]:
                    continue
                if stored_entry.incurred_hours != upstream_entry["hours"]:
                    continue
                if stored_entry.bill_rate != upstream_entry["bill_rate"]:
                    continue
                if stored_entry.notes != upstream_entry["notes"] or upstream_entry["notes"] is None or len(upstream_entry["notes"]) < 5:
                    continue
                if stored_entry.category != upstream_entry["task"]:
                    continue
                if stored_entry.assignable_id != upstream_entry["assignable_id"]:
                    continue
                created_at = parse_datetime(upstream_entry["created_at"])
                updated_at = parse_datetime(upstream_entry["updated_at"])
                upstream_id = upstream_entry["id"]
                if stored_entry.created_at != created_at or stored_entry.updated_at != updated_at or stored_entry.upstream_id != upstream_id:
                    stored_entry.created_at = created_at
                    stored_entry.updated_at = updated_at
                    stored_entry.upstream_id = upstream_id
                    stored_entry.save()

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
        deleted_entries = 0
        delete_days = set()
        updated_days = set()
        for date in dates:
            if date not in per_date_data:
                logger.info("No entries for %s - delete all existing entries.", date)
                delete_days.add(date)
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
                        "assignable_id": entry[2],
                        "approved_at": parse_date(entry[55]),
                        "upstream_id": parse_upstream_id(entry[59]),
                        "approved_by": entry[53],
                        "submitted_by": entry[54],
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
                    delete_days.add(entry_date)
                    updated_days.add(entry_date)

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
            deleted_entries, _ = HourEntry.objects.filter(date__gte=self.first_entry, date__lte=self.last_entry, date__in=list(delete_days), last_updated_at__lt=now).delete()
            logger.info("All old 10k entries deleted: %s.", deleted_entries)
        Event(event_type="sync_10000ft_report_hours", succeeded=True, message="Entries between {:%Y-%m-%d} and {:%Y-%m-%d}. Added {}, deleted {}; processed dates: {}.".format(self.start_date, self.end_date, len(entries), deleted_entries, ", ".join([day.strftime("%Y-%m-%d") for day in delete_days]))).save()
        return (self.first_entry, self.last_entry, deleted_entries + len(entries))


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
    c = 0
    for invoice in invoices:
        c += 1
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
    Event(event_type="refresh_invoice_statistics", succeeded=True, message="Refreshed {} invoices between {:%Y-%m-%d} and {:%Y-%m-%d}.".format(c, start_date, end_date)).save()
