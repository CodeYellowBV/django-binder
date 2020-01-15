from binder.permissions.views import PermissionView
from ..models import City


class CityView(PermissionView):
    model = City
