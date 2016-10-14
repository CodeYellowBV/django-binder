from django.db import connection


from django.test import TestCase, Client

from datetime import datetime, timedelta
import json
from binder.json import jsonloads
from binder.history import Change, Changeset
from django.contrib.auth.models import User

from .testapp.models import Animal, Zoo

class HistoryTest(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

	# Zoo has no history, Animal does
	def test_model_without_history_does_not_create_changes_on_creation(self):
		model_data = {
			'name': 'Artis',
		}
		response = self.client.post('/zoo/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)

		self.assertEqual(0, Changeset.objects.count())
		self.assertEqual(0, Change.objects.count())


	def test_model_with_history_creates_changes_on_creation(self):
		model_data = {
			'name': 'Daffy Duck',
		}
		response = self.client.post('/animal/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)

		self.assertEqual(1, Changeset.objects.count())
		cs = Changeset.objects.get()
		self.assertEqual('testuser', cs.user.username)
		self.assertAlmostEqual(datetime.now(), cs.date, delta=timedelta(seconds=1))

		self.assertEqual(3, Change.objects.count())
		self.assertEqual(1, Change.objects.filter(model='Animal', field='name', before='null', after='"Daffy Duck"').count())
		self.assertEqual(1, Change.objects.filter(model='Animal', field='zoo', before='null', after='null').count())
		self.assertEqual(1, Change.objects.filter(model='Animal', field='id', before='null', after=Animal.objects.get().id).count())


	def test_model_with_history_creates_changes_on_update_but_only_for_changed_fields(self):
		artis = Zoo(name='Artis')
		artis.full_clean()
		artis.save()
		daffy = Animal(name='Daffy Duck', zoo=artis)
		daffy.full_clean()
		daffy.save()

		# Model changes outside the HTTP API aren't recorded (should they be?)
		self.assertEqual(0, Changeset.objects.count())
		self.assertEqual(0, Change.objects.count())

		model_data = {
			'name': 'Daffy THE Duck',
		}
		response = self.client.patch('/animal/%d/' % (daffy.pk,), data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)

		self.assertEqual(1, Changeset.objects.count())
		cs = Changeset.objects.get()
		self.assertEqual('testuser', cs.user.username)
		self.assertAlmostEqual(datetime.now(), cs.date, delta=timedelta(seconds=1))

		self.assertEqual(1, Change.objects.count())
		self.assertEqual(1, Change.objects.filter(model='Animal', field='name', before='"Daffy Duck"', after='"Daffy THE Duck"').count())
