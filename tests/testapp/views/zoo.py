from binder.views import ModelView

from ..models import Zoo

# From the api docs
class ZooView(ModelView):
	model = Zoo
