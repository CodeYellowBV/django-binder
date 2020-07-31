from binder.views import ModelView

from ..models import Nickname

class NicknameView(ModelView):
	model = Nickname


from binder.views import ModelView

from ..models import NullableNickname

class NullableNicknameView(ModelView):
	model = NullableNickname
