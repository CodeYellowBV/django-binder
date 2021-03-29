# API

Binder automatically exposes a fairly powerful API for all your models.

## Registering an API endpoint

We’ll use this example model, added in `models.py`.

```python
from binder.models import BinderModel
from django.db import models

class Animal(BinderModel):
	name = models.TextField()
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

- `GET api/animal/` - view collection of models
- `GET api/animal/[id]/` - view a specific model
- `POST api/animal/` - create a new model
- `PUT api/animal/` - create or update (nested) models
- `PUT api/animal/[id]/` - update a specific model
- `DELETE api/animal/[id]/` - delete a specific model
- `POST api/animal/[id]/` - undelete a specific model

### Filtering on the collection

#### Simple field filtering
It is possible to filter on a field. The simplest example is `api/animal?.name=Scooby-Doo`. This will return the models where the name of the animal is exactly `Scooby-Doo`.

To use a partial case-insensitive match, you can use `api/animal?.name:icontains`. Behind the scenes, Djangos [Field Lookup](https://docs.djangoproject.com/en/1.10/ref/models/querysets/#field-lookups) is used. This means that other lookups like `in` and `startswith` also work!

Note that currently, it is not possible to search on many-to-many fields.

#### More advanced searching

Sometimes you want to search on multiple fields at once.

```python
class AnimalView(ModelView):
	model = Animal
	searches = ['id__startswith', 'name__icontains']
```

After adding the above, you can search on a model by using `api/animal?search=12`, or `api/animal?search=Scooby`.

### Ordering the collection
Ordering is a simple matter of enumerating the fields in the `order_by` query parameter, eg. `api/animal?order_by=name`.  If you want to make the ordering stable when there are multiple animals sharing the same name, you can separate with commas like `api/animal?order_by=name,id`.  The results will be sorted on name, and where the name is the same, they'll be sorted by `id`.

The default sort order is ascending.  If you want to sort in descending order, simply prefix the attribute name with a minus sign.  This honors the scoping, so `api/animal?order_by=-name,id` will sort by `name` in descending order and by `id` in ascending order.


### Saving or updating a model

Creating a new model is possible with `POST api/animal/`, and updating a model with `PUT api/animal/`. Both requests accept a JSON body, like this:

```json
{
	"name": "Scooby Doo"
}
```

If the request succeeds, it will return a `200` response, with a JSON body:

```json
{
	"name": "Scooby Doo",
	"id": 4,
	"_meta": {
		"ignored_fields": []
	}
}
```

If you leave the `name` field blank, and `blank=True` is not set on the field, this will result in a response with status `400`;

```json
{
	"code": "ValidationError",
	"error": {
		"validation_errors": {
			"name": [
				{
					"code": "This field cannot be blank."
				}
			]
		}
	},
}
```

#### Multi PUT

For models with relations, you often don't want to make a separate request to save each model. Multi PUT makes it easy to save related models in one request.

Imagine that the `Animal` model from above is linked to a `Zoo` model;

```python
zoo = models.ForeignKey(Zoo, on_delete=models.CASCADE, related_name='+')
```

Now you can create a new animal and zoo in one request to `PUT api/animal/`;

```json
{
	"data": [{
		"id": -1,
		"zoo": -1,
		"name": "Scooby Doo"
	}, {
		"id": -2,
		"zoo": -1,
		"name": "Alex"
	}],
	"with": {
		"zoo": [{
			"id": -1,
			"name": "Slagharen"
		}]
	}
}
```

The negative `id` indicates that it is made up. Because those models are not created yet, they don't have an `id`. By using a "fake" `id`, it is possible to reference a model in another model.

The fake `id` has to be unique per model type. So you can use `-1` once for `Animal`, and once for `Zoo`. The backend does not care what number you use exactly, as long as it is negative.

If this request succeeds, you'll get back a mapping of the fake ids and the real ones;

```json
{
	"idmap": {
		"zoo": [[
			-1,
			47
		]],
		"animal": [[
			-1,
			48
		]]
	}
}
```

It is also possible to update existing models with multi PUT. If you use a "real" id instead of a fake one, the model will be updated instead of created.


#### Standalone Validation (without saving models)

Sometimes you want to validate the model that you are going to save without actually saving it. This is useful, for example, when you want to inform the user of validation errors on the frontend, without having to implement the validation logic again. You may check for validation errors by sending a `POST`, `PUT` or `PATCH` request with an additional query parameter `validate`.

Currently this is implemented by raising an `BinderValidateOnly` exception, which makes sure that the atomic database transaction is aborted. Ideally, you would only want to call the validation logic on the models, so only calling validation for fields and validation for model (`clean()`). But for now, we do it this way, at the cost of a performance penalty.

It is important to realize that in this way, the normal `save()` function is called on a model, so it is possible that possible side effects are triggered, when these are implemented directly in `save()`, as opposed to in a signal method, which would be preferable. In other words, we cannot guarantee that the request will be idempotent. Therefore, the validation only feature is disabled by default and must be enabled by setting `allow_standalone_validation=True` on the view.

### Uploading files

To upload a file, you have to add it to the `file_fields` of the `ModelView`:

```python
class ArticleView(ModelView):
	model = Article
	file_fields = ['diagram']
```

Then, to upload the file, do a `POST api/<model>/<pk>/<file_field_name>/` with the data as form-data.

To retrieve the file, do `GET api/<model>/<pk>/<file_field_name>/`

TODO:
- permissions
-- change permission model

## Hacking the API

The standard API should provide most of your common needs, but most
projects have special requirements.  For example, you might want to
provide reports that decorate the existing models, or add special
filters.

### Defining custom endpoints

Binder has two kinds of view endpoints: *detail* and *list*.

A *detail* endpoint is intended for returning detailed information
about a single object.  Let's say we want an endpoint specifically for
displaying an animal's name, returning plain text instead of JSON.
Perhaps for easy `curl`ing.  This is how you'd do it:

```python
from binder.router import detail_route
from django.http import HttpResponse

class AnimalView(ModelView):
	model = Animal

	@detail_route(name='plain_name')
	def plain_name(self, request, pk):
		animal = self.model.objects.get(pk=pk)
		return HttpResponse(animal.name, content_type='text/plain')
```

With this view, `api/animal/1/plain_name/` will respond with the name
of the animal with `id` 1, in plaintext.  The `detail_route` function
will take care of passing the primary key to the view, as the argument
with name `pk`.


A *list* endpoint is intended for returning a list of multiple
objects.  For example, if we wanted a newline-separated list of names
of all animals, it would look like this:

```python
from binder.router import detail_route
from django.http import HttpResponse

class AnimalView(ModelView):
	model = Animal

	@list_route(name='all_names')
	def all_names(self, request):
		result = []
		for animal in self.model.objects.all():
			result.append(animal.name)
		return HttpResponse("\n".join(result), content_type='text/plain')
```

With this view, `api/animal/all_names/` will respond with the list of
all animal names.

The `list_route` does not **need** to return a list of objects.  It
may also return a single object or completely unrelated information.
For example, when generating a reporting endpoint, the `list_route`
would typically be used.

However, if you need to create completely custom endpoints that have
nothing to do with the Binder models, it might be more sensible to
just register a non-Binder view for those.  Just remember that you'll
need to perform an authentication check (Binder does that
automatically).

Speaking of authentication, both `list_route` and `detail_route`
accept the following keyword options:

- `unauthenticated`: If `True`, this route should skip the authentication check.
- `methods`: Either `None` or a list of strings that indicate the allowed methods.  Any other method results in a BinderNotAllowed exception (a 418 status).
- `extra_route`: An optional string suffix to append to the route. You can use named capturing groups here, just like in `urls.py`.

## Base View classes ("abstract views")

Sometimes it is desirable to share some logic in multiple View classes.
This can be achieved by having an unrouted View class to house the common
functionality, and subclassing that class to provide the actual views.

A View that specifies neither a model nor a route (more precise: model=None
and route in [None,True]) will be ignored by the router and thus can be used
as such a base class.

```python

class BaseView(ModelView):
    # Shared logic
    def get_queryset(self, request):
        return self.model.objects.filter(id__gte=1337)

class FooView(BaseView):
    model = Foo
```



TODO:

- how to add custom saving logic
- how to add custom viewing logic
- how to add custom filtering logic
- how to add custom routes
