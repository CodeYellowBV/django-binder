from django.db.models import Q

from ...permissions.views import PermissionView
from .models import MyFilter


class MyFilterView(PermissionView):

    unwritable_fields = ['user']

    model = MyFilter

    def _scope_view_own(self, request):
        return Q(user=request.user)

    def _store(self, obj, values, request, **kwargs):
        if obj.pk is None:
            obj.user = request.user
        return super()._store(obj, values, request, **kwargs)
