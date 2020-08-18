from django.db import transaction
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils.translation import ugettext as _
from django.contrib.auth.models import Group, Permission, ContentType


def parse_perm(perm_name):
	try:
		app, other = perm_name.split('.')
		if ':' in other:
			action_and_model, scope = other.split(':')
		else:
			action_and_model = other
		action, model = action_and_model.split('_')

		content_type = ContentType.objects.get(
			app_label=app,
			model=model,
		)

		return Permission.objects.get(
			content_type=content_type,
			codename=other,
		)
	except ContentType.DoesNotExist:
		raise RuntimeError(
			'Model for ' + perm_name + ' does not exist'
		)
	except Permission.DoesNotExist:
		raise RuntimeError(
			'Permission ' + perm_name + ' does not exist'
		)


class Command(BaseCommand):
	help = _('Define user groups/roles to their required specifications')

	@transaction.atomic
	def handle(self, *args, **options):
		# Collect all permissions that this command should ignore
		# We only need the pks
		ignored_perm_pks = {
			parse_perm(perm_name).pk
			for perm_name in getattr(settings, 'GROUP_IGNORED_PERMISSIONS', [])
		}

		# Delete any stale groups
		Group.objects.exclude(name__in=settings.GROUP_PERMISSIONS).delete()

		for group_name in settings.GROUP_PERMISSIONS:
			group, _ = Group.objects.get_or_create(name=group_name)

			# Get all groups that are contained by this group
			groups_to_expand = [group_name]
			groups = set()
			while groups_to_expand:
				group_name = groups_to_expand.pop()
				if group_name not in groups:
					groups.add(group_name)
					groups_to_expand.extend(
						getattr(settings, 'GROUP_CONTAINS', {})
						.get(group_name, [])
					)

			# Collect all permissions for these groups
			perms = {
				parse_perm(perm_name)
				for group_name in groups
				for perm_name in settings.GROUP_PERMISSIONS[group_name]
			}
			# Add all permissions that are ignored by this command that the
			# group already has
			perms.update(group.permissions.filter(pk__in=ignored_perm_pks))

			group.permissions.set(perms)
