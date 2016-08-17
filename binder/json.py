import json
import datetime

from django.http import HttpResponse

from .exceptions import BinderRequestError



class BinderJSONEncoder(json.JSONEncoder):
	def default(self, obj):
		if isinstance(obj, (datetime.datetime, datetime.date)):
			return obj.isoformat()
		if isinstance(obj, set):
			return list(obj)
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
