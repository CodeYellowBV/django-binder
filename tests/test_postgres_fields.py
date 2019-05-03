import os

import unittest

from django.test import TestCase, Client

from binder.json import jsonloads
from django.contrib.auth.models import User

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
		coyote.full_clean()
		coyote.save()

		roadrunner = Animal(name='Roadrunner', zoo=gaia)
		roadrunner.full_clean()
		roadrunner.save()

		self.coyote_feeding = FeedingSchedule(animal=coyote, foods=['meat'], schedule_details={'10:30': ['meat'], '16:00': ['meat']})
		self.coyote_feeding.full_clean()
		self.coyote_feeding.save()

		self.rr_feeding = FeedingSchedule(animal=roadrunner, foods=['corn', 'bugs'], schedule_details={'10:30': ['corn'], '16:00': ['corn', 'bugs']})
		self.rr_feeding.full_clean()
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
