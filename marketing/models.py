from django.db import models
from django.contrib.auth.models import User
from django_countries.fields import CountryField

class Customer(models.Model):
    id = models.AutoField(primary_key=True)
    Name = models.CharField(max_length=255)
    Country = CountryField(max_length=20)
    Website = models.URLField(max_length=255, blank=True, null=True)
    Address = models.CharField(max_length=1023, blank=True, null=True)
    AccountManager = models.ForeignKey(User, on_delete=models.PROTECT, blank=True, null=True)

    class Meta:
        """Meta definition for Customers."""

        indexes = [
            models.Index(fields=['AccountManager',]),
            models.Index(fields=['Country',]),
        ]

class ExportDataDraft(models.Model):
    id = models.AutoField(primary_key=True)
    Country = CountryField(max_length=20)
    Exporter = models.CharField(max_length=255, blank=True, null=True)
    ShipDate = models.DateField()
    Importer = models.CharField(max_length=255, blank=True, null=True)
    Quantity = models.FloatField()
    Price = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    Currency = models.CharField(max_length=10, blank=True, null=True)
    HSCode = models.CharField(max_length=50, blank=True, null=True)
    Description = models.TextField(blank=True, null=True)
    Source = models.CharField(max_length=20, default='export')

class ExportData(models.Model):
    id = models.AutoField(primary_key=True)
    Country = CountryField(max_length=20)
    Exporter = models.CharField(max_length=255, blank=True, null=True)
    ShipDate = models.DateField()
    Importer = models.CharField(max_length=255, blank=True, null=True)
    Quantity = models.FloatField()
    Price = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    Currency = models.CharField(max_length=10, blank=True, null=True)
    HSCode = models.CharField(max_length=50, blank=True, null=True)
    Description = models.TextField(blank=True, null=True)

    class Meta:
        """Meta Definition for ExportData"""
        indexes = [
            models.Index(fields=['ShipDate',]),
            models.Index(fields=['Country',]),
        ]

class ImporterAlias(models.Model):
    '''Model definition for Importer Aliasing.'''
    id = models.AutoField(primary_key=True)
    Name = models.CharField(max_length=255, unique=True)
    Alias = models.CharField(max_length=255)

    class Meta:
        indexes = [
            models.Index(fields=['Name',]),
        ]

class ExporterAlias(models.Model):
    '''Model definition for Exporter Aliasing.'''
    id = models.AutoField(primary_key=True)
    Name = models.CharField(max_length=255, unique=True)
    Alias = models.CharField(max_length=255)

    class Meta:
        indexes = [
            models.Index(fields=['Name',]),
        ]

class CustomerContact(models.Model):
    id = models.AutoField(primary_key=True)
    Customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    Name = models.CharField(max_length=255)
    Designation = models.CharField(max_length=50)
    IsActive = models.BooleanField(default=True)
    PhoneNumber = models.CharField(max_length=50, blank=True, null=True)
    Email = models.EmailField(blank=True, null=True)

    class Meta:
        """Meta definition for Contact persons in customer."""

        indexes = [
            models.Index(fields=['Customer',]),
        ]

class Correspondance(models.Model):
    id = models.AutoField(primary_key=True)
    User = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    Customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    Type = models.CharField(max_length=31)
    Date = models.DateField(auto_now_add=True)
    NextCorrespondanceDate = models.DateField(null=True, blank=True)
    IsClosed = models.BooleanField(default=False)
    Conversation = models.TextField(default='No answer')
    
    class Meta:
        """Meta definition for Correspondances."""

        indexes = [
            models.Index(fields=['User', 'Customer']),
            models.Index(fields=['IsClosed']),
        ]

class Inquiry(models.Model):
    id = models.AutoField(primary_key=True)
    Customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    Correspondance = models.ForeignKey(Correspondance, on_delete=models.PROTECT)
    Details = models.CharField(max_length=255)
    Attachment = models.FileField(upload_to='docuemnts/marketing/inquiries/', null=True, blank=True)
    ReceivedAt = models.DateTimeField(auto_now_add=True)
    ReceivedBy = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    IsClosed = models.BooleanField(default=False)

    class Meta:
        """Meta definition for Inquiries."""
        indexes = [
            models.Index(fields=['ReceivedBy', 'Customer']),
            models.Index(fields=['IsClosed']),
        ]

