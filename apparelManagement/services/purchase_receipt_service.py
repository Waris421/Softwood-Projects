import pandas as pd
import numpy as np
from decimal import Decimal
from typing import List
from .. import models

from django.forms import model_to_dict
from django.db.models import Q
from django.db import transaction

from .. import models
from core.services.generic_services import updateModelWithDF, convertTexttoObject, concatenateValues, dfToListOfDicts
# ^ All imports for new tasks

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
    '''
    Add the receipt from the receipt Form
    '''
    print('\n========== AddPurchaseReceipt START ==========')

    # Step 1 — Clean the quantity column: replace empty strings with 0, then convert to float
    dfRecInventories['Quantity'] = np.where(dfRecInventories['Quantity'].str.len()>0, dfRecInventories['Quantity'], 0.0)
    dfRecInventories['Quantity'] = dfRecInventories['Quantity'].astype(float)
    if dfRecInventories.empty:
        raise ValueError('No Inventory provided')

    print(f'\n[1] Received {len(dfRecInventories)} inventory item(s) from the form')
    print(dfRecInventories[['POInvId', 'Quantity']].to_string(index=False))

    # Step 2 — Fetch the Purchase Order object from the database using the PO id from the form
    purchaseOrder = dfReceipt['PONumber'][0]
    purchaseOrder = models.PurchaseOrder.objects.get(id=purchaseOrder)
    if models.InventoryReciept.objects.filter(PONumber=purchaseOrder).exists():
        raise ValueError(f'A receipt already exists for PO #{purchaseOrder.id}')
    print(f'\n[2] Purchase Order fetched: PO #{purchaseOrder.id} from supplier "{purchaseOrder.Supplier}"')

    # Step 3 — Fetch the original PO allocations: which work orders were expecting this inventory and how much
    fields = ['POInvId','WorkOrder','Quantity']
    poAllocations = models.POAllocation.objects.filter(POInvId__in=dfRecInventories['POInvId'].to_list()).values(*fields)
    if poAllocations:
        dfPOAllocation = pd.DataFrame(poAllocations)
    else:
        dfPOAllocation = pd.DataFrame(columns=fields)
    del poAllocations

    print(f'\n[3] PO Allocations fetched ({len(dfPOAllocation)} row(s)) — which work orders were expecting this inventory:')
    print(dfPOAllocation.to_string(index=False))

    # Step 4 — Fetch PO inventory details: price, forex rate, and variant for each item
    fields = ['id','Inventory','Variant','Price','Forex']
    poInventories  = models.POInventory.objects.filter(id__in=dfRecInventories['POInvId'].to_list()).values(*fields)
    if poInventories:
        dfPOInventories = pd.DataFrame(poInventories)
    else:
        dfPOInventories = pd.DataFrame(columns=fields)
    del poInventories, fields

    print(f'\n[4] PO Inventory details fetched (price, forex, variant):')
    print(dfPOInventories.to_string(index=False))

    # Step 5 — Build the receipt header object (supplier, PO, bilty etc) but do not save it yet
    invReceipt = dfReceipt.iloc[0].to_dict()
    invReceipt['PONumber'] = purchaseOrder
    if not invReceipt['BiltyValue']:
        invReceipt['BiltyValue'] = None
    invReceipt['Supplier'] = purchaseOrder.Supplier
    del purchaseOrder

    receiptCard = models.InventoryReciept(**invReceipt)
    del invReceipt, dfReceipt

    # Step 6 — Merge the received quantities with PO details (price, forex, variant) into one DataFrame
    dfRecInventories.drop(inplace=True, columns=['Name','Variant','Price'])
    dfRecInventories['POInvId'] = dfRecInventories['POInvId'].astype(int)
    dfRecInventories = pd.merge(left=dfRecInventories, right=dfPOInventories, left_on='POInvId', right_on='id', how='left')
    dfRecInventories.drop(inplace=True, columns=['id'])

    # Step 7 — Convert inventory code strings into actual Inventory model objects, then calculate stock value
    dfRecInventories['Inventory'] = convertTexttoObject(models.Inventory, dfRecInventories['Inventory'], 'Code')
    dfRecInventories.rename(inplace=True, columns={'Inventory':'InventoryCode'})
    dfRecInventories['StockValue'] = dfRecInventories['Quantity'] * dfRecInventories['Price'] * dfRecInventories['Forex']

    print(f'\n[5] Final received inventory rows with stock values calculated:')
    print(dfRecInventories[['InventoryCode','Variant','Quantity','Price','Forex','StockValue']].to_string(index=False))

    # Step 8 — Build RecInventory objects (one per item received) — still not saved to database yet
    recInventoryRows = []
    for _, row in dfRecInventories.iterrows():
        recInv = models.RecInventory(
            InventoryCode=row['InventoryCode'],
            Variant=row['Variant'],
            Quantity=row['Quantity'],
            ReceiptNumber=None,  # will be linked to receipt after it is saved
            Approval=False,
            QualityComments=None,
        )
        recInventoryRows.append({
            'object': recInv,
            'POInvId': row['POInvId'],
        })

    print(f'\n[6] Built {len(recInventoryRows)} RecInventory object(s) (not saved yet)')

    # Step 9 — Calculate allocations: for each received item, split the quantity across work orders
    # If less arrived than ordered, scale everyone's share down proportionally (shortfall logic)
    allocationData = []
    for item in recInventoryRows:
        recInv = item['object']
        allocation = dfPOAllocation[dfPOAllocation['POInvId'] == item['POInvId']].copy()

        if allocation.empty:
            print(f'     No allocation found for POInvId {item["POInvId"]} — skipping')
            continue

        totalOrdered = allocation['Quantity'].sum()
        shortfallPercentage = recInv.Quantity / totalOrdered
        print(f'\n[7] POInvId {item["POInvId"]}: ordered {totalOrdered}, received {recInv.Quantity} → shortfall {round(shortfallPercentage * 100, 1)}%')

        if shortfallPercentage < 1:
            allocation['Quantity'] = allocation['Quantity'] * shortfallPercentage
            print(f'     Shortfall detected — scaling down allocations proportionally')

        # Round down to 2 decimal places to avoid partial unit issues
        allocation['Quantity'] = np.floor(allocation['Quantity'] * 100) / 100
        allocation.drop(inplace=True, columns=['POInvId'])
        allocation['WorkOrder'] = convertTexttoObject(models.WorkOrder, allocation['WorkOrder'], 'OrderNumber')

        for _, allocRow in allocation.iterrows():
            allocationData.append({
                'WorkOrder': allocRow['WorkOrder'],
                'Quantity':  allocRow['Quantity'],
                'recInvRef': recInv,
            })
            print(f'     → Work Order {allocRow["WorkOrder"].OrderNumber} will receive {allocRow["Quantity"]} units')

    # Step 10 — Prepare stock update data: inventory code, variant, quantity, and total value
    stockUpdates = dfRecInventories[['InventoryCode','Variant','Quantity','StockValue']].to_dict('records')

    # Step 11 — Atomic transaction: save everything or nothing. If any step fails, the entire block rolls back
    print(f'\n[8] Starting atomic transaction — saving everything to the database')
    with transaction.atomic():

        # Step 11a — Save the receipt header first so we have its ID to link children to
        receiptCard.save()
        print(f'     Receipt header saved with ID: {receiptCard.id}')

        # Step 11b — Link each RecInventory row to the receipt and save
        for item in recInventoryRows:
            obj = item['object']
            obj.ReceiptNumber = receiptCard
            obj.save()
            print(f'     RecInventory saved: {obj.InventoryCode} | Qty: {obj.Quantity}')

        # Step 11c — Bulk save all work order allocations in one database call
        recAllocationList = [
                models.RecAllocation(
                    WorkOrder=item['WorkOrder'],
                    Quantity=item['Quantity'],
                    RecInvId=item['recInvRef'],
                )
                for item in allocationData
            ]
        if recAllocationList:
            models.RecAllocation.objects.bulk_create(recAllocationList)
            print(f'     {len(recAllocationList)} allocation(s) saved')

        # Step 11d — Fetch existing stock records for all received items in one query
        existingStocks = models.InventoryStock.objects.filter(
            Inventory__in=[s['InventoryCode'] for s in stockUpdates],
            Variant__in=[s['Variant'] for s in stockUpdates],
        )
        # Build a lookup dictionary: (InventoryCode, Variant) → stock record
        stockMap = {(s.Inventory, s.Variant): s for s in existingStocks}

        toCreate = []
        toUpdate = []
        for update in stockUpdates:
            key = (update['InventoryCode'], update['Variant'])
            if key in stockMap:
                # Step 11e — Item already has stock: add the new quantity and value on top
                record = stockMap[key]
                oldQty = record.StockQuantity
                oldVal = record.StockValue
                record.StockQuantity += Decimal(str(update['Quantity']))
                record.StockValue    += Decimal(str(update['StockValue']))
                toUpdate.append(record)
                print(f'     Stock UPDATE: {update["InventoryCode"]} | Qty {oldQty} → {record.StockQuantity} | Value {oldVal} → {record.StockValue}')
            else:
                # Step 11f — Item has no stock yet: create a brand new stock record
                newRecord = models.InventoryStock(
                    Inventory=update['InventoryCode'],
                    Variant=update['Variant'],
                    StockQuantity=Decimal(str(update['Quantity'])),
                    StockValue=Decimal(str(update['StockValue'])),
                )
                toCreate.append(newRecord)
                print(f'     Stock CREATE: {update["InventoryCode"]} | Qty: {update["Quantity"]} | Value: {update["StockValue"]}')

        # Step 11g — Save all stock changes in two bulk operations (faster than saving one by one)
        if toCreate:
            models.InventoryStock.objects.bulk_create(toCreate)
        if toUpdate:
            models.InventoryStock.objects.bulk_update(toUpdate, ['StockQuantity', 'StockValue'])

    print(f'\n========== AddPurchaseReceipt DONE — Receipt ID: {receiptCard.id} ==========\n')
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
    # Step 1: Save which RecInventory row's allocations are being edited, then strip non-editable columns.
    raw_rec_id = dfReceipt['recId'].iloc[0]
    manual_alloc_rec_inv_id = int(raw_rec_id) if raw_rec_id else None
    dfReceipt.drop(inplace=True, columns=['GRNNumber','ReceiptDate','PONumber','recId'])
    inventoryReceipt = dfReceipt.iloc[0].to_dict()
    del dfReceipt

    # Step 2: Convert Supplier name to a model object, cast BiltyValue to float, then save the header.
    inventoryReceipt['Supplier'] = models.Supplier.objects.get(Name=inventoryReceipt['Supplier'])
    if inventoryReceipt['BiltyValue']:
        inventoryReceipt['BiltyValue'] = float(inventoryReceipt['BiltyValue'])
    else:
        inventoryReceipt['BiltyValue'] = 0.0

    for key, value in inventoryReceipt.items():
        setattr(receiptObject, key, value)
    receiptObject.save()

    # Step 3: Fetch existing RecInventory rows for this receipt — needed to diff old vs new.
    fields = ['id','InventoryCode']
    previousInventories = models.RecInventory.objects.filter(ReceiptNumber=receiptObject).values(*fields)
    if previousInventories:
        dfPreviousInventories = pd.DataFrame(previousInventories)
    else:
        dfPreviousInventories = pd.DataFrame(columns=fields)
    del previousInventories
        
    # Snapshot old quantities before the update — needed for stock delta calculation.
    oldQtyFields = ['InventoryCode', 'Variant', 'Quantity']
    oldQuantities = models.RecInventory.objects.filter(ReceiptNumber=receiptObject).values(*oldQtyFields)
    dfOldQuantities = pd.DataFrame(oldQuantities) if oldQuantities else pd.DataFrame(columns=oldQtyFields)

    # Fetch price and forex from POInventory for this receipt's PO.
    poInventories = models.POInventory.objects.filter(
        PONumber=receiptObject.PONumber,
    ).values('id', 'Inventory', 'Variant', 'Price', 'Forex')
    dfPOInventories = pd.DataFrame(poInventories) if poInventories else pd.DataFrame(columns=['id','Inventory','Variant','Price','Forex'])

    # Fetch the original work order splits from POAllocation.
    poAllocations = models.POAllocation.objects.filter(
        POInvId__in=dfPOInventories['id'].tolist()
    ).values('POInvId', 'WorkOrder', 'Quantity')
    dfPOAllocations = pd.DataFrame(poAllocations) if poAllocations else pd.DataFrame(columns=['POInvId','WorkOrder','Quantity'])

    # Step 5: Clean quantities — replace empty strings with 0 and cast to float.
    dfRecInventory['Quantity'] = np.where(dfRecInventory['Quantity'].str.len()==0, 0, dfRecInventory['Quantity'])
    dfRecInventory['Quantity'] = dfRecInventory['Quantity'].astype(float)

    if dfRecInventory.empty:
        raise ValueError('No Inventory provided')

    # Step 6: Prepare dfRecInventory for the DB write — drop display columns, attach receipt link,
    # convert inventory codes to objects, and reset Approval since quantities may have changed.
    dfRecInventory.drop(inplace=True, columns=['InventoryName'])
    dfRecInventory['id'] = dfRecInventory['id'].astype(int)
    dfRecInventory = pd.merge(left=dfRecInventory, right=dfPreviousInventories, on='id', how='left')
    dfRecInventory['ReceiptNumber'] = receiptObject
    dfRecInventory['InventoryCode'] = convertTexttoObject(models.Inventory, dfRecInventory['InventoryCode'],'Code')
    dfRecInventory['Approval'] = False

    # Step 7: Sync RecInventory to DB — updateModelWithDF handles creates, updates, and deletes in one call.
    try:
        updateModelWithDF(targetTable=models.RecInventory, newData=dfRecInventory, previousData=dfPreviousInventories)
    except Exception as e:
        raise ValueError(e)
    del dfPreviousInventories

    # Step 8: Atomic transaction — recalculate all RecAllocations and update InventoryStock.
    print(f'\n========== EditPurchaseReceipt — Starting atomic transaction for Receipt ID: {receiptObject.id} ==========')
    with transaction.atomic():

        # Step 8a: Delete all existing RecAllocation rows tied to this receipt.
        recInvIds = list(models.RecInventory.objects.filter(ReceiptNumber=receiptObject).values_list('id', flat=True))
        deleted = models.RecAllocation.objects.filter(RecInvId__in=recInvIds).delete()
        print(f'\n[8a] Deleted old RecAllocations for RecInventory IDs {recInvIds}: {deleted}')

        # Step 8b: Rebuild RecAllocations — use submitted modal data for the manually edited item,
        # POAllocation shortfall logic for all other items.
        newAllocations = []
        updatedRecInventories = models.RecInventory.objects.filter(ReceiptNumber=receiptObject).values('id','InventoryCode','Variant','Quantity')
        for recInv in updatedRecInventories:
            print(f'\n[8b] Processing RecInventory ID {recInv["id"]} | Item: {recInv["InventoryCode"]} | Variant: {recInv["Variant"]} | New Qty: {recInv["Quantity"]}')
            recInvObj = models.RecInventory(id=recInv['id'])

            # If the user manually edited this item in the modal, use their submitted data directly
            if manual_alloc_rec_inv_id and recInv['id'] == manual_alloc_rec_inv_id and not dfRecAllocation.empty:
                print(f'     Using manually submitted allocation from modal')
                for _, allocRow in dfRecAllocation.iterrows():
                    if not allocRow['WorkOrder'] or not allocRow['Quantity']:
                        continue
                    workOrder = models.WorkOrder.objects.get(OrderNumber=int(allocRow['WorkOrder']))
                    newAllocations.append(models.RecAllocation(
                        RecInvId=recInvObj,
                        WorkOrder=workOrder,
                        Quantity=float(allocRow['Quantity']),
                    ))
                    print(f'     → Work Order {workOrder.OrderNumber} allocated {allocRow["Quantity"]} units (manual)')
                continue

            # For all other items — use POAllocation shortfall logic
            poInvRow = dfPOInventories[
                (dfPOInventories['Inventory'] == recInv['InventoryCode']) &
                (dfPOInventories['Variant'] == recInv['Variant'])
            ]
            if poInvRow.empty:
                print(f'     No matching POInventory found — skipping')
                continue
            poInvId = poInvRow.iloc[0]['id']
            allocations = dfPOAllocations[dfPOAllocations['POInvId'] == poInvId].copy()
            if allocations.empty:
                print(f'     No POAllocations found for POInvId {poInvId} — skipping')
                continue
            totalOrdered = allocations['Quantity'].sum()
            shortfallPct = recInv['Quantity'] / totalOrdered
            print(f'     Total ordered: {totalOrdered} | Shortfall: {round(shortfallPct * 100, 1)}%')
            if shortfallPct < 1:
                allocations['Quantity'] = allocations['Quantity'] * shortfallPct
                print(f'     Shortfall detected — scaling allocations down proportionally')
            allocations['Quantity'] = np.floor(allocations['Quantity'] * 100) / 100
            for _, allocRow in allocations.iterrows():
                workOrder = models.WorkOrder.objects.get(OrderNumber=allocRow['WorkOrder'])
                newAllocations.append(models.RecAllocation(
                    RecInvId=recInvObj,
                    WorkOrder=workOrder,
                    Quantity=allocRow['Quantity'],
                ))
                print(f'     → Work Order {workOrder.OrderNumber} allocated {allocRow["Quantity"]} units')

        # Step 8c: Update InventoryStock using delta = new quantity minus old quantity per item.
        print(f'\n[8c] Calculating stock deltas...')
        toUpdate = []
        toCreate = []
        for _, newRow in dfRecInventory.iterrows():
            invCode = newRow['InventoryCode'].Code
            variant = newRow['Variant']
            newQty = float(newRow['Quantity'])
            oldRow = dfOldQuantities[
                (dfOldQuantities['InventoryCode'] == invCode) &
                (dfOldQuantities['Variant'] == variant)
            ]
            oldQty = float(oldRow.iloc[0]['Quantity']) if not oldRow.empty else 0.0
            delta = newQty - oldQty
            print(f'     Item: {invCode} | Variant: {variant} | Old Qty: {oldQty} | New Qty: {newQty} | Delta: {delta}')
            if delta == 0:
                print(f'     No change — skipping stock update')
                continue
            poInvRow = dfPOInventories[
                (dfPOInventories['Inventory'] == invCode) &
                (dfPOInventories['Variant'] == variant)
            ]
            if poInvRow.empty:
                print(f'     No POInventory found for price — skipping stock update')
                continue
            price = float(poInvRow.iloc[0]['Price'])
            forex = float(poInvRow.iloc[0]['Forex'] or 1.0)
            valueDelta = delta * price * forex
            print(f'     Price: {price} | Forex: {forex} | Value Delta: {valueDelta}')
            stock = models.InventoryStock.objects.filter(
                Inventory=newRow['InventoryCode'],
                Variant=variant,
            ).first()
            if stock:
                oldStockQty = stock.StockQuantity
                oldStockVal = stock.StockValue
                stock.StockQuantity += Decimal(str(delta))
                stock.StockValue += Decimal(str(valueDelta))
                toUpdate.append(stock)
                print(f'     Stock UPDATE: Qty {oldStockQty} → {stock.StockQuantity} | Value {oldStockVal} → {stock.StockValue}')
            else:
                toCreate.append(models.InventoryStock(
                    Inventory=newRow['InventoryCode'],
                    Variant=variant,
                    StockQuantity=Decimal(str(newQty)),
                    StockValue=Decimal(str(newQty * price * forex)),
                ))
                print(f'     Stock CREATE: Qty {newQty} | Value {newQty * price * forex}')
        if toUpdate:
            models.InventoryStock.objects.bulk_update(toUpdate, ['StockQuantity','StockValue'])
        if toCreate:
            models.InventoryStock.objects.bulk_create(toCreate)
        print(f'\n========== EditPurchaseReceipt DONE — {len(toUpdate)} stock(s) updated, {len(toCreate)} stock(s) created ==========\n')

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