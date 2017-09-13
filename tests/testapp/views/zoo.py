from binder.views import ModelView

from ..models import Zoo

# From the api docs
class ZooView(ModelView):
	m2m_fields = ['animals', 'contacts', 'zoo_employees']
	model = Zoo
	file_fields = ['floor_plan']
	shown_properties = ['animal_count']
