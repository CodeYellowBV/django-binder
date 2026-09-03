from datetime import timedelta

from django.db import models

from binder.models import BinderModel


class Truck(BinderModel):
	name = models.TextField(max_length=64)
	truck_loading_time = models.DurationField(default=timedelta(minutes=30))
	maintenance_time = models.DurationField(null=True, blank=True)
