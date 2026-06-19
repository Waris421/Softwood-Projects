from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User

from apparelManagement.models import Department, StyleCard, WorkOrder, OrderVariant
from apparelManagement.models import StyleRoute, Currency, RoutePresetStage
from planning.models import ProductionPlan, Capacity

class Operation(models.Model):
    id = models.AutoField(primary_key=True)
    Name = models.CharField(max_length=511)
    Section = models.CharField(max_length=31)
    Category = models.CharField(max_length=31)
    SkillLevel = models.PositiveIntegerField()
    SMV = models.FloatField(null=True, blank=True)
    MachineRequirement = models.BooleanField(default=False)
    MachineType = models.CharField(max_length=31)
    Rate = models.FloatField(null=True, blank=True)
    Code = models.CharField(max_length=31, blank=True, null=True)

    class Meta:
        """Meta definition for Operations."""

        indexes = [
            models.Index(fields=['Section']),
            models.Index(fields=['MachineType']),
        ]

class Machine(models.Model):
    id = models.AutoField(primary_key=True)
    MachineId = models.CharField(max_length=31, unique=True)
    DisplayName = models.CharField(max_length=100, blank=True, null=True)
    PurchaseDate = models.DateField(auto_now_add=True)
    Type = models.CharField(max_length=63)
    FunctionStatus = models.CharField(max_length=15)
    Manufacturer = models.CharField(max_length=15, blank=True, null=True)
    ModelNumber = models.CharField(max_length=25, null=True, blank=True)
    SerialNumber = models.CharField(max_length=15, null=True, blank=True)
    Department = models.ForeignKey(Department, on_delete=models.PROTECT, blank=True, null=True)

    def __str__(self):
        return self.DisplayName or self.MachineId
    
    class Meta:
        """Meta definition for Machines."""

        indexes = [
            models.Index(fields=['FunctionStatus', 'Department'])
        ]

class StyleBulletin(models.Model):
    id = models.AutoField(primary_key=True)
    StyleCard = models.ForeignKey(StyleCard, on_delete=models.PROTECT)

    class Meta:
        """Meta definition for Style Bulletin."""
        indexes = [
            models.Index(fields=['StyleCard'])
        ]

class StyleBulletinOperation(models.Model):
    id = models.AutoField(primary_key=True)
    StyleBulletin = models.ForeignKey(StyleBulletin, on_delete=models.CASCADE)
    Sequence = models.PositiveIntegerField()
    Operation = models.ForeignKey(Operation, on_delete=models.PROTECT)
    Section = models.CharField(max_length=31)
    IsStart = models.BooleanField(default=False)
    IsEnd = models.BooleanField(default=False)

    class Meta:
        """Meta definition for Style Bulletin Operation."""
        indexes = [
            models.Index(fields=['StyleBulletin']),
            models.Index(fields=['Operation']),
            models.Index(fields=['Section']),
        ]

class Cut(models.Model):
    id = models.AutoField(primary_key=True)
    WorkOrder = models.ForeignKey(WorkOrder, on_delete=models.PROTECT)
    Shade = models.CharField(max_length=31)
    WarpShrinkage = models.FloatField()
    WeftShrinkage = models.FloatField()
    Inseam = models.CharField(max_length=31, null=True, blank=True)
    NoOfPlies = models.PositiveIntegerField()
    CutNumber = models.PositiveIntegerField()

    class Meta:
        indexes = [
            models.Index(fields=['WorkOrder']),
        ]

class Bundle(models.Model):
    id =  models.AutoField(primary_key=True)
    Cut = models.ForeignKey(Cut, on_delete=models.CASCADE)
    Size = models.CharField(max_length=31)
    Bundle = models.PositiveIntegerField()
    CreatedAt = models.DateTimeField(auto_now_add=True, null=True)
    def __str__(self):
        return f"Bundle {self.Bundle} — Cut {self.Cut_id} ({self.Size})"


    class Meta:
        indexes = [
            models.Index(fields=['Cut']),
            models.Index(fields=['Size']),
        ]

class Worker(models.Model):
    "20-Jan-2025: This model is deprecated"
    WorkerCode = models.PositiveBigIntegerField(primary_key=True)
    WorkerName = models.CharField(max_length=255)
    FatherSpouseName = models.CharField(max_length=255, blank=True, null=True)
    Department = models.ForeignKey(Department, on_delete=models.PROTECT, blank=True, null=True)
    SubDepartment = models.CharField(max_length=31, blank=True, null=True)
    CNIC = models.CharField(max_length=255, blank=True, null=True)
    DateOfBirth = models.DateField(blank=True, null=True)
    DateOfJoining = models.DateField(blank=True, null=True, auto_now_add=True)
    Status = models.CharField(max_length=31)
    Gender = models.CharField(max_length=7)
    User = models.ForeignKey(User, on_delete=models.PROTECT, blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['Department']),
            models.Index(fields=['Status']),
        ]

class RFIDCard(models.Model):
    CardId = models.CharField(max_length=50, primary_key=True)
    CardNumber = models.PositiveBigIntegerField(unique=True, null=True, blank=True)
    GroupNumber = models.PositiveBigIntegerField(null=True, blank=True)
    GroupStatus = models.CharField(max_length=31, default='Incomplete')

    class Meta:
        indexes = [
            models.Index(fields=['GroupNumber']),
            models.Index(fields=['GroupStatus']),
        ]

class WorkerCardAssignment(models.Model):
    id = models.AutoField(primary_key=True)
    RFIDCard = models.ForeignKey(RFIDCard, on_delete=models.CASCADE)
    Worker = models.ForeignKey(Worker, on_delete=models.CASCADE)

    class Meta:
        indexes = [
            models.Index(fields=['RFIDCard']),
        ]

class BundleCardAssignment(models.Model):
    id = models.AutoField(primary_key=True)
    RFIDCard = models.ForeignKey(RFIDCard, on_delete=models.CASCADE)
    Bundle = models.ForeignKey(Bundle, on_delete=models.CASCADE)

    class Meta:
        indexes = [
            models.Index(fields=['RFIDCard']),
        ]

class Serial(models.Model):
    id = models.AutoField(primary_key=True)
    Worker = models.ForeignKey(Worker, on_delete=models.PROTECT)
    Operation = models.ForeignKey(Operation, on_delete=models.PROTECT)
    Bundle = models.ForeignKey(Bundle, on_delete=models.PROTECT)
    Machine = models.ForeignKey(Machine, on_delete=models.PROTECT)
    TimeDate = models.DateTimeField(blank=True, null=True, default=timezone.now)
    Line = models.CharField(max_length=31)

    class Meta:
        indexes = [
            models.Index(fields=['Operation']),
            models.Index(fields=['Line', 'Worker']),
            models.Index(fields=['Bundle']),
        ]

class Attendance(models.Model):
    id = models.AutoField(primary_key=True)
    Worker = models.ForeignKey(Worker, on_delete=models.PROTECT)
    Date = models.DateField(blank=True, null=True, default=timezone.now)
    LoginTime = models.TimeField(blank=True, null=True, default=timezone.now)
    LogoutTime = models.TimeField(blank=True, null=True, default=timezone.now)

    class Meta:
        indexes = [
            models.Index(fields=['Worker']),
            models.Index(fields=['Date'])
        ]

class OutSourceJobContract(models.Model):
    id = models.AutoField(primary_key=True)
    StartDate = models.DateField()
    EndDate = models.DateField()
    Approval = models.BooleanField(blank=True, null=True)
    ApprovedBy = models.ForeignKey(User, on_delete=models.PROTECT, blank=True, null=True)
    Comments = models.CharField(max_length=255, blank=True, null=True)

class OutSourceJobContractDetails(models.Model):
    id = models.AutoField(primary_key=True)
    OutSourceJobContract = models.ForeignKey(OutSourceJobContract, on_delete=models.CASCADE)
    ProductionPlan = models.ForeignKey(ProductionPlan, on_delete=models.PROTECT)
    Price = models.DecimalField(max_digits=10, decimal_places=2)

# New model for energy consumption data (Test phase)
class EnergyReading(models.Model):
    Machine = models.ForeignKey('Machine', on_delete=models.CASCADE, to_field='MachineId') # — links each reading to a machine. CASCADE means if you delete a machine, all its readings get deleted too
    Timestamp = models.DateTimeField(db_index=True) # — stores the date and time of the reading, indexed for faster queries
    Value_kW = models.FloatField()

    class Meta:
        unique_together = ('Machine', 'Timestamp') # — this is the duplicate prevention. 

# RFID machine model
class RFIDBox(models.Model):
    mac_address  = models.CharField(max_length=255, unique=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.mac_address})"

class BoxAllotment(models.Model):
    Box        = models.ForeignKey(RFIDBox, on_delete=models.PROTECT)
    Machine    = models.ForeignKey(Machine, on_delete=models.PROTECT)
    Employee   = models.ForeignKey('HumanResource.Employee', on_delete=models.PROTECT)
    AssignedAt = models.DateTimeField(auto_now_add=True)

# Bundle tracking and completion model
class BundleCompletion(models.Model):
    id          = models.AutoField(primary_key=True)
    Employee    = models.ForeignKey('HumanResource.Employee', on_delete=models.PROTECT)
    Bundle      = models.ForeignKey(Bundle, on_delete=models.PROTECT, unique=True)
    Machine     = models.ForeignKey(RFIDMachine, on_delete=models.PROTECT, null=True, blank=True)
    CompletedAt = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['Employee']),
            models.Index(fields=['CompletedAt']),
        ]
