from django.test import TestCase

from django.db import models
from binder.models import BinderModel
from binder.router import Router
from binder.views import ModelView, RelatedModel


class AbstractBarView(ModelView):
	pass

class BarModel(BinderModel):
	baz = models.TextField()


class FooModel(BinderModel):
	bar = models.ForeignKey(BarModel, related_name=None, on_delete=models.CASCADE, default=None)


class BarView(AbstractBarView):
	model = BarModel


class FooView(AbstractBarView):
	model = FooModel



class TestNoneRelatedName(TestCase):
	"""
	related_name can be None for a field. Make sure that this doesn't break the application
	"""

	def test_simple_follow_related(self):
		"""
		previously, this threw the following error:

		File "/binder/binder/views.py", line 540, in _follow_related
		if '+' in related_field: # Skip missing related fields
		TypeError: argument of type 'NoneType' is not iterable

		:return:
		"""
		router = Router()
		router.register(AbstractBarView)

		view = FooView()
		view.router = router
		result = view._follow_related(['bar'])

		self.assertIsInstance(result[0], RelatedModel)
		self.assertIsNone(result[0].reverse_fieldname)
		self.assertEquals('bar', result[0].fieldname)
		self.assertEqual(BarModel, result[0].model)
