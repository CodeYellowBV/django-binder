from binder.views import ModelView

from ..models import Animal

# From the api docs
class AnimalView(ModelView):
	model = Animal
