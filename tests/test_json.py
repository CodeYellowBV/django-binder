import json as python_core_json

from datetime import datetime, date, timezone
from uuid import UUID
from decimal import Decimal
from django.test import TestCase

import binder.json as binder_json

class JsonTest(TestCase):
	def test_json_datetimes_dump_and_load_correctly(self):
		encoded = {
			# Include a few non-datetime objects to check
			# we defer to standard json encoding for them.
			'arr': ['matey'],
			'nest': {
				'num': 1234,
				'some_datetime': datetime.strptime('2016-01-01 12:00:00.123456+0000', '%Y-%m-%d %H:%M:%S.%f%z'),
			},
			'the_datetime': datetime.strptime('2016-06-21 01:02:03+0000', '%Y-%m-%d %H:%M:%S%z'),
			'timezoned_datetime': datetime.strptime('2016-10-04 11:28:20+0200', '%Y-%m-%d %H:%M:%S%z'),
			'plain_date': date(1998, 2, 3),
		}

		# We can't check directly against the serialized
		# string because dicts have no ordering, and space
		# usage might differ.  So instead, we load with the
		# core JSON parser and compare the raw string values.
		plain = {
			'arr': ['matey'],
			'nest': {
				'num': 1234,
				'some_datetime': '2016-01-01T12:00:00.123456+0000',
			},
			'the_datetime': '2016-06-21T01:02:03.000000+0000',
			'timezoned_datetime': '2016-10-04T11:28:20.000000+0200',
			'plain_date': '1998-02-03',
		}

		# Dumping to json
		self.assertEqual(plain, python_core_json.loads(binder_json.jsondumps(encoded)))

		# Loading from json, currently just defers to plain
		# JSON (after decoding).
		self.assertEqual(plain, binder_json.jsonloads(bytes(python_core_json.dumps(plain), 'utf-8')))


	def test_json_datetimes_dump_correctly_notz_nous(self):
		t = datetime(2016, 1, 1, 1, 2, 3)
		self.assertEqual('["2016-01-01T01:02:03.000000"]', binder_json.jsondumps([t]))


	def test_json_datetimes_dump_correctly_notz_us(self):
		t = datetime(2016, 1, 1, 1, 2, 3, 313337)
		self.assertEqual('["2016-01-01T01:02:03.313337"]', binder_json.jsondumps([t]))


	def test_json_datetimes_dump_correctly_tz_nous(self):
		t = datetime(2016, 1, 1, 1, 2, 3, tzinfo=timezone.utc)
		self.assertEqual('["2016-01-01T01:02:03.000000+0000"]', binder_json.jsondumps([t]))


	def test_json_datetimes_dump_correctly_tz_us(self):
		t = datetime(2016, 1, 1, 1, 2, 3, 313337, tzinfo=timezone.utc)
		self.assertEqual('["2016-01-01T01:02:03.313337+0000"]', binder_json.jsondumps([t]))


	def test_uuids_dump_correctly(self):
		u = UUID('{12345678-1234-5678-1234-567812345678}')
		self.assertEqual('["12345678-1234-5678-1234-567812345678"]', binder_json.jsondumps([u]))

	def test_decimals_dump_correctly(self):
		u = Decimal('1.1')
		self.assertEqual('["1.1"]', binder_json.jsondumps([u]))
