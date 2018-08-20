from django import setup
from django.conf import settings
import os

if (
	os.path.exists('/.dockerenv') and
	'CY_RUNNING_INSIDE_TRAVIS' not in os.environ
):
	db_settings = {
		'ENGINE': 'django.db.backends.postgresql',
		'NAME': 'postgres',
		'USER': 'postgres',
		'HOST': 'db',
		'PORT': 5432,
	}
else:
	db_settings = {
		'ENGINE': 'django.db.backends.postgresql_psycopg2',
		'NAME': 'binder-test',
	}

settings.configure(**{
	'DEBUG': True,
	'DATABASES': {
		'default': db_settings,
	},
	'MIDDLEWARE': [
		# TODO: Try to reduce the set of absolutely required middlewares
		'request_id.middleware.RequestIdMiddleware',
		'django.contrib.sessions.middleware.SessionMiddleware',
		'django.contrib.auth.middleware.AuthenticationMiddleware',
		'binder.plugins.token_auth.middleware.TokenAuthMiddleware',
	],
	'INSTALLED_APPS': [
		# TODO: Try to reduce the set of absolutely required applications
		'django.contrib.auth',
		'django.contrib.contenttypes',
		'django.contrib.sessions',
		'binder',
		'binder.plugins.token_auth',
		'binder.tests.testapp',
	],
	'MIGRATION_MODULES': {
		'testapp': None,
		'auth': None,
		'sessions': None,
		'contenttypes': None,
		'binder': None,
		'token_auth': None,
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
	},
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
