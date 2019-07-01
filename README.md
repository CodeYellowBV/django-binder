# Django-Binder

[![Build Status](https://travis-ci.org/CodeYellowBV/django-binder.svg?branch=master)](https://travis-ci.org/CodeYellowBV/django-binder)
[![codecov](https://codecov.io/gh/CodeYellowBV/django-binder/branch/master/graph/badge.svg)](https://codecov.io/gh/CodeYellowBV/django-binder)

Code Yellow backend framework for SPA webapps with REST-like API.

**This framework is a work-in-progress. There is no complete documentation yet. We are using it for a couple of projects and fine-tuning it.**

## Running the tests

There are two ways to run the tests:
- Run directly `./setup.py test` (requires you to have python3 and postgres installed)
- Run with docker `docker-compose run binder ./setup.py test`

## MySQL support

MySQL is supported, but only with the goal to replace it with
PostgreSQL.  This means it has a few limitations:

- `where` filtering on `with` relations is not supported.
- Only integer primary keys are supported.
