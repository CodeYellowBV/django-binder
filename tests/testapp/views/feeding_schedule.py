from binder.views import ModelView

from ..models import FeedingSchedule

class FeedingScheduleView(ModelView):
	model = FeedingSchedule
