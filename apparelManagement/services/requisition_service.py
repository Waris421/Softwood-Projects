import pandas as pd
import numpy as np

from django.utils.timezone import localtime

from .. import models

from .generic_services import convertTexttoObject, concatenateValues, LOCAL_TIMEZONE

pd.options.mode.chained_assignment = None
pd.set_option('display.max_columns', None)

def GetRequisitionList (
        searchTerm: str,
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
     
    requisitions = requisitions.values('id','DateTime','Department','RequestBy')
    if requisitions:
        dfRequisitions = pd.DataFrame(requisitions)
    else:
        return []
    del requisitions

    reqInvs = models.RequisitionInventory.objects.filter(Requisition__in=dfRequisitions['id'].to_list())
    reqInvs = reqInvs.values('Requisition','Inventory')
    if reqInvs:
        dfRequisitionInvs = pd.DataFrame(reqInvs)
    else:
        dfRequisitionInvs = pd.DataFrame(columns=['Requisition','Inventory'])
    del reqInvs

    invCards = models.Inventory.objects.filter(Code__in=dfRequisitionInvs['Inventory'].to_list()).values('Code','Name')
    if invCards:
        dfInvCards = pd.DataFrame(invCards)
    else:
        dfInvCards = pd.DataFrame(columns=['Code','Name'])
    del invCards
    

    dfRequisitions = pd.merge(left=dfRequisitions, right=dfRequisitionInvs, left_on='id', right_on='Requisition', how='left')
    del dfRequisitionInvs
    dfRequisitions.drop(inplace=True, columns=['Requisition'])
    
    dfRequisitions = pd.merge(left=dfRequisitions, right=dfInvCards, left_on='Inventory', right_on='Code', how='left')
    del dfInvCards
    dfRequisitions.drop(inplace=True, columns=['Code','Inventory'])

    #Concate rows who have same PO number in common
    dfRequisitions = dfRequisitions.groupby('id').agg({
        'DateTime': 'first',
        'Department': 'first',
        'RequestBy': 'first',
        'Name': concatenateValues,
    }).reset_index()

    dfRequisitions['DateTime'] = pd.to_datetime(dfRequisitions['DateTime']).dt.tz_convert(LOCAL_TIMEZONE)

    dfRequisitions = dfRequisitions.sort_values(by='DateTime', ascending=True)

    dfRequisitions['Date'] = dfRequisitions['DateTime'].dt.strftime('%d-%b')
    dfRequisitions['Time'] = dfRequisitions['DateTime'].dt.strftime('%I:%M %p')
    dfRequisitions.drop(inplace=True, columns=['DateTime'])

    searchTerm = searchTerm.lower()
    mask = dfRequisitions.apply(lambda row: any(searchTerm in str(val).lower() for val in row.values), axis=1)
    dfRequisitions = dfRequisitions[mask]

    cols = [i for i in dfRequisitions]
    data = [dict(zip(cols, i)) for i in dfRequisitions.values]
    return data

def PrepareDataForOrderRequitionAdd (order: int):
    try:
        workOrder = models.WorkOrder.objects.get(OrderNumber=order)
    except:
        raise LookupError('Work Order not found')

    consumption = models.StyleConsumption.objects.filter(Style=workOrder.StyleCode).values('InventoryCode','FinalCons')
    if consumption:
        dfConsumption = pd.DataFrame(consumption)
    else:
        dfConsumption = pd.DataFrame(columns=['InventoryCode','FinalCons'])
    del consumption
    
    requirement = models.InvRequirement.objects.filter(OrderNumber=workOrder).values('InventoryCode','Variant','Quantity')
    if requirement:
        dfRequirement = pd.DataFrame(requirement)
    else:
        dfRequirement = pd.DataFrame(columns=['InventoryCode','Variant','Quantity'])
    del requirement

    received = models.RecAllocation.objects.filter(WorkOrder=workOrder).values('RecInvId','Quantity')
    if received:
        dfReceived = pd.DataFrame(received)
    else:
        dfReceived = pd.DataFrame(columsn=['RecInvId','Quantity'])
    del received

    receivedInvs = models.RecInventory.objects.filter(id__in=dfReceived['RecInvId'].to_list()).values('id','InventoryCode','Variant')
    if receivedInvs:
        dfReceivedIvs = pd.DataFrame(receivedInvs)
    else:
        dfReceivedIvs = pd.DataFrame(columns=['id','InventoryCode','Variant'])
    del receivedInvs

    requisition = models.RequisitionAllocation.objects.filter(WorkOrder=workOrder)
    requisition = requisition.values('RequisitionInventory','Quantity')
    if requisition:
        dfRequisition = pd.DataFrame(requisition)
    else:
        dfRequisition = pd.DataFrame(columns=['RequisitionInventory','Quantity'])
    del requisition
    
    requisitionInvs = models.RequisitionInventory.objects.filter(id__in=dfRequisition['RequisitionInventory'].to_list())
    requisitionInvs = requisitionInvs.values('id','Inventory','Variant')
    if requisitionInvs:
        dfRequisitionInvs = pd.DataFrame(requisitionInvs)
    else:
        dfRequisitionInvs = pd.DataFrame(columns=['id','Inventory','Variant'])
    del requisitionInvs
    
    issued = models.IssueAllocation.objects.filter(WorkOrder=workOrder).values('IssueInventory','Quantity')
    if issued:
        dfIssued = pd.DataFrame(issued)
    else:
        dfIssued = pd.DataFrame(columns=['IssueInventory','Quantity'])
    del issued, workOrder
    
    issuedInvs = models.IssueInventory.objects.filter(id__in=dfIssued['IssueInventory'].to_list()).values('id','Inventory','Variant')
    if issuedInvs:
        dfIssuedInvs = pd.DataFrame(issuedInvs)
    else:
        dfIssuedInvs = pd.DataFrame(columns=['id','Inventory','Variant'])
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
    
    cols = [i for i in dfInventories]
    invs = [dict(zip(cols, i)) for i in dfInventories.values]
    
    cols = [i for i in dfResults]
    data = [dict(zip(cols, i)) for i in dfResults.values]
    return data, invs

def PrepareDataForInvRequisitionAdd (code: str):
    receiptInvs = models.RecInventory.objects.filter(InventoryCode=code).values('id','ReceiptNumber','Variant','Quantity')
    if receiptInvs:
        dfReceiptInvs = pd.DataFrame(receiptInvs)
    else:
        return None
    
    receipts = models.InventoryReciept.objects.filter(id__in=dfReceiptInvs['ReceiptNumber'].to_list())
    receipts = receipts.values('id','ReceiptDate','Supplier')
    if receipts:
        dfReceipts = pd.DataFrame(receipts)
    else:
        dfReceipts = pd.DataFrame(columns=['id','ReceiptDate','Supplier'])
    del receipts

    receiptAlloc = models.RecAllocation.objects.filter(RecInvId__in=dfReceiptInvs['id'].to_list())
    receiptAlloc = receiptAlloc.values('RecInvId','Quantity')
    if receiptAlloc:
        dfReceiptAlloc = pd.DataFrame(receiptAlloc)
    else:
        dfReceiptAlloc = pd.DataFrame(columns=['RecInvId','Quantity'])
    del receiptAlloc

    previousData = models.RequisitionInventory.objects.filter(Inventory=code).values('Variant','Quantity')
    if previousData:
        dfPreviousData = pd.DataFrame(previousData)
    else:
        dfPreviousData = pd.DataFrame(columns=['Variant','Quantity'])
    del previousData
        
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
        dfRequisition: pd.DataFrame,
        dfDetails: pd.DataFrame,
        requestBy: str
) -> int:
    dfDetails['Quantity'] = dfDetails['Quantity'].astype(float)
    dfDetails = dfDetails[dfDetails['Quantity']>0]
    
    if dfDetails.empty:
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

    dfRequisition['Inventory'] = convertTexttoObject(models.Inventory, dfRequisition['Inventory'], 'Code')
    dfDetails['Inventory'] = dfRequisition['Inventory'][0]
    del dfRequisition

    dfDetails['Requisition'] = requisition

    for _, row in dfDetails.iterrows():
        inv = models.RequisitionInventory(**row)
        inv.save()

    return requisition.id

def EditRequisition (
        requisition: models.Requisition,
        dfRequisition: pd.DataFrame,
        dfInventory: pd.DataFrame,
        dfAllocation: pd.DataFrame
):
    '''
    Update the Requisition from the data in the Requisition table.
    '''
    if requisition.Confirmation:
        raise PermissionError('This requisition is already closed')
    
    previousInventories = models.RequisitionInventory.objects.filter(Requisition=requisition).values('id','Inventory','Variant')
    print(previousInventories)

def ProcessRequsitionData (requisition: models.Requisition):
    '''
    Get the data of the provided Receipt.
    '''

    if requisition.Confirmation:
        raise PermissionError('This requisition is already closed')
    
    inventories = models.RequisitionInventory.objects.filter(Requisition=requisition).values('Inventory','Variant','Quantity')

    #Convert time of receipt from UTC to local time
    requisition.DateTime = localtime(requisition.DateTime)
    
    requisition = {
        'RequisitionNumber': requisition.id,
        'Date': requisition.DateTime.date,
        'Time': requisition.DateTime.time,
        'Department': requisition.Department,
        'RequestBy': requisition.RequestBy,
        'StoreComments': '' if requisition.StoreComments is None else requisition.StoreComments
    }
    
    #Replace any None values with blank
    for item in inventories:
        for key, value in item.items():
            item[key] = '' if value is None else value

    return requisition, inventories