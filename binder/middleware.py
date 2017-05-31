import logging
import resource
from django.conf import settings
import json



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



class VersionHeaderMiddleware:
	"""
	Middleware that adds a response header to every request with the version.

	The header is "Cy-Backend-Version", and its value is a JSON object
	containing the version number and the commit hash. e.g.:

	Cy-Backend-Version: {"version": "2.0.1", "commit_hash": "2b50dfb"}

	Simply including this middleware is enough to gain this functionality.
	"""
	def __init__(self, get_response):
		self.get_response = get_response

		version = getattr(settings, 'VERSION', None)
		commit_hash = getattr(settings, 'COMMIT_HASH', None)

		self.header_value = json.dumps({'version': version, 'commit_hash': commit_hash})

	def __call__(self, request):
		response = self.get_response(request)
		response['Cy-Backend-Version'] = self.header_value
		return response



class LogFrontEndVersionMiddleware:
	"""
	Middleware that logs the front-end version as found in a request header.

	Simply including this middleware will log the value of the request
	header "Cy-Frontend-Version". This aids debugging, showing if the FE and
	BE are in sync. Absence of the header is not an error.
	"""
	def __init__(self, get_response):
		self.get_response = get_response

	def __call__(self, request):
		logger.debug('front-end version: {}'.format(request.META.get('HTTP_CY_FRONTEND_VERSION')))

		response = self.get_response(request)
		return response



class LogFrontEndSourceLocMiddleware:
	"""
	Middleware that logs the source location of the request initiation in
	the front-end as found in a request header.

	Simply including this middleware will log the value of the request
	header "Cy-Frontend-Source-Loc". This aids debugging, showing where a
	particular request originated. Absence of the header is not an error.
	"""
	def __init__(self, get_response):
		self.get_response = get_response

	def __call__(self, request):
		logger.debug('front-end source location: {}'.format(request.META.get('HTTP_CY_FRONTEND_SOURCE_LOC')))

		response = self.get_response(request)
		return response
