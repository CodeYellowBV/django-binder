from django import setup
from django.conf import settings
from django.core.management import call_command
import os

if (
	os.path.exists('/.dockerenv') and
	'CY_RUNNING_INSIDE_CI' not in os.environ
):
	db_settings = {
		'ENGINE': 'django.db.backends.postgresql',
		'NAME': 'postgres',
		'USER': 'postgres',
		'HOST': 'db',
		'PORT': 5432,
	}
elif os.environ.get('BINDER_TEST_MYSQL', '0') == '1':
	db_settings = {
		'ENGINE': 'django.db.backends.mysql',
		'NAME': 'binder-test',
		'TIME_ZONE': 'UTC',
		'HOST': '127.0.0.1',
		'USER': 'root',
		'PASSWORD': 'rootpassword',
	}
else:
	db_settings = {
		'ENGINE': 'django.db.backends.postgresql',
		'NAME': 'binder-test',
		'HOST': 'localhost',
		'USER': 'postgres',
	}

settings.configure(**{
	'DEBUG': True,
	'SECRET_KEY': 'testy mctestface',
	'ALLOWED_HOSTS': ['*'],
	'DATABASES': {
		'default': db_settings,
	},
	'MIDDLEWARE': [
		# TODO: Try to reduce the set of absolutely required middlewares
		'request_id.middleware.RequestIdMiddleware',
		'django.contrib.sessions.middleware.SessionMiddleware',
		'django.middleware.csrf.CsrfViewMiddleware',
		'django.contrib.auth.middleware.AuthenticationMiddleware',
		'binder.plugins.token_auth.middleware.TokenAuthMiddleware',
	],
	'INSTALLED_APPS': [
		# TODO: Try to reduce the set of absolutely required applications
		'django.contrib.auth',
		'django.contrib.contenttypes',
		'django.contrib.sessions',
		*(
			['django.contrib.postgres']
			if db_settings['ENGINE'] == 'django.db.backends.postgresql' else
			[]
		),
		'binder',
		'binder.plugins.token_auth',
		'tests',
		'tests.testapp',
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
	'TIME_ZONE': 'UTC',
	'ROOT_URLCONF': 'tests.testapp.urls',
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
	'BINDER_PERMISSION': {
		'default': [
			('auth.reset_password_user', None),
			('auth.view_user', 'own'),
			('auth.activate_user', None),
			('auth.unmasquerade_user', None),  # If you are masquarade, the user must be able to unmasquarade
			('auth.login_user', None),
			('auth.signup_user', None),
			('auth.logout_user', None),
			('auth.change_own_password_user', None),
		],
		# Basic permissions which can be used to override stuff
		'testapp.view_country': [

		]
	},
	'GROUP_PERMISSIONS': {
		'admin': [
			'testapp.view_country'
		]
	},
	'GROUP_CONTAINS': {
		'admin': []
	}
})

setup()

# Do the dance to ensure the models are synched to the DB.
# This saves us from having to include migrations
from django.core.management.commands.migrate import Command as MigrationCommand # noqa
from django.db import connection, connections # noqa
from django.db.migrations.executor import MigrationExecutor # noqa

# This is oh so hacky....
cmd = MigrationCommand()
cmd.verbosity = 0
connection = connections['default']
executor = MigrationExecutor(connection)
cmd.sync_apps(connection, executor.loader.unmigrated_apps)

# Hack to make the view_country permission, which doesn't work with the MigrationCommand somehow
from django.contrib.auth.models import Group, Permission, ContentType
content_type = ContentType.objects.get_or_create(app_label='testapp', model='country')[0]
Permission.objects.get_or_create(content_type=content_type, codename='view_country')
call_command('define_groups')


# Create postgres extensions
if db_settings['ENGINE'] == 'django.db.backends.postgresql':
	with connection.cursor() as cursor:
		cursor.execute('CREATE EXTENSION IF NOT EXISTS unaccent;')
