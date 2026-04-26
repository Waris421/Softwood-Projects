from django.test import TestCase
import pandas as pd
from apparelManagement import models
from apparelManagement.services import purchase_receipt_service


class TestAddPurchaseReceipt(TestCase):

    def setUp(self):
        from datetime import date

        self.supplier, _ = models.Supplier.objects.get_or_create(Name='Test Supplier')

        self.unitGroup, _ = models.UnitGroup.objects.get_or_create(
            Name='Quantity', defaults={'StandardUnit': 'PCS'}
        )
        self.unit, _ = models.Unit.objects.get_or_create(
            Name='PCS', defaults={'Group': self.unitGroup, 'Factor': 1.0}
        )

        self.inventory = models.Inventory.objects.create(
            Code='TEST001',
            Name='Test Item',
            Unit=self.unit,
        )

        self.purchaseOrder = models.PurchaseOrder.objects.create(
            Supplier=self.supplier,
            DeliveryDate=date(2026, 12, 31),
        )

        self.workOrder = models.WorkOrder.objects.create(
            OrderNumber=9999,
            DeliveryDate=date(2026, 12, 31),
            Type='Export',
        )

        self.poInventory = models.POInventory.objects.create(
            PONumber=self.purchaseOrder,
            Inventory=self.inventory,
            Variant='',
            Quantity=100.0,
            Price=500.0,
            Forex=1.0,
        )

        self.poAllocation = models.POAllocation.objects.create(
            POInvId=self.poInventory,
            WorkOrder=self.workOrder,
            Quantity=100.0,
        )
        
    def test_full_flow(self):
        print('\n--- Setting up test data ---')
        print(f'Supplier: {self.supplier.Name}')
        print(f'Inventory: {self.inventory.Code} — {self.inventory.Name}')
        print(f'Purchase Order ID: {self.purchaseOrder.id}')
        print(f'Work Order: {self.workOrder.OrderNumber}')
        print(f'PO Inventory ID: {self.poInventory.id} | Qty: {self.poInventory.Quantity} | Price: {self.poInventory.Price}')
        print(f'PO Allocation: WorkOrder {self.workOrder.OrderNumber} gets {self.poAllocation.Quantity} units')

        dfReceipt = pd.DataFrame([{
            'PONumber': self.purchaseOrder.id,
            'Invoice': 'TEST-INV-001',
            'Vehicle': 'TEST-TRUCK',
            'Bilty': 'TEST-BILTY',
            'BiltyValue': '',
        }])

        dfRecInventories = pd.DataFrame([{
            'POInvId': self.poInventory.id,
            'Name': 'Test Item',
            'Variant': '',
            'Price': 500.0,
            'Quantity': '100',
        }])

        print('\n--- Calling AddPurchaseReceipt ---')
        result = purchase_receipt_service.AddPurchaseReceipt(dfReceipt, dfRecInventories)
        print(f'Receipt created with ID: {result}')

        # Receipt was created
        receipt = models.InventoryReciept.objects.filter(id=result).first()
        self.assertIsNotNone(receipt)
        print(f'\n--- Receipt ---')
        print(f'ID: {receipt.id} | Supplier: {receipt.Supplier} | PO: {receipt.PONumber.id}')

        # RecInventory row was created
        rec_inv = models.RecInventory.objects.filter(ReceiptNumber=result).first()
        self.assertIsNotNone(rec_inv)
        print(f'\n--- Received Inventory ---')
        print(f'ID: {rec_inv.id} | Inventory: {rec_inv.InventoryCode} | Qty: {rec_inv.Quantity}')

        # Allocation was created
        allocation = models.RecAllocation.objects.filter(RecInvId=rec_inv).first()
        self.assertIsNotNone(allocation)
        print(f'\n--- Allocation ---')
        print(f'Work Order: {allocation.WorkOrder.OrderNumber} | Qty allocated: {allocation.Quantity}')

        # Stock was updated
        stock = models.InventoryStock.objects.filter(Inventory=self.inventory).first()
        self.assertIsNotNone(stock)
        print(f'\n--- Stock Update ---')
        print(f'Inventory: {stock.Inventory} | New Qty: {stock.StockQuantity} | New Value: {stock.StockValue}')
        self.assertEqual(float(stock.StockQuantity), 100.0)
        self.assertEqual(float(stock.StockValue), 50000.0)

        print('\n--- All checks passed ---')
