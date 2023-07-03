from binder.views import ModelView

from ..models import Nickname, Zoo, NullableNickname


class NicknameView(ModelView):
	model = Nickname

	virtual_relations = {
		'source': {
			'model': Zoo,
			'annotation': '_virtual_source',
			'singular': True
		},
	}

	def _virtual_source(self, request, pks, q):

		nicknames =  Nickname.objects.filter(pk__in=pks)

		res = {}
		for nickname in nicknames:
			res[nickname.pk] = [
				nickname.animal.zoo_of_birth.pk
			]


		return res

class NullableNicknameView(ModelView):
	model = NullableNickname


