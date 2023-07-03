from django.contrib.auth.models import User
from django.test import TestCase, Client

from project.binder.json import jsonloads
from tests.testapp.models import Zoo, Nickname, Animal


class TestVirtualRelation(TestCase):

	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

	def test_simple_virtual_relation(self):
		og_zoo = Zoo.objects.create(name='og zoo')
		current_zoo = Zoo.objects.create(name='current zoo')
		current_animal = Animal.objects.create(zoo=current_zoo, zoo_of_birth=og_zoo, name='Peter')
		nickname_current_animal = Nickname.objects.create(nickname='prutser', animal=current_animal)
		res = self.client.get('/nickname/', data={'.nickname': 'prutser', 'with': 'source'})

		res = jsonloads(res.content)

		source_id = res['data'][0]['source']
		source_zoo = res['with']['zoo'][0]

		self.assertEqual(source_id, source_zoo['id'])


	def test_can_include_relation_with_and_without_virtual_relation(self):
		"""
		Previously there was a bug in binder if you included two relations of model foo:

		foo.virtual_relation
		bar.baz.foo

		the backend would crash, because it would try to annotate bar.baz.foo, but not request the relations.
		"""

		og_zoo = Zoo.objects.create(name='og zoo')
		current_zoo = Zoo.objects.create(name='current zoo')
		third_zoo = Zoo.objects.create(name='completely unreleated zoo')

		current_animal = Animal.objects.create(zoo=current_zoo, zoo_of_birth=og_zoo, name='Peter')
		other_animal = Animal.objects.create(zoo=current_zoo, zoo_of_birth=third_zoo, name='Kevin')

		nickname_current_animal = Nickname.objects.create(nickname='prutser', animal=current_animal)
		nickname_other_animal = Nickname.objects.create(nickname='The other one', animal=other_animal)


		response = self.client.get('/animal/', data={'.name': 'Peter', 'with': 'nickname.source,zoo.animals.nickname'})

		print(response.content)
