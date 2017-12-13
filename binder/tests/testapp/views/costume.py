from binder.views import ModelView

from ..models import Costume

class CostumeView(ModelView):
	model = Costume

	def get_rooms_for_user(user):
		return [
			{'costume': c}
			for c in user.costumes
		]
