from django.db.models import Count, Value

from binder.views import ModelView

from ..models import Animal

# From the api docs
class AnimalView(ModelView):
	model = Animal
	m2m_fields = ['costume']
	searches = ['name__icontains']
	transformed_searches = {'zoo_id': int}

	stats = {
		'without_caretaker': {
			'expr': Count(Value(1)),
			'filters': {
				'caretaker:isnull': 'true',
			},
		},
		'by_zoo': {
			'expr': Count(Value(1)),
			'group_by': 'zoo.name',
		},
	}
