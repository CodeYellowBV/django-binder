import json
import datetime
import uuid
import decimal

from django.http import HttpResponse
from psycopg2.extras import DateTimeTZRange


from .exceptions import BinderRequestError, BinderNotImplimented


def serialize_datetimeTZRange(v):
	if v.isempty:
		return [None]

	# check that not default bounds are not used in teh configuration of the field, if so raise a not implimented exception
	if not(v.lower_inc is True or v.lower_inf) or not(v.upper_inc is False):
		raise BinderNotImplimented(message='The exclusive bounds parameters of DateTimeTZRange are currently not supported')

	lower = None
	upper = None

	if v.lower and not v.lower_inf:
		lower = v.lower.strftime('%Y-%m-%dT%H:%M:%S.%f%z')
	if v.upper and not v.upper_inf:
		upper = v.upper.strftime('%Y-%m-%dT%H:%M:%S.%f%z')

	return [lower, upper]

# Default Binder serializers; override these by doing
# json.SERIALIZERS.update({}) in settings.py
SERIALIZERS = {
	set:                 list,
	datetime.datetime:   lambda v: v.strftime('%Y-%m-%dT%H:%M:%S.%f%z'),   # .isoformat() can omit microseconds
	datetime.date:       lambda v: v.isoformat(),
	datetime.time:       lambda v: v.strftime('%H:%M:%S.%f%z'),
	DateTimeTZRange:     lambda v: serialize_datetimeTZRange(v),
	uuid.UUID:           str,
	decimal.Decimal:     str,
}

# dateutil.relativedelta serializer, if available
try:
	from dateutil.relativedelta import relativedelta
	from relativedeltafield import format_relativedelta
	SERIALIZERS[relativedelta] = format_relativedelta
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
