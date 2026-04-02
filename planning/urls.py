from django.urls import path
from . import views

from core.services import options_service

app_name = 'planning'

urlpatterns = [
    path('planning', views.Home, name = 'planning'),
    path('planning/capacity', views.Capacity, name='capacity'),
    path('planning/set-source', views.SetSource, name='setSource'),

    path('options/capacities', options_service.GetCapacities, name='capacitiesOptons'),
]