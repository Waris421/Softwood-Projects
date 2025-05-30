from django.contrib import admin
from . import models
from import_export import resources
from import_export.admin import ImportExportModelAdmin

# Register your models here.

"""class ImpExpResource (resources.ModelResource):
    class Meta:
        model = models.Machines
@admin.register(models.Machines)
class ImpExp(ImportExportModelAdmin):
    list_display = ('MachineId', 'Manufacturer', 'Department')
    resource_class = ImpExpResource"""

@admin.register(models.Cut)
class CutAdmin(admin.ModelAdmin):
    '''Admin View for Cut'''

    list_display = ('WorkOrder','CutNumber')
    list_filter = ('WorkOrder',)
    ordering = ('WorkOrder',)

@admin.register(models.Bundle)
class BundleAdmin(admin.ModelAdmin):
    '''Admin View for Bundle'''

    list_display = ('Cut','Size')
    list_filter = ('Cut',)
    ordering = ('Cut',)

""" class ImpExpResource (resources.ModelResource):
    class Meta:
        model = models.RFIDCard
@admin.register(models.RFIDCard)
class ImpExp(ImportExportModelAdmin):
    list_display = ('GroupNumber','CardNumber','GroupStatus')
    list_filter = ('GroupStatus',)
    ordering = ('CardNumber',)
    resource_class = ImpExpResource """

@admin.register(models.Serial)
class SerialAdmin(admin.ModelAdmin):
    '''Admin View for Serial'''

    list_display = ('TimeDate','Operation')
    list_filter = ('TimeDate',)
    ordering = ('Operation',)