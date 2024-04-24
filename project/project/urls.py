from django.urls import re_path, include
from django.contrib import admin

import testapp.urls

urlpatterns = [
	re_path(r'^admin/', admin.site.urls, name='admin'),
	re_path(r'^api/', include(testapp.urls), name='testapp'),
]
