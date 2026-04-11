
from binder.views import ModelView

from ..models import Animal, Donor


# From the api docs
class DonorView(ModelView):
	model = Donor
