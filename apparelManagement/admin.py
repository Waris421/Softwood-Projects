from django.contrib import admin
from . import models
from import_export import resources
from import_export.admin import ImportExportModelAdmin

# Register your models here.

""" class ImpExpResource (resources.ModelResource):
    class Meta:
        model = models.Inventory
@admin.register(models.Inventory)
class ImpExp(ImportExportModelAdmin):
    list_display = ('id','Name')
    resource_class = ImpExpResource """

@admin.register(models.Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ('Name','Group')
    list_filter = ('Group',)
    ordering = ['Group','Name']

""" @admin.register(models.Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ('Code', 'Name') """


@admin.register(models.Attachment)
class AttachmentAdmin(admin.ModelAdmin):
    '''Admin View for Attachment'''

    list_display = ('id', 'Description')
    list_filter = ('ContentType',)
    ordering = ('AddedAt',)

@admin.register(models.RoutePreset)
class RoutePresetAdmin(admin.ModelAdmin):
    '''Admin View for RoutePreset'''

    list_display = ('Name',)
    list_filter = ('Name',)
    ordering = ('id',)

@admin.register(models.RoutePresetStage)
class RoutePresetStageAdmin(admin.ModelAdmin):
    '''Admin View for RoutePresetStage'''

    list_display = ('Stage','RoutePreset')
    list_filter = ('RoutePreset',)
    ordering = ('id',)

@admin.register(models.Supplier)
class SupplierAdmin(admin.ModelAdmin):
    '''Admin View for Supplier'''

    list_display = ('Name','TradeName')
    search_fields = ('Name', 'TradeName')
    ordering = ('Name',)

@admin.register(models.Customer)
class CustomerAdmin(admin.ModelAdmin):
    '''Admin View for Customer'''

    list_display = ('Name','TradeName')
    search_fields = ('Name', 'TradeName')
    ordering = ('Name',)

@admin.register(models.Department)
class DepartmentAdmin (admin.ModelAdmin):
    '''Admin View for Department'''

    list_display = ('Name','Location')
    search_fields = ('Name', 'Location')
    ordering = ('Name',)

@admin.register(models.InventoryCodePart1)
class InventoryCodeP1Admin(admin.ModelAdmin):
    '''Admin View for InventoryCodeP1'''

    list_display = ('Code', 'Name')
    list_filter = ('Code',)
    ordering = ('Code',)

@admin.register(models.InventoryCodePart2)
class InventoryCodeP2Admin(admin.ModelAdmin):
    '''Admin View for InventoryCodeP2'''

    list_display = ('Code', 'Name')
    list_filter = ('Code',)
    ordering = ('Part1',)

@admin.register(models.InventoryCodePart3)
class InventoryCodeP3Admin(admin.ModelAdmin):
    '''Admin View for InventoryCodeP3'''

    list_display = ('Code', 'Name')
    list_filter = ('Code',)
    ordering = ('Part2',)

@admin.register(models.ThreadConsumptionRequest)
class ConsRequestAdmin(admin.ModelAdmin):
    '''Admin View for ConsRequest'''

    list_display = ('id', 'RequestBy')
    list_filter = ('RequestBy',)
    ordering = ('id',)