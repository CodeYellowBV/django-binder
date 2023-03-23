from django.db import models
from binder.models import BinderModel

"""
Unfortunately people in the zoo cannot pay everything by just the people visiting, so they depend on donors. There are some
very wealthy donors in this detabase. They are a bit scared to give their money away. So they sponsor at most one zoo.

Some donors however do not feel like giving money to any zoo at all.

What is important about donors is that in general we want a list ordered by which zoo they are donating for.

Note that this creates a nullable join in normal select queries, which triggers some very interesting edge cases
"""
class Donor(BinderModel):
	zoo = models.ForeignKey('Zoo', null=True, blank=True, on_delete=models.SET_NULL)
	name = models.TextField()

	class Meta(BinderModel.Meta):
		ordering = ('zoo',)

