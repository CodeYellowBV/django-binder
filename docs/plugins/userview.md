# UserView 

## UserViewMixin

### Required callbacks
The following abc methods need to be implemented if this mixin is used:

```
@abstractmethod
def _after_soft_delete(self, request, user, undelete):
	"""
	Callback called after an user is softdeleted or softundeleted
	"""
	pass

@abstractmethod
def _send_reset_mail(self, request, user, token):
	"""
	Callback to send the actual reset mail using the token.
	"""
	pass

@staticmethod
def _send_activation_email(request, user):
	"""
	Callback to send a mail notifying that the user is activated.
	"""
	pass

```


### Login

Logs the user in

Request:

```
POST user/login/
{
	"username": "foo",
	"password": "password"
}
```

Response:

Returns the same parameters as GET user/{id}/

### Logout
Logs the user out

Request:
```
POST /user/logout/
{}
```

Response:
204
```
{}
```

### Reset request
Adds an endpoint to do a reset request. Generates a token, and calls the _send_reset_mail callback if the reset
request is successful

Request:

```
POST user/reset_request/
{
	'username': 'foo'
}
```

Response:
204
```
{
}
```

### Send activation mail

Endpoint that can be used to send an activation mail for an user.
Calls the _send_activation_email callback if the user is succesfully activated

Request:

```
POST
{
	"email": "email"
}
```

Response:

```
{
	"code": code
}
```

Possible codes:
| code | description |
|---|---|
| sent | Mail is sent sucessfully |
| already active |	User is already active, no mail was send |
| blacklisted | User was not activated |


### Activate
Adds an endpoint to activate an user. Also logs in the user

Request:
```
POST user/{id}/activate/
{
	"activation_code": string
}
```

Response:

Same as GET user/{id}/

### Reset password

Resets the password from an reset code

Request:

```
POST user/reset_password/
{
	"reset_code": str,
	"password": str
}
```

Response:

Same as GET user/{id}/

### Change password

Change the password from an old password

Request:
```
POST user/change_password/
{
	"old_password": str,
	"new_password": str
}
```

Response:
Same as GET user/{id}/

### Email exists
Adds an endpoint to check if an email exists or not

Request:
```
POST user/email_exists/
{
	"email": "str@str.com"
}
```

Return:
200 if it exists, of 404 if it does not exist.


## Masquerade plugin

### Masquerade
Masquerade as an user

Request:
```
POST user/{id}/masquerade/
```

response:
Same as GET user/{id}

### Endmasquerade
```
POST user/endmasquerade/
```

response:
Same as GET user/{id}

