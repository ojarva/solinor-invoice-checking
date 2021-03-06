from django.conf import settings
from django.conf.urls import include, url
from django.contrib import admin
from django.urls import path
from django.views.generic.base import RedirectView

import flex_hours.views
import invoices.views
import slack_hooks.views

admin.autodiscover()

urlpatterns = [
    path("clients", invoices.views.clients_list, name="clients"),
    path("clients/stats", invoices.views.clientbase_stats, name="clientbase_stats"),
    path("clients/<int:client_id>", invoices.views.client_details, name="client_details"),
    path("projects", invoices.views.projects_list, name="projects_list"),
    path("projects/<uuid:project_id>", invoices.views.project_details, name="project"),
    path("projects/<uuid:project_id>/charts", invoices.views.project_charts, name="project_charts"),
    path("invoices/<uuid:invoice_id>", invoices.views.invoice_page, name="invoice"),
    path("invoices/<uuid:invoice_id>/hours", invoices.views.invoice_hours, name="invoice_hours"),
    path("invoices/<uuid:invoice_id>/charts", invoices.views.invoice_charts, name="invoice_charts"),
    path("invoices/<uuid:invoice_id>/export/pdf/<slug:pdf_type>", invoices.views.get_invoice_pdf, name="get_invoice_pdf"),
    path("invoices/<uuid:invoice_id>/export/xls/<slug:xls_type>", invoices.views.get_invoice_xls, name="get_invoice_xls"),
    path("invoices/amazon/<int:linked_account_id>/<int:year>/<int:month>", invoices.views.amazon_invoice, name="amazon_invoice"),
    path("invoices/amazon", invoices.views.amazon_overview, name="amazon_overview"),
    path("invoices", invoices.views.invoices_list, name="invoices_list"),
    path("hours/browser", invoices.views.hours_browser, name="hours_browser"),
    path("hours/charts", invoices.views.hours_charts, name="hours_charts"),
    path("hours/overview", invoices.views.hours_overview, name="hours_overview"),
    path("hours/sickleaves", invoices.views.hours_sickleaves, name="hours_sickleaves"),
    path("users", invoices.views.users_list, name="users_list"),
    path("users/charts", invoices.views.users_charts, name="users_charts"),
    path("users/flexhours", flex_hours.views.flex_overview, name="flex_overview"),
    path("users/<uuid:user_guid>", invoices.views.person_overview, name="person_overview"),
    path("users/<uuid:user_guid>/<int:year>/<int:month>", invoices.views.person_details_month, name="person_month"),
    path("users/<uuid:user_guid>/flexhours", flex_hours.views.person_flex_hours, name="person_flex_hours"),
    path("users/<uuid:user_guid>/flexhours/json", flex_hours.views.person_flex_hours_json, name="person_flex_hours_json"),
    path("you/flexhours", flex_hours.views.your_flex_hours, name="your_flex_hours"),
    path("you/flexhours/json", flex_hours.views.your_flex_hours_json, name="your_flex_hours_json"),
    path("frontpage/stats", invoices.views.frontpage_stats, name="frontpage_stats"),
    path("you/hours/unsubmitted", invoices.views.your_unsubmitted_hours, name="your_unsubmitted_hours"),
    path("company/stats", invoices.views.company_stats, name="company_stats"),

    path("search", invoices.views.search, name="search"),

    path("queue_update", invoices.views.queue_update, name="queue_update"),
    path("queue_slack_notification", invoices.views.queue_slack_notification, name="queue_slack_notification"),
    path("admin_sync", invoices.views.admin_sync, name="admin_sync"),

    path("incoming_slack_event", slack_hooks.views.incoming_event),
    path("slack_query_flex_saldo", slack_hooks.views.slack_query_flex_saldo),

    url(r"^accounts/profile/$", RedirectView.as_view(pattern_name="frontpage", permanent=False)),
    url(r"^accounts/", include("googleauth.urls")),
    path("", invoices.views.frontpage, name="frontpage"),
    path("manifest", invoices.views.manifest, name="manifest"),
    url(r"^admin/", admin.site.urls),

    # Deprecated paths
    path("project/<uuid:project_id>", RedirectView.as_view(pattern_name="project")),
    path("project/<uuid:project_id>/charts", RedirectView.as_view(pattern_name="project_charts")),
    path("invoice/<uuid:invoice_id>/hours", RedirectView.as_view(pattern_name="invoice_hours")),
    path("invoice/<uuid:invoice_id>/charts", RedirectView.as_view(pattern_name="invoice_charts")),
    path("invoice/<uuid:invoice_id>/pdf/<slug:pdf_type>", RedirectView.as_view(pattern_name="get_invoice_pdf")),
    path("invoice/<uuid:invoice_id>/xls/<slug:xls_type>", RedirectView.as_view(pattern_name="get_invoice_xls")),
    path("invoice/<uuid:invoice_id>", RedirectView.as_view(pattern_name="invoice")),
    path("amazon_invoice/<int:linked_account_id>/<int:year>/<int:month>", RedirectView.as_view(pattern_name="amazon_invoice")),
    path("amazon", RedirectView.as_view(pattern_name="amazon_overview")),
    path("hours", RedirectView.as_view(pattern_name="hours_browser")),
    path("hours/charts", RedirectView.as_view(pattern_name="hours_charts")),
    path("people", RedirectView.as_view(pattern_name="users_list")),
    path("people/hourmarkings", RedirectView.as_view(pattern_name="hours_overview")),
    path("people/charts", RedirectView.as_view(pattern_name="users_charts")),
    path("person/<uuid:user_guid>/<int:year>/<int:month>", RedirectView.as_view(pattern_name="person_month")),
    path("person/<uuid:user_guid>", RedirectView.as_view(pattern_name="person_overview")),
    path("person/<uuid:user_guid>/flexhours", RedirectView.as_view(pattern_name="person_flex_hours")),
    path("your/flexhours", RedirectView.as_view(pattern_name="your_flex_hours")),
]

if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        url(r"^__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns
