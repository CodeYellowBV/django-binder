import logging
import sys
import json

import django
from django.http import HttpResponse



logger = logging.getLogger(__name__)



class BinderException(Exception):
	http_code = None
	code = None
	fields = None
	validation_errors = None

	def __init__(self):
		self.fields = {}

	def exception_location(self):
		import traceback
		# Exception traceback magic.
		tb = sys.exc_info()[2]
		file, line, method, code = traceback.extract_tb(tb)[-1]
		return (file, method, line, code)

	def log(self):
		loc = '{1}:{2} in {0}'.format(*self.exception_location())
		logger.warning('request raised exception {}: {} at {}'.format(self.__class__.__name__, self.data(), loc))

	def data(self):
		data = dict(self.fields)
		data['code'] = self.code
		if hasattr(self, 'object') and self.object:
			data['object'] = self.object
		return data

	def response(self, request=None):
		data = self.data()
		data['debug'] = {'request_id': request.request_id if request else None}
		if django.conf.settings.DEBUG:
			data['debug']['location'] = '{1}:{2} in {0}'.format(*self.exception_location())
		return HttpResponse(json.dumps(data), status=self.http_code, content_type='application/json')

	# The Python Exception __str__ can return something unhelpful like "('foo', SomeOb)".
	# This can be quite annoying during debug. __repr__ is better so we use that instead.
	def __str__(self):
		return repr(self)



class BinderInvalidURI(BinderException):
	http_code = 418
	code = 'InvalidURI'

	def __init__(self, path):
		super().__init__()
		self.fields['path'] = path
		self.fields['message'] = 'Undefined URI for this API.'
		if not path.endswith('/'):
			self.fields['message'] += ' (Hint: did you forget the trailing slash?)'



class BinderRequestError(BinderException):
	http_code = 418
	code = 'RequestError'

	def __init__(self, message):
		super().__init__()
		self.fields['message'] = message



class BinderReadOnlyFieldError(BinderRequestError):
	def __init__(self, model, field):
		super().__init__('Read-only field: {{{}.{}}}.'.format(model, field))



class BinderFieldTypeError(BinderRequestError):
	def __init__(self, *args):
		super().__init__('Type error for field: {{{}}}.'.format('.'.join(args)))



class BinderInvalidField(BinderRequestError):
	def __init__(self, model, field):
		super().__init__('Invalid field name for {{{}}}: {{{}}}.'.format(model, field))



class BinderMethodNotAllowed(BinderException):
	http_code = 405
	code = 'MethodNotAllowed'

	def __init__(self, methods=None):
		super().__init__()
		if methods is not None:
			self.fields['allowed_methods'] = methods



class BinderNotAuthenticated(BinderException):
	http_code = 403
	code = 'NotAuthenticated'



class BinderForbidden(BinderException):
	http_code = 403
	code = 'Forbidden'

	def __init__(self, perm, user):
		super().__init__()
		self.fields['required_permission'] = perm
		username_field = getattr(user, 'USERNAME_FIELD', 'username')
		self.fields['current_user'] = getattr(user, username_field)



class BinderCSRFFailure(BinderRequestError):
	http_code = 403
	code = 'CSRFFailure'



class BinderNotFound(BinderException):
	http_code = 404
	code = 'NotFound'

	def __init__(self, resource=None):
		super().__init__()
		if resource:
			self.fields['resource'] = resource



class BinderFileSizeExceeded(BinderException):
	http_code = 413
	code = 'FileSizeExceeded'

	def __init__(self, max_size):
		super().__init__()
		self.fields['max_size'] = int(max_size * 10**6)



class BinderFileTypeIncorrect(BinderException):
	http_code = 400
	code = 'FileTypeIncorrect'

	def __init__(self, allowed_types):
		super().__init__()
		self.fields['allowed_types'] = allowed_types



class BinderImageError(BinderException):
	http_code = 400
	code = 'ImageError'

	def __init__(self, message):
		super().__init__()
		self.fields['message'] = message



class BinderImageSizeExceeded(BinderException):
	http_code = 400
	code = 'ImageSizeExceeded'

	def __init__(self, max_width, max_height):
		super().__init__()
		self.fields['max_width'] = max_width
		self.fields['max_height'] = max_height



class BinderIsDeleted(BinderException):
	http_code = 405
	code = 'IsDeleted'



class BinderIsNotDeleted(BinderException):
	http_code = 405
	code = 'IsNotDeleted'



class BinderValidationError(BinderException):
	http_code = 400
	code = 'ValidationError'

	def __init__(self, errors):
		super().__init__()
		self.errors = errors

	def data(self):
		data = dict(self.fields)
		data['code'] = self.code
		data['errors'] = self.errors
		return data

	def __radd__(self, other):
		return self + other

	def __add__(self, other):
		if other is None:
			return self

		errors = {}
		for model in set(self.errors) | set(other.errors):
			if model in self.errors and model in other.errors:
				errors[model] = {}
				for pk in set(self.errors[model]) | set(other.errors[model]):
					if pk in self.errors[model] and pk in other.errors[model]:
						errors[model][pk] = {}
						for field in set(self.errors[model][pk]) | set(other.errors[model][pk]):
							errors[model][pk][field] = (
								self.errors[model][pk][field] if field in self.errors[model][pk] else []
							) + (
								other.errors[model][pk][field] if field in other.errors[model][pk] else []
							)
					elif pk in self.errors[model]:
						errors[model][pk] = self.errors[model][pk]
					else:
						errors[model][pk] = other.errors[model][pk]
			elif model in self.errors:
				errors[model] = self.errors[model]
			else:
				errors[model] = other.errors[model]
		return BinderValidationError(errors)
