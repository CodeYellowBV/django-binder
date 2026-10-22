from django.db import models
from binder.models import BinderModel
import os


def choose_pk_field():
    if 'DJANGO_VERSION' in os.environ and tuple(map(int, os.environ['DJANGO_VERSION'].split('.'))) < (5, 2, 0):
        return models.AutoField(primary_key=True)
    else:
        return models.CompositePrimaryKey('contact_person', 'date')

class ContactPersonRating(BinderModel):
    pk = choose_pk_field()
    contact_person = models.ForeignKey('ContactPerson', on_delete=models.CASCADE, related_name='ratings')
    date = models.DateField()
    rating = models.IntegerField()
    source_city = models.OneToOneField('City', on_delete=models.SET_NULL, blank=True, null=True, related_name='rating')

    class Binder:
        history = True
