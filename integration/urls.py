from django.urls import path
from core.services.generic_services import showMessageResponse
from . import views

urlpatterns = [
    path('alloc/export', views.ExportPOAllocation.as_view(), name='exportPOAlloc'),
]