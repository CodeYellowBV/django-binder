# Django-Binder

[![Build Status](https://travis-ci.org/CodeYellowBV/django-binder.svg?branch=master)](https://travis-ci.org/CodeYellowBV/django-binder)
[![codecov](https://codecov.io/gh/CodeYellowBV/django-binder/branch/master/graph/badge.svg)](https://codecov.io/gh/CodeYellowBV/django-binder)

Code Yellow backend framework for SPA webapps with REST-like API.

**This framework is a work-in-progress. There is no complete documentation yet. We are using it for a couple of projects and fine-tuning it.**

## Running the tests

Run with docker `docker compose run binder ./setup.py test` (but you may need to run `docker compose build db binder` first)
- Access the test database directly by with `docker compose run db psql -h db -U postgres`.
- It may be possible to recreate the test database (for example when you added/changed models). One way of achieving this is to just remove all the docker images that were build `docker compose rm`. The database will be created during the setup in `tests/__init__.py`.

The tests are set up in such a way that there is no need to keep migration files. The setup procedure in `tests/__init__.py` handles the preparation of the database by directly calling some build-in Django commands.

To only run a selection of the tests, use the `-s` flag like `./setup.py test -s tests.test_some_specific_test`.

## MySQL support

MySQL is supported, but only with the goal to replace it with
PostgreSQL.  This means it has a few limitations:

- `where` filtering on `with` relations is not supported.
- Only integer primary keys are supported.
- When fetching large number of records using `with` or the ids are big, be sure to increase `GROUP_CONCAT` max string length by:

```
DATABASES = {
	'default': {
		'OPTIONS': {
            'init_command': 'SET SESSION group_concat_max_len = 1000000',
        },
	},
}
```
