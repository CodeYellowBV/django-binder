from django.db import models
from django.conf import settings

from ...models import BinderModel


class MyFilter(BinderModel):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='+',
    )
    view = models.TextField()
    name = models.TextField()
    params = models.JSONField()
    columns = models.JSONField(default=list, blank=True)
    default = models.BooleanField(default=False)

    class Meta(BinderModel.Meta):
        unique_together = [('user', 'view', 'name')]
