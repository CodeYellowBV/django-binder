# Stats

Next to the regular CRUD API binder also supports an easy way to gather
statistics about the records you are querying. The rest of this document
assumes that `testapp.views.animal.AnimalView` is registered at `/api/animal/`.

## Querying Stats

Stats can be queried through `GET /api/animal/stats/`, this endpoint behaves
similar to `GET /api/animal/` in terms of what filters etc you can supply. The
only extra requirement is that it expects a `stats`-parameter indicating what
stats you want to query.

For example if you would want to query the stats `total` and `by_zoo` for all
animals that do not have a caretaker you could do the following request:

```
GET /api/animal/?stats=total,by_zoo&.caretaker:isnull=true
{
	"total": {
		"value": <total>,
		"filters": {},
	},
	"by_zoo": {
		"value": {,
			<zoo name>: <total>,
			...
		}
		"filters": {},
		"group_by": "zoo.name",
	},
}
```

So you can see you get some data for every statistic, the `value`-key here is
the most important since it will contain the actual statistic. Next to that you
will have some meta information with the `filters`-key and the optional
`group_by`-key. This information can be used to filter on certain
statistics.

## Defining Stats

You can define stats by setting the `stats` property on the view. This should
be a mapping of stat names to `binder.views.Stat`-instances.

This class has the following signature
`Stat(expr, filters={}, group_by=None, annotations=[])` where:
  - **expr**: an aggregate expr to get the statistic,
  - **filter**: a dict of filters to filter the queryset with before getting
  the aggregate, leading dot not included (optional),
  - **group_by**: a field to group by separated by dots if following relations
  (optional),
  - **annotations**: a list of annotation names that have to be applied to the
  queryset for the expr to work (optional),

By default the stat `total` is already defined for every view. This will give
the total amount of records in the dataset. This stat is defined as
`Stat(Count(Value(1)))`.
