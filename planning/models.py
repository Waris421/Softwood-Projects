from django.db import models
from apparelManagement.models import Department

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
