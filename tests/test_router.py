from django.test import TestCase, Client
from binder.models import BinderModel
from binder.router import Router
from binder.views import ModelView

from django.urls.base import resolve, is_valid_path
from django.conf.urls import url, include

from . import urls_module

# Two unique local models, to use for view registration
class FooModel(BinderModel):
	class Meta:
		app_label='test'
class BarModel(BinderModel):
	class Meta:
		app_label='test'


class RouterTest(TestCase):
	def setUp(self):
		# Defeat singleton hackery for now, until #28 is resolved.
		Router.model_views = {}
		Router.route_views = {}
		Router.model_routes = {}
		Router.name_models = {}
		# Ugh, more hackery
		urls_module.urlpatterns = []


	def test_double_model_registration_triggers_error(self):
		class ParentView(ModelView):
			pass
		class FooView1(ParentView):
			model=FooModel
		class FooView2(ParentView):
			model=FooModel

		with self.assertRaises(ValueError) as cm:
			Router().register(ParentView)


	def test_register_adds_default_routes_from_modelname(self):
		class ParentView(ModelView):
			pass
		class FooView(ParentView):
			model=FooModel
		class BarView(ParentView):
			model=BarModel

		r = Router()
		r.register(ParentView)
		urls_module.urlpatterns = [url(r'^', include(r.urls))]
		self.assertTrue(is_valid_path('/foo_model/', urls_module))
		self.assertTrue(is_valid_path('/foo_model/1/', urls_module))
		self.assertTrue(is_valid_path('/bar_model/12345/', urls_module))
		self.assertFalse(is_valid_path('/bar_model/lalala/', urls_module))
		self.assertFalse(is_valid_path('/another_model/', urls_module))
