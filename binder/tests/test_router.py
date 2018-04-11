from django.test import TestCase
from binder.models import BinderModel
from binder.router import Router, Route
from binder.views import ModelView

from django.db import models
from django.urls.base import is_valid_path, clear_url_caches
from django.conf.urls import url, include

from . import urls_module

# Five unique local models, to use for view registration
class FooModel(BinderModel):
	class Meta:
		app_label = 'test'

class BarModel(BinderModel):
	class Meta:
		app_label = 'test'

class BazModel(BinderModel):
	slug = models.SlugField(primary_key=True)
	class Meta:
		app_label = 'test'

class FooRefModel(BinderModel):
	foo = models.ForeignKey(FooModel, on_delete=models.CASCADE, primary_key=True)
	class Meta:
		app_label = 'test'

class BarRefModel(BinderModel):
	bar = models.OneToOneField(BarModel, on_delete=models.CASCADE, primary_key=True)
	class Meta:
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
		urls_module.urlpatterns = [url(r'^', include(r.urls))]

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
		urls_module.urlpatterns = [url(r'^', include(r.urls))]

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
		urls_module.urlpatterns = [url(r'^', include(r.urls))]

		self.assertFalse(is_valid_path('/foo/', urls_module))
		self.assertTrue(is_valid_path('/foo/1/', urls_module))

		self.assertTrue(is_valid_path('/bar/', urls_module))
		self.assertFalse(is_valid_path('/bar/1/', urls_module))


	def test_register_view_slug_pk(self):

		class ParentView(ModelView):
			pass

		class BazView(ParentView):
			model = BazModel
			route = 'baz'

		r = Router()
		r.register(ParentView)
		urls_module.urlpatterns = [url(r'^', include(r.urls))]

		self.assertTrue(is_valid_path('/baz/', urls_module))

		self.assertTrue(is_valid_path('/baz/foo/', urls_module))
		self.assertTrue(is_valid_path('/baz/bar/', urls_module))
		self.assertTrue(is_valid_path('/baz/baz/', urls_module))

		self.assertFalse(is_valid_path('/baz/@/', urls_module))
		self.assertFalse(is_valid_path('/baz/foo/bar/', urls_module))

		self.assertFalse(is_valid_path('/bar/', urls_module))

		self.assertFalse(is_valid_path('/bar/foo/', urls_module))
		self.assertFalse(is_valid_path('/bar/bar/', urls_module))
		self.assertFalse(is_valid_path('/bar/baz/', urls_module))

		self.assertFalse(is_valid_path('/bar/1/', urls_module))
		self.assertFalse(is_valid_path('/bar/12345/', urls_module))
		self.assertFalse(is_valid_path('/bar/blaat/', urls_module))


	def test_register_view_custom_pk_re(self):

		class ParentView(ModelView):
			pass

		class FooView(ParentView):
			model = FooModel
			route = 'foo'
			route_pk_regex = r'foo|bar|baz'
			route_pk_parser = str

		r = Router()
		r.register(ParentView)
		urls_module.urlpatterns = [url(r'^', include(r.urls))]

		self.assertTrue(is_valid_path('/foo/', urls_module))

		self.assertTrue(is_valid_path('/foo/foo/', urls_module))
		self.assertTrue(is_valid_path('/foo/bar/', urls_module))
		self.assertTrue(is_valid_path('/foo/baz/', urls_module))

		self.assertFalse(is_valid_path('/foo/1/', urls_module))
		self.assertFalse(is_valid_path('/foo/12345/', urls_module))
		self.assertFalse(is_valid_path('/foo/blaat/', urls_module))

		self.assertFalse(is_valid_path('/bar/', urls_module))

		self.assertFalse(is_valid_path('/bar/foo/', urls_module))
		self.assertFalse(is_valid_path('/bar/bar/', urls_module))
		self.assertFalse(is_valid_path('/bar/baz/', urls_module))

		self.assertFalse(is_valid_path('/bar/1/', urls_module))
		self.assertFalse(is_valid_path('/bar/12345/', urls_module))
		self.assertFalse(is_valid_path('/bar/blaat/', urls_module))

	def test_register_view_foreign_key_pk(self):

		class ParentView(ModelView):
			pass

		class FooRefView(ParentView):
			model = FooRefModel
			route = 'foo_ref'

		print('Foreign Key pk')
		print(FooRefView.pk_regex)
		print(FooRefView.pk_parser)

		r = Router()
		r.register(ParentView)
		urls_module.urlpatterns = [url(r'^', include(r.urls))]

		self.assertTrue(is_valid_path('/foo_ref/1/', urls_module))
		self.assertTrue(is_valid_path('/foo_ref/12345/', urls_module))

		self.assertFalse(is_valid_path('/foo_ref/foo/', urls_module))
		self.assertFalse(is_valid_path('/foo_ref/bar/', urls_module))

	def test_register_view_one_to_one_pk(self):

		class ParentView(ModelView):
			pass

		class BarRefView(ParentView):
			model = BarRefModel
			route = 'bar_ref'

		print('One to One pk')
		print(BarRefView.pk_regex)
		print(BarRefView.pk_parser)

		r = Router()
		r.register(ParentView)
		urls_module.urlpatterns = [url(r'^', include(r.urls))]

		self.assertTrue(is_valid_path('/bar_ref/1/', urls_module))
		self.assertTrue(is_valid_path('/bar_ref/12345/', urls_module))

		self.assertFalse(is_valid_path('/bar_ref/foo/', urls_module))
		self.assertFalse(is_valid_path('/bar_ref/bar/', urls_module))
