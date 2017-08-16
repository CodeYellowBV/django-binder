from binder.views import ModelView
from binder.plugins.views import ImageView

from ..models import Picture

# From the api docs
class PictureView(ModelView, ImageView):
	model = Picture

