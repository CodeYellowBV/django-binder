# Using models

## Extra fields

Binder provides some extra fields you can use for your models.

- `UpperCaseCharField`
- `LowerCaseCharField`

```python
from binder.models import BinderModel, UpperCaseCharField

class Animal(BinderModel):
	name = UpperCaseCharField()
```

### BinderFileField / BinderImageField


When a model has a file attached to it, the url normally becomes something like this:

`/api/some_model/123/some_file/`

In this case, the frontend has to hit the file endpoint to know if the file has changes. When using BinderFileField / BinderImageField, the url will contain extra info encoded in the url:

`/api/some_model/123/some_file/?h=0759a35e9983833ce52fe433d2326addf400f344&content_type=image/jpeg&filename=sample.pdf`

| key | description |
| - | - |
| `h` | The sha1 of the file. You can use this to check if the file has changed. |
| `content_type` | The content type of the file. |
| `filename` |  The name of the file. This can be used for the `download` attribute of an anchor. |

You can upgrade from default Django FileField / ImageField as follows:

```
# FileField
picture = models.FileField(blank=True, null=True) # Old
picture = BinderFileField(blank=True, null=True) # New

# ImageField
picture = models.ImageField(blank=True, null=True) # Old
picture = BinderImageField(blank=True, null=True) # New
```

Then, run `manage.py makemigrations` to add the required migrations.

---
> **_IMPORTANT:_** If you upgrade from an older BinderFileField to one that also includes filename, you unfortunately need to manually change your old migration file before you run makemigrations:

```
migrations.AlterField(
    ...
    # Old: without specifying `max_length=200`
    # field=binder.models.BinderImageField(blank=True, upload_to='document/file/%Y/%m/%d/'),

    # Manual change: add `max_length=200`
    field=binder.models.BinderImageField(blank=True, upload_to='document/file/%Y/%m/%d/', max_length=200),
)
```
When manually changed, Django will then correctly make new migration files.

---

#### Extra options

* `allowed_extensions` (default: `None`): limits the file extensions that can be uploaded
* `serve_directly` (default: `False`): delegates file serving to the web server (e.g. nginx)
  * Requires configuration of `INTERNAL_MEDIA_HEADER` and `INTERNAL_MEDIA_LOCATION` in `settings.py`

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

You can also exclude specific fields from history tracking by setting `exclude_history_fields`:

```python
from binder.models import BinderModel

class Animal(BinderModel):
	name = models.TextField()
	secret_notes = models.TextField()  # This field won't be tracked
	
	class Binder:
		history = True
		exclude_history_fields = ['secret_notes']
```

You can also include reverse relations in history tracking by setting `include_reverse_relations`. This is useful if you want to track when related objects are created or deleted on the parent model.

```python
class Zoo(BinderModel):
	# ...

	class Binder:
		history = True
		include_reverse_relations = ['animals']

class Animal(BinderModel):
	zoo = models.ForeignKey(Zoo, related_name='animals', on_delete=models.CASCADE)

	# History on the child model is not required for this to work
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

### Showing display names for foreign keys

By default, whenever a foreign key field is changed (reassigned), the old ID and the new ID are shown in the history.

If you want to show something else (e.g. the name instead of the ID),

you need to override the `format_instance_for_history` method on the target model, for instance if your target model is `ContactPerson`:

```python
@classmethod
def format_instance_for_history(cls, id: int):
	try:
		return ContactPerson.objects.get(id=id).name
	except:
		return 'deleted? ' + str(id)
```
