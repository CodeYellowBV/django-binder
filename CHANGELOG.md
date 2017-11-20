# master

### Views

- Multiput now supports softdeleting related models. (#24)
- Deleting models which don't have a "deleted" attribute now results in hard delete. (#42)
- Filtering on datetime fields allows filtering on (milli)second instead of date granulatity. (#41)
- The `_store`, `_store_field` and `_store__<fieldname>` methods now must accept a `pk` keyword argument (#64; **backwards incompatible**).
- BinderValidationError no longer accepts an `object` keyword argument (#64; **backwards incompatible**).

### Router

- Router is no longer a singleton (#28; **backwards incompatible**)

### Models

- `binder.models.CaseInsensitiveCharField` is now deprecated in favor of `django.contrib.postgres.fields.CITextField` (#9)
