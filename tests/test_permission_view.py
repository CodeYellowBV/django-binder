import os, unittest

from .compare import assert_json, EXTRA

from django.test import TestCase, Client
from django.contrib.auth.models import User

from binder.json import jsonloads

if os.environ.get('BINDER_TEST_MYSQL', '0') == '0':
	from .testapp.models import Animal, FeedingSchedule

@unittest.skipIf(
	os.environ.get('BINDER_TEST_MYSQL', '0') != '0',
	"Only available with PostgreSQL"
)
class TestWithoutPerm(TestCase):
	def setUp(self):
		super().setUp()

		u = User(username='testuser', is_active=True, is_superuser=False)
		u.set_password('test')
		u.save()

		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

		self.animal = Animal(name='Harambe')
		self.animal.save()
		self.feeding_schedule = FeedingSchedule(
			animal=self.animal,
			description='He is in heaven now, no feeding required.'
		)
		self.feeding_schedule.save()

	def test_get_resource(self):
		res = self.client.get('/feeding_schedule/{}/'.format(
			self.feeding_schedule.id
		))
		self.assertEqual(res.status_code, 403)
		response_data = jsonloads(res.content)
		assert_json(response_data, {
			'code': 'Forbidden',
			'required_permission': 'testapp.view_feedingschedule',
			EXTRA(): None,
		})

	def test_get_resource_through_with(self):
		res = self.client.get('/animal/{}/?with=feeding_schedule'.format(
			self.animal.id
		))
		self.assertEqual(res.status_code, 403)
		response_data = jsonloads(res.content)
		assert_json(response_data, {
			'code': 'Forbidden',
			'required_permission': 'testapp.view_feedingschedule',
			EXTRA(): None,
		})


@unittest.skipIf(
	os.environ.get('BINDER_TEST_MYSQL', '0') != '0',
	"Only available with PostgreSQL"
)
class TestWithPermButOutOfScope(TestCase):
	def setUp(self):
		super().setUp()

		u = User(username='testuser2', is_active=True, is_superuser=False)
		u.set_password('test')
		u.save()

		self.client = Client()
		r = self.client.login(username='testuser2', password='test')
		self.assertTrue(r)

		self.animal = Animal(name='Harambe')
		self.animal.save()
		self.feeding_schedule = FeedingSchedule(
			animal=self.animal,
			description='He is in heaven now, no feeding required.'
		)
		self.feeding_schedule.save()

	def test_get_resource(self):
		res = self.client.get('/feeding_schedule/{}/'.format(
			self.feeding_schedule.id
		))
		self.assertEqual(res.status_code, 404)
		response_data = jsonloads(res.content)
		assert_json(response_data, {
			'code': 'NotFound',
			EXTRA(): None,
		})

	def test_get_resource_through_with(self):
		res = self.client.get('/animal/{}/?with=feeding_schedule'.format(
			self.animal.id
		))
		self.assertEqual(res.status_code, 200)
		response_data = jsonloads(res.content)
		assert_json(response_data, {
			'data': {
				'id': self.animal.id,
				EXTRA(): None,
			},
			'with': {
				'feeding_schedule': [],
			},
			'with_mapping': {
				'feeding_schedule': 'feeding_schedule',
			},
			'with_related_name_mapping': {
				'feeding_schedule': 'animal',
			},
			EXTRA(): None,
		})
