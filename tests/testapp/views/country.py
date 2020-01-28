from binder.permissions.views import PermissionView

from ..models import Country


class CountryView(PermissionView):
    model = Country
