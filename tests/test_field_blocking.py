from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils.dateparse import parse_datetime
from binder.json import jsonloads, jsondumps

from .testapp.models import Caretaker

class TestFieldBlocking(TestCase):
	"""
	Check that unwritable_fields and unupdatable_fields work as designed.
	"""

	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)


	def test_writes_to_unwritable_fields_are_blocked_for_new_objects_and_updates(self):
		res = self.client.post('/caretaker/', data=jsondumps({'name': 'Fabby', 'last_seen': '2020-01-01T00:00:00Z'}), content_type='application/json')
		self.assertEqual(res.status_code, 200)

		data = jsonloads(res.content)

		self.assertEqual(['last_seen'], data['_meta']['ignored_fields'])
		self.assertIsNone(data['last_seen'])
		caretaker = Caretaker.objects.get(id=data['id'])
		self.assertIsNone(caretaker.last_seen)
		self.assertEqual('Fabby', caretaker.name)

		res = self.client.put(f'/caretaker/{caretaker.id}/', data=jsondumps({'name': 'Mr Fabby', 'last_seen': '2020-01-01T00:00:00Z'}), content_type='application/json')
		self.assertEqual(res.status_code, 200)

		data = jsonloads(res.content)

		self.assertEqual(['last_seen'], data['_meta']['ignored_fields'])
		self.assertIsNone(data['last_seen'])
		caretaker.refresh_from_db()
		self.assertIsNone(caretaker.last_seen)
		self.assertEqual('Mr Fabby', caretaker.name)

		# Just a paranoid check that we can't overwrite it, even if it has a value
		dt = parse_datetime('2020-07-31T12:34:56Z')
		caretaker.last_seen = dt
		caretaker.save()

		res = self.client.put(f'/caretaker/{caretaker.id}/', data=jsondumps({'name': 'Mrs Fabby', 'last_seen': '2020-01-01T00:00:00Z'}), content_type='application/json')
		self.assertEqual(res.status_code, 200)

		data = jsonloads(res.content)

		self.assertEqual(['last_seen'], data['_meta']['ignored_fields'])
		self.assertEqual(dt, parse_datetime(data['last_seen']))
		caretaker.refresh_from_db()
		self.assertEqual(dt, caretaker.last_seen)
		self.assertEqual('Mrs Fabby', caretaker.name)


		# A put without the field means it's not in ignored_fields
		res = self.client.put(f'/caretaker/{caretaker.id}/', data=jsondumps({'name': 'just Fabby'}), content_type='application/json')
		self.assertEqual(res.status_code, 200)

		data = jsonloads(res.content)

		self.assertEqual([], data['_meta']['ignored_fields'])
		self.assertEqual(dt, parse_datetime(data['last_seen']))
		caretaker.refresh_from_db()
		self.assertEqual(dt, caretaker.last_seen)
		self.assertEqual('just Fabby', caretaker.name)


	def test_writes_to_write_once_fields_are_blocked_for_updates(self):
		res = self.client.post('/caretaker/', data=jsondumps({'name': 'Fabby', 'first_seen': '2020-01-01T00:00:00Z'}), content_type='application/json')
		self.assertEqual(res.status_code, 200)

		data = jsonloads(res.content)

		self.assertEqual([], data['_meta']['ignored_fields'])
		dt = parse_datetime('2020-01-01T00:00:00Z')
		self.assertEqual(dt, parse_datetime(data['first_seen']))
		caretaker = Caretaker.objects.get(id=data['id'])
		self.assertEqual(dt, caretaker.first_seen)
		self.assertEqual('Fabby', caretaker.name)

		res = self.client.put(f'/caretaker/{caretaker.id}/', data=jsondumps({'name': 'Mr Fabby', 'first_seen': '2020-02-01T00:00:00Z'}), content_type='application/json')
		self.assertEqual(res.status_code, 200)

		data = jsonloads(res.content)

		self.assertEqual(['first_seen'], data['_meta']['ignored_fields'])
		self.assertEqual(dt, parse_datetime(data['first_seen']))
		caretaker.refresh_from_db()
		self.assertEqual(dt, caretaker.first_seen)
		self.assertEqual('Mr Fabby', caretaker.name)


		# A put without the field means it's not in ignored_fields
		res = self.client.put(f'/caretaker/{caretaker.id}/', data=jsondumps({'name': 'Mrs Fabby'}), content_type='application/json')
		self.assertEqual(res.status_code, 200)

		data = jsonloads(res.content)

		self.assertEqual([], data['_meta']['ignored_fields'])
		self.assertEqual(dt, parse_datetime(data['first_seen']))
		caretaker.refresh_from_db()
		self.assertEqual(dt, caretaker.first_seen)
		self.assertEqual('Mrs Fabby', caretaker.name)
