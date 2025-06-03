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

@admin.register(models.Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('Heading','Summary')
    list_filter = ('User',)
    search_fields = ('Summary','Body')

@admin.register(models.StyleCard)
class StyleAdmin(admin.ModelAdmin):
    '''Admin View for Style'''

    list_display = ('StyleCode','Customer')
    list_filter = ('Customer',)