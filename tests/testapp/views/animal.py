from django.db.models import F

from binder.views import ModelView

from ..models import Animal

# From the api docs
class AnimalView(ModelView):
	model = Animal
	m2m_fields = ['costume']
	searches = ['name__icontains']
	transformed_searches = {'zoo_id': int}

	virtual_relations = {
		'neighbours': {
			'model': Animal,
			'annotation': '_virtual_neighbours',
			'singular': False,
		},
	}

	def _virtual_neighbours(self, request, pks, q):
		neighbours = {}
		for pk, neighbour_pk in (
			Animal.objects
			.filter(q, zoo__animals__pk__in=pks)
			.values_list('zoo__animals__pk', 'pk')
		):
			if neighbour_pk != pk:
				neighbours.setdefault(pk, []).append(neighbour_pk)
		return neighbours
