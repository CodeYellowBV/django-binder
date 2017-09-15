from django.http import HttpResponse
from django.views.decorators.http import require_GET

from binder.json import jsondumps

@require_GET
def custom(request):
	return HttpResponse(jsondumps({'custom': True}))
