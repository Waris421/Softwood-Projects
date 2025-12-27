from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation

from core.services.generic_services import stringValidator as string_validator

InvGroups = [
    ('TRIM','Trim'),
    ('WASHING','Washing'),
    ('ELECTRICAL','Electrical'),
    ('FABRIC','Fabric'),
    ('MECHANICAL','Mechanical'),
    ('OTHERS','Others'),
    ('MEDICINE','Medicine'),
    ('STATIONERY','Stationery'),
    ('HOUSEKEEPING','Housekeeping'),
    ('ELECTRONICS','Electronics'),
    ('FXDASSETS','Fixed Assets')
    ]

AccTypes = [
    ('Customer','Customer'),
    ('Supplier','Supplier'),
    ('Department','Department')
]

Categories = [
    ('Man','Man'),
    ('Woman','Woman'),
    ('Boy','Boy'),
    ('Girl','Girl'),
    ('Baby','Baby')
]

ConsTypes = [
    ('Fab','Fabric'),
    ('BW','BW Trim'),
    ('AW','AW Trim')
]

Routes = [
    ('Cutting','Cutting'),
    ('Stitching','Stitching'),
    ('Washing','Washing'),
    ('Finishing','Finishing'),
    ('Embroidery','Embroidery'),
    ('Printing','Printing'),
    ('Embelishment','Embelishment'),
    ('Embossing','Embossing'),
    ('Final Audit','Final Audit'),
    ('Testing','Testing'),
]

OrderTypes = [
    ('Export','Export'),
    ('CMT','CMT'),
    ('Local','Local'),
    ('SMS','SMS'),
]

Sections = [
    ('Small Parts', 'Small Parts'),
    ('Front','Front'),
    ('Back','Back'),
    ('Assembly 1','Assembly 1'),
    ('Assembly 2','Assembly 2'),
    ('Finishing','Finishing')
]

SkillLevels = [
    (1, 1),
    (2, 2),
    (3, 3),
    (4, 4)
]

class Notification(models.Model):
    """Data model for handling notifications."""

    id = models.AutoField(primary_key=True)
    User = models.ForeignKey(User, on_delete=models.CASCADE)
    Heading = models.CharField(max_length=150)
    Summary = models.CharField(max_length=255)
    Body = models.TextField()
    URL = models.CharField(max_length=100)
    DateTime = models.DateTimeField(auto_now_add=True)
    IsRead = models.BooleanField(default=False)

    class Meta:
        #This reduces the loading time when reading the database, but increases writing time.
        indexes = [
            models.Index(fields=['User']),
            models.Index(fields=['IsRead']),
        ]

class Inventory (models.Model):
    """Data model for handling notifications."""

    Code = models.CharField (primary_key=True, max_length=255, validators=[string_validator]
                             ,help_text='Slash (/) is not allowed here.', unique=True)                  #Inventory Code
    Name = models.CharField (max_length=255)
    Group = models.CharField (max_length=15, choices=InvGroups)
    Unit = models.ForeignKey ('Unit', null=True, on_delete=models.SET_NULL)
    AuditReq = models.BooleanField (default=True, blank=True)
    Life = models.FloatField (default=0, blank=True, help_text='Days from IH to Expirty')
    InUse = models.BooleanField (default=True, blank=True)
    LeadTime = models.FloatField (blank=True, default=0)
    MinStockLvl = models.FloatField (blank=True, default=0)
    StandardPrice = models.FloatField (blank=True, default=0)
    Currency = models.ForeignKey ('Currency', null=True, blank=True, on_delete=models.SET_NULL)

    class Meta:
        #This reduces the loading time when reading the database, but increases writing time.
        indexes = [
            models.Index(fields=['Group']),
            models.Index(fields=['InUse']),
            models.Index(fields=['AuditReq']),
        ]

class InventoryCodePart1 (models.Model):
    """Data model for handling the first part of inventory code generator."""

    Code = models.CharField(max_length=3, primary_key=True)
    Name = models.CharField(max_length=10)

class InventoryCodePart2 (models.Model):
    """Data model for handling the second part of inventory code generator."""

    id = models.AutoField(primary_key=True)
    Code = models.CharField(max_length=5)
    Name = models.CharField(max_length=40)
    Part1 = models.ForeignKey (InventoryCodePart1, on_delete=models.PROTECT)

class InventoryCodePart3 (models.Model):
    """Data model for handling the third par of inventory code generator."""

    id = models.AutoField(primary_key=True)
    Code = models.CharField(max_length=5)
    Name = models.CharField(max_length=40)
    Part2 = models.ForeignKey (InventoryCodePart2, on_delete=models.PROTECT)

class UnitGroup (models.Model):
    """Data model for handling Main Unit Categories."""

    Name = models.CharField(primary_key=True, max_length=25)
    StandardUnit = models.CharField (max_length=25)

class Unit (models.Model):
    """Data model for handling all units."""

    Name = models.CharField(primary_key=True, max_length=25)
    Group = models.ForeignKey(UnitGroup, on_delete=models.CASCADE)
    Factor = models.FloatField(validators=[MinValueValidator(0.00000000001, "Must be greater than 0")])
    #Standard Unit = This Unit * Factor

class Currency (models.Model):
    """Data model for handling currencies."""

    Code = models.CharField (primary_key=True, max_length=5)
    Name = models.CharField (max_length=255)                      
    IsLocal = models.BooleanField (default=False, blank=True)           #There must be only one local currency.

class ForexRate(models.Model):
    """Data model for Forex Rates log."""

    id = models.AutoField(primary_key=True)
    Date = models.DateField(auto_now_add=True)
    Currency = models.ForeignKey(Currency, on_delete=models.CASCADE)
    Rate = models.FloatField(validators=[MinValueValidator(0.00000000001, "Must be greater than 0")])

class Supplier (models.Model):
    """Data model for handling Suppliers."""

    Name = models.CharField (primary_key=True, max_length=25)
    TradeName = models.CharField (max_length=255, blank=True, null=True)
    Address = models.CharField (max_length=15, blank=True, null=True)
    NTN = models.CharField (max_length=50, blank=True, null=True)
    PaymentTerms = models.CharField (max_length=255, blank=True, null=True)
    DocumentsURL = models.CharField (max_length=1000, blank=True, null=True)

class Customer (models.Model):
    """Data model for handling Customers."""

    Name = models.CharField (primary_key=True, max_length=25)
    TradeName = models.CharField (max_length=255, blank=True, null=True)
    Address = models.CharField (max_length=63, blank=True, null=True)
    VATNumber = models.CharField (max_length=50, blank=True, null=True)
    PaymentTerms = models.CharField (max_length=255, blank=True, null=True)
    DocumentsURL = models.CharField (max_length=1000, blank=True, null=True)

class Department (models.Model):
    """Data model for handling Departments."""

    Name = models.CharField (primary_key=True, max_length=25)
    FullName = models.CharField (max_length=255, blank=True, null=True)
    Location = models.CharField (max_length=255, blank=True, null=True)

class StyleCard (models.Model):
    """Data model for a style's main data."""

    StyleCode = models.CharField (primary_key=True, max_length=255, validators=[string_validator]
                             ,help_text='Slash (/) is not allowed here.')
    StyleName = models.CharField (max_length=255)
    Customer = models.ForeignKey (Customer, null=True, blank=True, on_delete=models.SET_NULL)
    Category = models.CharField (max_length=15, choices=Categories)
    Notes = models.CharField (max_length = 40)
    Attachments = GenericRelation('Attachment', content_type_field='ContentType', object_id_field='ObjectId')
    RoutePreset = models.ForeignKey('RoutePreset', on_delete=models.PROTECT)

class StyleVariant (models.Model):
    """Data model for a style's variants."""

    id = models.AutoField (primary_key=True)
    Style = models.ForeignKey (StyleCard, on_delete = models.CASCADE)
    VariantCode = models.CharField (max_length=50)

    class Meta:
        #This reduces the loading time when reading the database, but increases writing time.
        indexes = [
            models.Index(fields=['Style']),
        ]

class StyleConsumption (models.Model):
    """Data model for a style's consumptions."""

    id = models.AutoField (primary_key=True)
    Style = models.ForeignKey (StyleCard, on_delete = models.CASCADE)
    InventoryCode = models.ForeignKey (Inventory, on_delete = models.PROTECT)
    Consumption = models.FloatField (validators=[MinValueValidator(0, "Can't be less than 0")], blank=True, null=True)
    Unit = models.ForeignKey (Unit, on_delete = models.PROTECT, blank=True, null=True)
    Type = models.CharField (max_length=15, choices=ConsTypes, blank=True, null=True, default='BW')
    FinalCons = models.FloatField ()
    HasVariant = models.BooleanField (default=False, blank=True, null=True)
    SizeDetails = models.CharField (max_length=255, blank=True, null=True)

    class Meta:
        #This reduces the loading time when reading the database, but increases writing time.
        indexes = [
            models.Index(fields=['Style']),
        ]

class StyleRoute (models.Model):
    """Data model for a style's production route."""

    id = models.AutoField (primary_key=True)
    Style = models.ForeignKey(StyleCard, on_delete = models.CASCADE)
    Stage = models.CharField (max_length=50, choices = Routes, blank=True, null=True)
    Cost = models.FloatField (null=True)

    PreReqs = models.ManyToManyField('self', blank=True,symmetrical=False)

    class Meta:
        #This reduces the loading time when reading the database, but increases writing time.
        indexes = [
            models.Index(fields=['Style']),
        ]

class RoutePreset(models.Model):
    """Model definition for RoutePrest."""

    id = models.AutoField(primary_key=True)
    Name = models.CharField(max_length=100, unique=True)
    class Meta:
        """Meta definition for RoutePrest."""

        indexes = [
            models.Index(fields=['Name']),
        ]

class RoutePresetStage(models.Model):
    """Model definition for RoutePresetStage."""

    id = models.AutoField(primary_key=True)
    RoutePreset = models.ForeignKey(RoutePreset, on_delete=models.CASCADE)
    Stage = models.CharField (max_length=50, choices = Routes, blank=True, null=True) 
    PreReqs = models.ManyToManyField('self', blank=True,symmetrical=False)   

    class Meta:
        """Meta definition for RoutePresetStages."""
        indexes = [
            models.Index(fields=['RoutePreset']),
        ]

class WorkOrder (models.Model):
    """Data model for a Work Order's main data."""

    OrderNumber = models.IntegerField (primary_key=True)
    StyleCode = models.ForeignKey (StyleCard, null=True, on_delete=models.PROTECT)
    Customer = models.ForeignKey (Customer, null=True, on_delete=models.PROTECT)
    OrderDate = models.DateField (auto_now_add=True, blank=True)
    Merchandiser = models.ForeignKey (User, null=True, on_delete=models.SET_NULL)
    DeliveryDate = models.DateField()
    Type = models.CharField(max_length=15, choices=OrderTypes)
    Currency = models.ForeignKey (Currency, null=True, on_delete=models.PROTECT)
    Price = models.FloatField(null=True, blank=True)
    Agent = models.CharField (max_length=50, blank=True, null=True)
    Commission = models.FloatField (null=True, blank=True, default=0.0)
    ExcessCut = models.FloatField (blank=True, null=True, default=3.0)
    Attachments = GenericRelation('Attachment', content_type_field='ContentType', object_id_field='ObjectId')

    class Meta:
        #This reduces the loading time when reading the database, but increases writing time.
        indexes = [
            models.Index(fields=['StyleCode']),
            models.Index(fields=['Customer']),
            models.Index(fields=['Merchandiser']),
        ]

class WorkOrderInitialPlan (models.Model):
    """Data model for a Work Order's initial plan."""

    id = models.AutoField(primary_key=True)
    WorkOrder = models.ForeignKey(WorkOrder, on_delete=models.CASCADE)
    FabricETA = models.DateField()
    BWTrimETA = models.DateField()
    AWTrimETA = models.DateField()
    PullBack = models.IntegerField(default=0, null=True, blank=True)

    class Meta:
        #This reduces the loading time when reading the database, but increases writing time.
        indexes = [
            models.Index(fields=['WorkOrder']),
        ]

class OrderVariant (models.Model):
    """Data model for a Work Order's variants."""

    id = models.AutoField (primary_key=True)
    OrderNumber = models.ForeignKey (WorkOrder, on_delete=models.CASCADE)
    Name = models.CharField (max_length=255)
    Description = models.CharField (max_length=255, null=True, blank=True)
    Quantity = models.IntegerField(null=True, blank=True, default=0)

    class Meta:
        #This reduces the loading time when reading the database, but increases writing time.
        indexes = [
            models.Index(fields=['OrderNumber']),
        ]

class InvRequirement (models.Model):
    """Data model for a Work Order's inventory requirement."""

    id = models.AutoField (primary_key=True)
    OrderNumber = models.ForeignKey (WorkOrder, on_delete = models.CASCADE)
    InventoryCode = models.ForeignKey (Inventory, on_delete = models.PROTECT)
    Variant = models.CharField (max_length=255, blank=True, null=True)
    Quantity = models.FloatField (null=True, blank=True)

    class Meta:
        #This reduces the loading time when reading the database, but increases writing time.
        indexes = [
            models.Index(fields=['OrderNumber']),
        ]

class PurchaseOrder (models.Model):
    """Data model for purchase orders' main data."""

    id = models.AutoField (primary_key=True)
    OrderDate = models.DateField (auto_now_add=True)
    DeliveryDate = models.DateField ()
    Supplier = models.ForeignKey (Supplier, on_delete=models.PROTECT)
    Tax = models.FloatField (default=0.0, blank=True, null=True)

    class Meta:
        #This reduces the loading time when reading the database, but increases writing time.
        indexes = [
            models.Index(fields=['DeliveryDate']),
            models.Index(fields=['Supplier']),
        ]

class POInventory (models.Model):
    """Data model for a PO's inventory details."""

    id = models.AutoField (primary_key=True)
    PONumber = models.ForeignKey (PurchaseOrder, on_delete = models.CASCADE)
    Inventory = models.ForeignKey (Inventory, on_delete=models.PROTECT)
    Variant = models.CharField (max_length=50, blank=True, null=True)
    Quantity = models.FloatField (validators=[MinValueValidator(0, "Quantity can't be less than 0")])
    Price = models.FloatField (validators=[MinValueValidator(0, "Price can't be less than 0")])
    Currency = models.ForeignKey (Currency,null=True, on_delete=models.SET_NULL)
    Forex = models.FloatField (blank=True, null=True
                               , validators=[MinValueValidator(0.0000001, "Forex can't be less than 0")])
    
    class Meta:
        #This reduces the loading time when reading the database, but increases writing time.
        indexes = [
            models.Index(fields=['PONumber','Inventory']),
        ]

class POAllocation (models.Model):
    """Data model for a PO's inventory allocation details."""

    id = models.AutoField (primary_key=True)
    POInvId = models.ForeignKey (POInventory, on_delete=models.CASCADE)
    WorkOrder = models.ForeignKey (WorkOrder, on_delete=models.PROTECT)
    Quantity = models.FloatField()

    class Meta:
        #This reduces the loading time when reading the database, but increases writing time.
        indexes = [
            models.Index(fields=['POInvId','WorkOrder']),
        ]

class InventoryReciept (models.Model):
    """Data model for purchase receipts' main data."""

    id = models.AutoField (primary_key=True)
    ReceiptDate = models.DateField (auto_now_add=True)
    Invoice = models.CharField (max_length=100, blank=True, null=True)
    Supplier = models.ForeignKey (Supplier, on_delete=models.PROTECT)
    Vehicle = models.CharField (max_length=50, blank=True, null=True)
    Bilty = models.CharField (max_length=50, blank=True, null=True)
    BiltyValue = models.FloatField (default=0, blank=True, null=True)
    PONumber = models.ForeignKey (PurchaseOrder, on_delete=models.PROTECT)

    class Meta:
        #This reduces the loading time when reading the database, but increases writing time.
        indexes = [
            models.Index(fields=['PONumber']),
            models.Index(fields=['ReceiptDate']),
            models.Index(fields=['Supplier']),
        ]

class RecInventory (models.Model):
    """Data model for purchase receipts' inventories details."""

    id = models.AutoField (primary_key=True)
    ReceiptNumber = models.ForeignKey (InventoryReciept, on_delete=models.CASCADE)
    InventoryCode = models.ForeignKey (Inventory, on_delete=models.PROTECT)
    Variant = models.CharField (max_length=50, blank=True, null=True)
    Quantity = models.FloatField(validators=[MinValueValidator(0, "Quantity can't be less than 0")])
    Approval = models.BooleanField (blank=True, null=True, default=False)
    QualityComments = models.CharField (max_length=255,blank=True, null=True)

    class Meta:
        #This reduces the loading time when reading the database, but increases writing time.
        indexes = [
            models.Index(fields=['ReceiptNumber','InventoryCode']),
        ]

class RecAllocation (models.Model):
    """Data model for purchase receipts' allocation details."""

    id = models.AutoField (primary_key=True)
    RecInvId = models.ForeignKey (RecInventory, on_delete = models.CASCADE)
    WorkOrder = models.ForeignKey (WorkOrder, on_delete=models.PROTECT)
    Quantity = models.FloatField(validators=[MinValueValidator(0, "Quantity an't be less than 0")])
    
    class Meta:
        #This reduces the loading time when reading the database, but increases writing time.
        indexes = [
            models.Index(fields=['RecInvId','WorkOrder']),
        ]

class PurchaseDemand (models.Model):
    """Data model for purchase demands' main data."""

    id = models.AutoField  (primary_key=True)
    DemandDate = models.DateField (auto_now_add=True)
    Department = models.ForeignKey(Department, on_delete=models.PROTECT)
    Demandee = models.CharField (max_length=50, blank=False, null=False)
    Approval = models.BooleanField (null=True, blank=True)
    ApprovedBy = models.ForeignKey (User, null=True, on_delete=models.SET_NULL)
    PONumber = models.ForeignKey(PurchaseOrder,null=True, on_delete=models.SET_NULL)

    class Meta:
        #This reduces the loading time when reading the database, but increases writing time.
        indexes = [
            models.Index(fields=['Department']),
            models.Index(fields=['Approval']),
            models.Index(fields=['PONumber']),
        ]

class PDInventory (models.Model):
    """Data model for purchase demands' inventory details."""

    id=models.AutoField (primary_key=True)
    PDNumber = models.ForeignKey (PurchaseDemand, on_delete=models.CASCADE)
    Inventory = models.ForeignKey (Inventory, on_delete=models.PROTECT)
    Variant = models.CharField (max_length=50, blank=True, null=True)
    Quantity = models.FloatField(validators=[MinValueValidator(0, "Quantity can't be less than 0")])
    Price = models.FloatField(validators=[MinValueValidator(0, "Price can't be less than 0")])
    Currency = models.ForeignKey (Currency, null=True, on_delete=models.SET_NULL)
    Forex = models.FloatField (blank=True, null=True
                               , validators=[MinValueValidator(0.0000001, "Forex can't be less than 0")])
    PONumber = models.ForeignKey(PurchaseOrder,null=True, on_delete=models.SET_NULL)
    
    class Meta:
        #This reduces the loading time when reading the database, but increases writing time.
        indexes = [
            models.Index(fields=['PDNumber','Inventory']),
        ]

class Requisition (models.Model):
    """Data model for Inventory requisition from store."""

    id = models.AutoField (primary_key=True)
    DateTime = models.DateTimeField (auto_now_add=True)
    Department = models.ForeignKey(Department, on_delete=models.PROTECT)
    RequestBy = models.CharField (max_length=50, blank=False, null=False)
    Confirmation = models.BooleanField (blank=True, null=True, default=False)
    StoreComments = models.CharField (max_length=255, blank=True, null=True)

    class Meta:
        #This reduces the loading time when reading the database, but increases writing time.
        indexes = [
            models.Index(fields=['Department']),
            models.Index(fields=['DateTime']),
            models.Index(fields=['Confirmation']),
        ]

class RequisitionInventory (models.Model):
    """Data model for inventory details of requisitions."""

    id = models.AutoField (primary_key=True)
    Requisition = models.ForeignKey(Requisition, on_delete=models.CASCADE)
    Inventory = models.ForeignKey (Inventory, on_delete=models.PROTECT)
    Variant = models.CharField (max_length=50, blank=True, null=True)
    Quantity = models.FloatField(validators=[MinValueValidator(0, "Quantity can't be less than 0")])

    class Meta:
        #This reduces the loading time when reading the database, but increases writing time.
        indexes = [
            models.Index(fields=['Requisition','Inventory']),
        ]

class RequisitionAllocation (models.Model):
    """Data model for allocation details of requisitions."""

    id = models.AutoField (primary_key=True)
    RequisitionInventory = models.ForeignKey (RequisitionInventory, on_delete=models.CASCADE)
    WorkOrder = models.ForeignKey (WorkOrder, on_delete=models.PROTECT)
    Quantity = models.FloatField(validators=[MinValueValidator(0, "Quantity an't be less than 0")])

    class Meta:
        #This reduces the loading time when reading the database, but increases writing time.
        indexes = [
            models.Index(fields=['RequisitionInventory','WorkOrder']),
        ]

class Issuance (models.Model):
    """Data model for main data of issuances."""

    id = models.AutoField (primary_key=True)
    IssuanceDate = models.DateField (auto_now_add=True)
    Department = models.ForeignKey(Department, on_delete=models.PROTECT, blank=True, null=True)
    Supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, blank=True, null=True)
    ReceivedBy = models.CharField (max_length=50, blank=False, null=False)
    InventoryRequisition = models.ForeignKey(Requisition, on_delete=models.PROTECT)

    class Meta:
        #This reduces the loading time when reading the database, but increases writing time.
        indexes = [
            models.Index(fields=['Department']),
        ]

class IssueInventory (models.Model):
    """Data model for inventory details of issuances."""

    id = models.AutoField (primary_key=True)
    Issuance = models.ForeignKey(Issuance, on_delete=models.CASCADE)
    Inventory = models.ForeignKey (Inventory, on_delete=models.PROTECT)
    Variant = models.CharField (max_length=50, blank=True, null=True)
    Quantity = models.FloatField(validators=[MinValueValidator(0, "Quantity can't be less than 0")])

    class Meta:
        #This reduces the loading time when reading the database, but increases writing time.
        indexes = [
            models.Index(fields=['Issuance','Inventory']),
        ]

class IssueAllocation (models.Model):
    """Data model for allocation details of issuances."""

    id = models.AutoField (primary_key=True)
    IssueInventory = models.ForeignKey (IssueInventory, on_delete=models.CASCADE)
    WorkOrder = models.ForeignKey (WorkOrder, on_delete=models.PROTECT)
    Quantity = models.FloatField(validators=[MinValueValidator(0, "Quantity an't be less than 0")])

    class Meta:
        #This reduces the loading time when reading the database, but increases writing time.
        indexes = [
            models.Index(fields=['IssueInventory','WorkOrder']),
        ]

class Attachment(models.Model):
    """
    A model to hold file attachments, linked generically to any other model.
    """

    id = models.AutoField(primary_key=True)
    File = models.FileField(upload_to='documents/%Y/%m/%d/')
    Description = models.CharField(max_length=255, blank=True, null=True)
    AddedAt = models.DateTimeField(auto_now_add=True)
    ContentType = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    ObjectId = models.CharField(max_length=50, db_index=True)
    Content = GenericForeignKey('ContentType', 'ObjectId')

class ThreadConsumptionRequest(models.Model):
    id=models.AutoField(primary_key=True)
    RequestDate = models.DateField(auto_now_add=True)
    RequestBy = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    IsClosed = models.BooleanField(default=False)

class ThreadConsumptionRequestStyles(models.Model):
    id=models.AutoField(primary_key=True)
    Request = models.ForeignKey(ThreadConsumptionRequest, on_delete=models.CASCADE)
    Style = models.ForeignKey(StyleCard, on_delete=models.PROTECT)

class ThreadConsumptionRequestThreads(models.Model):
    id=models.AutoField(primary_key=True)
    Request = models.ForeignKey(ThreadConsumptionRequest, on_delete=models.CASCADE)
    Thread = models.CharField(max_length=255)