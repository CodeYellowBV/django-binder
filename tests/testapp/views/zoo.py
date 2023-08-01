from binder.views import FilterDescription
from binder.permissions.views import PermissionView
from binder.exceptions import BinderForbidden
from django.db.models import Q

from ..models import Zoo, Animal


# From the api docs
class ZooView(PermissionView):
    m2m_fields = ['contacts', 'zoo_employees', 'most_popular_animals']
    model = Zoo
    file_fields = ['floor_plan', 'django_picture', 'binder_picture', 'django_picture_not_null',
                   'binder_picture_not_null', 'binder_picture_custom_extensions']
    shown_properties = ['animal_count']
    image_resize_threshold = {
        'floor_plan': 500,
        'binder_picture': 500,
        'binder_picture_custom_extensions': 500,
    }
    image_format_override = {
        'floor_plan': 'jpeg',
    }
    alternative_filters={
        'all_contact_name': [
            'contacts.name',
            'name',
        ],
    }

    # Override this method so we don't have to deal with actual permissions in testing
    def _require_model_perm(self, perm_type, request, pk=None):
        request._has_permission_check = True
        if request.user.is_superuser:
            return ['all']
        elif perm_type == 'view' and request.user.username in ('testuser', 'testuser2'):
            return ['all']
        elif perm_type == 'view' and request.user.username == 'testuser_for_bad_q_filter':
            return ['bad_q_filter']
        elif perm_type == 'view' and request.user.username == 'testuser_for_good_q_filter':
            return ['good_q_filter']
        else:
            model = self.perms_via if hasattr(self, 'perms_via') else self.model
            perm = '{}.{}_{}'.format(model._meta.app_label, perm_type, model.__name__.lower())
            raise BinderForbidden(perm, request.user)

    def get_rooms_for_user(user):
        return [
            {
                'zoo': 'all',
            },
        ]

    def _scope_view_bad_q_filter(self, request):
        return Q(animals__id__in=Animal.objects.all())

    def _scope_view_good_q_filter(self, request):
        return FilterDescription(Q(animals__id__in=Animal.objects.all()), True)
