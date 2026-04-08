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

    class Meta:
        indexes = [
            models.Index(fields=['Department']),
            models.Index(fields=['Manager']),
            models.Index(fields=['Status']),
        ]

class Location(models.Model):
    id = models.AutoField(primary_key=True)
    LocationName = models.CharField(max_length=255)
    Latitude = models.DecimalField(max_digits=9, decimal_places=6)
    Longitude = models.DecimalField(max_digits=9, decimal_places=6)
    Radius = models.DecimalField(max_digits=5, decimal_places=3)

class CachedLocation(models.Model):
    id = models.AutoField(primary_key=True)
    LocationName = models.CharField(max_length=255)
    Latitude = models.DecimalField(max_digits=9, decimal_places=6)
    Longitude = models.DecimalField(max_digits=9, decimal_places=6)

class LocationAssignment(models.Model):
    id = models.AutoField(primary_key=True)
    Employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    Location = models.ForeignKey(Location, on_delete=models.PROTECT)

    class Meta:
        indexes = [
            models.Index(fields=['Employee']),
            models.Index(fields=['Location']),
        ]
        unique_together = ('Employee', 'Location')

class OffSaturday(models.Model):
    id = models.AutoField(primary_key=True)
    Employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    OffSaturdayDate = models.DateField()            #Any Off Saturday would be fine

    class Meta:
        indexes = [
            models.Index(fields=['Employee']),
        ]

class Holiday(models.Model):
    id = models.AutoField(primary_key=True)
    Department = models.ForeignKey(Department, on_delete=models.PROTECT)
    StartDate = models.DateField()
    EndDate = models.DateField()
    Description = models.CharField(max_length=255)

    class Meta:
        indexes = [
            models.Index(fields=['Department']),
            models.Index(fields=['StartDate', 'EndDate'])
        ]

class WorkingShift(models.Model):
    id = models.AutoField(primary_key=True)
    Employee = models.ForeignKey(Employee, on_delete=models.CASCADE)
    StartDate = models.DateField()
    EndDate = models.DateField(blank=True, null=True)
    StartTime = models.TimeField(auto_now=False, auto_now_add=False)
    EndTime = models.TimeField(auto_now=False, auto_now_add=False)

    class Meta:
        indexes = [
            models.Index(fields=['Employee'])
        ]

class Attendance(models.Model):
    id = models.AutoField(primary_key=True)
    Employee = models.ForeignKey(Employee, on_delete=models.PROTECT)
    TimeDate = models.DateTimeField(default=now)
    Type = models.CharField(max_length=10)
    Latitude = models.DecimalField(max_digits=9, decimal_places=6)
    Longitude = models.DecimalField(max_digits=9, decimal_places=6)
    Details = models.CharField (max_length=255, blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['Employee']),
            models.Index(fields=['TimeDate']),
        ] 

class AdjustmentHeader(models.Model):
    id = models.AutoField(primary_key=True)
    Employee = models.ForeignKey(Employee, on_delete=models.PROTECT)
    Type = models.CharField(max_length=31)
    Approval = models.BooleanField(null=True, blank=True)
    ManagerComments = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['Employee']),
            models.Index(fields=['Type']),
            models.Index(fields=['Approval']),
        ]

class LeaveAdjustmentHeader(models.Model):
    id = models.AutoField(primary_key=True)
    Header = models.OneToOneField(AdjustmentHeader, on_delete=models.CASCADE, related_name='LeaveInfo')
    LeaveType = models.CharField(max_length=31)

    class Meta:
        indexes = [
            models.Index(fields=['LeaveType']),
        ]

class SickLeaveAdjustment(models.Model):
    id = models.AutoField(primary_key=True)
    Header = models.OneToOneField(LeaveAdjustmentHeader, on_delete=models.CASCADE, related_name='SickLeaveInfo')
    StartDate = models.DateField(auto_now=False, auto_now_add=False)
    EndDate = models.DateField(auto_now=False, auto_now_add=False, blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['StartDate']),
            models.Index(fields=['EndDate']),
        ]

class CasualLeaveAdjustment(models.Model):
    id = models.AutoField(primary_key=True)
    Header = models.OneToOneField(LeaveAdjustmentHeader, on_delete=models.CASCADE, related_name='CasualLeaveInfo')
    StartDate = models.DateField(auto_now=False, auto_now_add=False)
    EndDate = models.DateField(auto_now=False, auto_now_add=False, blank=True, null=True)
    Reason = models.CharField(max_length=255)

    class Meta:
        indexes = [
            models.Index(fields=['StartDate']),
            models.Index(fields=['EndDate']),
        ]

class AnnualLeaveAdjustment(models.Model):
    id = models.AutoField(primary_key=True)
    Header = models.OneToOneField(LeaveAdjustmentHeader, on_delete=models.CASCADE, related_name='AnnualLeaveInfo')
    StartDate = models.DateField(auto_now=False, auto_now_add=False)
    EndDate = models.DateField(auto_now=False, auto_now_add=False)
    Reason = models.CharField(max_length=255)

    class Meta:
        indexes = [
            models.Index(fields=['StartDate']),
            models.Index(fields=['EndDate']),
        ]

class ShortLeaveAdjustment(models.Model):
    id = models.AutoField(primary_key=True)
    Header = models.OneToOneField(LeaveAdjustmentHeader, on_delete=models.CASCADE, related_name='ShortLeaveInfo')
    StartDateTime = models.DateTimeField(auto_now=False, auto_now_add=False)
    Duration = models.PositiveSmallIntegerField()
    Reason = models.CharField(max_length=255)

    class Meta:
        indexes = [
            models.Index(fields=['StartDateTime']),
        ]

class AttendanceAdjustmentHeader(models.Model):
    id = models.AutoField(primary_key=True)
    Header = models.OneToOneField(AdjustmentHeader, on_delete=models.CASCADE, related_name='AttendanceAdjustmentInfo')
    AdjustmentType = models.CharField(max_length=31)
    Date = models.DateField(auto_now=False, auto_now_add=False)

    class Meta:
        indexes = [
            models.Index(fields=['AdjustmentType']),
            models.Index(fields=['Date']),
        ]

class LocationAdjustmentHeader(models.Model):
    id = models.AutoField(primary_key=True)
    Header = models.OneToOneField(AttendanceAdjustmentHeader, on_delete=models.CASCADE, related_name='LocationAdjustmentInfo')
    LocationType = models.CharField(max_length=31)

    class Meta:
        indexes = [
            models.Index(fields=['LocationType']),
        ]

class InLocationAdjustment(models.Model):
    id = models.AutoField(primary_key=True)
    Header = models.OneToOneField(LocationAdjustmentHeader, on_delete=models.CASCADE, related_name='InLocationAdjustmentInfo')
    InLocation = models.CharField(max_length=255)
    Reason = models.CharField(max_length=255)

class OutLocationAdjustment(models.Model):
    id = models.AutoField(primary_key=True)
    Header = models.OneToOneField(LocationAdjustmentHeader, on_delete=models.CASCADE, related_name='OutLocationAdjustmentInfo')
    OutLocation = models.CharField(max_length=255)
    Reason = models.CharField(max_length=255)

class TimeAdjustmentHeader(models.Model):
    id = models.AutoField(primary_key=True)
    Header = models.OneToOneField(AttendanceAdjustmentHeader, on_delete=models.CASCADE, related_name='TimeAdjustmentInfo')
    TimeType = models.CharField(max_length=31)

    class Meta:
        indexes = [
            models.Index(fields=['TimeType']),
        ]

class InTimeAdjustment(models.Model):
    id = models.AutoField(primary_key=True)
    Header = models.OneToOneField(TimeAdjustmentHeader, on_delete=models.CASCADE, related_name='InTimeAdjustmentInfo')
    InTime = models.TimeField(auto_now=False, auto_now_add=False)
    Reason = models.CharField(max_length=255)

class OutTimeAdjustment(models.Model):
    id = models.AutoField(primary_key=True)
    Header = models.OneToOneField(TimeAdjustmentHeader, on_delete=models.CASCADE, related_name='OutTimeAdjustmentInfo')
    OutTime = models.TimeField(auto_now=False, auto_now_add=False)
    Reason = models.CharField(max_length=255)

class TravelAdjustment(models.Model):
    id = models.AutoField(primary_key=True)
    Header = models.OneToOneField(AdjustmentHeader, on_delete=models.CASCADE, related_name='TravelAdjustmentInfo')
    StartDate = models.DateField(auto_now=False, auto_now_add=False)
    EndDate = models.DateField(auto_now=False, auto_now_add=False)
    Destination = models.CharField(max_length=31)
    Reason = models.CharField(max_length=255)
    
    class Meta:
        indexes = [
            models.Index(fields=['StartDate']),
            models.Index(fields=['EndDate']),
        ]