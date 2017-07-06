from django.db import models

import binder.models
from binder.models import BinderModel

class ContactPerson(BinderModel):
	name=models.TextField(unique=True)
