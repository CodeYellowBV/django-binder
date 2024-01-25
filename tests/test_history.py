from datetime import datetime, timedelta, timezone
import json

from django.test import TestCase, Client
from django.contrib.auth.models import User

from binder import history
from binder.history import Change, Changeset

from .testapp.models import Animal, Caretaker, Costume, ContactPerson, Zoo


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
		response = self.client.post('/country/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)

		self.assertEqual(0, Changeset.objects.count())
		self.assertEqual(0, Change.objects.count())


	def test_m2m_using_binder_through_history_doesnt_crash(self):

		contact_person = ContactPerson.objects.create(
			name='Burhan'
		)

		contact_person_2 = ContactPerson.objects.create(
			name='Rene'
		)

		model_data = {
			'name': 'Code Yellow',
			'contacts': [contact_person.pk]
		}
		response = self.client.post('/zoo/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)

		_id = json.loads(response.content)['id']

		response = self.client.put(f'/zoo/{_id}/', data=json.dumps({
			"contacts": [contact_person.pk, contact_person_2.pk]
		}), content_type='application/json')
		self.assertEqual(response.status_code, 200)


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

		self.assertEqual(7, Change.objects.count())
		self.assertEqual(1, Change.objects.filter(changeset=cs, model='Animal', field='name', before='null', after='"Daffy Duck"').count())
		self.assertEqual(1, Change.objects.filter(changeset=cs, model='Animal', field='id', before='null', after=Animal.objects.get().id).count())
		self.assertEqual(1, Change.objects.filter(changeset=cs, model='Animal', field='caretaker', before='null', after='null').count())
		self.assertEqual(1, Change.objects.filter(changeset=cs, model='Animal', field='zoo', before='null', after='null').count())
		self.assertEqual(1, Change.objects.filter(changeset=cs, model='Animal', field='zoo_of_birth', before='null', after='null').count())
		self.assertEqual(1, Change.objects.filter(changeset=cs, model='Animal', field='deleted', before='null', after='false').count())
		self.assertEqual(1, Change.objects.filter(changeset=cs, model='Animal', field='birth_date', before='null', after='null').count())



	def test_model_with_history_creates_changes_on_update_but_only_for_changed_fields(self):
		daffy = Animal(name='Daffy Duck')
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
		mickey = Caretaker(name='Mickey')
		mickey.save()
		pluto = Animal(name='Pluto')
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


	def test_change_related_object(self):
		mickey = Caretaker(name='Mickey')
		mickey.save()
		pluto = Animal(name='Pluto', caretaker=mickey)
		pluto.save()

		self.assertEqual(0, Change.objects.count())

		model_data = {
			'data': [{
				'id': mickey.id,
				'name': 'Mickey Mouse',
			}],
		}
		response = self.client.put('/caretaker/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)

		self.assertEqual(2, Change.objects.count())
		self.assertEqual(1, Change.objects.filter(model='Animal', field='caretaker', before='Related object changed', after="Changed ['name']").count())
		self.assertEqual(1, Change.objects.filter(model='Caretaker', field='name', before='"Mickey"', after='"Mickey Mouse"').count())


	def test_change_related_object_one_to_one(self):
		pluto = Animal(name='Pluto')
		pluto.save()
		costume = Costume(nickname='Flapdrol', animal=pluto)
		costume.save()

		self.assertEqual(0, Change.objects.count())

		model_data = {
			'data': [{
				'id': pluto.id,
				'name': 'Pluto the dog',
			}],
		}
		response = self.client.put('/animal/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)

		self.assertEqual(2, Change.objects.count())
		self.assertEqual(1, Change.objects.filter(model='Animal', field='name', before='"Pluto"', after='"Pluto the dog"').count())
		self.assertEqual(1, Change.objects.filter(model='Costume', field='animal', before='Related object changed', after="Changed ['name']").count())


	def test_change_related_object_one_to_one_ignore_forward(self):
		pluto = Animal(name='Pluto')
		pluto.save()
		costume = Costume(nickname='Flapdrol', animal=pluto)
		costume.save()

		self.assertEqual(0, Change.objects.count())

		model_data = {
			'data': [{
				'id': pluto.id,
				'nickname': 'Cutie',
			}],
		}
		response = self.client.put('/costume/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)

		self.assertEqual(1, Change.objects.count())
		self.assertEqual(1, Change.objects.filter(model='Costume', field='nickname', before='"Flapdrol"', after='"Cutie"').count())


	def test_change_related_object_multiple_fields(self):
		mickey = Caretaker(name='Mickey')
		mickey.save()
		pluto = Animal(name='Pluto', caretaker=mickey)
		pluto.save()
		mars = Animal(name='Mars', caretaker=mickey)
		mars.save()

		self.assertEqual(0, Change.objects.count())

		model_data = {
			'data': [{
				'id': mickey.id,
				'name': 'Mickey Mouse',
				'ssn': 'test1234'
			}],
		}
		response = self.client.put('/caretaker/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)

		self.assertEqual(4, Change.objects.count())
		self.assertEqual(1, Change.objects.filter(model='Animal', oid=pluto.id, field='caretaker', before='Related object changed', after="Changed ['name', 'ssn']").count())
		self.assertEqual(1, Change.objects.filter(model='Animal', oid=mars.id, field='caretaker', before='Related object changed', after="Changed ['name', 'ssn']").count())
		self.assertEqual(1, Change.objects.filter(model='Caretaker', field='name', before='"Mickey"', after='"Mickey Mouse"').count())
		self.assertEqual(1, Change.objects.filter(model='Caretaker', field='ssn', before='"my secret ssn"', after='"test1234"').count())


	def test_assign_related_object(self):
		mickey = Caretaker(name='Mickey')
		mickey.save()
		pluto = Animal(name='Pluto')
		pluto.save()

		self.assertEqual(0, Change.objects.count())
		model_data = {
			'data': [{
				'id': pluto.id,
				'caretaker': mickey.id
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

		self.assertEqual(2, Change.objects.count())
		self.assertEqual(1, Change.objects.filter(model='Animal', field='caretaker', before='null', after=mickey.id).count())
		self.assertEqual(1, Change.objects.filter(model='Caretaker', field='name', before='"Mickey"', after='"Mickey Mouse"').count())


	def test_unassign_related_object(self):
		mickey = Caretaker(name='Mickey')
		mickey.save()
		pluto = Animal(name='Pluto', caretaker=mickey)
		pluto.save()

		self.assertEqual(0, Change.objects.count())
		model_data = {
			'data': [{
				'id': pluto.id,
				'caretaker': None
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

		self.assertEqual(2, Change.objects.count())
		self.assertEqual(1, Change.objects.filter(model='Animal', field='caretaker', before=mickey.id, after='null').count())
		self.assertEqual(1, Change.objects.filter(model='Caretaker', field='name', before='"Mickey"', after='"Mickey Mouse"').count())


	def test_change_object_and_related_object(self):
		mickey = Caretaker(name='Mickey')
		mickey.save()
		pluto = Animal(name='Pluto', caretaker=mickey)
		pluto.save()

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

		self.assertEqual(3, Change.objects.count())
		self.assertEqual(1, Change.objects.filter(model='Animal', field='name', before='"Pluto"', after='"Pluto the dog"').count())
		self.assertEqual(1, Change.objects.filter(model='Animal', field='caretaker', before='Related object changed', after="Changed ['name']").count())
		self.assertEqual(1, Change.objects.filter(model='Caretaker', field='name', before='"Mickey"', after='"Mickey Mouse"').count())


	def test_related_changes_ignore_many_to_many(self):
		pluto = Animal(name='Pluto')
		pluto.save()

		disney = Zoo(name='Disney')
		disney.save()

		disney.most_popular_animals.set([pluto])
		disney.save()

		self.assertEqual(0, Change.objects.count())

		model_data = {
			'data': [{
				'id': pluto.id,
				'name': 'Pluto the dog',
			}],
		}
		response = self.client.put('/animal/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)

		self.assertEqual(1, Change.objects.count())
		self.assertEqual(1, Change.objects.filter(model='Animal', field='name', before='"Pluto"', after='"Pluto the dog"').count())


	def test_related_changes_ignore_many_to_many_reverse(self):
		pluto = Animal(name='Pluto')
		pluto.save()

		disney = Zoo(name='Disney')
		disney.save()

		disney.most_popular_animals.set([pluto])
		disney.save()

		self.assertEqual(0, Change.objects.count())

		model_data = {
			'data': [{
				'id': disney.id,
				'name': 'Disneyland',
			}],
		}
		response = self.client.put('/zoo/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)

		self.assertEqual(1, Change.objects.count())
		self.assertEqual(1, Change.objects.filter(model='Zoo', field='name', before='"Disney"', after='"Disneyland"').count())


	def test_related_changes_ignore_many_to_many_named(self):
		contact = ContactPerson(name='Joe')
		contact.save()

		disney = Zoo(name='Disney')
		disney.save()

		disney.contacts.set([contact])
		disney.save()

		self.assertEqual(0, Change.objects.count())

		model_data = {
			'data': [{
				'id': contact.id,
				'name': 'Uncle Joe',
			}],
		}
		response = self.client.put('/contact_person/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)

		self.assertEqual(2, Change.objects.count())
		self.assertEqual(1, Change.objects.filter(model='ContactPerson', field='name', before='"Joe"', after='"Uncle Joe"').count())
		self.assertEqual(1, Change.objects.filter(model='ContactPerson', field='updated_at').count())


	def test_related_changes_ignore_many_to_many_named_reverse(self):
		contact = ContactPerson(name='Joe')
		contact.save()

		disney = Zoo(name='Disney')
		disney.save()

		disney.contacts.set([contact])
		disney.save()

		self.assertEqual(0, Change.objects.count())

		model_data = {
			'data': [{
				'id': disney.id,
				'name': 'Disneyland',
			}],
		}
		response = self.client.put('/zoo/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)

		self.assertEqual(1, Change.objects.count())
		self.assertEqual(1, Change.objects.filter(model='Zoo', field='name', before='"Disney"', after='"Disneyland"').count())
	

	def test_manual_history_direct_success(self):
		history.start(source='tests')

		# No history yet
		self.assertEqual(0, Changeset.objects.count())
		self.assertEqual(0, Change.objects.count())

		mickey = Caretaker(name='Mickey')
		mickey.save()

		# Still no history
		self.assertEqual(0, Changeset.objects.count())
		self.assertEqual(0, Change.objects.count())

		history.commit()

		# Aww yeah
		self.assertEqual(1, Changeset.objects.count())
		self.assertEqual(5, Change.objects.count())



	def test_manual_history_direct_abort(self):
		history.start(source='tests')

		# No history yet
		self.assertEqual(0, Changeset.objects.count())
		self.assertEqual(0, Change.objects.count())

		mickey = Caretaker(name='Mickey')
		mickey.save()

		# Still no history
		self.assertEqual(0, Changeset.objects.count())
		self.assertEqual(0, Change.objects.count())

		history.abort()

		# Aborted, so still no history
		self.assertEqual(0, Changeset.objects.count())
		self.assertEqual(0, Change.objects.count())



	def test_manual_history_contextmanager_success(self):
		with history.atomic(source='tests'):
			# No history yet
			self.assertEqual(0, Changeset.objects.count())
			self.assertEqual(0, Change.objects.count())

			mickey = Caretaker(name='Mickey')
			mickey.save()

			# Still no history
			self.assertEqual(0, Changeset.objects.count())
			self.assertEqual(0, Change.objects.count())

		# Aww yeah
		self.assertEqual(1, Changeset.objects.count())
		self.assertEqual(5, Change.objects.count())



	def test_manual_history_contextmanager_abort(self):
		class TestException(Exception):
			pass

		try:
			with history.atomic(source='tests'):
				# No history yet
				self.assertEqual(0, Changeset.objects.count())
				self.assertEqual(0, Change.objects.count())

				mickey = Caretaker(name='Mickey')
				mickey.save()

				# Still no history
				self.assertEqual(0, Changeset.objects.count())
				self.assertEqual(0, Change.objects.count())

				raise TestException('oeps')
		except TestException:
			pass

		# Aborted, so still no history
		self.assertEqual(0, Changeset.objects.count())
		self.assertEqual(0, Change.objects.count())
