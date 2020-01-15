from django.db import models
from binder.models import BinderModel


class Country(BinderModel):
    name = models.CharField(unique=True, max_length=100)
