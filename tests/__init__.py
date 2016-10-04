from django.conf import settings

settings.configure(**{
	'DEBUG': True,
	'DATABASES': {
		'default': {
			'ENGINE': 'django.db.backends.sqlite3', # For now
			'NAME': ':memory:',
		},
	},
})
