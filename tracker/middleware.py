from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin
import pytz

class TimezoneMiddleware(MiddlewareMixin):
    def process_request(self, request):
        tzname = request.COOKIES.get('django_timezone')
        if tzname:
            try:
                timezone.activate(pytz.timezone(tzname))
            except (pytz.UnknownTimeZoneError, pytz.exceptions.UnknownTimeZoneError):
                timezone.deactivate()
        else:
            timezone.deactivate()
