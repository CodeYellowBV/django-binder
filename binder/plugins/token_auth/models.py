from os import urandom

from django.db import models
from django.conf import settings
from django.utils import timezone

from binder.models import BinderModel


def generate_token():
	return urandom(16).hex()


class Token(BinderModel):
	"""
	A Token is a proof of authentication for a certain user.

	A token expires based on the settings BINDER_TOKEN_EXPIRE_TIME, and
	BINDER_TOKEN_EXPIRE_BASE.
	BINDER_TOKEN_EXPIRE_TIME determines how long it takes for a token to
	expire, if set to None a token can never expire.
	BINDER_TOKEN_EXPIRE_BASE determines which field to look at for the time of
	the expire calculation.
	"""

	user = models.ForeignKey(
		settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
		related_name='tokens',
	)
	token = models.CharField(default=generate_token, unique=True, max_length=32)
	created_at = models.DateTimeField(auto_now_add=True)
	last_used_at = models.DateTimeField(auto_now=True)

	@property
	def expires_at(self):
		expire_time = getattr(settings, 'BINDER_TOKEN_EXPIRE_TIME', None)

		if expire_time is None:
			return None

		base = getattr(self, settings.BINDER_TOKEN_EXPIRE_BASE)

		return base + expire_time

	@property
	def expired(self):
		expires_at = self.expires_at

		if expires_at is None:
			return False

		return timezone.now() > expires_at

	class Meta(BinderModel.Meta):
		permissions = [
			('manage_token', 'Manage authorization tokens.'),
		]
