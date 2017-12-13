from django.conf.urls import url, include
from django.contrib import admin

import testapp.urls

urlpatterns = [
	url(r'^admin/', admin.site.urls, name='admin'),
	url(r'^api/', include(testapp.urls), name='testapp'),
]
