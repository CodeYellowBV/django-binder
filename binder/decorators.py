import time
from functools import wraps

import django
from django.http.request import RawPostDataException
from django.db import transaction

from .views import ellipsize
from .exceptions import BinderException


def view_logger(logger, log_request_body=True):
	def decorator(view):
		@wraps(view)
		def decorated(request, *args, **kwargs):
			time_start = time.time()
			logger.info('request dispatch; verb={}, user={}/{}, path={}'.format(
				request.method,
				request.user.id,
				request.user,
				request.path,
			))
			logger.info('remote_addr={}, X-Real-IP={}, X-Forwarded-For={}'.format(
				request.META.get('REMOTE_ADDR', None),
				request.META.get('HTTP_X_REAL_IP', None),
				request.META.get('HTTP_X_FORWARDED_FOR', None),
			))
			logger.info('request parameters: {}'.format(dict(request.GET)))
			logger.debug('cookies: {}'.format(request.COOKIES))

			if not log_request_body:
				body = ' censored.'
			else:
				# FIXME: ugly workaround, remove when Django bug fixed
				# Try/except because https://code.djangoproject.com/ticket/27005
				try:
					if request.META.get('CONTENT_TYPE', '').lower() == 'application/json':
						body = ': ' + ellipsize(request.body, length=65536)
					else:
						body = ': ' + ellipsize(request.body, length=64)
				except RawPostDataException:
					body = ' unavailable.'

			logger.debug('body (content-type={}){}'.format(request.META.get('CONTENT_TYPE'), body))

			response = view(request, *args, **kwargs)

			logger.info('request response; status={} time={}ms bytes={} queries={}'.format(
				response.status_code,
				int((time.time() - time_start) * 1000),
				'?' if response.streaming else len(response.content),
				len(django.db.connection.queries),
			))

			return response
		return decorated
	return decorator


def handle_exceptions(view):
	@wraps(view)
	def decorated(request, *args, **kwargs):
		try:
			with transaction.atomic():
				return view(request, *args, **kwargs)
		except BinderException as e:
			return e.response(request)
	return decorated
