These are some old tickets from HERE that are really Binder issues.
They're also wishlist stuff that has been open for years.

Maybe these should be tickets on github. Then again, if we're never
gonna do them it's just more noise. Let's park them here for now.



# Use error codes for validation errors.

Instead of full English text messages, like now.
The Front-End should translate.



# Filtering v2

Filter not with ?.foo=5, but with a query language ?filter=<expr>.

This would allow a lot more than we can currently do, including nested
expressions and OR clauses.

Exmaple: ?filter=status:is:3:or:source:is:"foo"
See ticket for full grammar.

https://phabricator.codeyellow.nl/T2944



# Split up Views into Serializers and Views

This would allow more reusability. Let 2 views (for different parts of
the application) use the same serializer. See also Django Rest Framework.



# Embedding related objects

Like ?with, but as embedded json, instead of provided separately.

https://phabricator.codeyellow.nl/T2942



# Refactor _get_objs() to return models as well

This would sometimes make it a lot easier to calculate/manipulate custom
attributes.

Maybe include the model in the dict? Or return models with the dict as a
property? Or both in a tuple? Or split out getting/preparation of
objects and parsing them into dicts?



# Remove code duplication

Refactor to remove duplicate field resolution code in _get_with()
_parse_filter() _parse_order_by()



# Selectable fields

Let the front-end choose which fields it wants. Like ?with, but for
normal fields, not related entities.

This could greatly speed up getting and parsing large quantities of
large objects where the FE only really needs several fields.
