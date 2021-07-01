# Token Auth

To enable authentication using tokens, you can use the Token Auth plugin. Tokens are attached to users, and any action is seen as done by that user.

# Installation

Add to `settings.py`:

```
INSTALLED_APPS = [
	...
	'binder.plugins.token_auth',
	...
]
```

Then run the migrations:

```
./manage.py migrate
```

# Generate tokens


The following snippet shows how to generate tokens for users.

```
from django.contrib.auth.models import User
from binder.plugins.token_auth.models import Token

token = Token(user=u)
token.save()

# Contains token to authenticate, for example 'test-token'.
token.token
```

The token can be used in the `Authorization` header prefixed with `Token `. Take this example using curl:

```
curl --location --request POST 'http://localhost:1339/api/dfds/instruction/' --header 'Authorization: Token test-token' --data '{"foo":"bar"}'
```

# CSRF

When using token auth, csrf is completely bypassed.

# Customization
Authorization can be customized by overriding the `_get_authorization_token method`. Some external apis do not allow for customization of the authentication header, in this case you might want to customize to also allow the external headers. Next to that a parameter is attached to a request to indicate it is token authorized which could be used to skip other methods such as two-factor authentication.
