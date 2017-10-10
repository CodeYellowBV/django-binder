from django.test import TestCase, Client
from django.contrib.auth.models import User

from binder.json import jsonloads

from .testapp.models import Animal, Zoo, Caretaker
from .compare import assert_json, EXTRA

class WithFilterTest(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

	def test_filter_intermediate_relation(self):
		zoo = Zoo(name='Meerkerk')
		zoo.full_clean()
		zoo.save()

		gman = Caretaker(name='gman')
		gman.full_clean()
		gman.save()
		freeman = Caretaker(name='gordon')
		freeman.full_clean()
		freeman.save()


		antlion = Animal(zoo=zoo, name='antlion', caretaker=freeman)
		antlion.full_clean()
		antlion.save()

		sealion = Animal(zoo=zoo, name='sealion')
		sealion.full_clean()
		sealion.save()

		goat = Animal(zoo=zoo, name='goat', caretaker=gman)
		goat.full_clean()
		goat.save()

		# Filter the animal relations on animals with lion in the name
		# This means we don't expect the goat and its caretaker in the with response
		res = self.client.get('/zoo/', data={'with': 'animals.caretaker', 'where': 'animals(name:contains=lion)'})
		self.assertEqual(res.status_code, 200)
		res = jsonloads(res.content)

		assert_json(res, {
			'data': [
				{
					'id': zoo.id,
					'animals': [antlion.id, sealion.id, goat.id],  # Currently we only filter the withs, not foreign keys
					EXTRA(): None,
				}
			],
			'with': {
				'animal': [
					{
						'id': antlion.id,
						EXTRA(): None,
					},
					{
						'id': sealion.id,
						EXTRA(): None,
					},
				],
				'caretaker': [
					{
						'id': freeman.id,
						EXTRA(): None,
					},
				]
			},
			EXTRA(): None,
		})
