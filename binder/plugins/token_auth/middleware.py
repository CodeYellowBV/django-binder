from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.models import AnonymousUser

from binder.exceptions import BinderException
from binder.plugins.token_auth.models import Token


class BinderTokenNotFound(BinderException):
	"""
	Exception for when a user tries to authenticate with a token that does not
	exist.
	"""

	http_code = 404
	code = 'TokenNotFound'

	def __init__(self, token):
		super().__init__()
		self.fields['message'] = 'Token not found.'
		self.fields['token'] = token


class BinderTokenExpired(BinderException):
	"""
	Exception for when a user tries to authenticate with a token that is
	expired.
	"""

	http_code = 400
	code = 'TokenExpired'

	DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S.%f%z'

	def __init__(self, token):
		super().__init__()
		self.fields['message'] = 'Token expired.'
		self.fields['token'] = token.token
		self.fields['expired_at'] = (
			token.expires_at.strftime(self.DATETIME_FORMAT)
		)


class TokenAuthMiddleware:
	"""
	Authenticate by tokens provided by the HTTP_AUTHORIZATION header.
	"""

	def __init__(self, get_response):
		self.get_response_no_csrf = csrf_exempt(get_response)
		self.get_response = get_response

	def __call__(self, request):
		if not hasattr(request, 'user'):
			request.user = AnonymousUser()

		if request.user.is_authenticated:
			# Already authenticated
			return self.get_response(request)

		auth = request.META.get('HTTP_AUTHORIZATION')

		if auth is None:
			# No auth header sent
			return self.get_response(request)

		if not auth.startswith('Token '):
			# Auth header of wrong type
			return self.get_response(request)

		token = auth[6:]
		try:
			token = Token.objects.get(token=token)
		except Token.DoesNotExist:
			# Token does not exist
			# Raise and catch needed to provide location
			try:
				raise BinderTokenNotFound(token)
			except BinderTokenNotFound as exc:
				return exc.response(request)

		if token.expired:
			token.delete()
			# Token is expired
			# Raise and catch needed to provide location
			try:
				raise BinderTokenExpired(token)
			except BinderTokenExpired as exc:
				return exc.response(request)

		request.user = token.user
		token.save()  # Auto updates last_used_at
		# CSRF not needed because the token already establishes that the
		# request was not forged
		return self.get_response_no_csrf(request)
