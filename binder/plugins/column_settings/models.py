from django.db import models
from django.conf import settings

from ...models import BinderModel


class ColumnSetting(BinderModel):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='+',
    )
    view = models.TextField()
    columns = models.JSONField()
    class Meta(BinderModel.Meta):
        unique_together = [('user', 'view')]
