# Using models

## Extra fields

Binder provides some extra fields you can use for your models.

- `CaseInsensitiveCharField`
- `UpperCaseCharField`
- `LowerCaseCharField`

```python
from binder.models import BinderModel, CaseInsensitiveCharField

class Animal(BinderModel):
	name = models.CaseInsensitiveCharField()
```

## Enums

Binder makes it easy to use enums.

TODO: what exactly is the advantage of this over using `choices` directly?

```python
from binder.models import BinderModel, ChoiceEnum

class Animal(BinderModel):
	GENDER = ChoiceEnum('male', 'female')

	gender = models.CharField(max_length=6, choices=GENDER.choices())
```

## History

Binder can keep track of all mutations in a model.
Enabling this is very easy;

```python
from binder.models import BinderModel

class Animal(BinderModel):
	...

	class Binder:
		history = True
```

Saving the model will result in one changeset. With a changeset, the user that changed it and datetime is saved.

A changeset contains changes for each field that has been changed to a new value. For each change, you can see the old value and the new value.

Saving a new model also results in a changeset. It is possible to detect if a model is new by searching for the `id` column where the old value is `null`.

### Viewing the history

There are two ways to view the history; through the database, and via a built-in API endpoint.

Via the database, you can use the table `binder_changeset` to find a changeset you want to check. Note the ID, and open the `binder_change` table to view the exact changes.

To view the history through an API endpoint, add the following to your `urls.py`;

```python
import binder.views

urlpatterns = [
	url(r'^history/$',, binder.views.debug_changesets_24h, name='history'),
]
```

TODO: verify if this actually works.

Also make sure that `ENABLE_DEBUG_ENDPOINTS = True` in your `settings.py`.
