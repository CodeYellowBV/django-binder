# API

Binder automatically exposes a fairly powerful API for all your models.

## Registering an API endpoint

We’ll use this example model, added in `models.py`.

```python
from binder.models import BinderModel, CaseInsensitiveCharField

class Animal(BinderModel):
	name = models.CaseInsensitiveCharField()
```

In `views.py`, add the following:

```python
from binder.views import ModelView

from .models import Animal


class AnimalView(ModelView):
	model = Animal
```

And that’s it!

## Using an API endpoint

After registering the model, a couple of new routes are at your disposal:

- `GET api/animal` - view collection of models
- `GET api/animal/[id]` - view a specific model
- `POST api/animal` - create a new model
- `PUT api/animal/[id]` - update a specific model
- `DELETE api/animal/[id]` - delete a specific model

### Filtering on the collection

#### Simple field filtering
It is possible to filter on a field. The simplest example is `api/animal?.name=Scooby-Doo`. This will return the models where the name of the animal is exactly `Scooby-Doo`.

To use a partial case-insensitive match, you can use `api/animal?.name:icontains`. Behind the scenes, Djangos [Field Lookup](https://docs.djangoproject.com/en/1.10/ref/models/querysets/#field-lookups) are used. This means that other lookups like `in` and `startswith` also work!

Note that currently, it is not possible to search on many2many fields.

#### More advanced searching

Sometimes you want to search on multiple fields at once.

```python
class AnimalView(ModelView):
	model = Animal
	searches = ['id__startswith', 'name__icontains']
```

After adding the above, you can search on a model by using `api/animal?search=12`, or `api/animal?search=Scooby`.

### Saving a model

TODO:

- m2m
- `with`
- permissions
-- change permission model

## Hacking the API

TODO:

- how to add custom saving logic
- how to add custom viewing logic
- how to add custom filtering logic
- how to add custom routes
