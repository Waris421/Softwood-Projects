from django.contrib import admin
from . import models

from import_export import resources
from import_export.admin import ImportExportModelAdmin

"""class ImpExpResource (resources.ModelResource):
    class Meta:
        model = models.Customer
@admin.register(models.Customer)
class ImpExp(ImportExportModelAdmin):
    list_display = ('id','Name')
    resource_class = ImpExpResource"""

@admin.register(models.Correspondance)
class CorrespondanceAdmin(admin.ModelAdmin):
    '''Admin View for Correspondance'''

    list_display = ('User','Customer')
    list_filter = ('Type',)
    ordering = ('User',)

@admin.register(models.ImporterAlias)
class ImporterAliasAdmin(admin.ModelAdmin):
    '''Admin View for ImporterAlias'''

    list_display = ('Name', 'Alias')
    list_filter = ('Alias',)
    ordering = ('Name',)