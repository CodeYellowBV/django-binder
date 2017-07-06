from django.conf.urls import url, include

import binder.router
import binder.views
import binder.history
import binder.models
from .views import animal, caretaker, costume, custom, zoo, contact_person, gate

router = binder.router.Router().register(binder.views.ModelView)

urlpatterns = [
	url(r'^custom/route', custom.custom, name='custom'),
	url(r'^', include(router.urls)),
	url(r'^', binder.views.api_catchall, name='catchall'),
]

# FIXME: Hmm, this is a bit hackish. Especially here. But where else?
binder.models.install_m2m_signal_handlers(binder.models.BinderModel)
