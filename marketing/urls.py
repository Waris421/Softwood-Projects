from django.urls import path
from . import views
from core.services import options_service

app_name = 'marketing'

urlpatterns = [
    path('marketing', views.Home, name = 'marketing'),

    path('marketing/customers', views.CustomerData, name = 'customerData'),
    path('marketing/customer/add', views.AddCustomer, name='addCustomer'),
    path('marketing/customer/<int:pk>/edit', views.EditCustomer, name='editCustomer'),
    path('marketing/customer/<int:pk>/toggle', views.ToggleAssignment, name='toggleCustomerAssignment'),

    path('marketing/corespondence/pending', views.PendingCorrespondance, name='pendingCorresponance'),
    path('marketing/corespondence/history', views.CorresponanceHistory, name='corresponanceHistory'),

    path("marketing/export-data/", views.ExportData, name="exportData"),
    path("marketing/export-data/settings", views.ExportDataSettings, name="exportDataSettings"),
    path("marketing/export-data/refine/importers", views.RefineImporters, name="refineImporters"),
    path("marketing/export-data/upload", views.UploadExportReport, name="exportDataUpload"),
    path("marketing/export-data/confirm-upload", views.UploadExportReportConfirmation, name="confirmExportDataUpload"),

    path('marketing/export-data/countries', views.ExportDataCountries, name='exportDataCountries'),
    path('marketing/export-data/importers', views.ExportDataImporters, name='exportDataImporters'),
    path('marketing/export-data/exporters', views.ExportDataExporters, name='exportDataExporters'),
    path('marketing/export-data/categories', views.ExportDataCategories, name='exportDataCategories'),
    path('marketing/export-data/details', views.ExportDataTable, name='exportDataDetails'),
    path('marketing/export-data/stats', views.ExportDataStats, name='exportDataStats'),
    path('marketing/export-data/qty-range', views.ExportDataQuantityRange, name='exportDataQtyRange'),
    path('marketing/export-data/download', views.ExportDataDownload, name='exportDataDownload'),

    path('options/countries', options_service.GetCountries, name='countries'),
]