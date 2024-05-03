from binder.views import ModelView

from ..models import Pet

class PetView(ModelView):
	model = Pet
