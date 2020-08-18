from django.core import management
from django.contrib.auth.models import Group, ContentType, Permission
from django.test import TestCase, override_settings


class TestDefineGroups(TestCase):

	def _test_define_groups(self, permissions):
		management.call_command('define_groups')

		seen_groups = set()
		for group in Group.objects.all():
			seen_groups.add(group.name)
			group_permissions = {
				f'{perm.content_type.app_label}.{perm.codename}'
				for perm in group.permissions.all()
			}
			self.assertEqual(group_permissions, set(permissions[group.name]))

		self.assertEqual(seen_groups, set(permissions))

	@override_settings(
		GROUP_PERMISSIONS={},
		GROUP_CONTAINS={},
		GROUP_IGNORED_PERMISSIONS=[],
	)
	def test_no_groups(self):
		self._test_define_groups({})

	@override_settings(
		GROUP_PERMISSIONS={
			'caretaker': [
				'testapp.view_animal',
				'testapp.add_animal',
				'testapp.change_animal',
				'testapp.delete_animal',
			],
			'hr': [
				'testapp.view_zooemployee',
				'testapp.add_zooemployee',
				'testapp.change_zooemployee',
				'testapp.delete_zooemployee',
			],
			'manager': {},
		},
		GROUP_CONTAINS={
			'manager': ['caretaker', 'hr'],
		},
		GROUP_IGNORED_PERMISSIONS=[
			'testapp.view_country',
		],
	)
	def test_basic_groups(self):
		for ct in ContentType.objects.all():
			print('CONTENT TYPE', ct.app_label, ct.model)

		PERMS = {
			'caretaker': [
				'testapp.view_animal',
				'testapp.add_animal',
				'testapp.change_animal',
				'testapp.delete_animal',
			],
			'hr': [
				'testapp.view_zooemployee',
				'testapp.add_zooemployee',
				'testapp.change_zooemployee',
				'testapp.delete_zooemployee',
			],
			'manager': [
				'testapp.view_animal',
				'testapp.add_animal',
				'testapp.change_animal',
				'testapp.delete_animal',
				'testapp.view_zooemployee',
				'testapp.add_zooemployee',
				'testapp.change_zooemployee',
				'testapp.delete_zooemployee',
			],
		}
		self._test_define_groups(PERMS)

		# Test ignored permission remains after define groups
		manager = Group.objects.get(name='manager')
		view_country = Permission.objects.get(
			content_type__app_label='testapp',
			codename='view_country',
		)
		manager.permissions.add(view_country)

		self._test_define_groups({
			**PERMS,
			'manager': [
				*PERMS['manager'],
				'testapp.view_country',
			],
		})
