from django.contrib import admin
from . import models

@admin.register(models.SubDepartment)
class SubDepartmentAdmin(admin.ModelAdmin):
    '''Admin View for Supplier'''

    list_display = ('Name','FullName')
    search_fields = ('Name', 'FullName')
    ordering = ('Name',)
@admin.register(models.Capacity)
class CapacityAdmin(admin.ModelAdmin):
    '''Admin View for Capacity'''

    list_display = ('Source', 'Capacity')
    list_filter = ('Source',)
    ordering = ('Source',)