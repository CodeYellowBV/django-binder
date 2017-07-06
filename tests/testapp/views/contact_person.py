from binder.views import ModelView

from ..models import ContactPerson

class ContactPersonView(ModelView):
	model = ContactPerson
