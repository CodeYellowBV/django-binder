import os, unittest

from django.test import TestCase, Client
from django.contrib.auth.models import User

from binder.json import jsonloads

from .testapp.models import Animal, Zoo, Caretaker, ContactPerson
from .compare import assert_json, EXTRA

@unittest.skipIf(
	os.environ.get('BINDER_TEST_MYSQL', '0') != '0',
	"Only available with PostgreSQL"
)
class WithFilterTest(TestCase):
	def setUp(self):
		super().setUp()
		u = User(username='testuser', is_active=True, is_superuser=True)
		u.set_password('test')
		u.save()
		self.client = Client()
		r = self.client.login(username='testuser', password='test')
		self.assertTrue(r)

	def test_where(self):
		zoo = Zoo(name='Meerkerk')
		zoo.save()

		gman = Caretaker(name='gman')
		gman.save()
		freeman = Caretaker(name='gordon')
		freeman.save()


		antlion = Animal(zoo=zoo, name='antlion', caretaker=freeman)
		antlion.save()

		sealion = Animal(zoo=zoo, name='sealion')
		sealion.save()

		goat = Animal(zoo=zoo, name='goat', caretaker=gman)
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
					'animals': [antlion.id, sealion.id],
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


		# Regression test for missing filter caused by querysets being
		# falsy when there are no records...
		res = self.client.get('/zoo/', data={'with': 'animals.caretaker', 'where': 'animals(name:contains=nonexistent)'})
		self.assertEqual(res.status_code, 200)
		res = jsonloads(res.content)

		assert_json(res, {
			'data': [
				{
					'id': zoo.id,
					'animals': [],
					EXTRA(): None,
				}
			],
			'with': {
				'animal': [],
				'caretaker': [],
			},
			EXTRA(): None,
		})


	def test_multiple_wheres(self):
		zoo = Zoo(name='Meerkerk')
		zoo.save()

		freeman = Caretaker(name='gordon')
		freeman.save()
		alyx = Caretaker(name='alyx')
		alyx.save()


		antlion = Animal(zoo=zoo, name='antlion', caretaker=freeman)
		antlion.save()

		sealion = Animal(zoo=zoo, name='sealion', caretaker=alyx)
		sealion.save()

		goat = Animal(zoo=zoo, name='goat')
		goat.save()

		res = self.client.get('/zoo/', data={
			'with': 'animals.caretaker',
			'where': 'animals(name:contains=lion),animals.caretaker(name=gordon)'
		})
		self.assertEqual(res.status_code, 200)
		res = jsonloads(res.content)

		assert_json(res, {
			'data': [
				{
					'id': zoo.id,
					'animals': [antlion.id, sealion.id],
					EXTRA(): None,
				}
			],
			'with': {
				'animal': [
					{
						'id': antlion.id,
						'caretaker': freeman.id,
						EXTRA(): None,
					},
					{
						'id': sealion.id,
						'caretaker': None, # Was filtered out!
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

	def test_where_and_filter(self):
		zoo1 = Zoo(name='Meerkerk')
		zoo1.save()
		zoo2 = Zoo(name='Hardinxveld')
		zoo2.save()

		freeman = Caretaker(name='gordon')
		freeman.save()
		alyx = Caretaker(name='alyx')
		alyx.save()


		antlion = Animal(zoo=zoo1, name='antlion', caretaker=freeman)
		antlion.save()

		sealion = Animal(zoo=zoo1, name='sealion', caretaker=alyx)
		sealion.save()

		goat1 = Animal(zoo=zoo1, name='goat')
		goat1.save()

		goat2 = Animal(zoo=zoo2, name='goat')
		goat2.save()

		# Instead of filtering the animals relation,
		# we now filter the zoo relation on having certain animals
		res = self.client.get('/zoo/', data={
			'.animals.name:contains': 'lion',
			'with': 'animals.caretaker',
			'where': 'animals.caretaker(name=gordon)'
		})
		self.assertEqual(res.status_code, 200)
		res = jsonloads(res.content)

		assert_json(res, {
			'data': [
				{
					'id': zoo1.id,
					'animals': [antlion.id, sealion.id, goat1.id],
					EXTRA(): None,
				}
			],
			'with': {
				'animal': [
					{
						'id': antlion.id,
						'caretaker': freeman.id,
						EXTRA(): None,
					},
					{
						'id': sealion.id,
						'caretaker': None, # Was filtered out!
						EXTRA(): None,
					},
					{
						'id': goat1.id,
						'caretaker': None,
						EXTRA(): None,
					}
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


	def test_where_filter_on_reverse_foreign_key_field_causes_no_duplication_of_main_record(self):
		zoo1 = Zoo(name='Meerkerk')
		zoo1.save()
		zoo2 = Zoo(name='Hardinxveld')
		zoo2.save()

		antlion = Animal(zoo=zoo1, name='antlion')
		antlion.save()

		sealion = Animal(zoo=zoo1, name='sealion')
		sealion.save()

		# Because one zoo has multiple animals, this creates a join.
		# Having the join means we'll get multiple records.  Even
		# though the ORM hides this fact from us, we do get the
		# multiple results.  Therefore, Binder must add a distinct()
		# call to counteract this effect.  Performance will suffer
		# but there's not much else we can do.
		res = self.client.get('/zoo/', data={ '.animals.name:contains': 'lion', })
		self.assertEqual(res.status_code, 200)
		res = jsonloads(res.content)

		assert_json(res, {
			'data': [
				{
					'id': zoo1.id,
					EXTRA(): None,
				}
			],
			'meta': { 'total_records': 1, EXTRA(): None, },
			'with': {},
			EXTRA(): None,
		})


	def test_m2m(self):
		zoo = Zoo(name='Meerkerk')
		zoo.save()

		cp1 = ContactPerson(name='henk')
		cp1.save()
		cp2 = ContactPerson(name='hendrik')
		cp2.save()
		cp3 = ContactPerson(name='hans')
		cp3.save()

		zoo.contacts.set([cp1.id, cp2.id, cp3.id])

		res = self.client.get('/zoo/', data={
			'with': 'contacts',
			'where': 'contacts(name:startswith=he)'
		})
		self.assertEqual(res.status_code, 200)
		res = jsonloads(res.content)

		assert_json(res, {
			'data': [
				{
					'id': zoo.id,
					'contacts': [cp1.id, cp2.id],
					EXTRA(): None,
				}
			],
			'with': {
				'contact_person': [
					{
						'id': cp1.id,
						EXTRA(): None,
					},
					{
						'id': cp2.id,
						EXTRA(): None,
					},
				]
			},
			EXTRA(): None,
		})


	def test_where_filter_on_m2m_field_causes_no_duplication_of_main_record(self):
		zoo = Zoo(name='Meerkerk')
		zoo.save()

		cp1 = ContactPerson(name='henk')
		cp1.save()
		cp2 = ContactPerson(name='hendrik')
		cp2.save()
		cp3 = ContactPerson(name='hans')
		cp3.save()

		zoo.contacts.set([cp1.id, cp2.id, cp3.id])

		res = self.client.get('/zoo/', data={ '.contacts.name:startswith': 'he' })
		self.assertEqual(res.status_code, 200)
		res = jsonloads(res.content)

		assert_json(res, {
			'data': [
				{
					'id': zoo.id,
					EXTRA(): None,
				}
			],
			'meta': { 'total_records': 1, EXTRA(): None, },
			'with': {},
			EXTRA(): None,
		})


	def test_where_complains_on_syntax_error(self):
		res = self.client.get('/zoo/', data={
			'where': 'contacts'
		})
		self.assertEqual(res.status_code, 418)
		res = jsonloads(res.content)

		assert_json(res, {
			'message': 'Syntax error in {where=contacts}.',
			EXTRA(): None,
		})



	def test_where_complains_if_relation_not_in_with(self):
		res = self.client.get('/zoo/', data={
			'where': 'contacts(name:startswith=he)'
		})
		self.assertEqual(res.status_code, 418)
		res = jsonloads(res.content)

		assert_json(res, {
			'message': 'Relation of {where=contacts(name:startswith=he)} is missing from withs.',
			EXTRA(): None,
		})



	def test_where_complains_on_non_relation_field(self):
		res = self.client.get('/zoo/', data={
			'with': 'floor_plan',
			'where': 'floor_plan(foo=5)'
		})
		self.assertEqual(res.status_code, 418)
		res = jsonloads(res.content)

		assert_json(res, {
			'message': 'Field is not a related object {Zoo}.{floor_plan}.',
			EXTRA(): None,
		})



	def test_where_complains_on_invalid_value(self):
		res = self.client.get('/zoo/', data={
			'with': 'contacts',
			'where': 'contacts(id=foo)'
		})
		self.assertEqual(res.status_code, 418)
		res = jsonloads(res.content)

		assert_json(res, {
			'message': 'Invalid value {foo} for AutoField {ContactPerson}.{id}.',
			EXTRA(): None,
		})



	def test_where_handles_missing_close_parens(self):
		zoo = Zoo(name='Assen')
		zoo.save()
		cp1 = ContactPerson(name='henk')
		cp1.save()
		zoo.contacts.set([cp1])

		res = self.client.get('/zoo/', data={
			'with': 'contacts',
			'where': 'contacts(name=henk'
		})

		self.assertEqual(res.status_code, 418)
		res = jsonloads(res.content)

		assert_json(res, {
			'message': 'Syntax error in {where=contacts(name=henk}.',
			EXTRA(): None,
		})


	def test_where_ignores_commas_in_parens(self):
		zoo = Zoo(name='Apenheul')
		zoo.save()

		harambe = Animal(name='Harambe', zoo=zoo)
		harambe.save()
		bokito = Animal(name='Bokito', zoo=zoo)
		bokito.save()
		rafiki = Animal(name='Rafiki', zoo=zoo)
		rafiki.save()

		res = self.client.get('/zoo/', data={
			'with': 'animals',
			'where': 'animals(name:in=Harambe,Bokito)',
		})

		self.assertEqual(res.status_code, 200)
		res = jsonloads(res.content)

		assert_json(res, {
			'data': [
				{
					'id': zoo.id,
					'animals': [harambe.id, bokito.id],
					EXTRA(): None,
				}
			],
			'with': {
				'animal': [
					{
						'id': harambe.id,
						EXTRA(): None,
					},
					{
						'id': bokito.id,
						EXTRA(): None,
					},
				]
			},
			EXTRA(): None,
		})
