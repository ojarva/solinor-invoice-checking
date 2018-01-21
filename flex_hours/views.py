# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import json

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render

from flex_hours.utils import FlexHourException, calculate_flex_saldo
from invoices.models import TenkfUser


def get_flex_hours_for_user(request, person, json_responses=False):
    try:
        context = calculate_flex_saldo(person)
    except FlexHourException as error:
        if json_responses:
            return HttpResponse(json.dumps({"flex_enabled": False}), content_type="application/json")
        return render(request, "error.html", {"error": error, "message": "This is normal for flex hour calculations when some required information is missing. If this is your page, please contact HR to get this fixed."})
    if json_responses:
        return HttpResponse(json.dumps({"flex_enabled": True, "flex_hours": context["cumulative_saldo"], "kiky_saldo": context.get("kiky", {}).get("saldo")}), content_type="application/json")
    return render(request, "person_flex_hours.html", context)


@staff_member_required
def flex_overview(request):
    people = TenkfUser.objects.exclude(archived=True)
    return render(request, "flex_hours.html", {"people": people})


@login_required
def person_flex_hours(request, user_guid):
    person = get_object_or_404(TenkfUser, guid=user_guid)
    return get_flex_hours_for_user(request, person)


@login_required
def your_flex_hours(request):
    person = get_object_or_404(TenkfUser, email=request.user.email)
    return get_flex_hours_for_user(request, person)


@login_required
def your_flex_hours_json(request):
    person = get_object_or_404(TenkfUser, email=request.user.email)
    return get_flex_hours_for_user(request, person, json_responses=True)


@login_required
def person_flex_hours_json(request, user_guid):
    person = get_object_or_404(TenkfUser, guid=user_guid)
    return get_flex_hours_for_user(request, person, json_responses=True)
