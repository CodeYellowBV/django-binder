from binder.views import ModelView

from ..models import Nickname

class NicknameView(ModelView):
	model = Nickname
