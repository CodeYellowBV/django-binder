from re import I
from tests.testapp.models import contact_person
from tests.testapp.models.contact_person import ContactPerson
from django.test import TestCase, Client

import json
from binder.json import jsonloads
from django.contrib.auth.models import User
from .testapp.models import Animal, Caretaker, ContactPerson


class TestModelValidation(TestCase):
	"""
	Test the validate-only functionality.

	We check that the validation is executed as normal, but that the models
	are not created when the validate query paramter is set to true.

	We check validation for:
		- post
		- put
		- multi-put
		- delete
	"""


	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

		# some update payload
		self.model_data_with_error = {
			'name': 'very_special_forbidden_contact_person_name',  # see `contact_person.py`
		}
		self.model_data_with_non_validation_error = {
			'name': 'very_special_validation_contact_person_name',  # see `contact_person.py`
		}
		self.model_data = {
			'name': 'Scooooooby',
		}


	### helpers ###


	def assert_validation_error(self, response, person_id=None):
		if person_id is None:
			person_id = 'null' # for post

		self.assertEqual(response.status_code, 400)

		returned_data = jsonloads(response.content)

		# check that there were validation errors
		self.assertEqual(returned_data.get('code'), 'ValidationError')

		# check that the validation error is present
		validation_error = returned_data.get('errors').get('contact_person').get(str(person_id)).get('__all__')[0]
		self.assertEqual(validation_error.get('code'), 'invalid')
		self.assertEqual(validation_error.get('message'), 'Very special validation check that we need in `tests.M2MStoreErrorsTest`.')


	def assert_multi_put_validation_error(self, response):
		self.assertEqual(response.status_code, 400)

		returned_data = jsonloads(response.content)

		# check that there were validation errors
		self.assertEqual(returned_data.get('code'), 'ValidationError')

		# check that all (two) the validation errors are present
		for error in returned_data.get('errors').get('contact_person').values():
			validation_error = error.get('__all__')[0]
			self.assertEqual(validation_error.get('code'), 'invalid')
			self.assertEqual(validation_error.get('message'), 'Very special validation check that we need in `tests.M2MStoreErrorsTest`.')


	### tests ###


	def assert_no_validation_error(self, response):
		self.assertEqual(response.status_code, 200)

		# check that the validation was successful
		returned_data = jsonloads(response.content)
		self.assertEqual(returned_data.get('code'), 'SkipSave')
		self.assertEqual(returned_data.get('message'), 'No validation errors were encountered.')


	def test_validate_on_post(self):
		self.assertEqual(0, ContactPerson.objects.count())

		# trigger a validation error
		response = self.client.post('/contact_person/?validate=true', data=json.dumps(self.model_data_with_error), content_type='application/json')
		self.assert_validation_error(response)
		self.assertEqual(0, ContactPerson.objects.count())

		# now without validation errors
		response = self.client.post('/contact_person/?validate=true', data=json.dumps(self.model_data), content_type='application/json')
		self.assert_no_validation_error(response)
		self.assertEqual(0, ContactPerson.objects.count())

		# now for real
		response = self.client.post('/contact_person/', data=json.dumps(self.model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)
		self.assertEqual('Scooooooby', ContactPerson.objects.first().name)


	def test_validate_on_put(self):
		person_id = ContactPerson.objects.create(name='Scooby Doo').id
		self.assertEqual('Scooby Doo', ContactPerson.objects.first().name)

		# trigger a validation error
		response = self.client.put(f'/contact_person/{person_id}/?validate=true', data=json.dumps(self.model_data_with_error), content_type='application/json')
		self.assert_validation_error(response, person_id)
		self.assertEqual('Scooby Doo', ContactPerson.objects.first().name)

		# now without validation errors
		response = self.client.put(f'/contact_person/{person_id}/?validate=true', data=json.dumps(self.model_data), content_type='application/json')
		self.assert_no_validation_error(response)
		self.assertEqual('Scooby Doo', ContactPerson.objects.first().name)

		# now for real
		response = self.client.put(f'/contact_person/{person_id}/', data=json.dumps(self.model_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)
		self.assertEqual('Scooooooby', ContactPerson.objects.first().name)

	def test_validate_model_validation_whitelisting(self):
		person_id = ContactPerson.objects.create(name='Scooby Doo').id
		self.assertEqual('Scooby Doo', ContactPerson.objects.first().name)

		# the normal request should give a validation error
		response = self.client.put(f'/contact_person/{person_id}/', data=json.dumps(self.model_data_with_non_validation_error), content_type='application/json')
		self.assert_validation_error(response, person_id)
		self.assertEqual('Scooby Doo', ContactPerson.objects.first().name)

		# when just validating we want to ignore this validation error, so with validation it should not throw an error
		response = self.client.put(f'/contact_person/{person_id}/?validate=true', data=json.dumps(self.model_data), content_type='application/json')
		self.assert_no_validation_error(response)
		self.assertEqual('Scooby Doo', ContactPerson.objects.first().name)



	def test_validate_on_multiput(self):
		person_1_id = ContactPerson.objects.create(name='Scooby Doo 1').id
		person_2_id = ContactPerson.objects.create(name='Scooby Doo 2').id

		multi_put_data = {'data': [
				{
					'id': person_1_id,
					'name': 'New Scooby',
				},
				{
					'id': person_2_id,
					'name': 'New Doo'
				}
			]}

		multi_put_data_with_error = {'data': [
				{
					'id': person_1_id,
					'name': 'very_special_forbidden_contact_person_name',
				},
				{
					'id': person_2_id,
					'name': 'very_special_forbidden_contact_person_name'
				}
			]}

		multi_put_data_with_validation_whitelist = {'data': [
			{
				'id': person_1_id,
				'name': 'very_special_validation_contact_person_name',
			},
			{
				'id': person_2_id,
				'name': 'very_special_validation_contact_person_other_name'
			}
		]}

		# trigger a validation error
		response = self.client.put(f'/contact_person/?validate=true', data=json.dumps(multi_put_data_with_error), content_type='application/json')
		self.assert_multi_put_validation_error(response)
		self.assertEqual('Scooby Doo 1', ContactPerson.objects.get(id=person_1_id).name)
		self.assertEqual('Scooby Doo 2', ContactPerson.objects.get(id=person_2_id).name)


		# now without validation error
		response = self.client.put(f'/contact_person/?validate=true', data=json.dumps(multi_put_data), content_type='application/json')
		self.assert_no_validation_error(response)
		self.assertEqual('Scooby Doo 1', ContactPerson.objects.get(id=person_1_id).name)
		self.assertEqual('Scooby Doo 2', ContactPerson.objects.get(id=person_2_id).name)

		# multi put validation whitelist test
		response = self.client.put(f'/contact_person/?validate=true', data=json.dumps(multi_put_data_with_validation_whitelist), content_type='application/json')
		self.assert_no_validation_error(response)
		self.assertEqual('Scooby Doo 1', ContactPerson.objects.get(id=person_1_id).name)
		self.assertEqual('Scooby Doo 2', ContactPerson.objects.get(id=person_2_id).name)

		# multi put non validation whitelist test error
		response = self.client.put(f'/contact_person/',
								   data=json.dumps(multi_put_data_with_validation_whitelist),
								   content_type='application/json')
		self.assert_multi_put_validation_error(response)
		self.assertEqual('Scooby Doo 1', ContactPerson.objects.get(id=person_1_id).name)
		self.assertEqual('Scooby Doo 2', ContactPerson.objects.get(id=person_2_id).name)

		# now for real
		response = self.client.put(f'/contact_person/', data=json.dumps(multi_put_data), content_type='application/json')
		self.assertEqual(response.status_code, 200)
		self.assertEqual('New Scooby', ContactPerson.objects.get(id=person_1_id).name)
		self.assertEqual('New Doo', ContactPerson.objects.get(id=person_2_id).name)


	def test_validate_on_delete(self):
		'''Check if deletion is cancelled when we only attempt to validate
		the delete operation. This test only covers validation of the
		on_delete=PROTECT constraint of a fk.'''

		def is_deleted(obj):
			'''Whether the obj was soft-deleted, so when the 'deleted'
			attribute is not present, or when it is True.'''

			try:
				obj.refresh_from_db()
			except obj.DoesNotExist:
				return True # hard-deleted
			return animal.__dict__.get('deleted') or False


		# animal has a fk to caretaker with on_delete=PROTECT
		caretaker = Caretaker.objects.create(name='Connie Care')
		animal = Animal.objects.create(name='Pony', caretaker=caretaker)


		### with validation error

		response = self.client.delete(f'/caretaker/{caretaker.id}/?validate=true')
		# assert validation error
		# and check that it was about the PROTECTED constraint
		self.assertEqual(response.status_code, 400)
		returned_data = jsonloads(response.content)
		self.assertEqual(returned_data.get('code'), 'ValidationError')
		self.assertEqual(returned_data.get('errors').get('caretaker').get(str(caretaker.id)).get('id')[0].get('code'), 'protected')

		self.assertFalse(is_deleted(caretaker))


		### without validation error

		# now we delete the animal to make sure that deletion is possible
		# note that soft-deleting will of course not remove the validation error
		animal.delete()

		# now no validation error should be trown
		response = self.client.delete(f'/caretaker/{caretaker.id}/?validate=true')
		print(response.content)
		self.assert_no_validation_error(response)

		self.assertFalse(is_deleted(caretaker))


		### now for real

		response = self.client.delete(f'/caretaker/{caretaker.id}/')
		self.assertTrue(is_deleted(caretaker))
