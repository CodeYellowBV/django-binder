import json
import datetime
from uuid import UUID
from decimal import Decimal

from django.http import HttpResponse

from .exceptions import BinderRequestError

try:
	from dateutil.relativedelta import relativedelta
	from relativedeltafield import format_relativedelta
except ImportError:
	class relativedelta:
		pass

class BinderJSONEncoder(json.JSONEncoder):
	def default(self, obj):
		if isinstance(obj, datetime.datetime):
			# FIXME: was .isoformat(), but that omits the microseconds if they
			# are 0, which upsets our front-end devs. This is ugly.
			# I hear .isoformat() might learn a timespec parameter in 3.6...
			tz = obj.strftime("%z")
			tz = tz if tz else '+0000'
			return obj.strftime("%Y-%m-%dT%H:%M:%S.%f") + tz
		elif isinstance(obj, datetime.date):
			return obj.isoformat()
		elif isinstance(obj, UUID):
			return str(obj)  # Standard string notation
		elif isinstance(obj, set):
			return list(obj)
		elif isinstance(obj, relativedelta):
			return format_relativedelta(obj)
		elif isinstance(obj, Decimal):
			return float(obj)
		return json.JSONEncoder.default(self, obj)



def jsondumps(o, indent=None):
	return json.dumps(o, cls=BinderJSONEncoder, indent=indent)



def jsonloads(data):
	try:
		return json.loads(data.decode())
	except ValueError as e:
		raise BinderRequestError('JSON parse error: {}.'.format(str(e)))



def JsonResponse(data):
	return HttpResponse(jsondumps(data), content_type='application/json')
