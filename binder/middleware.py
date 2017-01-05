import logging
import resource
from django.conf import settings



logger = logging.getLogger(__name__)



class BuildLogMiddleware:
	"""
	Middleware to log a string on every request. Intended for version/commit/etc.

	Simply including this middleware will log the following settings variables
	on every request: ENV_NAME, DEBUG, BRANCH, VERSION, COMMIT_NR, COMMIT_HASH,
	BUILD_DATE.

	To provide a custom message, define settings.BUILD_LOG_MESSAGE. This will
	replace the entire log string.
	"""
	def __init__(self, get_response):
		self.get_response = get_response
		try:
			self.log_message = settings.BUILD_LOG_MESSAGE
		except AttributeError:
			self.log_message = 'env={} debug={} branch={} tag={} commit={}/{} built={}'.format(
				getattr(settings, 'ENV_NAME', None),
				settings.DEBUG,
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



class MemoryLogMiddleware:
	"""
	Middleware to log VM/memory stats of a request.

	Simply including this middleware is enough.

	Logs Max RSS size before and after the request, plus the number of minor and
	major page faults and swapouts that occured during the request.
	"""
	def __init__(self, get_response):
		self.get_response = get_response

	def __call__(self, request):
		before = resource.getrusage(resource.RUSAGE_SELF)
		response = self.get_response(request)
		after = resource.getrusage(resource.RUSAGE_SELF)

		logger.debug('rusage maxRSS = {} before / {} after, {} minor / {} major pagefaults, {} swapouts'.format(
			before.ru_maxrss,
			after.ru_maxrss,
			after.ru_minflt - before.ru_minflt,
			after.ru_majflt - before.ru_majflt,
			after.ru_nswap - before.ru_nswap,
		))
		return response
