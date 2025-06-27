from django.urls import path
from . import views
from core.services import options_service

app_name = 'marketing'

urlpatterns = [
    path ('marketing', views.Home, name = 'marketing'),

    path ('marketing/customers', views.CustomerData, name = 'customerData'),
    path ('marketing/customer/add', views.AddCustomer, name='addCustomer'),
    path ('marketing/customer/<int:pk>/edit', views.EditCustomer, name='editCustomer'),
    path ('marketing/customer/<int:pk>/toggle', views.ToggleAssignment, name='toggleAssignment'),

    path ('marketing/corespondence/pending', views.PendingCorrespondance, name='pendingCorresponance'),
    path ('marketing/corespondence/history', views.CorresponanceHistory, name='corresponanceHistory'),

    path('options/countries', options_service.GetCountries, name='countries'),
]