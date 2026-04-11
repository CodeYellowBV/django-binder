from django.test import TestCase

from binder.views import split_path, join_path


class PathTest(TestCase):

	def _test_path(self, path_str, path_keys):
		with self.subTest('str to keys'):
			self.assertEqual(tuple(split_path(path_str)), path_keys)
		with self.subTest('keys to str'):
			self.assertEqual(join_path(path_keys), path_str)

	def test_single_key(self):
		self._test_path('foo', ('foo',))

	def test_multiple_keys(self):
		self._test_path('foo.bar.baz', ('foo', 'bar', 'baz'))

	def test_escape_dot(self):
		self._test_path('foo.bar\\.baz', ('foo', 'bar.baz'))

	def test_escape_backslash(self):
		self._test_path('foo.bar\\\\baz', ('foo', 'bar\\baz'))
