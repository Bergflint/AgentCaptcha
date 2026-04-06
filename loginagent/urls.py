from django.urls import path, include
import django_eventstream
from . import views

urlpatterns = [
    path('run-test/', views.run_test, name='run_test'),
    path('rooms/<user>/events/', include(django_eventstream.urls), {
        'format-channels': ['room-{user}']
    }),
]