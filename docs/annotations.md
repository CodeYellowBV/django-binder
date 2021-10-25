# Annotations
Annotations are a way of adding query expressions that behave like read-only
fields to models. This means you can read / filter / sort these fields.

Changing the value or saving annotations from the frontend is automatically
ignored since they are read-only fields. And they are put in the `ignored_fields`
of the reponse.

## Specifying Annotations
You can specify annotations by adding a class called `Annotations` to your
`BinderModel`. Here you simply say `foo = expr` to add an annotation named `foo` that
will evaluate using `expr`.

Example:
```python
class Product(BinderModel):

	price = models.DecimalField()

	class Annotations:
		vat = F('price') * Value(0.21)
```

### Context Annotations
Sometimes an annotation needs some context of the current request. For this
you can import the wrapper class `ContextAnnotation` from `binder.models`.
This class takes a callable that returns a query expression based on a request
object.

Note that annotations can also be used outside of a request context, in this
case you will receive `None` as request object.

Example:
```python
class Task(BinderModel):

	assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, models.PROTECT)

	class Annotations:
		assigned_to_me = ContextAnnotation(lambda request: Case(
			When(assigned_to=request.user, then=Value(True)),
			default=Value(False),
			output_field=models.BooleanField(),
		))
```

### Optional Annotations
Some annotations can be very heavy to calculate, in this case you do not want
to include them by default. For this you can import the wrapper class
`OptionalAnnotation` from `binder.models`. This class takes a query expression
or a `ContextAnnotation`.

## Including annotations
Sometimes you want to specify which annotations you want included for
performance reasons. You can use the `include_annotations` query parameter for
this.

This parameter takes a comma seperated list of annotations that can take the
following two forms:
- `relation.annotation`
- `relation(annotation1,annotation2,...)`

Note that `relation` can be omitted to target the top level resource (including
the trailing `.`) or can contain a `.` seperated list of relations for when you
want to target a deeply nested resource.

This query parameter will only affect the relations mentioned in this list. If
you thus want to omit all annotations of a relation you will have to include
`relation()`.

There is a special value `*` that you can use as annotation name that will
evaluate to all annotations that are included by default. (Thus all annotations
that are not wrapped in `OptionalAnnotation`.)

Sometimes you will want to include all default annotations except for one. In
this case you can put the `-` modifier infront of an annotation name to exclude
it instead of include it. So if you want to include all default annotations
except for `foo` you can say `*,-foo`.
