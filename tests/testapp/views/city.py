from binder.views import ModelView

from ..models import City


class CityView(ModelView):
    model = City
