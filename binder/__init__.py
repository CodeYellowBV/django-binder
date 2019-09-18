# flake8: noqa
from .tests_discoverer import load_tests

def check_mysql_timezone_conversion(sender, connection, **kwargs):
	import logging
	import datetime
	logger = logging.getLogger(__name__)

	if connection.vendor.lower() == 'mysql':
		logger.debug('Database "{}" is MySQL; testing for timezone conversion.'.format(connection.alias))

		with connection.cursor() as cursor:
			cursor.execute("SELECT CONVERT_TZ('2019-09-18T14:23:45', 'UTC', 'Europe/Amsterdam');")
			result = cursor.fetchone()[0]
			if result != datetime.datetime(2019, 9, 18, 16, 23, 45):
				raise AssertionError('MySQL timezone conversion failed for database "{}" (got: {}); Is mysql.time_zone populated? Maybe you need mysql_tzinfo_to_sql.'.format(connection.alias, repr(result)))
	else:
		logger.debug('Database "{}" is {}, not testing timezone conversion.'.format(connection.alias, connection.vendor))

import django.db.backends.signals
django.db.backends.signals.connection_created.connect(check_mysql_timezone_conversion)
