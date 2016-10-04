from django.conf import settings
from django import setup

settings.configure(**{
	'DEBUG': True,
	'DATABASES': {
		'default': {
			'ENGINE': 'django.db.backends.sqlite3', # For now
			'NAME': ':memory:',
		},
	},
	'MIDDLEWARE_CLASSES': [ # Using MIDDLEWARE_CLASSES while still on django-request-id 0.1.0
		# TODO: Try to reduce the set of absolutely required middlewares
		'request_id.middleware.RequestIdMiddleware',
	],
	'INSTALLED_APPS': [
		# TODO: Try to reduce the set of absolutely required applications
		'django.contrib.auth',
		'django.contrib.contenttypes',
		'binder',
		'tests.testapp',
	],
	'ROOT_URLCONF': 'tests.testapp.urls',
	'LOGGING': {
		'version': 1,
		'loggers': {
			# We override only this one to avoid logspam
			# while running tests.  Django warnings are
			# stil shown.
			'binder': { 'level': 'ERROR', },
		}
	}
})

setup()
