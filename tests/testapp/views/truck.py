from binder.exceptions import BinderValidationError
from binder.router import detail_route, list_route
from binder.views import ModelView

from ..models import Truck


class TruckView(ModelView):
	model = Truck

	@list_route(name='atomic') # Routes are atomic by default
	def atomic_list_endpoint(self, request):
		Truck.objects.create(name='should be rolled back')
		raise BinderValidationError('should roll back')

	@list_route(name='non-atomic', inside_atomic_transaction=False)
	def non_atomic_list_endpoint(self, request):
		Truck.objects.create(name='should NOT be rolled back')
		raise BinderValidationError('should NOT roll back')

	@detail_route(name='atomic') # Routes are atomic by default
	def atomic_detail_endpoint(self, request, pk):
		Truck.objects.create(name='should be rolled back')
		raise BinderValidationError('should roll back')

	@detail_route(name='non-atomic', inside_atomic_transaction=False)
	def non_atomic_detail_endpoint(self, request, pk):
		Truck.objects.create(name='should NOT be rolled back')
		raise BinderValidationError('should NOT roll back')
