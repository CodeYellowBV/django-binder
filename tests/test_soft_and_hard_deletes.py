from django.test import TestCase, Client
from django.contrib.auth.models import User

from binder.json import jsonloads

from .testapp.models import Animal, Costume, Caretaker

class DeleteTest(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)


	def test_non_soft_deletable_model_is_hard_deleted_on_delete_verb(self):
		donald = Animal(name='Donald Duck')
		donald.full_clean()
		donald.save()

		sailor = Costume(description='Weird sailor costume', animal=donald)
		sailor.full_clean()
		sailor.save()

		response = self.client.delete('/costume/%d/' % sailor.pk)
		self.assertEqual(response.status_code, 204)
		self.assertEqual('', response.content.decode())

		self.assertFalse(Costume.objects.exists())


	def test_soft_deletable_model_is_softdeleted_on_delete_verb(self):
		donald = Animal(name='Donald Duck')
		donald.full_clean()
		donald.save()

		self.assertFalse(donald.deleted)

		response = self.client.delete('/animal/%d/' % donald.id)
		self.assertEqual(response.status_code, 204)
		self.assertEqual('', response.content.decode())

		donald.refresh_from_db()
		self.assertTrue(donald.deleted)


	def test_soft_deletable_model_is_undeleted_on_post(self):
		donald = Animal(name='Donald Duck', deleted=True)
		donald.full_clean()
		donald.save()

		self.assertTrue(donald.deleted)

		# Body must be empty, otherwise we get an error
		response = self.client.post('/animal/%d/' % donald.id, data='{"name": "Undead Donald"}', content_type='application/json')
		self.assertEqual(response.status_code, 418)

		response = self.client.post('/animal/%d/' % donald.id, data='{}', content_type='application/json')
		self.assertEqual(response.status_code, 204)
		self.assertEqual('', response.content.decode())

		donald.refresh_from_db()
		self.assertFalse(donald.deleted)


	def test_hard_deletable_model_raises_validation_error_on_cascaded_delete_failure(self):
		walt = Caretaker(name='Walt Disney')
		walt.full_clean()
		walt.save()

		donald = Animal(name='Donald Duck', caretaker=walt)
		donald.full_clean()
		donald.save()

		# Body must be empty, otherwise we get another error
		response = self.client.delete('/caretaker/%d/' % walt.id)
		self.assertEqual(response.status_code, 400)
		returned_data = jsonloads(response.content)
		self.assertEqual(returned_data['code'], 'ValidationError')
		self.assertEqual(len(returned_data['errors']), 1)
		self.assertEqual(len(returned_data['errors']['caretaker']), 1)
		self.assertEqual(len(returned_data['errors']['caretaker'][str(walt.id)]), 1)
		self.assertEqual(len(returned_data['errors']['caretaker'][str(walt.id)]['id']), 1)
		self.assertEqual(returned_data['errors']['caretaker'][str(walt.id)]['id'][0]['code'], 'protected')
		self.assertIn('message', returned_data['errors']['caretaker'][str(walt.id)]['id'][0])

		self.assertIn('objects', returned_data['errors']['caretaker'][str(walt.id)]['id'][0])
		self.assertEqual({'animal': [donald.id]}, returned_data['errors']['caretaker'][str(walt.id)]['id'][0]['objects'])

		walt.refresh_from_db() # Should not fail
		donald.refresh_from_db()
		self.assertFalse(donald.deleted)
