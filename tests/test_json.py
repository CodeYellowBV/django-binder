import json as python_core_json

from datetime import datetime
from django.test import TestCase

import binder.json as binder_json

class JsonTest(TestCase):
	def test_json_dates_dump_and_load_correctly(self):
		encoded = {
			# Include a few non-datetime objects to check
			# we defer to standard json encoding for them.
			'arr': ['matey'],
			'nest': {
				'num': 1234,
				'some_date': datetime.strptime('2016-01-01 12:00:00.123456+0000', '%Y-%m-%d %H:%M:%S.%f%z'),
			},
			'the_date': datetime.strptime('2016-06-21 01:02:03+0000', '%Y-%m-%d %H:%M:%S%z'),
			'timezoned_date': datetime.strptime('2016-10-04 11:28:20+0200', '%Y-%m-%d %H:%M:%S%z'),
		}

		# We can't check directly against the serialized
		# string because dicts have no ordering, and space
		# usage might differ.  So instead, we load with the
		# core JSON parser and compare the raw string values.
		plain = {
			'arr': ['matey'],
			'nest': {
				'num': 1234,
				'some_date': '2016-01-01T12:00:00.123456+0000',
			},
			'the_date': '2016-06-21T01:02:03.000000+0000',
			'timezoned_date': '2016-10-04T11:28:20.000000+0200',
		}

		# Dumping to json
		self.assertEqual(plain, python_core_json.loads(binder_json.jsondumps(encoded)))

		# Loading from json, currently just defers to plain
		# JSON (after decoding).
		self.assertEqual(plain, binder_json.jsonloads(bytes(python_core_json.dumps(plain), 'utf-8')))


	# This assumes missing timezone is UTC
	def test_nontimezoned_json_dates_dump_correctly(self):
		t = datetime.strptime('2016-01-01 01:02:03', '%Y-%m-%d %H:%M:%S')
		self.assertEqual('["2016-01-01T01:02:03.000000+0000"]', binder_json.jsondumps([t]))
