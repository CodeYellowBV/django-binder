from django.contrib.postgres.fields import ArrayField, JSONField
from django.db import models
from binder.models import BinderModel, ChoiceEnum


# Zoos are really secretive about their feeding schedules
class FeedingSchedule(BinderModel):
    FOODS = ChoiceEnum('meat', 'corn', 'oats', 'hay', 'bugs')

    animal = models.OneToOneField('Animal', on_delete=models.CASCADE, related_name='feeding_schedule')
    description = models.TextField(blank=True, null=True)
    foods = ArrayField(models.TextField(choices=FOODS.choices()), blank=True, default=[])
    schedule_details = JSONField(blank=True, default=[])

    def __str__(self):
        return 'feeding schedule %d: %s (for %s)' % (self.pk, self.description, self.animal)
