from django.contrib.auth.models import User

from binder.permissions.views import PermissionView
from binder.plugins.views import UserViewMixIn


class UserView(PermissionView, UserViewMixIn):
	model = User
