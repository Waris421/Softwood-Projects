from django.urls import path
from . import views

app_name = 'QC'

urlpatterns = [
    path ('quality', views.Home, name = 'quality'),
    
    path('trims/audit/pending', views.PendingTrimsAudit, name='pendingTrimAudit'),
    path('trims/audit/add', views.AddTrimsAudit, name='addTrimAudit'),
    path('trims/audit', views.TrimsAudit, name='trimAudit'),
    path('trims/audit/<int:pk>/edit', views.EditTrimsAudit, name='editTrimAudit'),
]