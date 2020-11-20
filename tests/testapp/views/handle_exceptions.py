from django.http import HttpResponse

from binder.decorators import handle_exceptions
from binder.exceptions import BinderRequestError

from ..models import Zoo


@handle_exceptions
def handle_exceptions_view(request):
	# We create a model so we can test transaction rollback on error
	Zoo.objects.create(name='Test zoo')

	try:
		res = request.GET['res']
	except KeyError:
		raise BinderRequestError('no res provided')
	else:
		return HttpResponse(res)
