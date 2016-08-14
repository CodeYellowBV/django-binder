# Installing

TODO: explain how to install with pip

It is necessary to change a couple of files from a standard Django application.

In `settings.py`, add the following:

```python
INSTALLED_APPS = [
	...
	'binder',
]

CSRF_FAILURE_VIEW = 'binder.router.csrf_failure'
```

In `urls.py`, add the following:

```python
from django.conf.urls import url, include

import binder.router
import binder.views
import binder.models

binder.router.Router().register(binder.views.ModelView)

urlpatterns = [
	url(r'^', include(binder.router.Router().urls)),
	url(r'^', binder.views.api_catchall, name='catchall'),
]

binder.models.install_m2m_signal_handlers(binder.models.BinderModel)
```
