import django_filters

from invoices.models import Client, HourEntry, Invoice, Project


class ClientsFilter(django_filters.FilterSet):

    class Meta:
        model = Client
        fields = {
            "name": ["icontains"],
        }


class HourListFilter(django_filters.FilterSet):
    date = django_filters.DateRangeFilter()
    status = django_filters.MultipleChoiceFilter(choices=HourEntry.STATUS_CHOICES)

    class Meta:
        model = HourEntry
        fields = {
            "user_name": ["icontains"],
            "calculated_has_phase": ["exact"],
            "calculated_has_notes": ["exact"],
            "calculated_is_billable": ["exact"],
            "calculated_is_approved": ["exact"],
            "calculated_has_category": ["exact"],
            "calculated_has_proper_price": ["exact"],
            "calculated_is_overtime": ["exact"],
            "date": ["gte", "lte"],
        }


class InvoiceFilter(django_filters.FilterSet):
    project_m__client_m__name = django_filters.filters.CharFilter(name="project_m__client_m__name", label="Client name", lookup_expr="icontains")
    project_m__name = django_filters.filters.CharFilter(name="project_m__name", label="Project name", lookup_expr="icontains")

    class Meta:
        model = Invoice
        fields = {
            "date": ["exact"],
            "invoice_state": ["exact"],
        }


class ProjectsFilter(django_filters.FilterSet):
    client_m__name = django_filters.filters.CharFilter(name="client_m__name", label="Client name", lookup_expr="icontains")
    name = django_filters.filters.CharFilter(name="name", label="Project name", lookup_expr="icontains")

    class Meta:
        model = Project
        fields = ["client_m__name", "name"]
