import pandas as pd
import numpy as np

from django.forms import model_to_dict
from django.db.models import Q
from django.db import transaction
from decimal import Decimal

from .. import models
from core.services.generic_services import updateModelWithDF, convertTexttoObject, concatenateValues, dfToListOfDicts

def GetReceiptList(supplier: str, receiptNumber: int):
    '''
    Get the list of all purchase orders
    '''
    fields = ['id','ReceiptDate','Supplier','PONumber']
    filters = Q()
    if receiptNumber:
        filters &= Q(id=receiptNumber)
    if supplier:
        filters &= Q(Supplier=supplier)
    
    receipts = models.InventoryReciept.objects.filter(filters).values(*fields)
    dfReceipts = pd.DataFrame(receipts) if receipts else pd.DataFrame(columns=fields)
    del receipts
    
    fields = ['id','ReceiptNumber','InventoryCode']
    inventories = models.RecInventory.objects.filter(ReceiptNumber__in=dfReceipts['id'].to_list()).values(*fields)
    dfInventories = pd.DataFrame(inventories) if inventories else pd.DataFrame(columns=fields)
    del inventories

    fields = ['RecInvId','WorkOrder']
    allocations = models.RecAllocation.objects.filter(RecInvId__in=dfInventories['id'].to_list()).values(*fields)
    dfAllocations = pd.DataFrame(allocations) if allocations else pd.DataFrame(columns=fields)
    del allocations

    fields = ['Code','Name']
    inventoryCards = models.Inventory.objects.filter(Code__in=dfInventories['InventoryCode'].to_list()).values(*fields)
    dfInventoryCards = pd.DataFrame(inventoryCards) if inventoryCards else pd.DataFrame(columns=fields)
    del inventoryCards, fields

    #Give verbose names to the id columns
    dfReceipts.rename(inplace=True, columns={'id':'ReceiptNumber'})
    dfInventories.rename(inplace=True, columns={'id':'RecInvId'})

    dfReceipts = pd.merge(left=dfReceipts, right=dfInventories, left_on='ReceiptNumber', right_on='ReceiptNumber', how='left')
    del dfInventories

    dfReceipts = pd.merge(left=dfReceipts, right=dfAllocations, left_on='RecInvId', right_on='RecInvId', how='left')
    dfReceipts.drop(inplace=True, columns=['RecInvId'])
    del dfAllocations

    dfReceipts = pd.merge(left=dfReceipts, right=dfInventoryCards, left_on='InventoryCode', right_on='Code', how='left')
    dfReceipts.drop(inplace=True, columns=['InventoryCode','Code'])
    del dfInventoryCards

    #Convert work order float to string, without decimals
    dfReceipts['WorkOrder'] = np.where(dfReceipts['WorkOrder'].isna(), 0, dfReceipts['WorkOrder'])
    dfReceipts['WorkOrder'] = dfReceipts['WorkOrder'].astype(int).astype(str)
    dfReceipts['WorkOrder'] = np.where(dfReceipts['WorkOrder']=='0', '', dfReceipts['WorkOrder'])

    #Concate rows who have same PO number in common
    dfReceipts = dfReceipts.groupby('ReceiptNumber').agg({
        'ReceiptDate': 'first',
        'Supplier': 'first',
        'PONumber': 'first',
        'Name': concatenateValues,
        'WorkOrder': concatenateValues,
    }).reset_index()

    dfReceipts = dfReceipts.sort_values(by='ReceiptNumber', ascending=False)
    return dfToListOfDicts(dfReceipts)

def GetPOData(purchaseOrder: models.PurchaseOrder):
    fields = ['id','Inventory','Variant','Quantity', 'Price', 'Currency']
    poInventories = models.POInventory.objects.filter(PONumber=purchaseOrder).values(*fields)
    dfPOInventories = pd.DataFrame(poInventories) if poInventories else pd.DataFrame(columns=fields)
    del poInventories

    fields=['Code','Name', 'Unit']
    inventories = models.Inventory.objects.filter(Code__in=dfPOInventories['Inventory'].to_list()).values(*fields)
    dfInventories = pd.DataFrame(inventories) if inventories else pd.DataFrame(inventories)
    del inventories, fields

    dfPOInventories = pd.merge(left=dfPOInventories, right=dfInventories, left_on='Inventory', right_on='Code', how='left')
    del dfInventories
    dfPOInventories.drop(inplace=True, columns=['Code','Inventory'])

    return dfToListOfDicts(dfPOInventories)


def GetPOContext(poInventory):
    fields = ['WorkOrder', 'Quantity']
    allocations = models.POAllocation.objects.filter(POInvId=poInventory).values(*fields)
    dfAllocations = pd.DataFrame(allocations) if allocations else pd.DataFrame(columns=fields)

    fields = ['OrderNumber', 'StyleCode', 'Customer', 'Merchandiser']
    workOrders = models.WorkOrder.objects.filter(OrderNumber__in=dfAllocations['WorkOrder'].to_list()).values(*fields)
    dfWorkOrders = pd.DataFrame(workOrders) if workOrders else pd.DataFrame(columns=fields)
    del workOrders

    fields = ['id', 'first_name', 'last_name']
    users = models.User.objects.filter(id__in=dfWorkOrders['Merchandiser'].to_list()).values(*fields)
    dfUsers = pd.DataFrame(users) if users else pd.DataFrame(columns=fields)
    del users, fields

    dfWorkOrders = pd.merge(left=dfWorkOrders, right=dfUsers, left_on='Merchandiser', right_on='id', how='left')
    del dfUsers
    dfWorkOrders.drop(inplace=True, columns=['Merchandiser', 'id'])

    dfWorkOrders['Merchandiser'] = dfWorkOrders['first_name'] + ' ' + dfWorkOrders['last_name']
    dfWorkOrders.drop(inplace=True, columns=['first_name', 'last_name'])

    dfAllocations = pd.merge(left=dfAllocations, right=dfWorkOrders, left_on='WorkOrder', right_on='OrderNumber', how='left')
    del dfWorkOrders
    dfAllocations.drop(inplace=True, columns=['OrderNumber'])

    columsOrder = ['WorkOrder', 'StyleCode', 'Customer', 'Merchandiser', 'Quantity']
    dfAllocations = dfAllocations[columsOrder]

    totalQuantity = dfAllocations['Quantity'].sum()
    totalRow = {
        'WorkOrder': '',
        'Quantity': totalQuantity,
        'StyleCode': 'Total',
        'Customer': '',
        'Merchandiser': ''
    }
    dfAllocations.loc[len(dfAllocations)] = totalRow

    return dfToListOfDicts(dfAllocations)

def AddPurchaseReceipt(dfReceipt:pd.DataFrame, dfRecInventories:pd.DataFrame): # Takes the receipt that has info on supplier, PO, vehicle etc
    # dfReceipt — the main receipt info (supplier, PO number, vehicle, etc.) — like the top section of the form
    # dfRecInventories — the list of items received (fabric codes, quantities) — like the table at the bottom of the form
    '''
    Add the receipt from new receipt Form
    '''
    dfRecInventories['Quantity'] = np.where(dfRecInventories['Quantity'].str.len()>0, dfRecInventories['Quantity'], 0.0) # Cleaning the data. Discards the empty cells
    dfRecInventories['Quantity'] = dfRecInventories['Quantity'].astype(float)
    if dfRecInventories.empty:
        raise ValueError('No Inventory provided')

    purchaseOrder = dfReceipt['PONumber'][0] #ID Number of the PO
    purchaseOrder = models.PurchaseOrder.objects.get(id=purchaseOrder)

#  Get work order allocations from the original PO
    fields = ['POInvId','WorkOrder','Quantity']
    poAllocations = models.POAllocation.objects.filter(POInvId__in=dfRecInventories['POInvId'].to_list()).values(*fields)
    if poAllocations:
        dfPOAllocation = pd.DataFrame(poAllocations)
    else:
        dfPOAllocation = pd.DataFrame(columns=fields)
    del poAllocations

# — Get PO inventory details
    fields = ['id','Inventory','Variant','Price','Forex']
    poInventories  = models.POInventory.objects.filter(id__in=dfRecInventories['POInvId'].to_list()).values(*fields)
    if poInventories:
        dfPOInventories = pd.DataFrame(poInventories)
    else:
        dfPOInventories = pd.DataFrame(columns=fields)
    del poInventories, fields

    invReceipt = dfReceipt.iloc[0].to_dict()
    invReceipt['PONumber'] = purchaseOrder
    if not invReceipt['BiltyValue']:
        invReceipt['BiltyValue'] = None
    invReceipt['Supplier'] = purchaseOrder.Supplier
    del purchaseOrder

    receiptCard = models.InventoryReciept(**invReceipt)
    #receiptCard.save() # — THIS IS WHERE THE RECEIPT IS SAVED TO THE DATABASE
    del invReceipt, dfReceipt 

    dfRecInventories.drop(inplace=True, columns=['Name','Variant','Price'])
    dfRecInventories['POInvId'] = dfRecInventories['POInvId'].astype(int)

    dfRecInventories = pd.merge(left=dfRecInventories, right=dfPOInventories, left_on='POInvId', right_on='id', how='left')
    dfRecInventories.drop(inplace=True, columns=['id'])
    
    dfRecInventories['Inventory'] = convertTexttoObject(models.Inventory, dfRecInventories['Inventory'], 'Code')
    dfRecInventories.rename(inplace=True, columns={'Inventory':'InventoryCode'})
   
    # ── CALCULATE STOCK VALUE ──────────────────────────────────────────
    dfRecInventories['StockValue'] = dfRecInventories['Quantity'] * dfRecInventories['Price'] * dfRecInventories['Forex']


    # ── LIST 1: Build RecInventory objects in memory (nothing saved yet) ──
    recInventoryRows = []
    for _, row in dfRecInventories.iterrows():
        recInv = models.RecInventory(
            InventoryCode=row['InventoryCode'],
            Variant=row['Variant'],
            Quantity=row['Quantity'],
            ReceiptNumber=None,
            Approval=False,
            QualityComments=None,
        )
        recInventoryRows.append({
            'object': recInv,
            'POInvId': row['POInvId'],
        })

    print(f"--- LIST 1: RecInventory ({len(recInventoryRows)} items) ---")
    for item in recInventoryRows:
        obj = item['object']
        print(f"  {obj.InventoryCode} | {obj.Variant} | Qty: {obj.Quantity}")


    # ── LIST 2: Build RecAllocation data in memory (shortfall logic runs here) ──
    allocationData = []
    for item in recInventoryRows:
        recInv = item['object']
        allocation = dfPOAllocation[dfPOAllocation['POInvId'] == item['POInvId']].copy()

        if allocation.empty:
            print(f"  No allocation for {recInv.Variant} — skipping")
            continue

        shortfallPercentage = recInv.Quantity / allocation['Quantity'].sum()
        print(f"  Shortfall % for {recInv.Variant}: {shortfallPercentage:.2%}")

        if shortfallPercentage < 1:
            allocation['Quantity'] = allocation['Quantity'] * shortfallPercentage

        allocation['Quantity'] = np.floor(allocation['Quantity'] * 100) / 100
        allocation.drop(inplace=True, columns=['POInvId'])
        allocation['WorkOrder'] = convertTexttoObject(models.WorkOrder, allocation['WorkOrder'], 'OrderNumber')

        for _, allocRow in allocation.iterrows():
            allocationData.append({
                'WorkOrder': allocRow['WorkOrder'],
                'Quantity':  allocRow['Quantity'],
                'recInvRef': recInv,
            })

    print(f"--- LIST 2: RecAllocations ({len(allocationData)} items) ---")
    for item in allocationData:
        print(f"  WO: {item['WorkOrder']} | Qty: {item['Quantity']}")


    # ── LIST 3: Stock update data ──────────────────────────────────────
    stockUpdates = dfRecInventories[['InventoryCode','Variant','Quantity','StockValue']].to_dict('records')

    print(f"--- LIST 3: Stock Updates ({len(stockUpdates)} items) ---")
    for s in stockUpdates:
        print(f"  {s['InventoryCode']} | {s['Variant']} | +Qty: {s['Quantity']} | +Value: {s['StockValue']}")


    # ── SAVE EVERYTHING IN ONE ATOMIC BLOCK ───────────────────────────
    with transaction.atomic():

        # Step 1: Save receipt header
        receiptCard.save()
        print(f"--- Receipt saved: ID {receiptCard.id} ---")

        # Step 2: Link all RecInventory objects to the saved receipt
        for item in recInventoryRows:
            item['object'].ReceiptNumber = receiptCard

        # Step 3: Bulk save all RecInventory at once
        recInventoryObjects = [item['object'] for item in recInventoryRows]
        models.RecInventory.objects.bulk_create(recInventoryObjects)
        print(f"--- RecInventory bulk saved ({len(recInventoryObjects)} items) ---")

        # Step 4: Build RecAllocation objects and bulk save
        recAllocationList = [
            models.RecAllocation(
                WorkOrder=item['WorkOrder'],
                Quantity=item['Quantity'],
                RecInvId=item['recInvRef'],
            )
            for item in allocationData
        ]
        models.RecAllocation.objects.bulk_create(recAllocationList)
        print(f"--- RecAllocation bulk saved ({len(recAllocationList)} items) ---")

        # Step 5: Update InventoryStock — fetch all at once, update in memory, save all at once
        existingStocks = models.InventoryStock.objects.filter(
            Inventory__in=[s['InventoryCode'] for s in stockUpdates],
            Variant__in=[s['Variant'] for s in stockUpdates],
        )
        stockMap = {(s.Inventory, s.Variant): s for s in existingStocks}

        toCreate = []
        toUpdate = []
        for update in stockUpdates:
            key = (update['InventoryCode'], update['Variant'])
            if key in stockMap:
                record = stockMap[key]
                print(f"  [UPDATE] {update['Variant']} | Before → Qty: {record.StockQuantity} | Value: {record.StockValue}")
                record.StockQuantity += Decimal(str(update['Quantity']))
                record.StockValue    += Decimal(str(update['StockValue']))
                print(f"  [UPDATE] {update['Variant']} | After  → Qty: {record.StockQuantity} | Value: {record.StockValue}")
                toUpdate.append(record)
            else:
                newRecord = models.InventoryStock(
                    Inventory=update['InventoryCode'],
                    Variant=update['Variant'],
                    StockQuantity=Decimal(str(update['Quantity'])),
                    StockValue=Decimal(str(update['StockValue'])),
                )
                print(f"  [CREATE] {update['Variant']} | Before → Qty: 0 | Value: 0")
                print(f"  [CREATE] {update['Variant']} | After  → Qty: {newRecord.StockQuantity} | Value: {newRecord.StockValue}")
                toCreate.append(newRecord)

        if toCreate:
            models.InventoryStock.objects.bulk_create(toCreate)
            print(f"--- New stock records created: {len(toCreate)} ---")
        if toUpdate:
            models.InventoryStock.objects.bulk_update(toUpdate, ['StockQuantity', 'StockValue'])
            print(f"--- Stock records updated: {len(toUpdate)} ---")

    print(f"--- All done. Receipt ID: {receiptCard.id} ---")
    return receiptCard.id



def EditPurchaseReceipt (
        receiptObject: models.InventoryReciept, 
        dfReceipt: pd.DataFrame,
        dfRecInventory: pd.DataFrame,
        dfRecAllocation: pd.DataFrame
):
    '''
    Update the Receipt from the data in the Receipt table.
    '''
    allocId = dfReceipt['recId'][0]
    dfReceipt.drop(inplace=True, columns=['GRNNumber','ReceiptDate','PONumber','recId'])
    inventoryReceipt = dfReceipt.iloc[0].to_dict()
    del dfReceipt

    inventoryReceipt['Supplier'] = models.Supplier.objects.get(Name=inventoryReceipt['Supplier'])
    if inventoryReceipt['BiltyValue']:
        inventoryReceipt['BiltyValue'] = float(inventoryReceipt['BiltyValue'])
    else:
        inventoryReceipt['BiltyValue'] = 0.0

    for key, value in inventoryReceipt.items():
        setattr(receiptObject, key, value)
    receiptObject.save()

    #Get the already saved inventories against this PO and their allocation
    fields = ['id','InventoryCode']
    previousInventories = models.RecInventory.objects.filter(ReceiptNumber=receiptObject).values(*fields)
    if previousInventories:
        dfPreviousInventories = pd.DataFrame(previousInventories)
    else:
        dfPreviousInventories = pd.DataFrame(columns=fields)    
    del previousInventories
    
    if allocId:
        previousAllocations = models.RecAllocation.objects.filter(RecInvId=allocId).values('id','WorkOrder')
        dfPreviousAllocations = pd.DataFrame(previousAllocations)
        del previousAllocations
    else:
        dfPreviousAllocations = pd.DataFrame(columns=['id'])

    dfRecInventory['Quantity'] = np.where(dfRecInventory['Quantity'].str.len()==0, 0, dfRecInventory['Quantity'])
    dfRecInventory['Quantity'] = dfRecInventory['Quantity'].astype(float)

    if dfRecInventory.empty:
        raise ValueError('No Inventory provided')
    
    dfRecInventory.drop(inplace=True, columns=['InventoryName'])

    dfRecInventory['id'] = dfRecInventory['id'].astype(int)

    dfRecInventory = pd.merge(left=dfRecInventory, right=dfPreviousInventories, on='id', how='left')

    dfRecInventory['ReceiptNumber'] = receiptObject
    dfRecInventory['InventoryCode'] = convertTexttoObject(models.Inventory, dfRecInventory['InventoryCode'],'Code')

    dfRecInventory['Approval'] = False

    try:
        updateModelWithDF(targetTable=models.RecInventory, newData=dfRecInventory, previousData=dfPreviousInventories)
    except Exception as e:
        raise ValueError(e)
    del dfPreviousInventories
    
    if allocId:
        dfRecAllocation = dfRecAllocation.replace('null', '')
        #Remove empty rows from allocation
        dfRecAllocation = dfRecAllocation[dfRecAllocation['WorkOrder'] !='']

        dfRecAllocation = dfRecAllocation[~dfRecAllocation['WorkOrder'].isna()]
        
        dfRecAllocation['WorkOrder'] = dfRecAllocation['WorkOrder'].astype(int)
        
        try:
            receiptInvObj = models.RecInventory.objects.get(id=allocId)
            dfRecAllocation['RecInvId'] = receiptInvObj
        except Exception as e:
            raise ValueError(e)
        
        if dfPreviousAllocations.empty:
            dfRecAllocation['id'] = None
        else:
            dfRecAllocation = pd.merge(left=dfRecAllocation, right=dfPreviousAllocations, left_on='WorkOrder', right_on='WorkOrder', how='left')
        
        dfRecAllocation['WorkOrder'] = convertTexttoObject(models.WorkOrder, dfRecAllocation['WorkOrder'],'OrderNumber')

        try:
            updateModelWithDF(targetTable=models.RecAllocation, newData=dfRecAllocation, previousData=dfPreviousAllocations)
        except Exception as e:
            raise ValueError (e)        

def ProcessReceiptData(receiptObject: models.InventoryReciept):
    '''
    Get the data of the provided Receipt.
    '''
    receipt = model_to_dict(receiptObject)
    receipt['ReceiptDate'] = receiptObject.ReceiptDate
    if not receipt['BiltyValue']:
        receipt['BiltyValue'] = ''

    fields = ['id','InventoryCode','Variant','Quantity','Approval','QualityComments']
    recIinventories = models.RecInventory.objects.filter(ReceiptNumber=receiptObject).values(*fields)
    if recIinventories:
        dfRecInventories = pd.DataFrame(recIinventories)
    else:
        dfRecInventories = pd.DataFrame(column=fields)
    del recIinventories

    fields = ['Code','Name']
    inventories = models.Inventory.objects.filter(Code__in=dfRecInventories['InventoryCode'].to_list()).values(*fields)
    if inventories:
        dfInventories = pd.DataFrame(inventories)
    else:
        dfInventories = pd.DataFrame(columns=fields)
    del inventories, fields
    
    dfRecInventories = pd.merge(left=dfRecInventories, right=dfInventories, left_on='InventoryCode', right_on='Code', how='left')
    del dfInventories
    dfRecInventories.drop(inplace=True, columns=['InventoryCode','Code'])
    dfRecInventories.rename(inplace=True, columns={'Name':'InventoryName'})

    dfRecInventories['QualityComments'] = np.where(dfRecInventories['QualityComments'].isna(), '', dfRecInventories['QualityComments'])
    
    return receipt, dfToListOfDicts(dfRecInventories)

def GetReceiptAllocation(recInventory: models.RecInventory):
    '''
    Get the allocation of an inventory code in a provided Receipt.
    '''

    allocation = models.RecAllocation.objects.filter(RecInvId=recInventory)
    allocation = allocation.values('WorkOrder','Quantity')

    if allocation:
        return list(allocation)
    else:
        return []

def ReAllocateReceiptInventory(recInventory: models.RecInventory, totalQtyStr: str, allocationMethod: str):
    purchaseOrder = recInventory.ReceiptNumber.PONumber
    inventory = recInventory.InventoryCode
    variant = recInventory.Variant

    poInventories = models.POInventory.objects.filter(
        PONumber=purchaseOrder,
        Inventory=inventory,
        Variant=variant
    )
    del purchaseOrder, inventory, variant
    
    fields = ['WorkOrder','Quantity']
    poAllocations = models.POAllocation.objects.filter(POInvId__in=poInventories).values(*fields)
    dfAllocations = pd.DataFrame(poAllocations) if poAllocations else pd.DataFrame(columns=fields)
    del poAllocations
    
    fields = ['OrderNumber','DeliveryDate']
    orderDDs = models.WorkOrder.objects.filter(OrderNumber__in=dfAllocations['WorkOrder'].to_list()).values(*fields)
    dfOrderDDs = pd.DataFrame(orderDDs) if orderDDs else pd.DataFrame(columns=fields)
    del orderDDs, fields

    totalReceivedQty = float(totalQtyStr)

    totalPOQty = float(dfAllocations['Quantity'].sum())

    if totalReceivedQty < totalPOQty:
        if allocationMethod == 'distribute':
            reductionFactor = totalReceivedQty / totalPOQty
            dfAllocations['Quantity'] = dfAllocations['Quantity'] * reductionFactor
        else:
            dfAllocations = pd.merge(dfAllocations, dfOrderDDs, left_on='WorkOrder', right_on='OrderNumber', how='left')
            dfAllocations.sort_values(by='DeliveryDate', ascending=True, inplace=True)

            remainingQty = totalReceivedQty
            dfAllocations['NewQuantity'] = 0

            for index, row in dfAllocations.iterrows():
                allocatedQty = min(row['Quantity'], remainingQty)
                dfAllocations.at[index, 'NewQuantity'] = allocatedQty
                remainingQty -= allocatedQty

                if remainingQty<=0:
                    break
            
            dfAllocations['Quantity'] = dfAllocations['NewQuantity']
            dfAllocations.drop(columns=['OrderNumber', 'DeliveryDate', 'NewQuantity'], inplace=True)

        dfAllocations['Quantity'] = np.floor(dfAllocations['Quantity'] * 100) / 100

    return dfToListOfDicts(dfAllocations)

def PrintRec(inventoryReceipt: models.InventoryReciept):
    fields = ['id', 'InventoryCode','Variant','Quantity','Approval']
    recInventory = models.RecInventory.objects.filter(ReceiptNumber=inventoryReceipt).values(*fields)
    dfRecInventory = pd.DataFrame(recInventory) if recInventory else pd.DataFrame(columns=fields)
    del recInventory

    fields = ['Code','Name','Unit']
    invCards = models.Inventory.objects.filter(Code__in=dfRecInventory['InventoryCode'].to_list()).values(*fields)
    dfInventoryCards = pd.DataFrame(invCards) if invCards else pd.DataFrame(columns=fields)
    del invCards

    fields = ['RecInvId','WorkOrder','Quantity']
    allocation = models.RecAllocation.objects.filter(RecInvId__in=dfRecInventory['id'].to_list()).values(*fields)
    dfAllocation = pd.DataFrame(allocation) if allocation else pd.DataFrame(columns=fields)
    del allocation

    fields = ['OrderNumber','StyleCode']
    workOrders = models.WorkOrder.objects.filter(OrderNumber__in=dfAllocation['WorkOrder'].to_list()).values(*fields)
    dfWorkOrders = pd.DataFrame(workOrders) if workOrders else pd.DataFrame(columns=fields)
    del workOrders, fields

    dfRecInventory = pd.merge(left=dfRecInventory, right=dfInventoryCards, left_on='InventoryCode', right_on='Code', how='left')
    del dfInventoryCards
    dfRecInventory.drop(inplace=True, columns=['Code','InventoryCode'])

    dfAllocation = pd.merge(left=dfAllocation, right=dfWorkOrders, left_on='WorkOrder', right_on='OrderNumber', how='left')
    del dfWorkOrders
    dfAllocation.drop(inplace=True, columns=['OrderNumber'])

    dfAllocation.sort_values(inplace=True, by='WorkOrder', ascending=True)

    dfRecInventory['Quantity'] = dfRecInventory['Quantity'].apply(lambda x: "{:,.2f}".format(x))
    
    recInv = dfToListOfDicts(dfRecInventory)
    alloc = dfToListOfDicts(dfAllocation)

    return inventoryReceipt, recInv, alloc