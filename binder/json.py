import json
import datetime
import uuid
import decimal

from django.http import HttpResponse
from django.conf import settings

from .exceptions import BinderRequestError



# datetime serializer
def serializer_datetime(encoder, value):
	# FIXME: was .isoformat(), but that omits the microseconds if they
	# are 0, which upsets our front-end devs. This is ugly.
	# I hear .isoformat() might learn a timespec parameter in 3.6...
	tz = value.strftime("%z")
	tz = tz if tz else '+0000'
	return value.strftime("%Y-%m-%dT%H:%M:%S.%f") + tz



# Default Binder serializers; override these with settings.BINDER_JSON_SERIALIZERS
# flake8: noqa
DEFAULT_SERIALIZERS = {
	set:                 lambda e, v: list(v),
	datetime.datetime:   serializer_datetime,
	datetime.date:       lambda e, v: v.isoformat(),
	uuid.UUID:           lambda e, v: str(v),
	decimal.Decimal:     lambda e, v: str(v),
}



# dateutil.relativedelta serializer, if available
try:
	from dateutil.relativedelta import relativedelta
	from relativedeltafield import format_relativedelta
	DEFAULT_SERIALIZERS[relativedelta] = lambda e, v: format_relativedelta(v)
except ImportError:
	pass



# Potentially slow implementation; we iterate over all of the values
# (super)classes and check if there's a serializer defined for it.
# An optimization would be to cache this on the BinderJSONEncoder instance.
class BinderJSONEncoder(json.JSONEncoder):
	def default(self, value):
		# Construct prioritized serializers
		serializers = DEFAULT_SERIALIZERS
		serializers.update(getattr(settings, 'BINDER_JSON_SERIALIZERS', {}))

		# Find a serializer in the Method Resolution Order
		for cls in type(value).mro():
			if cls in serializers:
				return serializers[cls](self, value)

		# Default json serializer
		return json.JSONEncoder.default(self, value)



def jsondumps(o, indent=None):
	return json.dumps(o, cls=BinderJSONEncoder, indent=indent)



def jsonloads(data):
	try:
		return json.loads(data.decode())
	except ValueError as e:
		raise BinderRequestError('JSON parse error: {}.'.format(str(e)))



def JsonResponse(data):
	return HttpResponse(jsondumps(data), content_type='application/json')
