from binder.exceptions import BinderValidationError
from binder.router import Router
from binder.views import ModelView
from .testapp.views import AnimalView
from .testapp.models import Animal, Caretaker
from django.test import TestCase

class TestWeirdBug(TestCase):

    def test_standard_filling_in_relation_to_existing_model(self):
        animal = Animal.objects.create(name='foo')
        caretaker = Caretaker.objects.create(name='bar')

        animal_view = AnimalView()

        class FakeUser:
            def has_perm(self, perm):
                return True

        class FakeRequest:
            user = FakeUser()

        router = Router()
        router.register(ModelView)

        animal_view.router = router

        animal_view._store(animal, {'caretaker': caretaker.pk}, FakeRequest())

        self.assertEqual(animal.caretaker, caretaker)


    def test_filling_in_relation_to_existing_model_after_evaulation(self):
        animal = Animal.objects.create(name='foo')
        caretaker = Caretaker.objects.create(name='bar')

        animal_view = AnimalView()

        class FakeUser:
            def has_perm(self, perm):
                return True

        class FakeRequest:
            user = FakeUser()

        router = Router()
        router.register(ModelView)

        animal_view.router = router

        assert animal.caretaker is None

        animal_view._store(animal, {'caretaker': caretaker.pk}, FakeRequest())

        self.assertEqual(animal.caretaker, caretaker)

    def test_setting_none_existing_caretaker_gives_validation_error(self):
        animal = Animal.objects.create(name='foo', caretaker=Caretaker.objects.create(name='bar2'))

        animal_view = AnimalView()

        class FakeUser:
            def has_perm(self, perm):
                return True

        class FakeRequest:
            user = FakeUser()

        router = Router()
        router.register(ModelView)

        animal_view.router = router

        animal.caretaker

        with self.assertRaises(BinderValidationError):
            animal_view._store(animal, {'caretaker': -1}, FakeRequest())

