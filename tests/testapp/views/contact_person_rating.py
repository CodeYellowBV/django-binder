from binder.permissions.views import PermissionView
from ..models import ContactPersonRating


class ContactPersonRatingView(PermissionView):
    model = ContactPersonRating
