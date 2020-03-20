from django.test import TestCase
from ..testapp.models import Animal, Zoo, Caretaker, ZooEmployee

class LoadedValuesMixinTest(TestCase):
	def test_old_values_after_initialization_are_identical_to_current_but_unchanged(self):
		artis = Zoo(name='Artis')
		artis.save()
		gaia = Zoo(name='Gaia Zoo')
		gaia.save()
		caretaker = Caretaker(name='Henk')
		caretaker.save()

		scooby = Animal(name='Scooby Doo', zoo_of_birth=artis, zoo=gaia, caretaker=caretaker)

		self.assertEqual('Scooby Doo', scooby.get_old_value('name'))
		self.assertEqual(gaia.id, scooby.get_old_value('zoo'))
		self.assertEqual(artis.id, scooby.get_old_value('zoo_of_birth'))
		self.assertEqual(caretaker.id, scooby.get_old_value('caretaker'))

		self.assertTrue(scooby.field_changed('zoo'))
		self.assertTrue(scooby.field_changed('zoo_of_birth'))
		self.assertTrue(scooby.field_changed('name'))
		self.assertTrue(scooby.field_changed('caretaker'))
		self.assertTrue(scooby.field_changed('name', 'zoo', 'zoo_of_birth', 'caretaker'))

		scooby.save()

		self.assertEqual('Scooby Doo', scooby.get_old_value('name'))
		self.assertEqual(gaia.id, scooby.get_old_value('zoo'))
		self.assertEqual(artis.id, scooby.get_old_value('zoo_of_birth'))
		self.assertEqual(caretaker.id, scooby.get_old_value('caretaker'))

		self.assertEqual({
			'id': scooby.id,
			'name': 'Scooby Doo',
			'zoo': gaia.id,
			'zoo_of_birth': artis.id,
			'caretaker': caretaker.id,
			'deleted': False,
		}, scooby.get_old_values())

		self.assertFalse(scooby.field_changed('zoo'))
		self.assertFalse(scooby.field_changed('zoo_of_birth'))
		self.assertFalse(scooby.field_changed('name'))
		self.assertFalse(scooby.field_changed('name', 'zoo', 'zoo_of_birth'))


	def test_old_values_after_change_are_marked_as_changed_and_old_values_returns_old_value(self):
		artis = Zoo(name='Artis')
		artis.save()
		gaia = Zoo(name='Gaia Zoo')
		gaia.save()
		caretaker = Caretaker(name='Henk')
		caretaker.save()

		scooby = Animal(name='Scooby Doo', zoo_of_birth=artis, zoo=gaia)
		scooby.save()

		# He goes back to the old zoo
		scooby.zoo=artis
		scooby.name='Scoooooby Doooo'

		self.assertEqual('Scooby Doo', scooby.get_old_value('name'))
		self.assertEqual(gaia.id, scooby.get_old_value('zoo'))
		self.assertEqual(artis.id, scooby.get_old_value('zoo_of_birth'))

		self.assertTrue(scooby.field_changed('zoo'))
		self.assertFalse(scooby.field_changed('zoo_of_birth'))
		self.assertTrue(scooby.field_changed('name'))
		self.assertTrue(scooby.field_changed('name', 'zoo', 'zoo_of_birth'))

		self.assertEqual({
			'id': scooby.id, # If mixin is loaded in correct order, id should be set
			'name': 'Scooby Doo',
			'zoo': gaia.id,
			'zoo_of_birth': artis.id,
			'caretaker': None,
			'deleted': False,
		}, scooby.get_old_values())


	def test_old_values_return_current_value_after_fresh_fetch_from_db(self):
		artis = Zoo(name='Artis')
		artis.save()
		gaia = Zoo(name='Gaia Zoo')
		gaia.save()
		caretaker = Caretaker(name='Henk')
		caretaker.save()

		scooby = Animal(name='Scooby Doo', zoo_of_birth=artis, zoo=gaia)
		scooby.save()

		# Let's not use refresh_from_db, but ensure this is a 100%
		# clean object
		scooby = Animal.objects.get(id=scooby.id)

		self.assertEqual('Scooby Doo', scooby.get_old_value('name'))
		self.assertEqual(gaia.id, scooby.get_old_value('zoo'))
		self.assertEqual(artis.id, scooby.get_old_value('zoo_of_birth'))

		self.assertFalse(scooby.field_changed('zoo'))
		self.assertFalse(scooby.field_changed('zoo_of_birth'))
		self.assertFalse(scooby.field_changed('name'))
		self.assertFalse(scooby.field_changed('name', 'zoo', 'zoo_of_birth'))

		self.assertEqual({
			'id': scooby.id,
			'name': 'Scooby Doo',
			'zoo': gaia.id,
			'zoo_of_birth': artis.id,
			'caretaker': None,
			'deleted': False,
		}, scooby.get_old_values())

		# He goes back to the old zoo
		scooby.zoo=artis
		scooby.name='Scoooooby Doooo'

		self.assertEqual('Scooby Doo', scooby.get_old_value('name'))
		self.assertEqual(gaia.id, scooby.get_old_value('zoo'))
		self.assertEqual(artis.id, scooby.get_old_value('zoo_of_birth'))

		self.assertTrue(scooby.field_changed('zoo'))
		self.assertFalse(scooby.field_changed('zoo_of_birth'))
		self.assertTrue(scooby.field_changed('name'))
		self.assertTrue(scooby.field_changed('name', 'zoo', 'zoo_of_birth'))


	def test_recursion_depth_issue_with_loaded_values_and_only(self):
		artis = Zoo(name='Artis')
		artis.save()
		gaia = Zoo(name='Gaia Zoo')
		gaia.save()
		caretaker = Caretaker(name='Henk')
		caretaker.save()

		scooby = Animal(name='Scooby Doo', zoo_of_birth=artis, zoo=gaia)
		scooby.save()

		# This would cause a maximum recursion depth exceeded error
		scooby = Animal.objects.only('name').get(id=scooby.id)

		self.assertEqual({
			'id': scooby.id,
			'name': 'Scooby Doo',
			'zoo': gaia.id,
			'zoo_of_birth': artis.id,
			'caretaker': None,
			'deleted': False,
		}, scooby.get_old_values())

		self.assertEqual('Scooby Doo', scooby.get_old_value('name'))
		self.assertEqual(gaia.id, scooby.get_old_value('zoo'))
		self.assertEqual(artis.id, scooby.get_old_value('zoo_of_birth'))

		self.assertFalse(scooby.field_changed('zoo'))
		self.assertFalse(scooby.field_changed('zoo_of_birth'))
		self.assertFalse(scooby.field_changed('name'))
		self.assertFalse(scooby.field_changed('name', 'zoo', 'zoo_of_birth'))


	def test_non_nullable_field_does_not_error_out_when_accessing(self):
		zoo_employee = ZooEmployee(name='Henk')

		self.assertEqual({
			'id': None,
			'name': 'Henk',
			'zoo': None,
			'deleted': False,
		}, zoo_employee.get_old_values())

		self.assertIsNone(zoo_employee.get_old_value('zoo'))

		self.assertTrue(zoo_employee.field_changed('id'))
		self.assertTrue(zoo_employee.field_changed('zoo'))
		self.assertTrue(zoo_employee.field_changed('name'))
		self.assertTrue(zoo_employee.field_changed('deleted'))

		artis = Zoo(name='Artis')
		artis.save()
		zoo_employee.zoo = artis

		zoo_employee.save()


		self.assertEqual({
			'id': zoo_employee.id,
			'name': 'Henk',
			'zoo': artis.id,
			'deleted': False,
		}, zoo_employee.get_old_values())

		self.assertEqual(artis.id, zoo_employee.get_old_value('zoo'))

		self.assertFalse(zoo_employee.field_changed('id'))
		self.assertFalse(zoo_employee.field_changed('zoo'))
		self.assertFalse(zoo_employee.field_changed('name'))
		self.assertFalse(zoo_employee.field_changed('deleted'))


		zoo_employee.zoo = None
		zoo_employee.clean()

		self.assertEqual({
			'id': zoo_employee.id,
			'name': 'Henk',
			'zoo': artis.id,
			'deleted': False,
		}, zoo_employee.get_old_values())

		self.assertEqual(artis.id, zoo_employee.get_old_value('zoo'))

		self.assertFalse(zoo_employee.field_changed('id'))
		self.assertTrue(zoo_employee.field_changed('zoo'))
		self.assertFalse(zoo_employee.field_changed('name'))
		self.assertFalse(zoo_employee.field_changed('deleted'))
