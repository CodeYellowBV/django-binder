from django.db import models

import binder.models
from binder.models import BinderModel

class ContactPerson(BinderModel):
	name = models.TextField(unique=True)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)
