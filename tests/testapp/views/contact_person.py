from binder.router import detail_route, list_route
from binder.views import ModelView
from django.http import HttpResponse

from ..models import ContactPerson

class ContactPersonView(ModelView):
	model = ContactPerson
	m2m_fields = ['zoos']
	unwritable_fields = ['created_at', 'updated_at']

	@detail_route(name='upper-name', methods=['GET'], fetch_obj=True)
	def upper_name(self, request, obj: ContactPerson):
		return HttpResponse(obj.name.upper())

	@list_route(name='counter', methods=['GET'])
	def counter(self, request):
		return HttpResponse(str(ContactPerson.objects.all().count()))
