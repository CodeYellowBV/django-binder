from binder.permissions.views import PermissionView
from binder.router import detail_route, list_route
from django.http import HttpResponse

from ..models import Pet

class PetView(PermissionView):
	model = Pet

	@list_route(name='atomic') # Routes are atomic by default
	def atomic_list_endpoint(self, request):
		Pet.objects.create(name='should be rolled back')
		return HttpResponse(status=200) # Note that I skipped the permission check, so it should fail!

	@list_route(name='non-atomic', inside_atomic_transaction=False)
	def non_atomic_list_endpoint(self, request):
		Pet.objects.create(name='should NOT be rolled back')
		return HttpResponse(status=200)

	@detail_route(name='atomic') # Routes are atomic by default
	def atomic_detail_endpoint(self, request, pk):
		Pet.objects.create(name='should be rolled back')
		return HttpResponse(status=200)

	@detail_route(name='non-atomic', inside_atomic_transaction=False)
	def non_atomic_detail_endpoint(self, request, pk):
		Pet.objects.create(name='should NOT be rolled back')
		return HttpResponse(status=200)
