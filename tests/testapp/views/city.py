from django.db.models import Q

from binder.permissions.views import PermissionView
from ..models.city import CityState, City, PermanentCity


class CityView(PermissionView):
	model = City


class CityStateView(PermissionView):
	model = CityState

	def _scope_view_netherlands(self, request):
		"""
		This is a bit of a weird edge case, but using this type of Q object creates an outer join with
		nullable side, thus preventhing us from doing a "select FOR UPDATE" clause
		"""
		return Q(country__name='Netherlands') | Q(name='Luxembourg')


class PermanentCityView(PermissionView):
	model = PermanentCity
