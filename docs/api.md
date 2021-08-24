# API

Binder automatically exposes a fairly powerful API for all registered models. You may want to use the [test application](./test-app.md) for trying out the below described features.

## Registering API endpoints

In order to illustrate the API, we’ll use the following minimal set of models (similar to the models found in the test application):

```python
from binder.models import BinderModel
from django.db import models

class Animal(BinderModel):
	name = models.TextField()
	zoo = models.ForeignKey('Zoo', on_delete=models.CASCADE, related_name='animals', blank=True, null=True)

class Zoo(BinderModel):
	name = models.TextField()
	contacts = models.ManyToManyField('ContactPerson', blank=True, related_name='zoos')

class ContactPerson(BinderModel):
	name = models.CharField(unique=True, max_length=50)
```

Each model is registered as a separate API endpoint by defining a `ModelView` for it:

```python
from binder.views import ModelView
from .models import Animal

class AnimalView(ModelView):
	model = Animal

class ZooView(ModelView):
	model = Zoo
	
class ContactPersonView(ModelView):
	model = ContactPerson
```

After registering the models, a couple of routes is immediately available for each of them:

- `GET api/animal/` - view collection of models
- `GET api/animal/[id]/` - view a specific model
- `POST api/animal/` - create a new model
- `PUT api/animal/[id]/` - update a specific model
- `PUT api/animal/` - create, update or delete multiple models at once ("Multi PUT")
- `DELETE api/animal/[id]/` - delete a specific model
- `POST api/animal/[id]/` - undelete a specific "soft-deleted" (see below) model

## Viewing data

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

### Fetching related resources (aka compound documents)
When fetching an object that has relations, it is very convenient to receive these related models in the same response.  Related resources may be requested by specifying a list of model types in the `with` query parameter using "dotted relationship" notation.  Consider the following example: an animal belongs to at most one zoo, which may have multiple contact persons.  Suppose that we want to list all animals with their zoo and all contact persons for each zoo, then we would make the request 

`api/animal/?with=zoo.contacts`
 
which produces the following response (some fields are left out for clarity)

```json5
{
  "data": [
    {
      "name": "Scooby Doo",
      "id": 1,
      "zoo": 1,

      // ...

    }
  ],
  "with": {
    "zoo": [
      {
        "name": "Dierentuin",
        "id": 1,
        "contacts": [
          1
        ],

        // ...

      }
    ],
    "contact_person": [
      {
        "name": "Tom",
        "id": 1,
        "zoos": [
          1
        ],

        // ...

      }
    ]
  },
  "with_mapping": {
    "zoo": "zoo",
    "zoo.contacts": "contact_person"
  },
  "with_related_name_mapping": {
    "zoo": "animals",
    "zoo.contacts": "zoos"
  },

  // ...

}
```

We note that there is currently only one animal (Scooby Doo) in our database.  The `with` clause includes a list of related objects per related object type (`related_model_name`), which includes the zoo that the animal belongs to and a list of contact persons that belong to that zoo.  The translation between the dotted relationship and the actual name of the related model is given in the `with_mapping` entry.  The `with_related_name_mapping` entry gives backwards relationship name (`related_name`) that belongs to the last part of each dotted relationship.  So for example, we see that in `zoo.contacts`, the `related_name` for the last `contacts` many-to-many relation is `zoos`.  To summarize:

- `withs: { related model name: [ids] }`
- `mappings: { dotted relationship: related model name }`
- `related_name_mappings: { dotted relationship: related model reverse key }`

Note that the `with` query parameter is heavily used by [mobx-spine](https://github.com/CodeYellowBV/mobx-spine).  For some more background we refer to the `json-api` specification of [Compound Documents](https://jsonapi.org/format/#document-compound-documents), which is related to our implementation.


## Writing data

### Creating and updating a single object
Creating a new object is possible with `POST api/animal/`, and updating an object with `PUT api/animal/[id]`.  Both requests accept a JSON body, like this:

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

If the request did not pass validation, errors are included in the response, grouped by field name. For example, if you leave the `name` field blank, and `blank=True` is not set on the field, this will result in a response with status `400`:

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

### Creating and updating multiple objects using Multi PUT
Instead of having to make separate requests for each model type, it is common practice to group operations on a bunch of (possibly related) objects together in a single request.  For some additional background on this technique, we refer to the `json-api` specification of [Atomic Operations](https://jsonapi.org/ext/atomic), to which our specification of Multi PUT is somewhat related.

Remember that the `Animal` model that we defined is linked to the `Zoo` model by:

```python
zoo = models.ForeignKey('Zoo', on_delete=models.CASCADE, related_name='animals', blank=True, null=True)
```

Now you can create objects for a zoo housing two animals in one request to `PUT api/animal/`:

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

The negative `id` indicates that it is made up.  Because those objects are not created yet, they don't have an `id`.  By using a "fake" `id`, it is possible to reference an object in another object.

The fake `id` has to be unique per model type. So you can use `-1` once for `Animal`, and once for `Zoo`. The backend does not care what number you use exactly, as long as it is negative.

If this request succeeds, you'll get back a mapping from the fake ids to the real ones:

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

It is also possible to update existing models with Multi PUT.  If you use a "real" id instead of a fake one, the model will be updated instead of created.

It is also possible to delete existing models with Multi PUT by providing a `deletions` list containing the ids of the models that need to be deleted.  It is also possible to remove related models by specifying a list of ids for each related model type in the `with_deletions` dictionary.  For example, we may make the following request to the endpoint for `animal`, which deletes three animals, one zoo and two care takers:

```json
{
	"deletions": [
		1,
		2,
		3
	],
	"with_deletions": {
		"zoo": [
			1,
		],
		"care_taker": [
			2,
			4
		]
	}
}
```


### Updating relationship fields
Updating relations is rather straightforward either using a direct PUT request or a Multi PUT request.  Set the foreign key field to the id of the object you want to link to or include the id in the list in case of a reverse foreign key or many-to-many relation.  When leaving out an id in the list of related object ids, you are effectively "unlinking" the object, which also triggers the action as defined by the `on_delete` setting (CASCADE, PROTECT, SET_NULL).

We will now shortly illustrate how to update foreign keys (one-to-many) in both directions and many-to-many relations.  Suppose that we have the following objects and relationships: two animals (1 and 2), one zoo (1) that houses both animals and two contact persons (1 and 2) that are both affiliated to the zoo.  The following API calls may be made using curl, see [Test Application](test-app.md). You may verify their effects using the Django admin panels.

**Forward foreign key.**
Let's unlink Animal 2 from the zoo:
```json
PUT api/animal/2/
{ "zoo": null }
```

**Reverse foreign key.**
Now let's add Animal 2 back to the zoo and at the same time unlink Animal 1 by updating the `related_name` field on the zoo:
```json
PUT api/zoo/1/
{ "animals": [ 2 ] }
```

**M2M zoos.**
Let's unlink Contact Person 1 from the zoo:
```json
PUT api/contact_person/1/
{ "zoos": [ ] }
```

**M2M contacts.**
Let's now swap Contact Person 1 back in and remove Contact Person 2 from the zoo:
```json
PUT api/zoo/1/
{ "contacts": [ 2 ] }
```


### Uploading files

To upload a file, you have to add it to the `file_fields` of the `ModelView`:

```python
class ArticleView(ModelView):
	model = Article
	file_fields = ['diagram']
```

Then, to upload the file, do a `POST api/<model>/<pk>/<file_field_name>/` with the data as form-data.

To retrieve the file, do `GET api/<model>/<pk>/<file_field_name>/`

**TODO**
- permissions
	- change permission model

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



**TODO**

- how to add custom saving logic
- how to add custom viewing logic
- how to add custom filtering logic
- how to add custom routes
