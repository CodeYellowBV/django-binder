from django import setup
from django.conf import settings

settings.configure(**{
	'DEBUG': True,
	'DATABASES': {
		'default': {
			'ENGINE': 'django.db.backends.postgresql_psycopg2',
			'NAME': 'binder-test',
		},
	},
	'MIDDLEWARE': [
		# TODO: Try to reduce the set of absolutely required middlewares
		'request_id.middleware.RequestIdMiddleware',
		'django.contrib.sessions.middleware.SessionMiddleware',
		'django.contrib.auth.middleware.AuthenticationMiddleware',
	],
	'INSTALLED_APPS': [
		# TODO: Try to reduce the set of absolutely required applications
		'django.contrib.auth',
		'django.contrib.contenttypes',
		'django.contrib.sessions',
		'binder',
		'binder.tests.testapp',
	],
	'MIGRATION_MODULES': {
		'testapp': None,
		'auth': None,
		'sessions': None,
		'contenttypes': None,
		'binder': None,
	},
	'USE_TZ': True,
	'ROOT_URLCONF': 'binder.tests.testapp.urls',
	'LOGGING': {
		'version': 1,
		'handlers': {
			'console': {
				'level': 'DEBUG',
				'class': 'logging.StreamHandler',
			},
		},
		'loggers': {
			# We override only this one to avoid logspam
			# while running tests.  Django warnings are
			# stil shown.
			'binder': {
				'handlers': ['console'],
				'level': 'ERROR',
			},
		}
	}
})

setup()

# Do the dance to ensure the models are synched to the DB.
# This saves us from having to include migrations
from django.core.management.commands.migrate import Command as MigrationCommand # noqa
from django.db import connections # noqa
from django.db.migrations.executor import MigrationExecutor # noqa

# This is oh so hacky....
cmd = MigrationCommand()
cmd.verbosity = 0
connection = connections['default']
executor = MigrationExecutor(connection)
cmd.sync_apps(connection, executor.loader.unmigrated_apps)
