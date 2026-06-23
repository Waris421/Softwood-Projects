from django.contrib import admin
from . import models
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from prodManagement.models import RFIDBox

# Register your models here.

"""class ImpExpResource (resources.ModelResource):
    class Meta:
        model = models.Machines
@admin.register(models.Machines)
class ImpExp(ImportExportModelAdmin):
    list_display = ('MachineId', 'Manufacturer', 'Department')
    resource_class = ImpExpResource"""

@admin.register(RFIDBox)
class RFIDBoxAdmin(admin.ModelAdmin):
    list_display = ('mac_address','registered_at')
    search_fields = ('mac_address',)

@admin.register(models.BoxAllotment)
class BoxAllotmentAdmin(admin.ModelAdmin):
    list_display = ('Box', 'Machine', 'Employee', 'AssignedAt')
    ordering = ('-AssignedAt',)

@admin.register(models.BoxOperation)
class BoxOperationAdmin(admin.ModelAdmin):
    list_display = ('Box', 'Operation', 'AssignedAt')
    list_filter = ('Box',)
    ordering = ('-AssignedAt',)
    search_fields = ('Box__mac_address', 'Operation__Name')

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

    list_display = ('TimeDate', 'Bundle', 'Operation', 'Machine')
    list_filter = ('Line',)
    ordering = ('TimeDate',)

@admin.register(models.Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    '''Admin View for Attendance'''

    list_display = ('Date','Worker','LoginTime','LogoutTime')
    list_filter = ('Worker',)
    ordering = ('Date',)

@admin.register(models.RFIDCard)
class RFIDCardAdmin(admin.ModelAdmin):
    '''Admin View for RFIDCard'''

    list_display = ('CardId', 'GroupNumber', 'GroupStatus')
    search_fields = ('CardId', 'GroupNumber', 'GroupStatus')
    ordering = ('CardId',)

@admin.register(models.EnergyReading)
class EnergyReadingAdmin(admin.ModelAdmin):
    list_display = ('Machine', 'Timestamp', 'Value_kW')
    list_filter = ('Machine', 'Timestamp')
    date_hierarchy = 'Timestamp'

@admin.register(models.Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ('MachineId', 'DisplayName', 'Type', 'FunctionStatus', 'Department')
    list_filter = ('FunctionStatus', 'Department')
    ordering = ('MachineId',)
    search_fields = ('MachineId', 'DisplayName')

@admin.register(models.BundleCardAssignment)
class BundleCardAssignmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'RFIDCard', 'Bundle')
    search_fields = ('RFIDCard__CardId',)
    list_filter = ('Bundle__Cut__WorkOrder',)

@admin.register(models.EmployeeCardAssignment)
class EmployeeCardAssignmentAdmin(admin.ModelAdmin):
    list_display = ('RFIDCard', 'Employee', )
    search_fields = ('RFIDCard__CardId', 'Employee__WorkerName')

@admin.register(models.Operation)
class OperationAdmin(admin.ModelAdmin):
    list_display = ('id', 'Name', 'Section', 'Category', 'SMV', 'Rate')
    search_fields = ('Name', 'Section', 'Category')
    list_filter = ('Section', 'Category')

@admin.register(models.RFIDLog)
class RFIDLogAdmin(admin.ModelAdmin):
    list_display = ('Employee', 'Machine', 'TimeDate')
    list_filter = ('Employee', 'Machine')
    ordering = ('-TimeDate',)
    search_fields = ('Employee__WorkerName',)
