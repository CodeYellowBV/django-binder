from django.db import models

from .animal import Animal


class Lion(Animal):

	mane_magnificence = models.SmallIntegerField()
