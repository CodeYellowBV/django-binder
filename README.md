# Django-Binder

[![Build Status](https://travis-ci.org/CodeYellowBV/django-binder.svg?branch=master)](https://travis-ci.org/CodeYellowBV/django-binder)
[![codecov](https://codecov.io/gh/CodeYellowBV/django-binder/branch/master/graph/badge.svg)](https://codecov.io/gh/CodeYellowBV/django-binder)

Code Yellow backend framework for SPA webapps with REST-like API.

**This framework is a work-in-progress. There is no complete documentation yet. We are using it for a couple of projects and fine-tuning it.**

## Running the tests

- Run with `./test`
- Access the test database directly by with `docker compose run --rm db psql -h db -U postgres`.

The tests are set up in such a way that there is no need to keep migration files. The setup procedure in `tests/__init__.py` handles the preparation of the database by directly calling some build-in Django commands.

To only run a selection of the tests, use the `-k` flag like `./test -k tests.test_some_specific_test`.

## Refreshing the test database
After changing models, you may need to forcibly 'refresh' the test database. Use:
- `docker compose stop binder db`
- `docker compose rm -f binder db`

After running these commands, the next `./test` may or may not fail with:
```
django.db.utils.OperationalError: connection to server at "db" (172.20.0.2), port 5432 failed: Connection refused
	Is the server running on that host and accepting TCP/IP connections?
```

If it fails, just retry it.

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
