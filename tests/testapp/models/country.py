from django.db import models
from binder.models import BinderModel


class Country(BinderModel):
    push_websocket_updates_upon_save = True
    name = models.CharField(unique=True, max_length=100)
