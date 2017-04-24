from binder.views import ModelView
from django.db import transaction
from django.db.models import Q
from binder.exceptions import BinderForbidden, BinderNotFound
from django.conf import settings

import logging

from enum import Enum


logger = logging.getLogger(__name__)

class PermissionNotCheckedError(Exception):
	pass

class ScopingError(BinderForbidden):
	pass


class UnexpectedScopeException(Exception):
	pass


class Scope(Enum):
	VIEW = 'view'
	ADD = 'add'
	CHANGE = 'change'
	DELETE = 'delete'


class PermissionView(ModelView):
	class Meta:
		abstract = True

	@property
	def _permission_definition(self):
		return settings.BINDER_PERMISSION

	def _get_objs(self, queryset, request):
		return super()._get_objs(queryset, request)

	def get_queryset(self, request):
		queryset = self.model.objects
		return self.scope_view(request, queryset)

	def _require_model_perm(self, perm_type, request, pk=None):
		'''
		Check if you have a model permission, and return the scopes
		'''
		if hasattr(self, 'perms_via'):
			model = self.perms_via
		else:
			model = self.model

		setattr(request, '_has_permission_check', True)

		# Allow the superuser to do everything
		if request.user.is_superuser:
			return ['all']

		perm = '{}.{}_{}'.format(model._meta.app_label, perm_type, model.__name__.lower())

		if getattr(request, '_permission', None) is None:
			self._parse_permissions(request)

		if perm not in request._permission:
			raise BinderForbidden(perm, request.user)

		scopes = request._permission[perm]
		if perm_type not in ['view', 'add', 'change', 'delete'] and len(scopes) > 0:
			raise Exception('Scoping for permission {} can not be done. Scoping is only possible for view, add, '
							'change and delete'.format(perm_type))
		return scopes

	def _parse_permissions(self, request):
		'''
		Translate high level permissions to low level permissions on the request
		'''
		permissions = request.user.get_all_permissions()
		permissions.add('default')

		# Mapping from permission_name => list of scopes
		_permission_class = {}
		for p in permissions:
			if p in self._permission_definition:
				for permission, scope in self._permission_definition[p]:
					if permission not in _permission_class:
						_permission_class[permission] = [] # Permission, without any scopes
					if scope is not None:
						_permission_class[permission].append(scope)
		request._permission = _permission_class

	def _has_one_of_permissions(self, request, permissions):
		'''
		Check if we have one of a set of permissions
		'''
		for p in permissions:
			if request.user.has_perm(p):
				logger.debug('passed permission check: {}'.format(p))
				return True
		return False

	def dispatch(self, request, *args, **kwargs):
		'''
		make sure that permissions are checked, and scoping is done
		'''
		setattr(request, '_has_permission_check', False)
		with transaction.atomic():
			result = super().dispatch(request, *args, **kwargs)

			# If an error occured, we can return the result directly
			if result.status_code >= 300:
				return result

			permission_checked = getattr(request, '_has_permission_check', True)
			if not permission_checked:
				raise PermissionError('No permission check done. Shame on you!')

			scopes = getattr(request, '_scopes', [])

			if request.method.lower() == 'get':
				if Scope.VIEW not in scopes:
					raise PermissionError('No view scoping done!')
			elif request.method.lower() == 'delete':
				if Scope.DELETE not in scopes:
					raise PermissionError('No delete scoping done!')
			else:
				# NOTE: The DELETE here is actually for undeletes.  We
				# could use CHANGE scope in delete() if undelete=True,
				# but it makes more sense that delete and undelete are
				# both allowed iff you have "delete" permission.
				if Scope.ADD not in scopes and Scope.CHANGE not in scopes and Scope.DELETE not in scopes:
					raise PermissionError('No change or add scoping done!')
		return result

	def dispatch_file_field(self, request, pk=None, file_field=None):
		'''
		GET requests are not permission checked in binder
		'''
		if pk is not None:
			# Check if we have permission for the object to get
			objs = self._get_objs(self.get_queryset(request).filter(pk=pk), request)
			if len(objs) != 1:
				raise BinderNotFound()

		if request.method == 'POST':
			self.scope_add(request, None, [])
		elif request.method == 'PUT' or request.method == 'add':
			self.scope_change(request, objs[0], [])

		return super().dispatch_file_field(request, pk, file_field)

	def _scope_view_all(self, request):
		return self.model.objects

	def _scope_add_all(self, request, object, values):
		return True

	def _scope_change_all(self, request, object, values):
		return True

	def _scope_delete_all(self, request, object, values):
		return True

	@staticmethod
	def _save_scope(request, scope):
		'''
		Save that we did a scoping on the request object. This allows us to check that scoping is done
		'''
		if getattr(request, '_scopes', None) is None:
			request._scopes = []
		request._scopes.append(scope)


	'''
	Scope the creation/changing of an object
	'''
	def _store(self, obj, values, request, ignore_unknown_fields=False):

		if obj.pk is None:
			self.scope_add(request, obj, values)
		else:
			self.scope_change(request, obj, values)

		return super()._store(obj, values, request, ignore_unknown_fields)

	def scope_add(self, request, object, values):
		'''
		Scope adding of an object. Raises binderforbidden error if the user does not have the scope to add a model
		'''
		scopes = self._require_model_perm('add', request)
		can_add = False

		for s in scopes:
			scope_name = '_scope_add_{}'.format(s)
			if getattr(self, scope_name, None) is None:
				raise UnexpectedScopeException(
					'Scope {} is not implemented for model {}'.format(scope_name, self.model))
			can_add |= getattr(self, scope_name)(request, object, values)

		if not can_add:
			raise ScopingError(user=request.user,
							   perm='You do not have a scope that allows you to add model={}'.format(self.model))

		self._save_scope(request, Scope.ADD)

	def scope_change(self, request, object, values):
		scopes = self._require_model_perm('change', request)
		can_change = False

		for s in scopes:
			scope_name = '_scope_change_{}'.format(s)
			if getattr(self, scope_name, None) is None:
				raise UnexpectedScopeException(
					'Scope {} is not implemented for model {}'.format(scope_name, self.model))
			can_change |= getattr(self, scope_name)(request, object, values)

		if not can_change:
			raise ScopingError(user=request.user, perm='You do not have a scope that allows you to change model={}'.format(self.model))

		self._save_scope(request, Scope.CHANGE)

	'''Do a scoping on a possibly empty list'''
	def scope_change_list(self, request, objects, values):
		for o in objects:
			self.scope_change(request, o, values)
		self._save_scope(request, Scope.CHANGE)

	def scope_view(self, request, queryset):
		'''
		Performs the scopes for a get request
		'''
		scopes = self._require_model_perm('view', request)
		scope_queries = []
		for s in scopes:
			scope_name = '_scope_view_{}'.format(s)
			if getattr(self, scope_name, None) is None:
				raise UnexpectedScopeException(
					'Scope {} is not implemented for model {}'.format(scope_name, self.model))
			scope_queries.append(getattr(self, scope_name)(request))
		subfilter = Q(id__in=[-1])
		for scope_query in scope_queries:
			subfilter |= Q(id__in=scope_query.values('id'))

		self._save_scope(request, Scope.VIEW)


		return queryset.filter(subfilter)

	def delete(self, request, pk=None, undelete=False):
		query = self.get_queryset(request)
		object = query.filter(pk=pk)

		if len(object) == 0:
			raise BinderNotFound()

		self.scope_delete(request, object, {})

		return super().delete(request, pk, undelete)


	def scope_delete(self, request, object, values):
		'''
		Performs the scopes for deletion of an obbject
		'''
		scopes = self._require_model_perm('delete', request)

		can_change = False

		for s in scopes:
			scope_name = '_scope_delete_{}'.format(s)
			if getattr(self, scope_name, None) is None:
				raise UnexpectedScopeException(
					'Scope {} is not implemented for model {}'.format(scope_name, self.model))
			can_change |= getattr(self, scope_name)(request, object, values)

		if not can_change:
			raise ScopingError(user=request.user,
							   perm='You do not have a scope that allows you to delete model={}'.format(self.model))

		self._save_scope(request, Scope.DELETE)

	def view_history(self, request, pk=None, **kwargs):
		if not pk:
			raise BinderNotFound()

		# We must have permission to view the object. If not we can not view the history
		data = self._get_objs(self.get_queryset(request), request=request)
		if not data:
			raise BinderNotFound()

		return super().view_history(request, pk, **kwargs)


def no_scoping_required(*args, **kwargs):
	def decorator(func):
		def wrapper(self, request, *args, **kwargs):
			if request.method == 'GET':
				scope = Scope.VIEW
			elif request.method == 'POST':
				scope = Scope.ADD
			elif request.method == 'PUT':
				scope = Scope.CHANGE
			else:
				scope = Scope.DELETE
			PermissionView._save_scope(request=request, scope=scope)
			return func(self, request, *args, **kwargs)
		return wrapper
	return decorator
