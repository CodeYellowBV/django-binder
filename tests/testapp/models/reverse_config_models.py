from django.db import models
from binder.models import BinderModel


class ReverseParent(BinderModel):
    name = models.CharField(max_length=64)

    class Binder:
        history = True
        include_reverse_relations = ["children"]

    class Meta:
        app_label = "testapp"


class ReverseChild(BinderModel):
    name = models.CharField(max_length=64)
    parent = models.ForeignKey(
        ReverseParent,
        on_delete=models.CASCADE,
        related_name="children",
        null=True,
        blank=True,
    )

    class Binder:
        history = True

    class Meta:
        app_label = "testapp"


class ReverseParentNoChildHistory(BinderModel):
    name = models.CharField(max_length=64)

    class Binder:
        history = True
        include_reverse_relations = ["children"]

    class Meta:
        app_label = "testapp"


class ReverseChildNoHistory(BinderModel):
    name = models.CharField(max_length=64)
    parent = models.ForeignKey(
        ReverseParentNoChildHistory,
        on_delete=models.CASCADE,
        related_name="children",
        null=True,
        blank=True,
    )

    class Binder:
        history = False

    class Meta:
        app_label = "testapp"
