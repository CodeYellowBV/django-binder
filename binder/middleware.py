import logging
from django.conf import settings



logger = logging.getLogger(__name__)



class BuildLogMiddleware:
	"""
	Middleware to log a string on every request. Intended for version/commit/etc.

	Simply including this middleware will log the following settings variables
	on every request: BRANCH, VERSION, COMMIT_NR, COMMIT_HASH, BUILD_DATE.

	To provide a custom message, define settings.BUILD_LOG_MESSAGE. This will
	replace the entire log string.
	"""
	def __init__(self, get_response):
		self.get_response = get_response
		try:
			self.log_message = settings.BUILD_LOG_MESSAGE
		except AttributeError:
			self.log_message = 'branch={} tag={} commit={}/{} built={}'.format(
				getattr(settings, 'BRANCH', None),
				getattr(settings, 'VERSION', None),
				getattr(settings, 'COMMIT_NR', None),
				getattr(settings, 'COMMIT_HASH', None),
				getattr(settings, 'BUILD_DATE', None),
			)

	def __call__(self, request):
		logger.info(self.log_message)

		response = self.get_response(request)
		return response
