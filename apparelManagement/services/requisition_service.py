import pandas as pd
import numpy as np

from django.utils.timezone import localtime
from django.db.models import Sum

from .. import models

from core.services.generic_services import convertTexttoObject, concatenateValues, dfToListOfDicts
from core.constants.generic import LOCAL_TIMEZONE

def GetRequisitionList (
        departmentFilter: str,
        statusFilter: str,
        requisitionNumber: int
        ):
    '''
    Get the list of requisitions
    '''
    if departmentFilter:
        requisitions = models.Requisition.objects.filter(Department=departmentFilter)
    else:
        requisitions = models.Requisition.objects.all()
    del departmentFilter

    if requisitionNumber:
        requisitions = requisitions.filter(id=requisitionNumber)
    
    if statusFilter:
        match statusFilter:
            case 'Pending':
                requisitions = requisitions.exclude(Confirmation=True)
            case 'Closed':
                requisitions = requisitions.filter(Confirmation=True)
            case _:
                raise ValueError('Invalid Input')
     
    fields = ['id','DateTime','Department','RequestBy','Confirmation']
    requisitions = requisitions.values(*fields)
    if requisitions:
        dfRequisitions = pd.DataFrame(requisitions)
    else:
        dfRequisitions = pd.DataFrame(columns=fields)
    del requisitions

    fields = ['Requisition','Inventory','Quantity']
    reqInvs = models.RequisitionInventory.objects.filter(Requisition__in=dfRequisitions['id'].to_list()).values(*fields)
    if reqInvs:
        dfRequisitionInvs = pd.DataFrame(reqInvs)
    else:
        dfRequisitionInvs = pd.DataFrame(columns=fields)
    del reqInvs

    invCodes = dfRequisitionInvs['Inventory'].to_list()

    fields = ['Code','Name']
    invCards = models.Inventory.objects.filter(Code__in=invCodes).values(*fields)
    if invCards:
        dfInvCards = pd.DataFrame(invCards)
    else:
        dfInvCards = pd.DataFrame(columns=fields)
    del invCards, fields

    # Step 1: Total received (ALL receipts, no approval filter)
    received = models.RecInventory.objects.filter(
        InventoryCode__in=invCodes
    ).values('InventoryCode').annotate(TotalReceived=Sum('Quantity'))
    dfReceived = pd.DataFrame(list(received)) if received else pd.DataFrame(columns=['InventoryCode','TotalReceived'])
    del received

    # Step 2: Total already physically issued out of the warehouse
    issued = models.IssueInventory.objects.filter(
        Inventory__in=invCodes
    ).values('Inventory').annotate(TotalIssued=Sum('Quantity'))
    dfIssued = pd.DataFrame(list(issued)) if issued else pd.DataFrame(columns=['Inventory','TotalIssued'])
    dfIssued.rename(columns={'Inventory': 'InventoryCode'}, inplace=True)
    del issued

    # Step 3: Total already requisitioned (pending requests that haven't been issued yet)
    requisitioned = models.RequisitionInventory.objects.filter(
        Inventory__in=invCodes,
        Requisition__Confirmation=False
    ).values('Inventory').annotate(TotalRequisitioned=Sum('Quantity'))
    dfRequisitioned = pd.DataFrame(list(requisitioned)) if requisitioned else pd.DataFrame(columns=['Inventory','TotalRequisitioned'])
    dfRequisitioned.rename(columns={'Inventory': 'InventoryCode'}, inplace=True)
    del requisitioned, invCodes

    # Step 4: Merge all three, fill blanks with 0, subtract to get what's actually free
    dfStock = pd.merge(dfReceived, dfIssued, on='InventoryCode', how='left')
    dfStock = pd.merge(dfStock, dfRequisitioned, on='InventoryCode', how='left')
    dfStock.fillna(0, inplace=True)
    dfStock['InStock'] = dfStock['TotalReceived'] - dfStock['TotalIssued'] - dfStock['TotalRequisitioned']
    dfStock = dfStock[['InventoryCode', 'InStock']]
    del dfReceived, dfIssued, dfRequisitioned



    dfRequisitionInvs = pd.merge(left=dfRequisitionInvs, right=dfStock, left_on='Inventory', right_on='InventoryCode', how='left')
    dfRequisitionInvs['InStock'] = dfRequisitionInvs['InStock'].fillna(0)
    dfRequisitionInvs.drop(inplace=True, columns=['InventoryCode'])
    del dfStock

    dfRequisitions = pd.merge(left=dfRequisitions, right=dfRequisitionInvs, left_on='id', right_on='Requisition', how='left')
    del dfRequisitionInvs
    dfRequisitions.drop(inplace=True, columns=['Requisition'])

    dfRequisitions = pd.merge(left=dfRequisitions, right=dfInvCards, left_on='Inventory', right_on='Code', how='left')
    del dfInvCards
    dfRequisitions.drop(inplace=True, columns=['Code','Inventory'])

    if not dfRequisitions.empty:
        dfRequisitions['DateTime'] = pd.to_datetime(dfRequisitions['DateTime']).dt.tz_convert(LOCAL_TIMEZONE)
        dfRequisitions = dfRequisitions.sort_values(by=['DateTime', 'id'])
        dfRequisitions['Date'] = dfRequisitions['DateTime'].dt.strftime('%d-%b')
        dfRequisitions['Time'] = dfRequisitions['DateTime'].dt.strftime('%I:%M %p')
    dfRequisitions.drop(inplace=True, columns=['DateTime'])

    # Build nested structure: one dict per requisition with an items list inside
    unique_ids = list(dict.fromkeys(dfRequisitions['id'].tolist()))
    result = []
    for req_id in unique_ids:
        group = dfRequisitions[dfRequisitions['id'] == req_id]
        first = group.iloc[0]
        items = [
            {'Name': row['Name'], 'Quantity': row['Quantity'], 'InStock': row['InStock']}
            for _, row in group.iterrows()
            if pd.notna(row.get('Name'))
        ]
        result.append({
            'id': int(req_id),
            'Date': str(first['Date']),
            'Time': str(first['Time']),
            'Department': str(first['Department']),
            'RequestBy': str(first['RequestBy']),
            'Status': 'Closed' if first['Confirmation'] else 'Pending',
            'items': items
        })
    return result

def PrepareDataForOrderRequitionAdd (order: int):
    try:
        workOrder = models.WorkOrder.objects.get(OrderNumber=order)
    except:
        raise LookupError('Work Order not found')

    fields = ['InventoryCode','FinalCons']
    consumption = models.StyleConsumption.objects.filter(Style=workOrder.StyleCode).values(*fields)
    if consumption:
        dfConsumption = pd.DataFrame(consumption)
    else:
        dfConsumption = pd.DataFrame(columns=fields)
    del consumption
    
    fields = ['InventoryCode','Variant','Quantity']
    requirement = models.InvRequirement.objects.filter(OrderNumber=workOrder).values(*fields)
    if requirement:
        dfRequirement = pd.DataFrame(requirement)
    else:
        dfRequirement = pd.DataFrame(columns=fields)
    del requirement

    fields = ['RecInvId','Quantity']
    received = models.RecAllocation.objects.filter(WorkOrder=workOrder).values(*fields)
    if received:
        dfReceived = pd.DataFrame(received)
    else:
        dfReceived = pd.DataFrame(columns=fields)
    del received

    fields = ['id','InventoryCode','Variant']
    receivedInvs = models.RecInventory.objects.filter(id__in=dfReceived['RecInvId'].to_list()).values(*fields)
    if receivedInvs:
        dfReceivedIvs = pd.DataFrame(receivedInvs)
    else:
        dfReceivedIvs = pd.DataFrame(columns=fields)
    del receivedInvs

    fields = ['RequisitionInventory','Quantity']
    requisition = models.RequisitionAllocation.objects.filter(WorkOrder=workOrder).values(*fields)
    if requisition:
        dfRequisition = pd.DataFrame(requisition)
    else:
        dfRequisition = pd.DataFrame(columns=fields)
    del requisition
    
    fields = ['id','Inventory','Variant']
    requisitionInvs = models.RequisitionInventory.objects.filter(id__in=dfRequisition['RequisitionInventory'].to_list()).values(*fields)
    if requisitionInvs:
        dfRequisitionInvs = pd.DataFrame(requisitionInvs)
    else:
        dfRequisitionInvs = pd.DataFrame(columns=fields)
    del requisitionInvs
    
    fields = ['IssueInventory','Quantity']
    issued = models.IssueAllocation.objects.filter(WorkOrder=workOrder).values(*fields)
    if issued:
        dfIssued = pd.DataFrame(issued)
    else:
        dfIssued = pd.DataFrame(columns=fields)
    del issued, workOrder
    
    fields = ['id','Inventory','Variant']
    issuedInvs = models.IssueInventory.objects.filter(id__in=dfIssued['IssueInventory'].to_list()).values(*fields)
    if issuedInvs:
        dfIssuedInvs = pd.DataFrame(issuedInvs)
    else:
        dfIssuedInvs = pd.DataFrame(columns=fields)
    del issuedInvs
    
    dfResults = pd.merge(left=dfConsumption, right=dfRequirement, left_on='InventoryCode',right_on='InventoryCode', how='outer')
    del dfConsumption, dfRequirement
    
    dfResults.rename(inplace=True, columns={'FinalCons':'Consumption', 'Quantity':'Required'})

    inventories = models.Inventory.objects.filter(Code__in=dfResults['InventoryCode'].to_list()).values('Code','Name')
    if inventories:
        dfInventories = pd.DataFrame(inventories)
    else:
        dfInventories = pd.DataFrame(columns=['Code','Name'])
    del inventories

    dfReceived = pd.merge(left=dfReceived, right=dfReceivedIvs, left_on='RecInvId', right_on='id', how='left')
    del dfReceivedIvs
    dfReceived.drop(inplace=True, columns=['RecInvId','id'])
    dfReceived = dfReceived.groupby(['InventoryCode', 'Variant'])['Quantity'].sum().reset_index()

    dfRequisition = pd.merge(left=dfRequisition, right=dfRequisitionInvs, left_on='RequisitionInventory', right_on='id', how='left')
    del dfRequisitionInvs
    dfRequisition.drop(inplace=True, columns=['RequisitionInventory','id'])
    dfRequisition = dfRequisition.groupby(['Inventory', 'Variant'])['Quantity'].sum().reset_index()

    dfIssued = pd.merge(left=dfIssued, right=dfIssuedInvs, left_on='IssueInventory', right_on='id', how='left')
    del dfIssuedInvs
    dfIssued.drop(inplace=True, columns=['IssueInventory','id'])
    dfIssued = dfIssued.groupby(['Inventory', 'Variant'])['Quantity'].sum().reset_index()
    
    dfResults = pd.merge(left=dfResults, right=dfInventories, left_on='InventoryCode', right_on='Code', how='left')
    del dfInventories
    dfResults.drop(inplace=True, columns=['Code'])

    dfResults = pd.merge(left=dfResults, right=dfReceived, left_on=['InventoryCode','Variant'],
                         right_on=['InventoryCode','Variant'], how='left')
    del dfReceived
    dfResults.rename(inplace=True, columns={'Quantity':'Received'})
    
    dfResults = pd.merge(left=dfResults, right=dfRequisition, left_on=['InventoryCode','Variant'],
                         right_on=['Inventory','Variant'], how='left')
    del dfRequisition
    dfResults.drop(inplace=True, columns=['Inventory'])
    dfResults.rename(inplace=True, columns={'Quantity':'Requested'})
    
    dfResults = pd.merge(left=dfResults, right=dfIssued, left_on=['InventoryCode','Variant'],
                         right_on=['Inventory','Variant'], how='left')
    del dfIssued
    dfResults.drop(inplace=True, columns=['Inventory'])
    dfResults.rename(inplace=True, columns={'Quantity':'Issued'})

    columns = ['Required','Received','Requested','Issued']
    for column in columns:
        dfResults[column] = np.where(dfResults[column].isna(), 0, dfResults[column])
    del columns

    dfResults['Balance'] = dfResults['Received'] - dfResults['Requested']

    dfInventories = dfResults[['InventoryCode','Name']]
    dfInventories = dfInventories.drop_duplicates(subset=['InventoryCode'], keep='first')
    dfInventories.rename(inplace=True, columns={'InventoryCode':'value','Name':'text'})
    
    return dfToListOfDicts(dfResults), dfToListOfDicts(dfInventories)

def PrepareDataForInvRequisitionAdd (code: str):
    fields = ['id','ReceiptNumber','Variant','Quantity']
    receiptInvs = models.RecInventory.objects.filter(InventoryCode=code).values(*fields)
    if receiptInvs:
        dfReceiptInvs = pd.DataFrame(receiptInvs)
    else:
        dfReceiptInvs = pd.DataFrame(columns=fields)
    del receiptInvs
    
    fields = ['id','ReceiptDate','Supplier']
    receipts = models.InventoryReciept.objects.filter(id__in=dfReceiptInvs['ReceiptNumber'].to_list()).values(*fields)
    if receipts:
        dfReceipts = pd.DataFrame(receipts)
    else:
        dfReceipts = pd.DataFrame(columns=fields)
    del receipts

    fields = ['RecInvId','Quantity']
    receiptAlloc = models.RecAllocation.objects.filter(RecInvId__in=dfReceiptInvs['id'].to_list()).values(*fields)
    if receiptAlloc:
        dfReceiptAlloc = pd.DataFrame(receiptAlloc)
    else:
        dfReceiptAlloc = pd.DataFrame(columns=fields)
    del receiptAlloc

    fields = ['Variant','Quantity']
    previousData = models.RequisitionInventory.objects.filter(Inventory=code).values(*fields)
    if previousData:
        dfPreviousData = pd.DataFrame(previousData)
    else:
        dfPreviousData = pd.DataFrame(columns=fields)
    del previousData, fields
        
    dfReceiptAlloc = dfReceiptAlloc.groupby('RecInvId')['Quantity'].sum().reset_index()
    dfReceiptAlloc.rename(inplace=True, columns={'Quantity':'AllocatedQty'})

    dfReceiptInvs = pd.merge(left=dfReceiptInvs, right=dfReceiptAlloc, left_on='id', right_on='RecInvId', how='left')
    del dfReceiptAlloc
    dfReceiptInvs.drop(inplace=True, columns=['id','RecInvId'])
    
    dfReceiptInvs['AllocatedQty'] = np.where(dfReceiptInvs['AllocatedQty'].isna(), 0, dfReceiptInvs['AllocatedQty'])
    dfReceiptInvs['Available'] = dfReceiptInvs['Quantity'] - dfReceiptInvs['AllocatedQty']
    dfReceiptInvs.drop(inplace=True, columns=['Quantity','AllocatedQty'])

    dfReceiptInvs = pd.merge(left=dfReceiptInvs, right=dfReceipts, left_on='ReceiptNumber', right_on='id', how='left')
    del dfReceipts
    dfReceiptInvs.drop(inplace=True, columns=['id'])

    dfPreviousData = dfPreviousData.groupby('Variant')['Quantity'].sum().reset_index()

    #Remove the already requested quantity from available
    for _, row in dfPreviousData.iterrows():
        # Find all entries for the variant in df1
        variantIndices = dfReceiptInvs[dfReceiptInvs['Variant'] == row['Variant']].index

        remainingQty = row['Quantity']
        for i in variantIndices:
            if dfReceiptInvs.loc[i, 'Available'] >= remainingQty:
                dfReceiptInvs.loc[i, 'Available'] -= remainingQty
                remainingQty = 0
                break
            else:
                remainingQty -= dfReceiptInvs.loc[i, 'Available']
                dfReceiptInvs.loc[i, 'Available'] = 0
    
    #Remove rows where available qty is 0
    dfReceiptInvs = dfReceiptInvs[dfReceiptInvs['Available']>0]

    #Sort by ascending order w.r.t. date of receipt
    dfReceiptInvs = dfReceiptInvs.sort_values(by='ReceiptDate', ascending=True)

    cols = [i for i in dfReceiptInvs]
    data = [dict(zip(cols, i)) for i in dfReceiptInvs.values]
    return data

def GetReceiptAllocation(inventoryCode: str, variant: str, urlPath: str):
    urlParts = urlPath.strip('/').split('/')
    del urlPath

    if len(urlParts) == 2:
        #This is true for a new requisutions and there would be no allocation
        return None
    elif len(urlParts) == 3:
        reqNumber = int(urlParts[1])
        requisition = models.Requisition.objects.get(id=reqNumber)

        reqInventory = models.RequisitionInventory.objects.get(Requisition=requisition, Inventory=inventoryCode, Variant=variant)
        
        allocation = models.RequisitionAllocation.objects.filter(RequisitionInventory=reqInventory)
        allocation = allocation.values('WorkOrder','Quantity')
        if allocation:
            return list(allocation)
        else:
            return None
    else:
        raise SyntaxError('Invalid Input')

def AddRequisitionForOrder (
        dfRequisition: pd.DataFrame,
        dfInventory: pd.DataFrame,
        requestBy: str
) -> int:
    dfInventory['Quantity'] = dfInventory['Quantity'].astype(float)
    dfInventory = dfInventory[dfInventory['Quantity']>0]
    
    if dfInventory.empty:
        raise ValueError('Please select valid inventory')

    dfRequisition['Department'] = convertTexttoObject(models.Department, dfRequisition['Department'], 'Name')

    requisition = {
        'Department':dfRequisition['Department'][0],
        'RequestBy': requestBy,
        'Confirmation': False,
        'StoreComments': None
    }

    requisition = models.Requisition(**requisition)
    requisition.save()

    try:
        dfRequisition['WorkOrder'] = dfRequisition['WorkOrder'].astype(int)
        workOrder = dfRequisition['WorkOrder'][0]
        workOrder = models.WorkOrder.objects.get(OrderNumber=workOrder)
    except Exception as e:
        raise LookupError(e)
    del dfRequisition

    dfInventory['Inventory'] = convertTexttoObject(models.Inventory, dfInventory['InventoryCode'], 'Code')
    dfInventory.drop(inplace=True, columns=['InventoryCode'])

    dfInventory['Requisition'] = requisition
    
    for _, row in dfInventory.iterrows():
        inv = models.RequisitionInventory(**row)
        inv.save()
        
        alloc = {
            'RequisitionInventory':inv,
            'WorkOrder':workOrder,
            'Quantity': inv.Quantity
        }
        alloc = models.RequisitionAllocation(**alloc)
        alloc.save()
    
    return requisition.id

def AddRequistionForInv (
        department: str,
        items: list,
        requestBy: str
) -> int:
    if not items:
        raise ValueError('Please select valid inventory')

    dept = models.Department.objects.get(Name=department)

    requisition = models.Requisition(
        Department=dept,
        RequestBy=requestBy,
        Confirmation=False,
        StoreComments=None
    )
    requisition.save()

    for item in items:
        quantity = float(item['quantity'])
        if quantity <= 0:
            continue
        inventory = models.Inventory.objects.get(Code=item['inventory'])
        req_inv = models.RequisitionInventory(
            Requisition=requisition,
            Inventory=inventory,
            Variant=item.get('variant', ''),
            Quantity=quantity
        )
        req_inv.save()

    return requisition.id

def DeleteRequisition(requisition_id: int):
    try:
        requisition = models.Requisition.objects.get(id=requisition_id)
    except models.Requisition.DoesNotExist:
        raise LookupError('Requisition not found')

    # Issuance has on_delete=PROTECT, so we must delete it before the requisition
    # Deleting Issuance cascades to IssueInventory → IssueAllocation automatically
    models.Issuance.objects.filter(InventoryRequisition=requisition).delete()

    # Deleting Requisition cascades to RequisitionInventory → RequisitionAllocation automatically
    # InStock recalculates dynamically so no manual stock update is needed
    requisition.delete()