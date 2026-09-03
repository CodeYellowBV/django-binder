from binder.views import ModelView

from ..models import Truck


class TruckView(ModelView):
	model = Truck
