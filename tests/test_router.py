from django.test import TestCase

from binder.exceptions import BinderNotFound
from binder.json import jsondumps
from binder.models import BinderModel
from binder.router import Router, Route, detail_route
from binder.views import ModelView

from django.urls.base import is_valid_path, clear_url_caches
from django.urls import re_path, include

from . import urls_module

# Two unique local models, to use for view registration
from .testapp.models import Country


class FooModel(BinderModel):
	class Meta(BinderModel.Meta):
		app_label = 'test'
class BarModel(BinderModel):
	class Meta(BinderModel.Meta):
		app_label = 'test'


class RouterTest(TestCase):
	def tearDown(self):
		# Without this, tests can influence one another!
		clear_url_caches()


	def test_double_model_registration_triggers_error(self):
		class ParentView(ModelView):
			pass

		class FooView1(ParentView):
			model = FooModel

		class FooView2(ParentView):
			model = FooModel

		with self.assertRaises(ValueError):
			Router().register(ParentView)


	def test_double_route_registration_triggers_error(self):
		class ParentView(ModelView):
			pass

		class FooView(ParentView):
			model = FooModel
			route = 'myroute'

		class BarView(ParentView):
			model = BarModel
			route = 'myroute'

		with self.assertRaises(ValueError):
			Router().register(ParentView)


	def test_register_adds_default_routes_from_modelname(self):
		class ParentView(ModelView):
			pass

		class FooView(ParentView):
			model = FooModel

		class BarView(ParentView):
			model = BarModel

		r = Router()
		r.register(ParentView)
		urls_module.urlpatterns = [re_path(r'^', include(r.urls))]

		self.assertTrue(is_valid_path('/foo_model/', urls_module))
		self.assertTrue(is_valid_path('/foo_model/1/', urls_module))
		self.assertTrue(is_valid_path('/bar_model/12345/', urls_module))
		self.assertFalse(is_valid_path('/bar_model/lalala/', urls_module))
		self.assertFalse(is_valid_path('/another_model/', urls_module))


	def test_register_adds_custom_route_names(self):
		class ParentView(ModelView):
			pass

		class FooView(ParentView):
			model = FooModel
			route = 'foo'

		class BarView(ParentView):
			model = BarModel
			# Explicit Route objects should also be accepted
			route = Route('bar')

		r = Router()
		r.register(ParentView)
		urls_module.urlpatterns = [re_path(r'^', include(r.urls))]

		self.assertTrue(is_valid_path('/foo/', urls_module))
		self.assertTrue(is_valid_path('/foo/1/', urls_module))
		self.assertTrue(is_valid_path('/bar/12345/', urls_module))

		# Default named routes should not be there
		self.assertFalse(is_valid_path('/foo_model/1/', urls_module))
		self.assertFalse(is_valid_path('/bar_model/1/', urls_module))


	def test_register_obeys_custom_route_config(self):
		class ParentView(ModelView):
			pass

		class FooView(ParentView):
			model = FooModel
			route = Route('foo', list_endpoint=False)

		class BarView(ParentView):
			model = BarModel
			route = Route('bar', detail_endpoint=False)

		r = Router()
		r.register(ParentView)
		urls_module.urlpatterns = [re_path(r'^', include(r.urls))]

		self.assertFalse(is_valid_path('/foo/', urls_module))
		self.assertTrue(is_valid_path('/foo/1/', urls_module))

		self.assertTrue(is_valid_path('/bar/', urls_module))
		self.assertFalse(is_valid_path('/bar/1/', urls_module))


class TestFetchObj(TestCase):

		
	def test_get_obj_turns_pk_in_object(self):
		that = self

		country = Country.objects.create(name='foo')

		class RequestMock:
			method='GET'

		class Foo(ModelView):
			model = Country

			@detail_route('foo', methods=['GET'], fetch_obj=True, unauthenticated=True)
			def foo(self, request, obj):
				that.assertTrue(isinstance(obj, Country))
				that.assertEqual(country.pk, obj.pk)
				return jsondumps({})

		Foo().foo(RequestMock(), country.pk)

	def test_get_obj_turns_kwarg_pk_in_object(self):
		that = self

		country = Country.objects.create(name='foo')

		class RequestMock:
			method = 'GET'

		class Foo(ModelView):
			model = Country

			@detail_route('foo', methods=['GET'], fetch_obj=True, unauthenticated=True)
			def foo(self, request, obj):
				that.assertTrue(isinstance(obj, Country))
				that.assertEqual(country.pk, obj.pk)
				return jsondumps({})

		Foo().foo(RequestMock(), pk=country.pk)

	def test_get_obj_raises_binder_not_exists_error(self):
		class RequestMock:
			method='GET'

		class Foo(ModelView):
			model = Country

			@detail_route('foo', methods=['GET'], fetch_obj=True, unauthenticated=True)
			def foo(self, request, obj):
				return jsondumps({})

		with self.assertRaises(BinderNotFound):
			Foo().foo(RequestMock(), 5)
