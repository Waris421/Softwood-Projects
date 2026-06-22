from django.contrib import admin
from . import models

@admin.register(models.Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['id', 'WorkerName', 'Status', 'Gender']

@admin.register(models.Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['id', 'Employee', 'TimeDate', 'Type', 'Details']

# Attendance Log
@admin.register(models.RFIDLog)
class RFIDLogAdmin(admin.ModelAdmin):
    list_display = ('Employee', 'Machine', 'TimeDate')
    list_filter = ('Employee', 'Machine')
    ordering = ('-TimeDate',)
