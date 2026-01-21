from django.db.models import Q

from ...permissions.views import PermissionView
from .models import ColumnSetting


class ColumnSettingView(PermissionView):

    unwritable_fields = ['user']

    model = ColumnSetting

    def _scope_view_own(self, request):
        return Q(user=request.user)

    def _store(self, obj, values, request, **kwargs):
        if obj.pk is None:
            obj.user = request.user
        return super()._store(obj, values, request, **kwargs)
