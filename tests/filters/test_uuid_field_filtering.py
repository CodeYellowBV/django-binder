from django.test import TestCase, Client

from binder.json import jsonloads
from django.contrib.auth.models import User

from ..testapp.models import Zoo, Caretaker, Gate

class UUIDFieldFilteringTest(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

		self.gaia = Zoo(name='GaiaZOO')
		self.gaia.save()

		self.emmen = Zoo(name='Wildlands Adventure Zoo Emmen')
		self.emmen.save()

		self.artis = Zoo(name='Artis')
		self.artis.save()

		fabbby = Caretaker(name='fabbby')
		fabbby.full_clean()
		fabbby.save()

		door1 = Gate(zoo=self.gaia, keeper=fabbby, serial_number=None)
		door1.full_clean()
		door1.save()

		door2 = Gate(zoo=self.emmen, keeper=fabbby, serial_number='{2e93ec15-2d68-477d-960f-52779ef6198b}')
		door2.full_clean()
		door2.save()

		door3 = Gate(zoo=self.artis, keeper=fabbby, serial_number='3e93ec15-2d68-477d-960f-52779ef6198b')
		door3.full_clean()
		door3.save()


	def test_get_uuidfield_contains_filtering(self):
		response = self.client.get('/gate/', data={'.serial_number:contains': '5277', 'order_by': 'serial_number'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(2, len(result['data']))
		self.assertEqual(self.emmen.id, result['data'][0]['id'])
		self.assertEqual(self.artis.id, result['data'][1]['id'])

		response = self.client.get('/gate/', data={'.serial_number:contains': '000', 'order_by': 'serial_number'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))


	def test_get_uuidfield_startswith_filtering(self):
		response = self.client.get('/gate/', data={'.serial_number:startswith': '2e'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual(self.emmen.id, result['data'][0]['id'])


		response = self.client.get('/gate/', data={'.serial_number:startswith': '3e'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(1, len(result['data']))
		self.assertEqual(self.artis.id, result['data'][0]['id'])

		# OK, this is a bit weird and possibly unexpected:
		# uuid is case sensitive (in Postgres, at least)
		response = self.client.get('/gate/', data={'.serial_number:startswith': '2E'})
		self.assertEqual(response.status_code, 200)

		result = jsonloads(response.content)
		self.assertEqual(0, len(result['data']))
