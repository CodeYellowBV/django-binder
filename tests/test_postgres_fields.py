import os

import unittest

from django.test import TestCase, Client

from binder.json import jsonloads
from django.contrib.auth.models import User
from datetime import datetime, date, timedelta
from django.core.exceptions import ValidationError
from .testapp.models import TimeTable

from psycopg2.extras import DateTimeTZRange

if os.environ.get('BINDER_TEST_MYSQL', '0') == '0':
	from .testapp.models import FeedingSchedule, Animal, Zoo

# TODO: Currently these only really test filtering.  Move to test/filters?
@unittest.skipIf(
	os.environ.get('BINDER_TEST_MYSQL', '0') != '0',
	"Only available with PostgreSQL"
)
class PostgresFieldsTest(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

		gaia = Zoo(name='GaiaZOO')
		gaia.save()

		coyote = Animal(name='Wile E. Coyote', zoo=gaia)
		coyote.save()

		roadrunner = Animal(name='Roadrunner', zoo=gaia)
		roadrunner.save()

		self.coyote_feeding = FeedingSchedule(animal=coyote, foods=['meat'], schedule_details={'10:30': ['meat'], '16:00': ['meat']})
		self.coyote_feeding.save()

		self.rr_feeding = FeedingSchedule(animal=roadrunner, foods=['corn', 'bugs'], schedule_details={'10:30': ['corn'], '16:00': ['corn', 'bugs']})
		self.rr_feeding.save()


	def test_get_collection_arrayfield_exact_filtering(self):
		response = self.client.get('/feeding_schedule/', data={'.foods': 'corn,bugs'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual(self.rr_feeding.id, result['data'][0]['id'])


		response = self.client.get('/feeding_schedule/', data={'.foods': 'corn'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))


		response = self.client.get('/feeding_schedule/', data={'.foods': 'corn,bugs,meat'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))


		response = self.client.get('/feeding_schedule/', data={'.foods': 'meat'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual(self.coyote_feeding.id, result['data'][0]['id'])


	def test_get_collection_jsonfield_exact_filtering(self):
		response = self.client.get('/feeding_schedule/', data={'.schedule_details': '{"10:30": ["meat"], "16:00": ["meat"]}'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual(self.coyote_feeding.id, result['data'][0]['id'])

		response = self.client.get('/feeding_schedule/', data={'.schedule_details': '{"10:30": ["meat"]}'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))


		response = self.client.get('/feeding_schedule/', data={'.schedule_details': '{"10:30": ["corn"], "16:00": ["corn", "bugs"]}'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual(self.rr_feeding.id, result['data'][0]['id'])


		response = self.client.get('/feeding_schedule/', data={'.schedule_details': '{}'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))


	def test_get_collection_arrayfield_overlap_filtering(self):
		response = self.client.get('/feeding_schedule/', data={'.foods:overlap': 'corn'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual(self.rr_feeding.id, result['data'][0]['id'])

		response = self.client.get('/feeding_schedule/', data={'.foods:overlap': 'corn,meat'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(2, len(result['data']))


		response = self.client.get('/feeding_schedule/', data={'.foods:overlap': 'corn,bricks'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual(self.rr_feeding.id, result['data'][0]['id'])


		response = self.client.get('/feeding_schedule/', data={'.foods:overlap': ''})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))


	def test_get_collection_arrayfield_contains_filtering(self):
		response = self.client.get('/feeding_schedule/', data={'.foods:contains': 'corn,bugs'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual(self.rr_feeding.id, result['data'][0]['id'])

		response = self.client.get('/feeding_schedule/', data={'.foods:contains': 'corn,meat'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))


		response = self.client.get('/feeding_schedule/', data={'.foods:contains': 'corn'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual(self.rr_feeding.id, result['data'][0]['id'])


		response = self.client.get('/feeding_schedule/', data={'.foods:contains': ''})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(2, len(result['data']))


	def test_get_collection_jsonfield_contains_filtering(self):
		response = self.client.get('/feeding_schedule/', data={'.schedule_details:contains': '{"10:30": ["meat"]}'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual(self.coyote_feeding.id, result['data'][0]['id'])

		# Embedded commas should not produce issues
		response = self.client.get('/feeding_schedule/', data={'.schedule_details:contains': '{"10:30": ["corn"], "16:00": ["corn", "bugs"]}'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual(self.rr_feeding.id, result['data'][0]['id'])


		response = self.client.get('/feeding_schedule/', data={'.schedule_details:contains': '{"10:30": ["meat"], "16:00": ["corn", "bugs"]}'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))


		response = self.client.get('/feeding_schedule/', data={'.schedule_details:contains': '{}'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(2, len(result['data']))


	def test_get_collection_jsonfield_invalid_json_filtering_fails(self):
		response = self.client.get('/feeding_schedule/', data={'.schedule_details:contains': '{'})
		self.assertEqual(response.status_code, 418)

		result = jsonloads(response.content)
		self.assertEqual('RequestError', result['code'])


		response = self.client.get('/feeding_schedule/', data={'.schedule_details:contained_by': '{'})
		self.assertEqual(response.status_code, 418)

		result = jsonloads(response.content)
		self.assertEqual('RequestError', result['code'])


	def test_get_collection_arrayfield_contained_by_filtering(self):
		response = self.client.get('/feeding_schedule/', data={'.foods:contained_by': 'corn,bugs'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual(self.rr_feeding.id, result['data'][0]['id'])

		response = self.client.get('/feeding_schedule/', data={'.foods:contained_by': 'corn,meat'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual(self.coyote_feeding.id, result['data'][0]['id'])


		response = self.client.get('/feeding_schedule/', data={'.foods:contained_by': 'corn'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))


		response = self.client.get('/feeding_schedule/', data={'.foods:contained_by': ''})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))

		response = self.client.get('/feeding_schedule/', data={'.foods:contained_by': 'corn,meat,bugs,whatever'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(2, len(result['data']))


	def test_get_collection_jsonfield_contained_by_filtering(self):
		response = self.client.get('/feeding_schedule/', data={'.schedule_details:contained_by': '{"10:30": ["meat"]}'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))

		# Embedded commas should not produce issues
		response = self.client.get('/feeding_schedule/', data={'.schedule_details:contained_by': '{"10:30": ["corn"], "16:00": ["corn", "bugs"]}'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual(self.rr_feeding.id, result['data'][0]['id'])


		response = self.client.get('/feeding_schedule/', data={'.schedule_details:contained_by': '{"10:30": ["meat"], "16:00": ["corn", "bugs"]}'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))


		response = self.client.get('/feeding_schedule/', data={'.schedule_details:contained_by': '{}'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))

		response = self.client.get('/feeding_schedule/', data={'.schedule_details:contained_by': '{"10:29": ["meat"], "10:30": ["corn"], "16:00": ["corn", "bugs"]}'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual(self.rr_feeding.id, result['data'][0]['id'])

		# This is a bit odd; first array is contained by the
		# supplied array; in other words, we match recursively.
		response = self.client.get('/feeding_schedule/', data={'.schedule_details:contained_by': '{"10:30": ["corn", "meat"], "16:00": ["corn", "bugs"]}'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual(self.rr_feeding.id, result['data'][0]['id'])


	def test_get_collection_jsonfield_has_key(self):
		response = self.client.get('/feeding_schedule/', data={'.schedule_details:has_key': '10:30'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(2, len(result['data']))

		# Embedded commas should not be parsed (see has_[any_]keys instead)
		response = self.client.get('/feeding_schedule/', data={'.schedule_details:has_key': '10:30,16:00'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))


		response = self.client.get('/feeding_schedule/', data={'.schedule_details:has_key': '15:00'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))


		response = self.client.get('/feeding_schedule/', data={'.schedule_details:has_key': ''})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))


	def test_get_collection_jsonfield_has_keys(self):
		response = self.client.get('/feeding_schedule/', data={'.schedule_details:has_keys': '10:30'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(2, len(result['data']))

		# Embedded commas should be parsed
		response = self.client.get('/feeding_schedule/', data={'.schedule_details:has_keys': '10:30,16:00'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(2, len(result['data']))


		response = self.client.get('/feeding_schedule/', data={'.schedule_details:has_keys': '15:00'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))

		response = self.client.get('/feeding_schedule/', data={'.schedule_details:has_keys': '10:30,15:00,16:00'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))

		response = self.client.get('/feeding_schedule/', data={'.schedule_details:has_keys': ''})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(2, len(result['data']))


	def test_get_collection_jsonfield_has_any_keys(self):
		response = self.client.get('/feeding_schedule/', data={'.schedule_details:has_any_keys': '10:30'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(2, len(result['data']))

		# Embedded commas should be parsed
		response = self.client.get('/feeding_schedule/', data={'.schedule_details:has_any_keys': '10:30,16:00'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(2, len(result['data']))


		response = self.client.get('/feeding_schedule/', data={'.schedule_details:has_any_keys': '15:00'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))

		response = self.client.get('/feeding_schedule/', data={'.schedule_details:has_any_keys': '10:30,15:00,16:00'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(2, len(result['data']))

		response = self.client.get('/feeding_schedule/', data={'.schedule_details:has_any_keys': ''})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))


@unittest.skipIf(
	os.environ.get('BINDER_TEST_MYSQL', '0') != '0',
	"Only available with PostgreSQL"
)
class TestDateTimeRangeField(TestCase):
	def test_value_None(self):
		# This should be valid (if not set to non-nullable)
		test_model = TimeTable(daterange=None)
		test_model.save()

		self.assertIsNone(test_model.daterange)


	def test_value_DateTimeRangeTZ_empty(self):
		# empty is equivalent to None
		test_model = TimeTable(daterange=DateTimeTZRange())
		test_model.save()

		self.assertIsNone(test_model.daterange.lower)
		self.assertIsNone(test_model.daterange.upper)


	def test_value_DateTimeRangeTZ_None(self):
		# None is a valid value for the bounds
		test_model = TimeTable(daterange=DateTimeTZRange(None, None))
		test_model.save()

		self.assertIsNone(test_model.daterange.lower)
		self.assertIsNone(test_model.daterange.upper)


	def test_value_DateTimeRangeTZ_datetime(self):
		tmrw = date.today() + timedelta(days=1)
		lower = datetime(tmrw.year, tmrw.month, tmrw.day, 8, 30)
		upper = datetime(tmrw.year, tmrw.month, tmrw.day, 17, 30)

		test_model = TimeTable(daterange=DateTimeTZRange(lower, upper))
		test_model.save()


	def test_value_DateTimeRangeTZ_date(self):
		today = date.today()
		lower = today + timedelta(days=1)
		upper = today + timedelta(days=2)

		test_model = TimeTable(daterange=DateTimeTZRange(lower, upper))
		test_model.save()

		# range_type.to_python should cast dates to datetimes + making them
		# tz aware!
		self.assertTrue(isinstance(test_model.daterange.lower, datetime))
		self.assertTrue(isinstance(test_model.daterange.upper, datetime))


	def test_value_DateTimeRangeTZ_valid_string(self):
		tmrw = date.today() + timedelta(days=1)
		lower = datetime(tmrw.year, tmrw.month, tmrw.day, 8, 30)
		upper = datetime(tmrw.year, tmrw.month, tmrw.day, 17, 30)

		lower_parsed = lower.strftime('%Y-%m-%dT%H:%M:%S.%f%z')
		upper_parsed = upper.strftime('%Y-%m-%dT%H:%M:%S.%f%z')

		test_model = TimeTable(daterange=DateTimeTZRange(lower_parsed, upper_parsed))
		test_model.save()


	def test_value_DateTimeRangeTZ_invalid_string(self):
		tmrw = date.today() + timedelta(days=1)
		lower = datetime(tmrw.year, tmrw.month, tmrw.day, 8, 30)
		upper = "]&!" # invalid but json parsable

		with self.assertRaises(ValidationError) as ve:
			test_model = TimeTable(daterange=DateTimeTZRange(lower, upper))
			test_model.save()

		self.assertSetEqual(set(['daterange']), set(ve.exception.error_dict.keys()))
		errors = ve.exception.message_dict['daterange']
		self.assertEqual(1, len(errors))
		self.assertEqual('“%s” value has an invalid format. It must be in YYYY-MM-DD HH:MM[:ss[.uuuuuu]][TZ] format.' % upper, str(errors[0]))


	# This case should not happen (http payloads are always interpreted as strings)
	def test_value_DateTimeRangeTZ_invalid_non_json_parsable(self):
		tmrw = date.today() + timedelta(days=1)
		lower = datetime(tmrw.year, tmrw.month, tmrw.day, 8, 30)
		upper = 1 # not json parsable

		with self.assertRaises(TypeError) as te:
			test_model = TimeTable(daterange=DateTimeTZRange(lower, upper))
			test_model.save()

		self.assertEqual("expected string or bytes-like object", str(te.exception))


	def test_value_tuple_empty(self):
		# empty is equivalent to None
		test_model = TimeTable(daterange=())
		test_model.save()

		self.assertIsNone(test_model.daterange.lower)
		self.assertIsNone(test_model.daterange.upper)


	def test_value_tuple_None(self):
		test_model = TimeTable(daterange=(None, None))
		test_model.save()

		self.assertIsNone(test_model.daterange.lower)
		self.assertIsNone(test_model.daterange.upper)


	def test_value_tuple_datetime(self):
		tmrw = date.today() + timedelta(days=1)
		lower = datetime(tmrw.year, tmrw.month, tmrw.day, 8, 30)
		upper = datetime(tmrw.year, tmrw.month, tmrw.day, 17, 30)

		test_model = TimeTable(daterange=(lower, upper))
		test_model.save()


	def test_value_tuple_date(self):
		today = date.today()
		lower = today + timedelta(days=1)
		upper = today + timedelta(days=2)

		test_model = TimeTable(daterange=(lower, upper))
		test_model.save()

		# range_type.to_python should cast dates to datetimes + making them
		# tz aware!
		self.assertTrue(isinstance(test_model.daterange.lower, datetime))
		self.assertTrue(isinstance(test_model.daterange.upper, datetime))


	def test_value_tuple_valid_string(self):
		tmrw = date.today() + timedelta(days=1)
		lower = datetime(tmrw.year, tmrw.month, tmrw.day, 8, 30)
		upper = datetime(tmrw.year, tmrw.month, tmrw.day, 17, 30)

		lower_parsed = lower.strftime('%Y-%m-%dT%H:%M:%S.%f%z')
		upper_parsed = upper.strftime('%Y-%m-%dT%H:%M:%S.%f%z')

		test_model = TimeTable(daterange=(lower_parsed, upper_parsed))
		test_model.save()


	def test_value_tuple_invalid_string(self):
		tmrw = date.today() + timedelta(days=1)
		lower = datetime(tmrw.year, tmrw.month, tmrw.day, 8, 30)
		upper = "]&!" # invalid but json parsable

		with self.assertRaises(ValidationError) as ve:
			test_model = TimeTable(daterange=(lower, upper))
			test_model.save()

		self.assertSetEqual(set(['daterange']), set(ve.exception.error_dict.keys()))
		errors = ve.exception.message_dict['daterange']
		self.assertEqual(1, len(errors))
		self.assertEqual('“%s” value has an invalid format. It must be in YYYY-MM-DD HH:MM[:ss[.uuuuuu]][TZ] format.' % upper, str(errors[0]))


	# This case should not happen (http payloads are always interpreted as strings)
	def test_value_tuple_invalid_non_json_parsable(self):
		tmrw = date.today() + timedelta(days=1)
		lower = datetime(tmrw.year, tmrw.month, tmrw.day, 8, 30)
		upper = 1 # not json parsable

		with self.assertRaises(TypeError) as te:
			test_model = TimeTable(daterange=(lower, upper))
			test_model.save()

		self.assertEqual("expected string or bytes-like object", str(te.exception))


	def test_value_array_empty(self):
		# empty is equivalent to None
		test_model = TimeTable(daterange=[])
		test_model.save()

		self.assertIsNone(test_model.daterange.lower)
		self.assertIsNone(test_model.daterange.upper)


	def test_value_array_None(self):
		test_model = TimeTable(daterange=[None, None])
		test_model.save()

		self.assertIsNone(test_model.daterange.lower)
		self.assertIsNone(test_model.daterange.upper)


	def test_value_array_datetime(self):
		tmrw = date.today() + timedelta(days=1)
		lower = datetime(tmrw.year, tmrw.month, tmrw.day, 8, 30)
		upper = datetime(tmrw.year, tmrw.month, tmrw.day, 17, 30)

		test_model = TimeTable(daterange=[lower, upper])
		test_model.save()


	def test_value_array_date(self):
		today = date.today()
		lower = today + timedelta(days=1)
		upper = today + timedelta(days=2)

		test_model = TimeTable(daterange=[lower, upper])
		test_model.save()

		# range_type.to_python should cast dates to datetimes + making them
		# tz aware!
		self.assertTrue(isinstance(test_model.daterange.lower, datetime))
		self.assertTrue(isinstance(test_model.daterange.upper, datetime))


	def test_value_array_valid_string(self):
		tmrw = date.today() + timedelta(days=1)
		lower = datetime(tmrw.year, tmrw.month, tmrw.day, 8, 30)
		upper = datetime(tmrw.year, tmrw.month, tmrw.day, 17, 30)

		lower_parsed = lower.strftime('%Y-%m-%dT%H:%M:%S.%f%z')
		upper_parsed = upper.strftime('%Y-%m-%dT%H:%M:%S.%f%z')

		test_model = TimeTable(daterange=[lower_parsed, upper_parsed])
		test_model.save()


	def test_value_array_invalid_string(self):
		tmrw = date.today() + timedelta(days=1)
		lower = datetime(tmrw.year, tmrw.month, tmrw.day, 8, 30)
		upper = "]&!" # invalid but json parsable

		with self.assertRaises(ValidationError) as ve:
			test_model = TimeTable(daterange=[lower, upper])
			test_model.save()

		self.assertSetEqual(set(['daterange']), set(ve.exception.error_dict.keys()))
		errors = ve.exception.message_dict['daterange']
		self.assertEqual(1, len(errors))
		self.assertEqual('“%s” value has an invalid format. It must be in YYYY-MM-DD HH:MM[:ss[.uuuuuu]][TZ] format.' % upper, str(errors[0]))


	# This case should not happen (http payloads are always interpreted as strings)
	def test_value_array_invalid_non_json_parsable(self):
		tmrw = date.today() + timedelta(days=1)
		lower = datetime(tmrw.year, tmrw.month, tmrw.day, 8, 30)
		upper = 1 # not json parsable

		with self.assertRaises(TypeError) as te:
			test_model = TimeTable(daterange=[lower, upper])
			test_model.save()

		self.assertEqual("expected string or bytes-like object", str(te.exception))


	def test_value_stringified_array(self):
		tmrw = date.today() + timedelta(days=1)
		lower = datetime(tmrw.year, tmrw.month, tmrw.day, 8, 30)
		upper = datetime(tmrw.year, tmrw.month, tmrw.day, 17, 30)

		lower_parsed = lower.strftime('%Y-%m-%dT%H:%M:%S.%f%z')
		upper_parsed = upper.strftime('%Y-%m-%dT%H:%M:%S.%f%z')

		# just test through some valid possibilities
		for daterange in ['[]', '["{}", "{}"]'.format(lower_parsed, upper_parsed)]:
			test_model = TimeTable(daterange=daterange)
			test_model.save()

		test_model = TimeTable(daterange='["2000-01-01", "2000-01-02"]')
		test_model.save()

		# range_type.to_python should cast dates to datetimes + making them
		# tz aware!
		self.assertTrue(isinstance(test_model.daterange.lower, datetime))
		self.assertTrue(isinstance(test_model.daterange.upper, datetime))

		with self.assertRaises(TypeError):
			test_model = TimeTable(daterange='[1, ""]')
			test_model.save()

		with self.assertRaises(ValidationError):
			test_model = TimeTable(daterange='["", ""]')
			test_model.save()


	def test_value_stringified_dict(self):
		tmrw = date.today() + timedelta(days=1)
		lower = datetime(tmrw.year, tmrw.month, tmrw.day, 8, 30)
		upper = datetime(tmrw.year, tmrw.month, tmrw.day, 17, 30)

		lower_parsed = lower.strftime('%Y-%m-%dT%H:%M:%S.%f%z')
		upper_parsed = upper.strftime('%Y-%m-%dT%H:%M:%S.%f%z')

		test_model = TimeTable(daterange='{}')
		test_model.save()
		self.assertIsNone(test_model.daterange.lower)
		self.assertIsNone(test_model.daterange.upper)

		test_model = TimeTable(daterange='{ "lower": "%s", "upper": "%s" }' % (lower_parsed, upper_parsed))
		test_model.save()
		self.assertTrue(isinstance(test_model.daterange.lower, datetime))
		self.assertTrue(isinstance(test_model.daterange.upper, datetime))

		test_model = TimeTable(daterange='{ "lower": "2000-01-01", "upper": "2000-01-02"}')
		test_model.save()

		# range_type.to_python should cast dates to datetimes + making them
		# tz aware!
		self.assertTrue(isinstance(test_model.daterange.lower, datetime))
		self.assertTrue(isinstance(test_model.daterange.upper, datetime))

		with self.assertRaises(TypeError):
			test_model = TimeTable(daterange='[1, ""]')
			test_model.save()

		with self.assertRaises(ValidationError):
			test_model = TimeTable(daterange='["", ""]')
			test_model.save()


	def test_upper_bound_smaller_than_lower_bound(self):
		tmrw = date.today() + timedelta(days=1)
		lower = datetime(tmrw.year, tmrw.month, tmrw.day, 8, 30)
		upper = datetime(tmrw.year, tmrw.month, tmrw.day, 17, 30)

		with self.assertRaises(ValidationError) as ve:
			test_model = TimeTable(daterange=(upper, lower))
			test_model.save()

		self.assertSetEqual(set(['daterange']), set(ve.exception.error_dict.keys()))
		errors = ve.exception.message_dict['daterange']
		self.assertEqual(1, len(errors))
		self.assertEqual("Lower bound must be smaller or equal to upper bound.", str(errors[0]))
