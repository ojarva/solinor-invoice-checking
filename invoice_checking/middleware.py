from django.conf import settings
from django.http import HttpResponsePermanentRedirect


class DomainRedirectMiddleware(object):  # pylint: disable=too-few-public-methods
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.REDIRECT_OLD_DOMAIN and settings.REDIRECT_NEW_DOMAIN:
            if request.META.get("HTTP_HOST") == settings.REDIRECT_OLD_DOMAIN:
                if "slack" not in request.get_full_path():
                    return HttpResponsePermanentRedirect("https://{}{}".format(settings.REDIRECT_NEW_DOMAIN, request.get_full_path()))

        return self.get_response(request)
