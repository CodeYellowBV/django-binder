from django.db import models
from django.contrib.postgres.fields import JSONField
from django.conf import settings

from ...models import BinderModel


class MyFilter(BinderModel):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='+',
    )
    view = models.TextField()
    name = models.TextField()
    params = JSONField()
    default = models.BooleanField(default=False)

    class Meta(BinderModel.Meta):
        unique_together = [('user', 'view', 'name')]
