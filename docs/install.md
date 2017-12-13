# Installing

Binder requires Python 3+.

The preferred way to install Binder is with pip.

```
pip install git+ssh://git@github.com/CodeYellowBV/django-binder.git@1.0
```

To get started, a couple of files need to be changed from a standard Django application.

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

router = binder.router.Router().register(binder.views.ModelView)

urlpatterns = [
	url(r'^', include(router.urls)),
	url(r'^', binder.views.api_catchall, name='catchall'),
]

binder.models.install_history_signal_handlers(binder.models.BinderModel)
```
