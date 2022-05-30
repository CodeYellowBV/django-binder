import json

from django.contrib.auth.models import User
from django.test import TestCase

from .testapp.models import Zoo, Animal


class VirtualRelationTestCase(TestCase):

	def setUp(self):
		user = User(username='testuser', is_active=True, is_superuser=True)
		user.set_password('test')
		user.save()

		self.client.login(username='testuser', password='test')

	def test_virtual_relation(self):
		pride_rock = Zoo.objects.create(name='Pride Rock')
		simba = Animal.objects.create(zoo=pride_rock, name='Simba')
		nala = Animal.objects.create(zoo=pride_rock, name='Nala')

		res = self.client.get(f'/zoo/?with=animals.neighbours&where=animals(id={simba.id})')
		self.assertEqual(res.status_code, 200)
		res = json.loads(res.content)

		animals_by_id = {
			obj['id']: obj
			for obj in res['with']['animal']
		}

		self.assertEqual(set(animals_by_id), {simba.id, nala.id})
		self.assertEqual(animals_by_id[simba.id]['neighbours'], [nala.id])
		self.assertNotIn('neighbours', animals_by_id[nala.id])
