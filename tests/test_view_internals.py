from django.test import TestCase
from .testapp.views import ZooView

class ViewInternalsTest(TestCase):
	def setUp(self):
		self.view = ZooView()

	def test_obj_diff_on_dicts_with_nulls(self):
		diff = self.view._obj_diff({'foo': {'bar': 'whatever'}}, {'foo': None}, 'lala')
		self.assertEqual(["changed lala.foo: {'bar': 'whatever'} -> None"], diff)
