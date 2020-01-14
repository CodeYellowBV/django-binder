from binder.permissions.views import PermissionView

from ..models import Country


class CountryView(PermissionView):
    model = Country

    def _scope_view_all(self, request):
        raise Exception('foo', request.user.is_superuser)
        return Q(pk__isnull=False)