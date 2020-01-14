from django.db import models
from binder.models import BinderModel


class Country(BinderModel):
    name = models.TextField(unique=True)
