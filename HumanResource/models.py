from django.db import models
from django.contrib.auth.models import User
from django.utils.timezone import now

from apparelManagement.models import Department

class Employee(models.Model):
    id = models.AutoField(primary_key=True)
    WorkerName = models.CharField(max_length=255)
    FatherSpouseName = models.CharField(max_length=255, blank=True, null=True)
    Manager = models.ForeignKey('Employee', blank=True, null=True, on_delete=models.PROTECT)
    Department = models.ForeignKey(Department, on_delete=models.PROTECT, blank=True, null=True)
    SubDepartment = models.CharField(max_length=31, blank=True, null=True)
    CNIC = models.CharField(max_length=255, blank=True, null=True)
    DateOfBirth = models.DateField(blank=True, null=True)
    DateOfJoining = models.DateField(blank=True, null=True, auto_now_add=True)
    DateOfLeaving = models.DateField(blank=True, null=True)
    Status = models.CharField(max_length=31)
    Gender = models.CharField(max_length=7)
    User = models.ForeignKey(User, on_delete=models.PROTECT, blank=True, null=True)
    CardUID = models.CharField(max_length=255, blank=True, null=True, unique=True)
    def __str__(self):
        return self.WorkerName

# Attendance model
class Attendance(models.Model):
    id = models.AutoField(primary_key=True)
    Employee = models.ForeignKey(Employee, on_delete=models.PROTECT)
    TimeDate = models.DateTimeField(default=now)
    Type = models.CharField(max_length=10)
    Latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    Longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    Details = models.CharField(max_length=255, blank=True, null=True)
    def __str__(self):
        return f"{self.Employee} - {self.TimeDate}"

    class Meta:
        indexes = [
            models.Index(fields=['Employee']),
            models.Index(fields=['TimeDate']),
        ]
