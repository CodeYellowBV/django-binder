# Permission system

## Install and use the permission system
To install and use the permission system do the following:

- First create a file `permissions.py` in the main package. This will define the permissions in the system
- Add the following content to the `permissions.py`
```
permissions = {
	'default': [ # Default permissions everybody has
		('auth.view_user', 'own'),
		('auth.unmasquerade_user', None), # If you are masquarade, the user must be able to unmasquarade
		('auth.login_user', None),
		('auth.logout_user', None),
	],
}
```
This will allow everybody to login, logout, unmasquerade, and view their own user account.
- Add the following to settings.py
```
from .permissions import permissions
BINDER_PERMISSION = permissions
```

## Defining custom scopes
There are 4 permissions for which there exists a scoping system in binder:
view, add, change and delete. For all 4 of these there is a scope already
implemented called `all` which allows everything.

However it is is also possible to create custom scopes. To do this you put
a method called `_scope_{view|add|change|delete}_{name}` on the view. So if you
want to create a view scope called `own` for the `User`-model you would add a
method named `_scope_view_own` to the `UserView`.

The arguments and return values of these methods depends on the type of the
scope.

### View scopes
A view scope gets the request as an argument. As a return value it can return
one of three things:
1. A `django.db.models.Q`-object representing what we should filter on.
2. A `binder.views.FilterDescription`-object representing what we should filter on.
3. A queryset of the models that we should be able to see.

The difference between option 1 and option 2 is that a `FilterDescription`
exists of 2 fields: `filter` and `need_distinct`. `filter` behaves the same as
the `Q`-object in option 1, so the difference is the `need_distinct` field.
This field can be used to indicate that this filter can cause duplicates and
thus needs to call distinct on the query to prevent this issue. This often
happens when you filter on a many to many relation and there are multiple
matches.

Option 3 mainly exists out of historic reasons, this will generate a subquery
and thus often leads to performance issues. Thus it is advised to use option 1
or 2 whenever possible.

### Add/Change/Delete scopes
Add, change and delete scopes all work the same. They receive 3 arguments:
`request`, `object` and `values`. And should return a boolean indicating if the
operation is allowed.

In these arguments `request` is current request, `object` is the object we are
trying to add, change or delete. And `values` is a dict of  the values we are
trying to save. In case of `delete` this is always empty.


### Check permissions & scoping for requests
Based on whether the created endpoint accepts a `GET`, `PUT`, `POST`, ... a set of scopes is defined that need to be checked.

The following scopes are checked automatically when calling the following methods

Get scoping:
- view.get_queryset()

Change scoping:
- view.store(obj, fields, request)

## @no_scoping_required()
In some cases you might not need the automated scoping. An example might be when your endpoint does not make any  
changes to the data-model but simply triggers an event or if you have already implemented custom scoping. In that 
case there is the option of adding `@no_scoping_required()` before the endpoint, which will ignore the scoping checks for the endpoint.

```python
@detail_route('download', methods=['POST'])
@no_scoping_required()
def download(self, request, pk):
```
