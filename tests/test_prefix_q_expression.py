from unittest import TestCase

from django.db.models import Q

from binder.views import prefix_q_expression
from binder.permissions.views import is_q_child_equal

from .testapp.models import Animal


class TestPrefixQExpression(TestCase):

	def test_simple_prefix(self):
		self.assertTrue(is_q_child_equal(
			prefix_q_expression(Q(foo=1), 'prefix'),
			Q(prefix__foo=1),
		))

	def test_nested_prefix(self):
		self.assertTrue(is_q_child_equal(
			prefix_q_expression(Q(foo=1) & ~Q(bar=2) | Q(baz=3), 'prefix'),
			Q(prefix__foo=1) & ~Q(prefix__bar=2) | Q(prefix__baz=3),
		))

	def test_prefix_identity(self):
		self.assertTrue(is_q_child_equal(
			prefix_q_expression(Q(pk__in=[]), 'prefix'),
			Q(pk__in=[]),
		))

	def test_antiprefix_field(self):
		self.assertTrue(is_q_child_equal(
			prefix_q_expression(Q(name='Apenheul', animals__name='Bokito'), 'zoo', 'animals', Animal),
			Q(zoo__name='Apenheul', name='Bokito'),
		))

	def test_antiprefix_no_field(self):
		self.assertTrue(is_q_child_equal(
			prefix_q_expression(Q(name='Apenheul', animals=1), 'zoo', 'animals', Animal),
			Q(zoo__name='Apenheul', pk=1),
		))

	def test_antiprefix_pk(self):
		self.assertTrue(is_q_child_equal(
			prefix_q_expression(Q(name='Apenheul', animals__pk=1), 'zoo', 'animals', Animal),
			Q(zoo__name='Apenheul', pk=1),
		))

	def test_antiprefix_modifier(self):
		self.assertTrue(is_q_child_equal(
			prefix_q_expression(Q(name='Apenheul', animals__in=[1, 2, 3]), 'zoo', 'animals', Animal),
			Q(zoo__name='Apenheul', pk__in=[1, 2, 3]),
		))
