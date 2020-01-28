from django.db import transaction
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils.translation import ugettext as _
from django.contrib.auth.models import Group, Permission, ContentType


class Command(BaseCommand):
    help = _('Define user groups/roles to their required specifications')

    @transaction.atomic
    def handle(self, *args, **options):
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
                    groups_to_expand.extend(settings.GROUP_CONTAINS[group_name])

            # Collect all permissions for these groups
            perms = set()
            for group_name in groups:
                for perm_name in settings.GROUP_PERMISSIONS[group_name]:
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

                        perm = Permission.objects.get(
                            content_type=content_type,
                            codename=other,
                        )
                        perms.add(perm)
                    except ContentType.DoesNotExist:
                        raise RuntimeError(
                            'Model for ' + perm_name + ' does not exist'
                        )
                    except Permission.DoesNotExist:
                        raise RuntimeError(
                            'Permission ' + perm_name + ' does not exist'
                        )

            group.permissions.set(perms)
