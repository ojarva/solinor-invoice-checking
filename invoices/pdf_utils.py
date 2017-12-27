import pdfkit
from django.conf import settings
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string

from invoices.models import HourEntry, Invoice


def generate_pdf(title, content):
    pdfkit_config = pdfkit.configuration(wkhtmltopdf=settings.WKHTMLTOPDF_CMD)
    wk_options = {
        'page-size': 'a4',
        'orientation': 'landscape',
        'title': title,
        # In order to specify command-line options that are simple toggles
        # using this dict format, we give the option the value None
        'no-outline': None,
        'disable-javascript': None,
        'encoding': 'UTF-8',
        'margin-left': '0.2cm',
        'margin-right': '0.2cm',
        'margin-top': '0.3cm',
        'margin-bottom': '0.3cm',
        'lowquality': None,
    }
    return pdfkit.from_string(content,
                              False,
                              options=wk_options,
                              configuration=pdfkit_config
                              )


def generate_hours_pdf_for_invoice(request, invoice):
    invoice_data = get_object_or_404(Invoice, invoice_id=invoice)
    title = u"%s - %s - %s-%s" % (invoice_data.client, invoice_data.project, invoice_data.year, invoice_data.month)
    title = title.replace(u"\xe4", u"a").replace(u"\xb6", u"o").replace(u"\x84", u"A").replace(u"\x96", u"O").replace(u"\xf6", "o")

    entries = HourEntry.objects.filter(project=invoice_data.project, client=invoice_data.client, date__year__gte=invoice_data.year, date__month=invoice_data.month).filter(incurred_hours__gt=0)
    phases = {}
    for entry in entries:
        if entry.phase_name not in phases:
            phases[entry.phase_name] = []
        phases[entry.phase_name].append(entry)
    context = {"phases": phases}

    # We can generate the pdf from a url, file or, as shown here, a string
    content = render_to_string('pdf_template.html', context=context, request=request)
    return generate_pdf(title, content), title
