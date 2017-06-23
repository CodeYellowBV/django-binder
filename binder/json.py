import json
import datetime
import uuid
import decimal

from django.http import HttpResponse

from .exceptions import BinderRequestError



# datetime serializer
def serializer_datetime(value):
	# FIXME: was .isoformat(), but that omits the microseconds if they
	# are 0, which upsets our front-end devs. This is ugly.
	# I hear .isoformat() might learn a timespec parameter in 3.6...
	tz = value.strftime("%z")
	tz = tz if tz else '+0000'
	return value.strftime("%Y-%m-%dT%H:%M:%S.%f") + tz



# Default Binder serializers; override these by doing
# json.SERIALIZERS.update({}) in settings.py
SERIALIZERS = {
	set:                 list,
	datetime.datetime:   serializer_datetime,
	datetime.date:       lambda v: v.isoformat(),
	uuid.UUID:           str,
	decimal.Decimal:     str,
}



# dateutil.relativedelta serializer, if available
try:
	from dateutil.relativedelta import relativedelta
	from relativedeltafield import format_relativedelta
	DEFAULT_SERIALIZERS[relativedelta] = lambda e, v: format_relativedelta(v)
except ImportError:
	pass




# Converts values json.dumps can't convert itself.
def default(value):
	# Find a serializer in the Method Resolution Order
	for cls in type(value).mro():
		if cls in SERIALIZERS:
			return SERIALIZERS[cls](value)

	raise TypeError('{} is not JSON serializable'.format(repr(value)))



def jsondumps(o, default=default, indent=None):
	return json.dumps(o, default=default, indent=indent)



def jsonloads(data):
	try:
		return json.loads(data.decode())
	except ValueError as e:
		raise BinderRequestError('JSON parse error: {}.'.format(str(e)))



def JsonResponse(data):
	return HttpResponse(jsondumps(data), content_type='application/json')
