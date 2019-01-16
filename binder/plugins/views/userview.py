import logging
import json
from abc import ABCMeta, abstractmethod

from django.contrib import auth
from django.contrib.auth import update_session_auth_hash, password_validation
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.cache import never_cache
from django.utils.translation import ugettext as _

from binder.permissions.views import no_scoping_required
from binder.exceptions import BinderForbidden, BinderReadOnlyFieldError, BinderMethodNotAllowed, BinderIsNotDeleted, \
	BinderIsDeleted, BinderNotAuthenticated, BinderFieldTypeError, BinderRequestError, BinderValidationError, \
	BinderNotFound
from binder.router import list_route, detail_route
from binder.json import JsonResponse
from binder.views import annotate

logger = logging.getLogger(__name__)


class UserBaseMixin:
	__metaclass__ = ABCMeta

	def respond_with_user(self, request, user_id):
		return JsonResponse(
			self._get_objs(
				annotate(self.get_queryset(request).filter(pk=user_id)),
				request=request,
			)[0]
		)


class MasqueradeMixin(UserBaseMixin):
	__metaclass__ = ABCMeta

	@detail_route(name='masquerade')
	@no_scoping_required()
	def masquerade(self, request, pk=None):
		from hijack.helpers import login_user

		if request.method != 'POST':
			raise BinderMethodNotAllowed()

		try:
			user = self.model._default_manager.get(pk=pk)
		except self.model.DoesNotExist:
			raise BinderNotFound()

		self._require_model_perm('masquerade', request)

		login_user(request, user)  # Ignore returned redirect response object
		return self.respond_with_user(request, user.id)

	@list_route(name='endmasquerade')
	@no_scoping_required()
	def endmasquerade(self, request):
		from hijack.helpers import release_hijack

		if request.method != 'POST':
			raise BinderMethodNotAllowed()

		self._require_model_perm('unmasquerade', request)

		release_hijack(request)  # Ignore returned redirect response object
		return self.respond_with_user(request, request.user.id)


class UserViewMixIn(UserBaseMixin):
	__metaclass__ = ABCMeta
	log_request_body = False
	token_generator = default_token_generator

	def _require_model_perm(self, perm_type, request, pk=None):
		"""
		Overwrite the _require_model_perm, to make sure that you can not modify a superuser as non superuser

		We need to be very careful about permission assumptions after this point
		"""
		# If the user is trying to change a superuser and is not a superuser, disallow
		if pk and self.model.objects.get(pk=int(pk)).is_superuser and not request.user.is_superuser:
			# Maybe BinderRequestError?
			raise BinderForbidden('modify superuser', request.user)

		# Everything normal
		return super()._require_model_perm(perm_type, request, pk)

	def _store__groups(self, obj, field, value, request, pk=None):
		"""
		Store the groups of the user.

		If we get here, the user might not actually have admin permissions;
		If the user does not have user change perms, disallow setting groups.
		"""
		try:
			self._require_model_perm('changegroups', request)
			return self._store_field(obj, field, value, request, pk=pk)
		except BinderForbidden:  # convert to read-only error, so the field is ignored
			raise BinderReadOnlyFieldError(self.model.__name__, field)

	def _parse_filter(self, queryset, field, value, partial=''):
		"""
		Add the has_permission as a filter
		"""
		if field == 'has_permission':
			users = self.model.objects.filter(
				Q(groups__permissions__codename=value) |
				Q(user_permissions__codename=value) |
				Q(is_superuser=True)
			)
			if not partial:
				return users
			return queryset.filter(Q(**{partial + 'in': set(users.values_list('id', flat=True))}))
		else:
			return super()._parse_filter(queryset, field, value, partial)

	@method_decorator(sensitive_post_parameters())
	@list_route(name='login', unauthenticated=True)
	@no_scoping_required()
	def login(self, request):
		"""
		Login the user

		Request:

		POST user/login/
		{
			"username": "foo",
			"password": "password"
		}

		Response:

		returns the same parameters as GET user/{id}/
		"""

		if request.method != 'POST':
			raise BinderMethodNotAllowed()

		try:
			decoded = request.body.decode()
			body = json.loads(decoded)
			username = body.get(self.model.USERNAME_FIELD, '')
			password = body.get('password', '')
		except Exception:
			username = request.POST.get(self.model.USERNAME_FIELD, '')
			password = request.POST.get('password', '')

		user = auth.authenticate(**{
			self.model.USERNAME_FIELD: username.lower(),
			'password': password,
		})
		self._require_model_perm('login', request)

		if user is None:
			logger.info('login failed for "{}"'.format(username))
			raise BinderNotAuthenticated()
		else:
			auth.login(request, user)
			logger.info('login for {}/{}'.format(user.id, user))
			return self.respond_with_user(request, user.id)

	@list_route(name='logout')
	@no_scoping_required()
	def logout(self, request):
		"""
		Logout the user

		Request:

		POST /user/logout/
		{}

		Response:
		204
		{}
		"""
		if request.method != 'POST':
			raise BinderMethodNotAllowed()

		self._require_model_perm('logout', request)
		logger.info('logout for {}/{}'.format(request.user.id, request.user))
		auth.logout(request)
		return HttpResponse(status=204)

	def get_users(self, username):
		"""
		Given a username, return matching user(s) who should receive a reset.

		This allows subclasses to more easily customize the default policies
		that prevent inactive users and users with unusable passwords from
		resetting their password.

		Copied from django.contrib.auth.forms.PasswordResetForm
		"""
		active_users = self.model._default_manager.filter(**{
			self.model.USERNAME_FIELD + '__iexact': username,
			'is_active': True,
		})
		return (u for u in active_users if u.has_usable_password())

	def _store__username(self, user, field, value, request, pk=None):
		"""
		Makes sure the username is always stored as a lowercase
		"""
		if not isinstance(value, str):
			raise BinderFieldTypeError(self.model.__name__, field)
		return self._store_field(user, field, value.lower(), request, pk=pk)

	def filter_deleted(self, queryset, pk, deleted, request=None):
		"""
		Can be used to filter deleted users, or unfilter them.
		"""
		if pk or deleted == 'true':
			return queryset
		if deleted is None:
			return queryset.filter(is_active=True)
		if deleted == 'only':
			return queryset.filter(is_active=False)
		raise BinderRequestError(_('Invalid value: deleted=%s.') % request.GET.get('deleted'))

	def soft_delete(self, user, undelete=False, request=None):
		"""
		Allows the user to be soft deleted, and undeleted. What actually needs to be done on soft deletion
		can be implemented in

		_after_soft_delete
		"""
		try:
			if not user.is_active and not undelete:
				raise BinderIsDeleted()
			if not not user.is_active and undelete:
				raise BinderIsNotDeleted()
		except AttributeError:
			raise BinderMethodNotAllowed()

		user.is_active = undelete
		user.save()

		self._after_soft_delete(request, user, undelete)

	@list_route(name='reset_request', unauthenticated=True)
	@no_scoping_required()
	def reset_request(self, request):
		"""
		Adds an endpoint to do a reset request. Generates a token, and calls the _send_reset_mail callback if the reset
		request is successful

		Request:

		POST user/reset_request/
		{
			'username': 'foo'
		}

		Response:
		204
		{
		}

		"""
		if request.method != 'POST':
			raise BinderMethodNotAllowed()

		self._require_model_perm('reset_password', request)

		decoded = request.body.decode()
		try:
			body = json.loads(decoded)
		except ValueError:
			raise BinderRequestError(_('Invalid request body: not a JSON document.'))

		logger.info('password reset attempt for {}'.format(body.get(self.model.USERNAME_FIELD, '')))

		for user in self.get_users(body.get(self.model.USERNAME_FIELD, '').lower()):
			token = self.token_generator.make_token(user)
			self._send_reset_mail(request, user, token)

		return HttpResponse(status=204)

	@never_cache
	@list_route(name='send_activation_email', unauthenticated=True)
	@no_scoping_required()
	def send_activation_email(self, request):
		"""
		Endpoint that can be used to send an activation mail for an user.
		Calls the _send_activation_email callback if the user is succesfully activated

		Request:

		POST
		{
			"email": "email"
		}

		Response:
		{
			"code": code
		}

		Possible codes:

		sent			Mail is send sucessfully
		already active 	User is already active, no mail was send
		blacklisted		User was not activated

		"""
		if request.method != 'PUT':
			raise BinderMethodNotAllowed()

		# For lack of a better check
		self._require_model_perm('reset_password', request)

		decoded = request.body.decode()
		try:
			body = json.loads(decoded)
		except ValueError:
			raise BinderRequestError(_('Invalid request body: not a JSON document.'))

		logger.info('activation email attempt for {}'.format(body.get('email', '')))

		if body.get('email') is None:
			raise BinderValidationError({'email': ['missing']})

		try:
			user = self.model._default_manager.get(email=body.get('email'))
		except self.model.DoesNotExist:
			raise BinderNotFound()

		if user.is_active:
			if user.last_login is None:
				# TODO: Figure out a way to make this customisable without
				# allowing injection of arbitrary URLs (phishing!)
				self._send_activation_email(request, user)
				response = JsonResponse({'code': 'sent'})
				response.status_code = 201
			else:
				response = JsonResponse({'code': 'already active'})
		else:
			response = JsonResponse({'code': 'blacklisted'})
			response.status_code = 400

		return response

	@method_decorator(sensitive_post_parameters())
	@never_cache
	@detail_route(name='activate', unauthenticated=True)
	@no_scoping_required()
	def activate(self, request, pk=None):
		"""
		Adds an endpoint to activate an user. Also logs in the user

		Request:

		POST user/{id}/activate/
		{
			"activation_code": string
		}

		Response:

		Same as GET user/{id}/
		"""
		if request.method != 'PUT':
			raise BinderMethodNotAllowed()

		self._require_model_perm('activate', request)

		decoded = request.body.decode()
		try:
			body = json.loads(decoded)
		except ValueError:
			raise BinderRequestError(_('Invalid request body: not a JSON document.'))

		errors = {}
		for item in ['activation_code']:
			if body.get(item) is None:
				errors[item] = ['missing']
		if len(errors) != 0:
			raise BinderValidationError(errors)

		try:
			user = self.model._default_manager.get(pk=pk)
		except (TypeError, ValueError, OverflowError, self.model.DoesNotExist):
			user = None

		if user is None or not self.token_generator.check_token(user, body.get('activation_code')):
			raise BinderNotFound()

		logger.info('login for {}/{} via successful activation'.format(user.id, user))

		user.is_active = True
		user.save()
		auth.login(request, user)
		return self.respond_with_user(request, user.id)

	@method_decorator(sensitive_post_parameters())
	@never_cache
	@detail_route(name='reset_password', unauthenticated=True, methods=['PUT'])
	@no_scoping_required()
	def reset_password(self, request, pk=None):
		"""
		Resets the password from an reset code

		Request:

		POST user/reset_password/
		{
			"reset_code": str,
			"password": str
		}

		Response:

		Same as GET user/{id}/

		"""

		self._require_model_perm('reset_password', request)

		decoded = request.body.decode()
		try:
			body = json.loads(decoded)
		except ValueError:
			raise BinderRequestError(_('Invalid request body: not a JSON document.'))

		errors = {item: 'missing' for item in ['reset_code', 'password'] if item not in body}
		if errors:
			raise BinderValidationError(errors)

		return self._reset_pass_for_user(request, int(pk), body['reset_code'], body['password'])

	def _reset_pass_for_user(self, request, user_id, token, password):
		"""
		Helper function that actually resets the password for an user
		"""
		try:
			user = self.model._default_manager.get(pk=user_id)
		except (TypeError, ValueError, OverflowError, self.model.DoesNotExist):
			user = None

		if user is None or not self.token_generator.check_token(user, token):
			raise BinderNotFound()

		logger.info('login for {}/{} via successful password reset'.format(user.id, user))

		try:
			password_validation.validate_password(password, user)
		except ValidationError as ve:
			raise BinderValidationError({'password': ve.messages})

		user.set_password(password)
		user.save()
		auth.login(request, user)
		return self.respond_with_user(request, user.id)

	@method_decorator(sensitive_post_parameters())
	@never_cache
	@list_route(name='change_password')
	@no_scoping_required()
	def change_password(self, request):
		"""
		Change the password from an old password

		Request:

		POST user/change_password/
		{
			"old_password": str,
			"new_password": str
		}

		Response:
		Same as GET user/{id}/

		"""
		if request.method != 'PUT':
			raise BinderMethodNotAllowed()

		self._require_model_perm('change_own_password', request)

		decoded = request.body.decode()
		try:
			body = json.loads(decoded)
		except ValueError:
			raise BinderRequestError(_('Invalid request body: not a JSON document.'))

		user = request.user

		errors = {}
		for item in ['old_password', 'new_password']:
			if body.get(item) is None:
				errors[item] = ['missing']

		if not user.check_password(body.get('old_password')):
			errors['old_password'] = ['incorrect']

		if len(errors) != 0:
			raise BinderValidationError(errors)

		password = body.get('new_password')
		try:
			password_validation.validate_password(password, user)
		except ValidationError as ve:
			validation_errors = {'new_password': ve.messages}
			raise BinderValidationError(validation_errors)

		user.set_password(password)
		user.save()
		logger.info('password changed for {}/{}'.format(user.id, user))

		if user == request.user:
			"""
			No need to change the password of an user that is not our own
			"""
			update_session_auth_hash(request, user)

		return self.respond_with_user(request, user.id)

	@list_route(name='email_exists', unauthenticated=True, methods=['GET'])
	@no_scoping_required()
	def email_exists(self, request):
		"""
		Adds an endpoint to check if an email exists or not

		Request:

		POST user/email_exists/
		{
			"email": "str@str.com"
		}

		Return:
		200 if it exists, of 404 if it does not exist.

		"""
		self._require_model_perm('email_exists', request)

		email = request.GET.get('email')
		if self.model.objects.filter(email=email.lower()).exists():
			return JsonResponse({})
		else:
			raise BinderNotFound()

	@abstractmethod
	def _after_soft_delete(self, request, user, undelete):
		"""
		Callback called after an user is softdeleted or softundeleted
		"""
		pass

	@abstractmethod
	def _send_reset_mail(self, request, user, token):
		"""
		Callback to send the actual reset mail using the token.
		"""
		pass

	@abstractmethod
	def _send_activation_email(self, request, user):
		"""
		Callback to send a mail notifying that the user is activated.
		"""
		pass
