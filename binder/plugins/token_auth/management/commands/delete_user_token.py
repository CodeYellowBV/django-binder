from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import ugettext as _
from django.contrib.auth.models import User
from django.db import transaction

from binder.plugins.token_auth.models import Token

class Command(BaseCommand):
	help = _('Delete all tokens for the given user')

	def add_arguments(self, parser):
		parser.add_argument('username', type=str)


	@transaction.atomic
	def handle(self, *args, **options):
		try:
			user = User.objects.get(username=options['username'])
		except User.DoesNotExist:
			raise CommandError(_('User with username "%s" does not exist') % options['username'])

		counts = Token.objects.filter(user=user).delete()

		self.stdout.write(_("Deleted %(count)d token(s) for user %(user)s.") % {'count': counts[0], 'user': user} )
