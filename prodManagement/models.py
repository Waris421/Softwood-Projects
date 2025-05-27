from django.db import models
from django.contrib.auth.models import User
from apparelManagement.models import Department, StyleCard, WorkOrder, OrderVariant

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
    MachineId = models.CharField(max_length=31)
    PurchaseDate = models.DateField(auto_now_add=True)
    Type = models.CharField(max_length=63)
    FunctionStatus = models.CharField(max_length=15)
    Manufacturer = models.CharField(max_length=15, blank=True, null=True)
    ModelNumber = models.CharField(max_length=25, null=True, blank=True)
    SerialNumber = models.CharField(max_length=15, null=True, blank=True)
    Department = models.ForeignKey(Department, on_delete=models.PROTECT, blank=True, null=True)

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

    class Meta:
        indexes = [
            models.Index(fields=['Cut']),
            models.Index(fields=['Size']),
        ]

class Worker(models.Model):
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
    CardId = models.PositiveBigIntegerField(primary_key=True)
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