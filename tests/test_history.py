from datetime import datetime, timedelta, timezone
import json

from django.test import TestCase, Client
from django.contrib.auth.models import User

from binder import history
from binder.history import Change, Changeset

from .testapp.models import Animal, Caretaker, ContactPerson, Zoo


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

		response = self.client.get(f'/zoo/{_id}/history/')
		self.assertEqual(200, response.status_code)
		data = json.loads(response.content)['data']
		self.assertEqual(2, len(data))

		self.assertEqual(1, len(data[0]['changes']))
		add_rene = data[0]['changes'][0]
		self.assertEqual('contacts', add_rene['field'])
		self.assertEqual('Burhan, Rene', add_rene['after'])
		self.assertEqual('Burhan', add_rene['before'])

		self.assertEqual(13, len(data[1]['changes']))
		add_burhan = data[1]['changes'][4]
		self.assertEqual('contacts', add_burhan['field'])
		self.assertEqual('Burhan', add_burhan['after'])
		self.assertEqual('', add_burhan['before'])

	def test_basic_relation_formatting(self):
		contact_person = ContactPerson.objects.create(
			name='Burhan'
		)

		model_data = {
			'name': 'Code Yellow',
			'director': contact_person.pk
		}
		response = self.client.post('/zoo/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)

		zoo_id = json.loads(response.content)['id']
		response = self.client.get(f'/zoo/{zoo_id}/history/')
		self.assertEqual(200, response.status_code)
		data = json.loads(response.content)['data']

		self.assertEqual(1, len(data))
		changes = data[0]['changes']
		set_director = changes[4]
		self.assertEqual('director', set_director['field'])
		self.assertEqual('null', set_director['before'])
		self.assertEqual('Burhan', set_director['after'])

		model_data = {
			'name': 'Code Yellow',
			'director': None,
		}
		response = self.client.put('/zoo/' + str(zoo_id) + '/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)

		response = self.client.get(f'/zoo/{zoo_id}/history/')
		self.assertEqual(200, response.status_code)
		data = json.loads(response.content)['data']

		self.assertEqual(2, len(data))
		changes = data[0]['changes']
		set_director = changes[0]
		self.assertEqual('director', set_director['field'])
		self.assertEqual('Burhan', set_director['before'])
		self.assertEqual('null', set_director['after'])

	def test_m2m_relation_formatting(self):
		burhan = ContactPerson.objects.create(name='Burhan')
		rene = ContactPerson.objects.create(name='Rene')
		tim = ContactPerson.objects.create(name='Tim')
		nuria = ContactPerson.objects.create(name='Nuria')

		model_data = {
			'name': 'Code Yellow',
			'contacts': [burhan.id, rene.id]
		}
		response = self.client.post('/zoo/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)
		zoo_id = json.loads(response.content)['id']

		model_data = {
			'contacts': [rene.id, tim.id, nuria.id]
		}
		response = self.client.put(f'/zoo/{zoo_id}/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)

		model_data = {
			'contacts': [burhan.id, nuria.id]
		}
		response = self.client.put(f'/zoo/{zoo_id}/', data=json.dumps(model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)

		response = self.client.get(f'/zoo/{zoo_id}/history/')
		self.assertEqual(200, response.status_code)
		data = json.loads(response.content)['data']
		self.assertEqual(3, len(data))

		remove_all = data[0]['changes']
		self.assertEqual(1, len(remove_all))
		self.assertEqual('contacts', remove_all[0]['field'])
		self.assertEqual('Burhan, Nuria', remove_all[0]['after'])
		self.assertEqual('Rene, Tim, Nuria', remove_all[0]['before'])

		replace = data[1]['changes']
		self.assertEqual(1, len(replace))
		self.assertEqual('contacts', replace[0]['field'])
		self.assertEqual('Rene, Tim, Nuria', replace[0]['after'])
		self.assertEqual('Burhan, Rene', replace[0]['before'])

		initial = data[2]['changes']
		first_contacts = initial[4]
		self.assertEqual('contacts', first_contacts['field'])
		self.assertEqual('Burhan, Rene', first_contacts['after'])
		self.assertEqual('', first_contacts['before'])

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

	def test_exclude_history_fields_prevents_tracking(self):
		"""Test that fields listed in exclude_history_fields are not tracked in history"""
		original_exclude_fields = getattr(Animal.Binder, 'exclude_history_fields', [])
		Animal.Binder.exclude_history_fields = ['name']
		
		try:
			model_data = {
				'name': 'Test Animal',
			}
			response = self.client.post('/animal/', data=json.dumps(model_data), content_type='application/json')
			self.assertEqual(response.status_code, 200)
			animal_id = json.loads(response.content)['id']
			
			# Check that we have a changeset for the creation
			self.assertEqual(1, Changeset.objects.count())
			cs = Changeset.objects.get()
			
			# Check that changes exist for normal fields but not for excluded fields
			changes = Change.objects.filter(changeset=cs)
			field_names = [change.field for change in changes]
			
			# The 'name' field should be excluded from history
			self.assertNotIn('name', field_names)
			# Other fields should still be tracked
			self.assertIn('id', field_names)
			self.assertIn('deleted', field_names)
			
			model_data = {
				'name': 'Updated Animal Name',
			}
			response = self.client.patch(f'/animal/{animal_id}/', data=json.dumps(model_data), content_type='application/json')
			self.assertEqual(response.status_code, 200)
			
			# Should still only have 1 changeset (no new one created for excluded field)
			self.assertEqual(1, Changeset.objects.count())
			
			# Now update both an excluded field AND a non-excluded field
			zoo = Zoo.objects.create(name='Test Zoo')
			model_data = {
				'name': 'Another Name Update',  # excluded field
				'zoo': zoo.id,  # non-excluded field
			}
			response = self.client.patch(f'/animal/{animal_id}/', data=json.dumps(model_data), content_type='application/json')
			self.assertEqual(response.status_code, 200)
			
			# Now we should have 2 changesets (original creation + this mixed update)
			self.assertEqual(2, Changeset.objects.count())
			
			# Check the latest changeset (for the mixed update)
			latest_cs = Changeset.objects.order_by('-id').first()
			latest_changes = Change.objects.filter(changeset=latest_cs)
			latest_field_names = [change.field for change in latest_changes]
			
			# Only the zoo field should be recorded, not the name
			self.assertEqual(1, len(latest_field_names))
			self.assertIn('zoo', latest_field_names)
			self.assertNotIn('name', latest_field_names)
			
		finally:
			# Restore original exclude_history_fields setting
			Animal.Binder.exclude_history_fields = original_exclude_fields