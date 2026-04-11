from binder.models import BinderModel, DateTimeRangeField


# This is just a mock class to test DateTimeRangeField
class TimeTable(BinderModel):
	daterange = DateTimeRangeField(null=True)
