from django.test import TestCase, Client
from .testapp.models import Caretaker
from django.contrib.auth.models import User

from binder.json import jsonloads


class HiddenFieldTest(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

		self.secret_caretaker = Caretaker(
			name='C.A.R.E Taker',
			ssn='1234'
		)
		self.secret_caretaker.save()

		self.other_secret_caretaker = Caretaker(
			name='C.A.R.E Taker2',
			ssn='5678'
		)
		self.other_secret_caretaker.save()



	def test_get_caretaker_doesnt_return_ssn(self):
		"""
		The SSN is a hidden field for a caretaker. Make sure it is not returned on a get request
		"""
		# Filter the animal relations on animals with lion in the name
		# This means we don't expect the goat and its caretaker in the with response
		res = self.client.get('/caretaker/{}/'.format(self.secret_caretaker.id), data={})
		self.assertEqual(res.status_code, 200)
		res = jsonloads(res.content)

		# Make sure the ssn is not in the dataset
		self.assertNotIn('ssn', res['data'])


	def test_filtering_on_ssn_is_ignored(self):
		"""
		Make sure that filtering on hidden fields is ignored, otherwise it may leak information stored in
		hidden fields by doing a smart lookup
		"""
		res = self.client.get('/caretaker/', data={})
		self.assertEqual(res.status_code, 200)
		res = jsonloads(res.content)

		# No filtering, every records is returned
		self.assertEqual(2, res['meta']['total_records'])
		self.assertEqual(2, len(res['data']))

		# A normal where is filter
		res = self.client.get('/caretaker/', data={
			'.ssn': 1234
		})

		self.assertEqual(res.status_code, 200)
		res = jsonloads(res.content)
		# Filtering should be ignored,
		self.assertEqual(2, res['meta']['total_records'])
		self.assertEqual(2, len(res['data']))

		# A more complicated filter
		res = self.client.get('/caretaker/', data={
			'ssn:startswith': '1234'
		})
		self.assertEqual(res.status_code, 200)
		res = jsonloads(res.content)
		# Filtering should be ignored,
		self.assertEqual(2, res['meta']['total_records'])
		self.assertEqual(2, len(res['data']))
