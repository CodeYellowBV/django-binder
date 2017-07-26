from binder.views import ModelView

from ..models import ZooEmployee

# From the api docs
class ZooEmployeeView(ModelView):
	model = ZooEmployee
