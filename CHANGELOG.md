# master

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
