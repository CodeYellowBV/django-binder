from django.conf.urls import url, include

import binder.router # noqa
import binder.websocket # noqa
import binder.views # noqa
import binder.history # noqa
import binder.models # noqa
from .views import animal, caretaker, costume, custom, zoo, contact_person, gate # noqa

router = binder.router.Router().register(binder.views.ModelView)
room_controller = binder.websocket.RoomController().register(binder.views.ModelView)

urlpatterns = [
	url(r'^custom/route', custom.custom, name='custom'),
	url(r'^', include(router.urls)),
	url(r'^', binder.views.api_catchall, name='catchall'),
]

# FIXME: Hmm, this is a bit hackish. Especially here. But where else?
binder.models.install_history_signal_handlers(binder.models.BinderModel)
