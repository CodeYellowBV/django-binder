# Permission system

## Install and use the permission system
To install and use the permission system do the following:

- First create a file `permissions.py` in the main package. This will define the permissions in the system
- Add the following content to the `permissions.py`
```python
permissions = {
	'default': [ # Default permissions everybody has
		('auth.view_user', 'own'),
		('auth.unmasquerade_user', None), # If you are masquerade, the user must be able to unmasquerade
		('auth.login_user', None),
		('auth.logout_user', None),
	],
}
```
This will allow everybody to login, logout, unmasquerade, and view their own user account.
- Add the following to settings.py
```python
from .permissions import permissions
BINDER_PERMISSION = permissions
```

