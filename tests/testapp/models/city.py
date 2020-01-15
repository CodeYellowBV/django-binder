from django.db import models
from binder.models import BinderModel


class City(BinderModel):
    country = models.ForeignKey('Country', null=False, blank=False,  related_name='cities', on_delete=models.CASCADE)
    name = models.TextField(unique=True)


class CityState(BinderModel):
    """
    City states are like cities, but they can also decide that they do not belong to a country
    """
    country = models.ForeignKey('Country', null=True, blank=True, related_name='city_states', on_delete=models.SET_NULL)
    name = models.TextField(unique=True)


class PermanentCity(BinderModel):
    """
    Some cities are indestrucable. Even if we delete them, they are not really deleted, and can be rerissen from their ashes
    """
    country = models.ForeignKey('Country', null=False, blank=False,  related_name='permanent_cities', on_delete=models.CASCADE)
    name = models.TextField(unique=True)
    deleted = models.BooleanField()