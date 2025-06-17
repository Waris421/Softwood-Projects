from django.urls import path
from . import views
from core.services import options_service

urlpatterns = [
    path ('marketing', views.Home, name = 'marketing'),

    path ('marketing/customers', views.CustomerData, name = 'customerData'),
    path ('marketing/customer/add', views.AddCustomer, name='addCustomer'),
    path ('marketing/customer/<int:pk>/edit', views.EditCustomer, name='editCustomer'),
    path ('marketing/customer/<int:pk>/toggle', views.ToggleAssignment, name='toggleAssignment'),

    path ('marketing/corespondence/pending', views.PendingCalls, name='pendingCalls'),
    path ('marketing/corespondence/calls', views.CallHistory, name='callHistory'),

    path('options/countries', options_service.GetCountries, name='countries'),
]