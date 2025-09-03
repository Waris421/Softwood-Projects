from django.db import models
from apparelManagement.models import Department, StyleCard, StyleRoute, WorkOrder, WorkOrderInitialPlan
from apparelManagement.models import InvRequirement, POAllocation, POInventory, PurchaseOrder, Inventory
from apparelManagement.models import RecAllocation, RecInventory, InventoryReciept
from apparelManagement.models import StyleConsumption

class SubDepartment (models.Model):
    id=models.AutoField(primary_key=True)
    Department = models.ForeignKey(Department, on_delete=models.CASCADE)
    Name = models.CharField(max_length=31)
    FullName = models.CharField(max_length=63, null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['Department',])
        ]

class Capacity (models.Model):
    id = models.AutoField(primary_key=True)
    Source = models.CharField(max_length=50)
    Capacity = models.FloatField()

    class Meta:
        indexes = [
            models.Index(fields=['Source',]),
        ]

class ProductionPlan(models.Model):
    id = models.AutoField(primary_key=True)
    WorkOrder = models.ForeignKey(WorkOrder, on_delete=models.PROTECT)
    StyleRoute = models.ForeignKey(StyleRoute, on_delete=models.CASCADE)
    Source = models.ForeignKey(Capacity, on_delete=models.SET_NULL, null=True)
    MDate = models.DateField(blank=True, null=True)
    ActualDate = models.DateField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['WorkOrder',]),
            models.Index(fields=['StyleRoute',]),
            models.Index(fields=['Source',]),
            models.Index(fields=['ActualDate',]),
        ]