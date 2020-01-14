from django.db import models
from binder.models import BinderModel


class City(BinderModel):
    country = models.ForeignKey('Country', null=False, blank=False,  related_name='cities', on_delete=models.CASCADE)
    name = models.TextField(unique=True)
