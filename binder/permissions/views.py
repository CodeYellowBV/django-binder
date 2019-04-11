import logging
import warnings
from enum import Enum
from functools import reduce

from django.db import transaction
from django.db.models import Q
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist

from binder.exceptions import BinderForbidden, BinderNotFound
from binder.views import ModelView



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
	@property
	def _permission_definition(self):
		return settings.BINDER_PERMISSION



	def get_queryset(self, request):
		queryset = super().get_queryset(request)
		return self.scope_view(request, queryset)



	def _require_model_perm(self, perm_type, request, pk=None):
		"""
		Check if you have a model permission, and return the scopes
		"""
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
		return list(set(scopes)) # Remove duplicates to avoid unnecessary OR queries (which can be SLOOOOW)



	def _parse_permissions(self, request):
		"""
		Translate high level permissions to low level permissions on the request
		"""
		permissions = request.user.get_all_permissions()
		permissions.add('default')

		# Mapping from permission_name => list of scopes
		_permission_class = {}
		for p in permissions:
			if p in self._permission_definition:
				for permission, scope in self._permission_definition[p]:
					if permission not in _permission_class:
						_permission_class[permission] = []  # Permission, without any scopes
					if scope is not None:
						_permission_class[permission].append(scope)
		request._permission = _permission_class



	def _has_one_of_permissions(self, request, permissions):
		"""
		Check if we have one of a set of permissions
		"""
		for p in permissions:
			if request.user.has_perm(p):
				logger.debug('passed permission check: {}'.format(p))
				return True
		return False



	def dispatch(self, request, *args, **kwargs):
		"""
		Make sure that permissions are checked, and scoping is done
		"""
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
		if isinstance(pk, self.model):
			obj = pk
		else:
			try:
				obj = self.get_queryset(request).get(pk=int(pk))
			except ObjectDoesNotExist:
				raise BinderNotFound()

		if request.method in {'POST', 'DELETE'}:
			# Here we pretend that a DELETE scope is done. We only need a change
			# scope, but the dispatch checks if have a DELETE scope done.
			request._scopes.append(Scope.DELETE)
			self.scope_change(request, obj, {file_field: ...})


		return super().dispatch_file_field(request, obj, file_field)



	def _scope_view_all(self, request):
		return Q(pk__isnull=False)



	def _scope_add_all(self, request, object, values):
		return True



	def _scope_change_all(self, request, object, values):
		return True



	def _scope_delete_all(self, request, object, values):
		return True



	@staticmethod
	def _save_scope(request, scope):
		"""
		Save that we did a scoping on the request object. This allows us to check that scoping is done
		"""
		if getattr(request, '_scopes', None) is None:
			request._scopes = []
		request._scopes.append(scope)



	def _store(self, obj, values, request, **kwargs):
		"""
		Scope the creation/changing of an object
		"""
		if obj.pk is None:
			self.scope_add(request, obj, values)
		else:
			self.scope_change(request, obj, values)

		return super()._store(obj, values, request, **kwargs)



	def scope_add(self, request, object, values):
		"""
		Scope adding of an object. Raises binderforbidden error if the user does not have the scope to add a model
		"""
		scopes = self._require_model_perm('add', request)
		can_add = False

		for s in scopes:
			scope_name = '_scope_add_{}'.format(s)
			if getattr(self, scope_name, None) is None:
				raise UnexpectedScopeException(
					'Scope {} is not implemented for model {}'.format(scope_name, self.model))
			can_add |= getattr(self, scope_name)(request, object, values)

		if not can_add:
			raise ScopingError(user=request.user, perm='You do not have a scope that allows you to add model={}'.format(self.model))

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



	def scope_change_list(self, request, objects, values):
		"""
		Do a scoping on a possibly empty list
		"""
		for o in objects:
			self.scope_change(request, o, values)
		else:
			setattr(request, '_has_permission_check', True)
		self._save_scope(request, Scope.CHANGE)



	def scope_view(self, request, queryset):
		"""
		Performs the scopes for a get request
		"""
		scopes = self._require_model_perm('view', request)
		scope_queries = []
		scope_querysets = []
		for s in scopes:
			scope_name = '_scope_view_{}'.format(s)
			scope_func = getattr(self, scope_name, None)
			if scope_func is None:
				raise UnexpectedScopeException(
					'Scope {} is not implemented for model {}'.format(scope_name, self.model))
			query_or_q = scope_func(request)
			# Allow either a ORM filter query manager or a Q object.
			# Q objects generate more efficient queries (so we don't
			# get an "id IN (subquery)"), but query managers allow
			# filtering on annotations, which Q objects don't.
			if isinstance(query_or_q, Q):
				scope_queries.append(query_or_q)
			else:
				# Reset the ORDER BY at least to get a faster query.
				# Even better performance could be gained if
				# https://code.djangoproject.com/ticket/29338 is
				# fixed; then add an OuterRef to scope the subquery.
				scope_querysets.append(query_or_q.order_by().values('pk'))

		# It looks like a chain of OR subqueries is *much* slower than
		# one equivalent UNION subquery (to an insane degree).
		if scope_querysets:
			qs = reduce(lambda scope_qs, qs: qs.union(scope_qs), scope_querysets)
			scope_queries.append(Q(pk__in=qs))

		subfilter = reduce(lambda scope_query, q: q | scope_query, scope_queries)

		self._save_scope(request, Scope.VIEW)

		return queryset.filter(subfilter)



	def delete(self, request, pk=None, undelete=False):
		try:
			object = self.get_queryset(request).get(pk=pk)
		except self.model.DoesNotExist:
			raise BinderNotFound()

		self.scope_delete(request, object, {})

		return super().delete(request, pk, undelete)



	def scope_delete(self, request, object, values):
		"""
		Performs the scopes for deletion of an obbject
		"""
		scopes = self._require_model_perm('delete', request)

		can_change = False

		for s in scopes:
			scope_name = '_scope_delete_{}'.format(s)
			if getattr(self, scope_name, None) is None:
				raise UnexpectedScopeException(
					'Scope {} is not implemented for model {}'.format(scope_name, self.model))
			scope_func = getattr(self, scope_name)
			try:
				scope = scope_func(request, object, values)
			except Exception as e:
				# Call with queryset instead of object for backwards compat
				try:
					qs = self.get_queryset(request).filter(pk=object.pk)
					scope = scope_func(request, qs, values)
				except Exception:
					# Both failed so exception probably was not related to
					# instance vs queryset so raise original exception
					raise e
				# Only reached when scope on queryset doesnt raise an exception
				# while scope on instance did
				warnings.warn(RuntimeWarning(
					'{}.{} still scopes on querysets instead of instances.'
					.format(type(self).__name__, scope_name)
				))

			can_change |= scope

		if not can_change:
			raise ScopingError(user=request.user, perm='You do not have a scope that allows you to delete model={}'.format(self.model))

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
