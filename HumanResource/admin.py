from django.contrib import admin
from . import models

@admin.register(models.Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['id', 'WorkerName', 'Status', 'Gender']

@admin.register(models.Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['id', 'Employee', 'TimeDate', 'Type', 'Details']
