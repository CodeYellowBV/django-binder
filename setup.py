#! /usr/bin/env python3

import os
from setuptools import find_packages, setup

with open(os.path.join(os.path.dirname(__file__), 'README.md')) as readme:
	README = readme.read()

# allow setup.py to be run from any path
os.chdir(os.path.normpath(os.path.join(os.path.abspath(__file__), os.pardir)))

test_require_database_engine = {
	'mysql': ['mysqlclient >= 1.3.12', 'psycopg2 >= 2.7'],
	'mssql': ['django-pyodbc-azure >= 2.1.0.0', 'django-pyodbc >= 1.1.3', 'django-hijack == 2.1.10', 'psycopg2 >= 2.7'],
	# Alternative mssql setup with django 3 setup. For later
	# 'mssql': ['mssql-django==1.0rc1', 'psycopg2 >= 2.7']
}.get(os.environ.get('BINDER_TEST_DATABASE_ENGINE'),  ['psycopg2 >= 2.7'])


setup(
	name='django-binder',
	version='1.5.0',
	package_dir={'binder': 'binder'},
	packages=find_packages(),
	include_package_data=True,
	license='MIT License',
	description='Code Yellow backend framework for SPA webapps with REST-like API.',
	long_description=README,
	url='https://github.com/CodeYellowBV/django-binder',
	author='Marcel Moreaux',
	author_email='marcel@codeyellow.nl',
	test_suite='tests',
	classifiers=[
		'Environment :: Web Environment',
		'Framework :: Django',
		'Framework :: Django :: 2.0',
		'Intended Audience :: Developers',
		'License :: OSI Approved :: MIT License',
		'Operating System :: OS Independent',
		'Programming Language :: Python',
		'Programming Language :: Python :: 3',
		'Programming Language :: Python :: 3.4',
		'Programming Language :: Python :: 3.5',
		'Topic :: Internet :: WWW/HTTP',
		'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
	],
	install_requires=[
		'Django >= 2.0, < 4.0',
		'Pillow >= 3.2.0',
		'django-request-id >= 1.0.0',
		'requests >= 2.13.0',
	],
	tests_require=[
		'django-hijack >= 2.1.10',
		*test_require_database_engine,
		"openpyxl >= 3.0.0"
	],
)
