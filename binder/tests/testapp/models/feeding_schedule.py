from django.db import models
from binder.models import BinderModel


# Zoos are really secretive about their feeding schedules
class FeedingSchedule(BinderModel):
    animal = models.OneToOneField('Animal', on_delete=models.CASCADE, related_name='feeding_schedule')
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return 'feeding schedule %d: %s (for %s)' % (self.pk or 0, self.description, self.animal)
