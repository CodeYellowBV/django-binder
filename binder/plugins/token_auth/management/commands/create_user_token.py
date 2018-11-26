from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import ugettext as _
from django.contrib.auth import get_user_model
from django.db import transaction

from binder.plugins.token_auth.models import Token

class Command(BaseCommand):
	help = _('Create a fresh token for the given user')

	def add_arguments(self, parser):
		parser.add_argument('username', type=str)
		parser.add_argument('-k', '--keep-existing', action='store_true', help='Keep existing tokens (by default, the new token will replace any existing ones)')


	@transaction.atomic
	def handle(self, *args, **options):
		User = get_user_model()

		try:
			user = User.objects.get(**{User.USERNAME_FIELD: options['username']})
		except User.DoesNotExist:
			raise CommandError(_('User with username "%s" does not exist') % options['username'])

		if not options['keep_existing']:
			Token.objects.filter(user=user).delete() # If any

		token = Token(user=user)
		token.save()

		self.stdout.write(_("Generated token for user %(user)s: %(token)s.") % {'user': user, 'token': token.token})
		self.stdout.write(_("User now has %(count)d token(s).") % {'count': Token.objects.filter(user=user).count()} )
