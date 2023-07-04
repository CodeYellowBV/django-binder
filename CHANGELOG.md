## HEAD

### BUGFIX csv export with null foreign keys
CSV export will now work with null foreign keys

### Chained qualifiers
Chained qualifiers have been added [T35707](https://phabricator.codeyellow.nl/T35707). For more information on how they work and how to use it see [documentation](/docs/api.md)

#### Breaking change

The `_filter_field` method signature has been changed from
```
def _filter_field(self, field_name, qualifier, value, invert, request, include_annotations, partial=''):
```
to
```
def _filter_field(self, field_name, qualifiers, value, invert, request, include_annotations, partial=''):
```

So it now contains an array of qualifiers instead of THE qualifier. 
So for the call `api/caretaker?.last_seen:date:range` it will contain both date and range qualifiers.

To get previously used qualifier variable and upgrade previously written code that was overriding `_filter_field` use: 
```
qualifier = qualifiers[0]
```
See full changes [here](https://github.com/CodeYellowBV/django-binder/pull/206/files#diff-0d5633deb444395cd44b49e7a39f87da98bb86de20666038277730991c62b1a5).


### Breaking changes

The `_filter_field` method now returns a `Q()` object, not a queryset.
Similarly, the `_filter_relation` method no longer accepts a queryset
and now returns a new namedtuple called `FilterDescription`, which
contains a `Q()` object property called `filter` and a boolean called
`need_distinct` which indicated if the master query should be made
distinct.

Using `Q()` objects instead of querysets allows making queries in
`with_ids` without requiring a subquery on filtered relations, which
can be a big performance win on large tables.

Now, `full_clean` is automatically called upon `save()` of a
`BinderModel`.  This should not be a huge breaking change because most
projects "in the wild" are already using the
[django-fullclean](https://github.com/fish-ball/django-fullclean)
plugin.  This should reduce the number of checks done while saving
objects.  However, it also means that if a non-binder model is saved
it will no longer be validated.  If you want this to happen you need
to override `_store` to do some checking.

### Features
- TextFields can now be filtered with the `isnull` qualifier (#134).
- Added a new `unupdatable_fields` property to views which lists
  fields which can be written on creation of an object only and are
  ignored on updates (#135).
- It is now possible to POST or PUT an id for the "remote" end of a
  OneToOneField (#117).
- An error will be logged when `Q()` objects are used in scopes when
  this is unsuitable (i.e., in a one to many relationship) as this
  will result in multiple objects being returned due to missing
  `distinct()` call.  The distinct call is not added because this
  would decrease performance.

## Version 1.4.0

### Features
- Add `Router.bootstrap()`function, which automatically imports all `views` directories of all the registered apps in django. Also, it automatically registers the default ModelView of binder.
  
  Old:
  
	```python
	from binder.router import Router
	from binder.views import ModelView
	
	# needed for binder.router to work
	import cyrm.views  # noqa
	import base.orders.views  # noqa
	import ib.ib_orders.views  # noqa
	....
	import base.planning.views # noqa
	
	router = Router().register(ModelView)
	
	api_urls = [
		re_path('^', include(router.urls)),
	]
	
	```
	
	New:
	```python
	from binder.router import Router
	router = Router.bootstrap()
	api_urls = [
		re_path('^', include(router.urls)),
	]
	```
	
- Allow callables for annotations, deferring their initializations until the corresponding view is initialized. Example:
```python
    class Annotations:
        @staticmethod
        def ready_to_go_cb():
            from base.orders.models import PlannedStep
            return Exists(PlannedStep.objects.filter(works__works__route=OuterRef('pk')))
        ready_to_go = ready_to_go_cb
```

- When using date-only syntax for filtering on DateTimeFields, ranges
  are now inclusive of the end date, and "greater than" filters will
  now do the right thing and skip the given date completely instead of
  using midnight of that date as a starting point.


### Bugfixes
- Fix error when `related_name=None`

### Deprecations / removals

## Version 1.3.0

### Features
- Add support for `nulls_first` and `nulls_last` sorting postfixes on annotations (only in Django >=2.1)
- Add automated test discovery script. All tests in the application are automatically discovered when including binder.load_tests in the `__init__.py` from the main application
- Allow usage of custom user model in TokenView and UserView plugins


### Bugfixes
- `UserviewPlugin` custom functions do not break anymore if the user object has annotations
- `UserviewPlugin` doesn't use deprecated `_get_obj` function anymore

### Deprecations / removals
- Removed (broken) `nulls_first` and `nulls_last` sorting postfixes for annotations (Django <= 2.0), in favour of a totally working version from Django > 2.1
- `get_obj` is deprecated in favour of `_get_objs` endpoint

## OLD

### Views

- Multiput now supports softdeleting related models. (#24)
- Deleting models which don't have a "deleted" attribute now results in hard delete. (#42)
- Filtering on datetime fields allows filtering on (milli)second instead of date granulatity. (#41)
- The `_store`, `_store_field` and `_store__<fieldname>` methods now must accept a `pk` keyword argument (#64; **backwards incompatible**).
- BinderValidationError no longer accepts an `object` keyword argument (#64; **backwards incompatible**).
- The `_parse_order_by` method now must return a tuple of 3 objects, not 2 objects.  The final object should be a boolean that indicates whether nulls should be last (or None if there's no preference).
- The `_follow_related` and `_get_withs` function now must return a (named)tuple of 3 objects, not 2 objects.  In `_follow_related`, the third attribute of the `RelatedModel` namedtuple should be the name of the field which points to the model in the foreign model (its `related_name`).  In `_get_withs`, the third object in the tuple should be a `related_name_mappings` dict which contains as a value the foreign field pointing back to the field that is in its key.

### Router

- Router is no longer a singleton (#28; **backwards incompatible**)

### Models

- `binder.models.CaseInsensitiveCharField` is now deprecated in favor of `django.contrib.postgres.fields.CITextField` (#9)
