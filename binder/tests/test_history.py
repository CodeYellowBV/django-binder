from django.test import TestCase, Client

from datetime import datetime, timedelta, timezone
import json
from binder.history import Change, Changeset
from django.contrib.auth.models import User

from .testapp.models import Animal, Caretaker

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
		self.assertAlmostEqual(datetime.now(tz=timezone.utc), cs.date, delta=timedelta(seconds=1))

		self.assertEqual(5, Change.objects.count())
		self.assertEqual(1, Change.objects.filter(changeset=cs, model='Animal', field='name', before='null', after='"Daffy Duck"').count())
		self.assertEqual(1, Change.objects.filter(changeset=cs, model='Animal', field='id', before='null', after=Animal.objects.get().id).count())
		self.assertEqual(1, Change.objects.filter(changeset=cs, model='Animal', field='caretaker', before='null', after='null').count())
		self.assertEqual(1, Change.objects.filter(changeset=cs, model='Animal', field='zoo', before='null', after='null').count())
		self.assertEqual(1, Change.objects.filter(changeset=cs, model='Animal', field='deleted', before='null', after='false').count())


	def test_model_with_history_creates_changes_on_update_but_only_for_changed_fields(self):
		daffy = Animal(name='Daffy Duck')
		daffy.full_clean()
		daffy.save()

		# Model changes outside the HTTP API aren't recorded (should they be?)
		self.assertEqual(0, Changeset.objects.count())
		self.assertEqual(0, Change.objects.count())

		model_data = {
			'name': 'Daffy Duck',
		}
		response = self.client.patch('/animal/%d/' % (daffy.pk,), data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)

		# No actual change was done
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
		self.assertAlmostEqual(datetime.now(tz=timezone.utc), cs.date, delta=timedelta(seconds=1))

		self.assertEqual(1, Change.objects.count())
		self.assertEqual(1, Change.objects.filter(changeset=cs, model='Animal', field='name', before='"Daffy Duck"', after='"Daffy THE Duck"').count())


	def test_model_with_related_history_model_creates_changes_on_the_same_changeset(self):
		mickey = Caretaker(name='Mickey', ssn='mouse_1234')
		mickey.full_clean()
		mickey.save()
		pluto = Animal(name='Pluto')
		pluto.full_clean()
		pluto.save()

		# Model changes outside the HTTP API aren't recorded (should they be?)
		self.assertEqual(0, Changeset.objects.count())
		self.assertEqual(0, Change.objects.count())

		model_data = {
			'data': [{
				'id': pluto.id,
				'name': 'Pluto the dog',
			}],
			'with': {
				'caretaker': [{
					'id': mickey.id,
					'name': 'Mickey Mouse',
				}],
			},
		}
		response = self.client.put('/animal/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)

		self.assertEqual(1, Changeset.objects.count())
		cs = Changeset.objects.get()
		self.assertEqual('testuser', cs.user.username)
		self.assertAlmostEqual(datetime.now(tz=timezone.utc), cs.date, delta=timedelta(seconds=1))

		self.assertEqual(2, Change.objects.count())
		self.assertEqual(1, Change.objects.filter(changeset=cs, model='Animal', field='name', before='"Pluto"', after='"Pluto the dog"').count())
		self.assertEqual(1, Change.objects.filter(changeset=cs, model='Caretaker', field='name', before='"Mickey"', after='"Mickey Mouse"').count())
