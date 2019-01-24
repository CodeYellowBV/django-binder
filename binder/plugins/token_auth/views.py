from django.db.models import Q
from django.contrib.auth import authenticate

from binder.permissions.views import PermissionView
from binder.exceptions import BinderNotAuthenticated, BinderForbidden
from binder.json import jsonloads, JsonResponse
from binder.router import list_route

from .models import Token


class TokenView(PermissionView):

	model = Token
	unwritable_fields = ['created_at', 'last_used_at', 'expires_at']

	def _scope_view_own(self, request):
		return Q(user=request.user)

	def _scope_add_own(self, request, obj, values):
		return values['user'] == request.user.pk

	def _scope_change_own(self, request, obj, values):
		return (
			self._scope_delete_own(request, obj, values) and
			self._scope_add_own(request, obj, values)
		)

	def _scope_delete_own(self, request, obj, values):
		if not isinstance(obj, Token):
			obj = obj.get()
		return obj.user == request.user

	@list_route('login', unauthenticated=True, methods=['POST'])
	def login(self, request):
		perm = 'auth.login_user'
		# {permissions/views.py copy-paste}
		if getattr(request, '_permission', None) is None:
			self._parse_permissions(request)
		if perm not in request._permission:
			raise BinderForbidden(perm, request.user)

		try:
			body = jsonloads(request.body)
			username = body.get('username', '')
			password = body.get('password', '')
		except Exception:
			username = request.POST.get('username', '')
			password = request.POST.get('password', '')

		user = authenticate(username=username.lower(), password=password)
		if user is None:
			raise BinderNotAuthenticated()

		request.user = user
		data = self._store(Token(), {'user': user.pk}, request)
		meta = data.setdefault('_meta', {})
		withs = self._get_withs([data['id']], request=request, withs=None)
		meta['with'], meta['with_mapping'], meta['with_related_name_mapping'], field_results = withs

		for datum in data:
			for (w, (view, ids_dict, is_singular)) in field_results.items():
				if is_singular:
					try:
						datum[w] = list(ids_dict[datum['id']])[0]
					except IndexError:
						datum[w] = None
				else:
					datum[w] = list(ids_dict[datum['id']])

		return JsonResponse(data)
