import pandas as pd
import numpy as np

from django.forms import model_to_dict
from django.db.models import Q

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

def AddPurchaseReceipt(dfReceipt:pd.DataFrame, dfRecInventories:pd.DataFrame):
    '''
    Add the receipt from new receipt Form
    '''
    dfRecInventories = dfRecInventories[dfRecInventories['Quantity'].str.len()>0]
    dfRecInventories['Quantity'] = dfRecInventories['Quantity'].astype(float)
    if dfRecInventories.empty:
        raise ValueError('No Inventory provided')

    purchaseOrder = dfReceipt['PONumber'][0]
    purchaseOrder = models.PurchaseOrder.objects.get(id=purchaseOrder)

    fields = ['POInvId','WorkOrder','Quantity']
    poAllocations = models.POAllocation.objects.filter(POInvId__in=dfRecInventories['POInvId'].to_list()).values(*fields)
    if poAllocations:
        dfPOAllocation = pd.DataFrame(poAllocations)
    else:
        dfPOAllocation = pd.DataFrame(columns=fields)
    del poAllocations

    fields = ['id','Inventory','Variant']
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
    receiptCard.save()
    del invReceipt, dfReceipt 

    dfRecInventories.drop(inplace=True, columns=['Name','Variant'])
    dfRecInventories['POInvId'] = dfRecInventories['POInvId'].astype(int)

    dfRecInventories = pd.merge(left=dfRecInventories, right=dfPOInventories, left_on='POInvId', right_on='id', how='left')
    dfRecInventories.drop(inplace=True, columns=['id'])
    
    dfRecInventories['Inventory'] = convertTexttoObject(models.Inventory, dfRecInventories['Inventory'], 'Code')
    dfRecInventories.rename(inplace=True, columns={'Inventory':'InventoryCode'})
    
    for _, row in dfRecInventories.iterrows():
        allocation = dfPOAllocation[dfPOAllocation['POInvId']==row['POInvId']]
        recInventory = row[['InventoryCode','Variant','Quantity']].to_dict()
        del row
        
        recInventory['ReceiptNumber'] = receiptCard
        recInventory['Approval'] = False
        recInventory['QualityComments'] = None

        recInventory = models.RecInventory(**recInventory)
        recInventory.save()
        
        if allocation.empty:
            continue
        shortfallPercentage = recInventory.Quantity/allocation['Quantity'].sum()

        if shortfallPercentage < 1:
            allocation['Quantity'] = allocation['Quantity'] * shortfallPercentage
        
        allocation['Quantity'] = np.floor(allocation['Quantity'] * 100)/100
        allocation.drop(inplace=True, columns=['POInvId'])

        allocation['WorkOrder'] = convertTexttoObject(models.WorkOrder, allocation['WorkOrder'],'OrderNumber')
        allocation['RecInvId'] = recInventory

        for _, allocRow in allocation.iterrows():
            recAllocation = models.RecAllocation(**allocRow)
            recAllocation.save()

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

    try:
        poInventory = models.POInventory.objects.get(
            PONumber=purchaseOrder,
            Inventory=inventory,
            Variant=variant
        )
    except:
        raise ValueError('Bad Inventory value in PO')
    del purchaseOrder, inventory, variant
    
    fields = ['WorkOrder','Quantity']
    poAllocations = models.POAllocation.objects.filter(POInvId=poInventory).values(*fields)
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