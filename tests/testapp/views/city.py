from binder.permissions.views import PermissionView
from ..models.city import CityState, City, PermanentCity


class CityView(PermissionView):
    model = City


class CityStateView(PermissionView):
    model = CityState


class PermanentCityView(PermissionView):
    model = PermanentCity
