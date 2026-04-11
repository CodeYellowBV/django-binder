from binder.views import ModelView

from ..models import WebPage

# From the api docs
class WebPageView(ModelView):
	model = WebPage
