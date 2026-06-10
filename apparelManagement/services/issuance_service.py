import pandas as pd
import numpy as np

from typing import Dict, List

from django.db.models import Q
from django.db import transaction

from core.constants.generic import TODAY

from .. import models

from core.services.generic_services import concatenateValues, dfToListOfDicts, convertTexttoObject, updateModelWithDF
from core.constants.prod import SAMPLING_WORK_WORKER

#TODO: This would be obsolete once we transfer to next
def calculateBalance(df: pd.DataFrame) -> pd.Series:
    '''Checks the balance qty that can be issued.'''
    minQty = np.minimum(df['Required'], df['Received'])

    balance = minQty - df['Issued']

    return balance

#TODO: This would be obsolete once we transfer to next
def calculateMaxBalance(df: pd.DataFrame) -> pd.Series:
    partA = (1.02 * df['Required']) - df['Issued']
    partB = df['Received'] - df['Issued']

    maxBalance = np.minimum(partA, partB)

    return maxBalance

def consumeFIFO(row: pd.Index):
    required = row['Quantity']

    receipts = sorted(row['Details'], key=lambda x: x['ReceiptNumber'])

    consumedReceipts = []
    for receipt in receipts:
        if required <= 0:
            break
        
        rcptNum = receipt['ReceiptNumber']
        availQty = receipt['BalanceQty']

        if availQty <= 0:
            continue

        if availQty >= required:
            consumedReceipts.append({'ReceiptNumber': rcptNum, 'TakenQty': required})
            required = 0
        else:
            consumedReceipts.append({'ReceiptNumber': rcptNum, 'TakenQty': availQty})
            required -= availQty

    return consumedReceipts

#TODO: This would be obsolete once we transfer to next
def AddIssuance(requisition: models.Requisition, comments: str):
    issuance = {
        'Department': requisition.Department,
        'ReceivedBy': requisition.RequestBy,
        'InventoryRequisition': requisition
    }
    issuance = models.Issuance(**issuance)
    issuance.save()

    requisition.Confirmation = True
    requisition.StoreComments = comments
    requisition.save()

    requisitionInventories = models.RequisitionInventory.objects.filter(Requisition=requisition)
    for requisitionInventory in requisitionInventories:
        issueInventory = {
            'Issuance': issuance,
            'Inventory': requisitionInventory.Inventory,
            'Variant': requisitionInventory.Variant,
            'Quantity': requisitionInventory.Quantity
        }

        issueInventory = models.IssueInventory(**issueInventory)
        issueInventory.save()

        requisitionAllocations = models.RequisitionAllocation.objects.filter(RequisitionInventory=requisitionInventory)
        for requisitionAllocation in requisitionAllocations:
            issueAllocation = {
                'IssueInventory': issueInventory,
                'WorkOrder': requisitionAllocation.WorkOrder,
                'Quantity': requisitionAllocation.Quantity
            }
            issueAllocation = models.IssueAllocation(**issueAllocation)
            issueAllocation.save()

def AddIssuanceForWorkOrder(data: Dict[str, str | List[Dict[str, str|int]]]):
    inventories = data.get('Inventories', [])
    department = data.get('Department', None)
    workOrder = data.get('WorkOrder', None)

    try:
        department = models.Department.objects.get(Name = department)
    except:
        raise LookupError('Invalid Department')

    try:
        workOrder = models.WorkOrder.objects.get(OrderNumber=workOrder)
    except:
        raise LookupError('Invalid Work Order')
    
    requisition = models.Requisition.objects.all().first()

    issuance = {
        'Department': department,
        'Supplier': None,
        'ReceivedBy': department.Name,
        'InventoryRequisition': requisition
    }

    try:
        issuance = models.Issuance(**issuance)
    except Exception as e:
        raise ValueError(e)

    dfIssueInventories = pd.DataFrame(inventories)
    del inventories

    fields = ['POInvId__Inventory', 'POInvId__Variant', 'POInvId__Price', 'POInvId__Forex', 'Quantity']
    purchaseOrders = models.POAllocation.objects.filter(WorkOrder=workOrder).values(*fields)
    dfPurchaseOrders = pd.DataFrame(purchaseOrders) if purchaseOrders else pd.DataFrame(columns=fields)
    del purchaseOrders

    fields = ['id', 'Inventory', 'Variant', 'StockQuantity', 'StockValue']
    stockStatus = models.InventoryStock.objects.filter(
        Inventory__in=dfIssueInventories['Inventory'].unique(),
        Variant__in=dfIssueInventories['Variant'].unique(),
    ).values(*fields)
    dfPreviousStock = pd.DataFrame(stockStatus) if stockStatus else pd.DataFrame(columns=fields)
    del stockStatus

    dfPurchaseOrders.rename(inplace=True, columns={
        'POInvId__Inventory': 'Inventory',
        'POInvId__Variant': 'Variant',
        'POInvId__Price': 'Price',
        'POInvId__Forex': 'Forex',
    })

    dfPurchaseOrders['Price'] = dfPurchaseOrders['Price'].astype(float) * dfPurchaseOrders['Forex'].astype(float)
    dfPurchaseOrders.drop(inplace=True, columns=['Forex'])

    dfPurchaseOrders['Value'] = dfPurchaseOrders["Price"] * dfPurchaseOrders["Quantity"]

    dfPurchaseOrders = dfPurchaseOrders.groupby(["Inventory", "Variant"]).agg(
        Value=("Value", "sum"),
        Quantity=("Quantity", "sum")
    ).reset_index()

    dfPurchaseOrders["AveragePrice"] = dfPurchaseOrders["Value"] / dfPurchaseOrders["Quantity"]

    dfStockToRemove = pd.merge(
        left=dfIssueInventories,
        right=dfPurchaseOrders[["Inventory", "Variant", "AveragePrice"]],
        on=["Inventory", "Variant"],
        how="left",
    )

    dfStockToRemove['Value'] = dfStockToRemove["Quantity"] * dfStockToRemove["AveragePrice"]
    dfStockToRemove.drop(inplace=True, columns=['AveragePrice'])

    dfStockToRemove = pd.merge(left=dfStockToRemove, right=dfPreviousStock, on=['Inventory', 'Variant'], how='left')
    del dfPreviousStock

    dfStockToRemove['StockQuantity'] = dfStockToRemove['StockQuantity'].astype(float).sub(dfStockToRemove['Quantity'], fill_value=0)
    dfStockToRemove['StockValue'] = dfStockToRemove['StockValue'].astype(float).sub(dfStockToRemove['Value'], fill_value=0)
    dfStockToRemove.drop(inplace=True, columns=['Quantity', 'Value'])


    dfIssueInventories['Inventory'] = convertTexttoObject(models.Inventory, dfIssueInventories['Inventory'], 'Code')
    dfStockToRemove['Inventory'] = convertTexttoObject(models.Inventory, dfStockToRemove['Inventory'], 'Code')

    issueInventories = []
    issueAllocations = []
    for _, row in dfIssueInventories.iterrows():
        issueInventory = models.IssueInventory(**row)
        issueInventory.Issuance = issuance

        issueInventories.append(issueInventory)

        issueAllocation = models.IssueAllocation(
            IssueInventory=issueInventory,
            WorkOrder=workOrder,
            Quantity=row['Quantity']
        )
        issueAllocations.append(issueAllocation)
    
    with transaction.atomic():
        issuance.save()

        for inv in issueInventories:
            inv.save()

        models.IssueAllocation.objects.bulk_create(issueAllocations)

        updateModelWithDF(models.InventoryStock, dfStockToRemove, dfStockToRemove[['id']].dropna())
    
    return issuance.id

#TODO: This would be obsolete once we transfer to next
def AddIsuanceForOrder(dfIssuance: pd.DataFrame, dfWorkOrder: pd.DataFrame):
    try:
        workOrder = models.WorkOrder.objects.get(OrderNumber = dfWorkOrder['WorkOrder'][0])
    except:
        raise ValueError('Invalid WorkOrder')
    
    try:
        department = models.Department.objects.get(Name = dfWorkOrder['Department'][0])
        supplier = None
    except:
        department = None
        try:
            supplier = models.Supplier.objects.get(Name=dfWorkOrder['Department'][0])
        except:
            raise ValueError('Invalid Department')
    
    requisition = models.Requisition.objects.all().first()

    issuance = {
        'Department': department,
        'Supplier': supplier,
        'ReceivedBy': department if department else supplier,
        'InventoryRequisition': requisition
    }
    try:
        issuance = models.Issuance(**issuance)
        issuance.save()
    except Exception as e:
        raise ValueError(e)
    
    dfIssuance['Inventory'] = convertTexttoObject(models.Inventory, dfIssuance['Inventory'], 'Code')
    
    for _, row in dfIssuance.iterrows():
        issueInventory = models.IssueInventory(**row)
        issueInventory.Issuance = issuance
        issueInventory.save()

        models.IssueAllocation(
            IssueInventory=issueInventory,
            WorkOrder=workOrder,
            Quantity=row['Quantity']
        ).save()
    
    return issuance.id

def GetDataForWorkOrderIssuance(workOrder: models.WorkOrder):
    fields = ['InventoryCode', 'InventoryCode__Name', 'InventoryCode__Unit', 'Type']
    inventories = models.StyleConsumption.objects.filter(Style=workOrder.StyleCode).values(*fields)
    dfInventories = pd.DataFrame(inventories) if inventories else pd.DataFrame(columns=fields)
    del inventories

    filters = Q(OrderNumber=workOrder) & Q(InventoryCode__in=dfInventories['InventoryCode'].unique().tolist())
    fields = ['InventoryCode', 'Variant', 'Quantity']
    requirement = models.InvRequirement.objects.filter(filters).values(*fields)
    dfRequirement = pd.DataFrame(requirement) if requirement else pd.DataFrame(columns=fields)
    del requirement

    fields = ['POInvId__Inventory', 'POInvId__Variant', 'Quantity']
    purchaseOrders = models.POAllocation.objects.filter(WorkOrder=workOrder).values(*fields)
    dfPurchaseOrders = pd.DataFrame(purchaseOrders) if purchaseOrders else pd.DataFrame(columns=fields)
    del purchaseOrders

    fields = ['RecInvId__InventoryCode', 'RecInvId__Variant', 'Quantity']
    receipts = models.RecAllocation.objects.filter(WorkOrder=workOrder).values(*fields)
    dfReceipts = pd.DataFrame(receipts) if receipts else pd.DataFrame(columns=fields)
    del receipts

    fields = ['IssueInventory__Inventory', 'IssueInventory__Variant', 'Quantity']
    issuances= models.IssueAllocation.objects.filter(WorkOrder=workOrder).values(*fields)
    dfIssuances = pd.DataFrame(issuances) if issuances else pd.DataFrame(columns=fields)
    del issuances

    dfRequirement.rename(inplace=True, columns={'InventoryCode':'Inventory', 'Quantity': 'Required'})
    dfPurchaseOrders.rename(inplace=True, columns={
        'POInvId__Inventory': 'Inventory',
        'POInvId__Variant': 'Variant',
        'Quantity': 'Ordered'
    })
    dfReceipts.rename(inplace=True, columns={
        'RecInvId__InventoryCode': 'Inventory',
        'RecInvId__Variant': 'Variant',
        'Quantity': 'Received'
    })
    dfIssuances.rename(inplace=True, columns={
        'IssueInventory__Inventory': 'Inventory',
        'IssueInventory__Variant': 'Variant',
        'Quantity': 'Issued',
    })
    dfInventories.rename(inplace=True, columns={
        'InventoryCode': 'Inventory',
        'InventoryCode__Name': 'InventoryName',
        'InventoryCode__Unit': 'Unit'
    })

    dfRequirement = dfRequirement.groupby(by=['Inventory', 'Variant']).agg(
        Required = ('Required', 'sum')
    ).reset_index()

    dfResults = pd.merge(left=dfRequirement, right=dfPurchaseOrders, on=['Inventory', 'Variant'], how='left')
    del dfRequirement, dfPurchaseOrders
    dfResults = dfResults.groupby(by=['Inventory', 'Variant']).agg(
        Required = ('Required', 'first'),
        Ordered = ('Ordered', 'sum'),
    ).reset_index()

    dfResults = pd.merge(left=dfResults, right=dfReceipts, on=['Inventory', 'Variant'], how='left')
    del dfReceipts

    dfResults = dfResults.groupby(by=['Inventory', 'Variant']).agg(
        Required = ('Required', 'first'),
        Ordered = ('Ordered', 'first'),
        Received = ('Received', 'sum'),
    ).reset_index()

    dfResults = pd.merge(left=dfResults, right=dfIssuances, on=['Inventory', 'Variant'], how='left')
    del dfIssuances
    dfResults = dfResults.groupby(by=['Inventory', 'Variant']).agg(
        Required = ('Required', 'first'),
        Ordered = ('Ordered', 'first'),
        Received = ('Received', 'first'),
        Issued = ('Issued', 'sum'),
    ).reset_index()

    dfResults = pd.merge(left=dfResults, right=dfInventories, on=['Inventory'], how='left')
    del dfInventories

    return dfToListOfDicts(dfResults)

#TODO: This would be obsolete once we transfer to next
def GetDataForOrderIssuance(orderNumber: str|None, type: str|None, selectedInvs: List[str]):
    try:
        workOrder = models.WorkOrder.objects.get(OrderNumber=orderNumber)
        del orderNumber
    except:
        return [], []

    filters = Q(Style=workOrder.StyleCode)
    if type:
        filters &= Q(Type=type)
        del type
    fields = ['InventoryCode']
    inventories = models.StyleConsumption.objects.filter(filters).values(*fields)
    
    filters = Q(OrderNumber=workOrder) & Q(InventoryCode__in=inventories)
    fields = ['InventoryCode', 'Variant', 'Quantity']
    requirement = models.InvRequirement.objects.filter(filters).values(*fields)
    dfRequirement = pd.DataFrame(requirement) if requirement else pd.DataFrame(columns=fields)
    del requirement, inventories

    fields = ['POInvId', 'Quantity']
    poAllocations = models.POAllocation.objects.filter(WorkOrder=workOrder).values(*fields)
    dfPOAllocation = pd.DataFrame(poAllocations) if poAllocations else pd.DataFrame(columns=fields)
    del poAllocations

    fields = ['id', 'Inventory','Variant']
    poInventory = models.POInventory.objects.filter(id__in=dfPOAllocation['POInvId'].to_list()).values(*fields)
    dfPOInventory = pd.DataFrame(poInventory) if poInventory else pd.DataFrame(columns=fields)
    del poInventory

    fields = ['RecInvId', 'Quantity']
    recAllocation = models.RecAllocation.objects.filter(WorkOrder=workOrder).values(*fields)
    dfRecAllocation = pd.DataFrame(recAllocation) if recAllocation else pd.DataFrame(columns=fields)
    del recAllocation

    fields = ['id', 'InventoryCode', 'Variant']
    recInventory = models.RecInventory.objects.filter(id__in=dfRecAllocation['RecInvId'].to_list()).values(*fields)
    dfRecInventory = pd.DataFrame(recInventory) if recInventory else pd.DataFrame(columns=fields)
    del recInventory

    fields = ['IssueInventory', 'Quantity']
    issueAllocation = models.IssueAllocation.objects.filter(WorkOrder=workOrder).values(*fields)
    dfIssueAllocation = pd.DataFrame(issueAllocation) if issueAllocation else pd.DataFrame(columns=fields)
    del issueAllocation

    fields = ['id', 'Inventory', 'Variant']
    issueInventory = models.IssueInventory.objects.filter(id__in=dfIssueAllocation['IssueInventory'].to_list()).values(*fields)
    dfIssueInventory = pd.DataFrame(issueInventory) if issueInventory else pd.DataFrame(columns=fields)
    del issueInventory

    fields = ['Code', 'Name', 'Unit']
    inventories = models.Inventory.objects.filter(Code__in=dfRequirement['InventoryCode'].to_list()).values(*fields)
    dfInventories = pd.DataFrame(inventories) if inventories else pd.DataFrame(columns=fields)
    del inventories, fields

    dfRequirement.rename(inplace=True, columns={'InventoryCode':'Inventory', 'Quantity': 'Required'})
    
    dfPOAllocation = pd.merge(left=dfPOAllocation, right=dfPOInventory, left_on='POInvId', right_on='id', how='left')
    del dfPOInventory
    dfPOAllocation.drop(inplace=True, columns=['id','POInvId'])
    dfPOAllocation.rename(inplace=True, columns={'Quantity':'Ordered'})

    dfRecAllocation = pd.merge(left=dfRecAllocation, right=dfRecInventory, left_on='RecInvId', right_on='id', how='left')
    del dfRecInventory
    dfRecAllocation.drop(inplace=True, columns=['RecInvId', 'id'])
    dfRecAllocation.rename(inplace=True, columns={'Quantity':'Received'})

    dfIssueAllocation = pd.merge(left=dfIssueAllocation, right=dfIssueInventory, left_on='IssueInventory', right_on='id', how='left')
    del dfIssueInventory
    dfIssueAllocation.drop(inplace=True, columns=['IssueInventory', 'id'])
    dfIssueAllocation.rename(inplace=True, columns={'Quantity':'Issued'})

    dfRequirement = dfRequirement.groupby(by=['Inventory', 'Variant']).agg(
        Required = ('Required', 'sum')
    ).reset_index()
    
    dfResults = pd.merge(left=dfRequirement, right=dfPOAllocation, on=['Inventory', 'Variant'], how='left')
    del dfRequirement, dfPOAllocation
    dfResults = dfResults.groupby(by=['Inventory', 'Variant']).agg(
        Required = ('Required', 'first'),
        Ordered = ('Ordered', 'sum'),
    ).reset_index()

    dfResults = pd.merge(left=dfResults, right=dfRecAllocation, left_on=['Inventory', 'Variant'], right_on=['InventoryCode', 'Variant'], how='left')
    del dfRecAllocation
    dfResults.drop(inplace=True, columns=['InventoryCode'])

    dfResults = dfResults.groupby(by=['Inventory', 'Variant']).agg(
        Required = ('Required', 'first'),
        Ordered = ('Ordered', 'first'),
        Received = ('Received', 'sum'),
    ).reset_index()

    dfResults = pd.merge(left=dfResults, right=dfIssueAllocation, on=['Inventory', 'Variant'], how='left')
    del dfIssueAllocation
    dfResults = dfResults.groupby(by=['Inventory', 'Variant']).agg(
        Required = ('Required', 'first'),
        Ordered = ('Ordered', 'first'),
        Received = ('Received', 'first'),
        Issued = ('Issued', 'sum'),
    ).reset_index()

    dfResults = pd.merge(left=dfResults, right=dfInventories, left_on=['Inventory'], right_on=['Code'], how='left')
    del dfInventories
    dfResults.drop(inplace=True, columns=['Code'])
    dfResults.rename(inplace=True, columns={'Name': 'InventoryName'})

    allInventories = dfResults[['Inventory', 'InventoryName']].drop_duplicates().to_dict('records')
    if selectedInvs:
        dfResults = dfResults[dfResults['Inventory'].isin(selectedInvs)]

    qtyCols = ['Required', 'Ordered', 'Received', 'Issued']
    for col in qtyCols:
        dfResults[col] = pd.to_numeric(dfResults[col], errors='coerce')
    dfResults[qtyCols] = dfResults[qtyCols].fillna(0)

    dfResults['Balance'] = calculateBalance(dfResults)
    dfResults['MaxBalance'] = calculateMaxBalance(dfResults)

    return dfToListOfDicts(dfResults), allInventories

def GetIssuances():
    twoYearsAgo = TODAY.replace(year=TODAY.year - 2)
    filters = Q(IssuanceDate__gte=twoYearsAgo)
    fields = ['id', 'IssuanceDate', 'Department', 'Supplier', 'ReceivedBy']
    issuances = models.Issuance.objects.filter(filters).values(*fields)
    dfIssuances = pd.DataFrame(issuances) if issuances else pd.DataFrame(columns=fields)
    del issuances

    fields = ['id', 'Issuance', 'Inventory', 'Inventory__Name']
    inventories = models.IssueInventory.objects.filter(Issuance__in=dfIssuances['id'].unique().tolist()).values(*fields)
    dfInventories = pd.DataFrame(inventories) if inventories else pd.DataFrame(columns=fields)
    del inventories

    fields = ['IssueInventory','WorkOrder', 'WorkOrder__StyleCode']
    allocations = models.IssueAllocation.objects.filter(IssueInventory__in=dfInventories['id'].unique().tolist()).values(*fields)
    dfAllocations = pd.DataFrame(allocations) if allocations else pd.DataFrame(columns=fields)
    del allocations

    dfIssuances.rename(inplace=True, columns={'id':'IssuanceNumber'})
    dfInventories.rename(inplace=True, columns={'id':'IssueInventory', 'Issuance': 'IssuanceNumber', 'Inventory__Name': 'InventoryName'})
    dfAllocations.rename(inplace=True, columns={'WorkOrder__StyleCode': 'StyleCode'})

    dfIssuances['Department'] = dfIssuances['Department'].fillna(dfIssuances['Supplier'])
    dfIssuances.drop(inplace=True, columns=['Supplier'])

    dfIssuances = pd.merge(left=dfIssuances, right=dfInventories, on='IssuanceNumber', how='left')
    del dfInventories

    dfIssuances = pd.merge(left=dfIssuances, right=dfAllocations, on='IssueInventory', how='left')
    dfIssuances.drop(inplace=True, columns=['IssueInventory'])
    del dfAllocations

    dfIssuances = dfIssuances.groupby('IssuanceNumber').agg({
        'IssuanceDate': 'first',
        'Department': 'first',
        'ReceivedBy': 'first',
        'Inventory': lambda x: list(set(x)),
        'InventoryName': lambda x: list(set(x)),
        'StyleCode': lambda x: list(set(i for i in x if pd.notnull(i))),
        'WorkOrder': lambda x: list(set(int(i) for i in x if pd.notnull(i))),
    }).reset_index()

    dfIssuances.rename(inplace=True, columns={
        'IssuanceNumber': 'id', 'Inventory': 'InventoryCodes', 'ReceivedBy': 'IssuedTo',
        'InventoryName': 'InventoryNames', 'StyleCode': 'StyleCodes', 'WorkOrder': 'WorkOrders',
    })

    dfIssuances.sort_values(inplace=True, by='id', ascending=False)

    return dfToListOfDicts(dfIssuances)

#TODO: This would be obsolete once we transfer to next
def GetIssuanceList (
        searchTerm: str,
        departmentFilter: str,
        issuanceNumber: int
):
    '''
    Get the list of requisitions
    '''
    if departmentFilter:
        issuances = models.Issuance.objects.filter(Department=departmentFilter)
    else:
        issuances = models.Issuance.objects.all()
    del departmentFilter

    if issuanceNumber:
        issuances = issuances.filter(id=issuanceNumber)
    
    issuances = issuances.values('id','IssuanceDate','Department','ReceivedBy','InventoryRequisition')

    if issuances:
        dfIssuances = pd.DataFrame(issuances)
    else:
        return []
    del issuances

    issuanceInventories = models.IssueInventory.objects.filter(Issuance__in=dfIssuances['id'].to_list())
    issuanceInventories = issuanceInventories.values('id','Issuance','Inventory')
    if issuanceInventories:
        dfIssuanceInventories = pd.DataFrame(issuanceInventories)
    else:
        dfIssuanceInventories = pd.DataFrame(columns=['id','Issuance','Inventory'])
    del issuanceInventories

    issuanceAllocations = models.IssueAllocation.objects.filter(IssueInventory__in=dfIssuanceInventories['id'].to_list())
    issuanceAllocations = issuanceAllocations.values('IssueInventory','WorkOrder')
    if issuanceAllocations:
        dfIssuanceAllocations = pd.DataFrame(issuanceAllocations)
    else:
        dfIssuanceAllocations = pd.DataFrame(columns=['IssueInventory','WorkOrder'])
    del issuanceAllocations

    invCards = models.Inventory.objects.filter(Code__in=dfIssuanceInventories['Inventory'].to_list()).values('Code','Name')
    if invCards:
        dfInvCards = pd.DataFrame(invCards)
    else:
        dfInvCards = pd.DataFrame(columns=['Code','Name'])
    del invCards

    dfIssuanceInventories = pd.merge(left=dfIssuanceInventories, right=dfInvCards, left_on='Inventory', right_on='Code', how='left')
    del dfInvCards
    dfIssuanceInventories.drop(inplace=True, columns=['Inventory','Code'])
    
    dfIssuanceInventories = pd.merge(left=dfIssuanceInventories, right=dfIssuanceAllocations, left_on='id', right_on='IssueInventory', how='left')
    del dfIssuanceAllocations
    dfIssuanceInventories.drop(inplace=True, columns=['id','IssueInventory'])

    dfIssuances = pd.merge(left=dfIssuances, right=dfIssuanceInventories, left_on='id', right_on='Issuance', how='left')
    del dfIssuanceInventories
    dfIssuances.drop(inplace=True, columns=['Issuance'])

    dfIssuances = dfIssuances.groupby('id').agg({
        'IssuanceDate': 'first',
        'Department': 'first',
        'ReceivedBy': 'first',
        'InventoryRequisition': 'first',
        'Name': concatenateValues,
        'WorkOrder': concatenateValues,
    }).reset_index()

    dfIssuances = dfIssuances.sort_values(by='IssuanceDate', ascending=False)

    searchTerm = searchTerm.lower()
    mask = dfIssuances.apply(lambda row: any(searchTerm in str(val).lower() for val in row.values), axis=1)
    dfIssuances = dfIssuances[mask]

    return dfToListOfDicts(dfIssuances)

#TODO: This would be unused once we transfer to next, but should resume once requistion is implemented
def ProcessRequisitionData(requisition: models.Requisition):
    fields = ['id', 'Inventory','Variant','Quantity']
    requisitionInventories = models.RequisitionInventory.objects.filter(Requisition=requisition).values(*fields)
    if requisitionInventories:
        dfRequisitionInventories = pd.DataFrame(requisitionInventories)
    else:
        dfRequisitionInventories = pd.DataFrame(columns=fields)
    del requisitionInventories

    fields = ['Code', 'Name', 'Unit']
    inventories = models.Inventory.objects.filter(Code__in=dfRequisitionInventories['Inventory'].to_list()).values(*fields)
    if inventories:
        dfInventories = pd.DataFrame(inventories)
    else:
        dfInventories = pd.DataFrame(columns=fields)
    del inventories

    fields = ['RequisitionInventory', 'WorkOrder']
    allocations = models.RequisitionAllocation.objects.filter(RequisitionInventory__in=dfRequisitionInventories['id'].to_list()).values(*fields)
    if allocations:
        dfAllocations = pd.DataFrame(allocations)
    else:
        dfAllocations = pd.DataFrame(columns=fields)
    del fields, allocations

    dfResults = pd.merge(left=dfRequisitionInventories, right=dfInventories, left_on='Inventory', right_on='Code', how='left')
    del dfRequisitionInventories, dfInventories
    dfResults.drop(inplace=True, columns=['Inventory', 'Code'])
    dfResults.rename(inplace=True, columns={'Name': 'InventoryName'})

    dfResults = pd.merge(left=dfResults, right=dfAllocations, left_on='id', right_on='RequisitionInventory', how='left')
    del dfAllocations
    dfResults.drop(inplace=True, columns=['id','RequisitionInventory'])

    dfResults['WorkOrder'] = np.where(dfResults['WorkOrder'].isna(), '', dfResults['WorkOrder'])

    return dfToListOfDicts(dfResults)

def GetDataForSamplingIssuance():
    fields = ['RecInvId__InventoryCode', 'RecInvId__InventoryCode__Name', 'RecInvId__InventoryCode__Unit', 'RecInvId__Variant', 'RecInvId__ReceiptNumber', 'RecInvId__ReceiptNumber__ReceiptDate', 'Quantity']
    recAllocations = models.RecAllocation.objects.filter(WorkOrder=SAMPLING_WORK_WORKER).values(*fields)
    dfReceipts = pd.DataFrame(recAllocations) if recAllocations else pd.DataFrame(columns=fields)
    del recAllocations

    fields = ['IssueInventory__Inventory', 'IssueInventory__Variant', 'Quantity']
    issuances = models.IssueAllocation.objects.filter(WorkOrder=SAMPLING_WORK_WORKER).values(*fields)
    dfIssuances = pd.DataFrame(issuances) if issuances else pd.DataFrame(columns=fields)
    del issuances

    dfReceipts.rename(inplace=True, columns={
        'RecInvId__InventoryCode': 'Inventory',
        'RecInvId__InventoryCode__Name': 'InventoryName',
        'RecInvId__InventoryCode__Unit': 'Unit',
        'RecInvId__Variant': 'Variant',
        'RecInvId__ReceiptNumber': 'ReceiptNumber',
        'RecInvId__ReceiptNumber__ReceiptDate': 'ReceiptDate',
        'Quantity': 'Received',
    })
    dfIssuances.rename(inplace=True, columns={
        'IssueInventory__Inventory': 'Inventory',
        'IssueInventory__Variant': 'Variant',
        'Quantity': 'Issued',  
    })

    
    #FIFO calculations for issuances against received
    dfReceipts['ReceiptDate'] = pd.to_datetime(dfReceipts['ReceiptDate'])
    dfReceipts = dfReceipts.sort_values(['Inventory', 'Variant', 'ReceiptDate'])

    dfIssuances = dfIssuances.groupby(['Inventory', 'Variant'])['Issued'].sum().reset_index()

    dfReceipts = pd.merge(left=dfReceipts, right=dfIssuances, on=['Inventory', 'Variant'], how='left')
    del dfIssuances

    dfReceipts['Issued'] = dfReceipts['Issued'].fillna(0).infer_objects(copy=False)

    dfReceipts['RunningTotal'] = dfReceipts.groupby(['Inventory', 'Variant'])['Received'].cumsum()
    dfReceipts['RemainingInRow'] = dfReceipts['RunningTotal'] - dfReceipts['Issued']

    dfReceipts = dfReceipts[dfReceipts['RemainingInRow'] > 0].copy()

    dfReceipts['Quantity'] = dfReceipts.apply(
        lambda x: min(x['Received'], x['RemainingInRow']), axis=1
    )
    dfReceipts.drop(inplace=True, columns=['Received', 'Issued', 'RunningTotal', 'RemainingInRow'])

    dfReceipts['URL'] = '/mmc/inventory-receipt/'+dfReceipts['ReceiptNumber'].astype(str)+'/edit'
    dfReceipts['Details'] = dfReceipts.apply(
        lambda row: {
            'ReceiptNumber': row['ReceiptNumber'],
            'ReceiptDate': row['ReceiptDate'],
            'BalanceQty': row['Quantity'],
            'URL': row['URL'],
        },
        axis=1
    )
    
    dfReceipts = dfReceipts.groupby(['Inventory', 'Variant']).agg({
        'Quantity': 'sum',
        'InventoryName': 'first',
        'Unit': 'first',
        'Details': list
    }).reset_index()

    return dfToListOfDicts(dfReceipts)

def AddSamplingIssuance(data: Dict[str, str | List[Dict[str, str|int]]]):
    inventories = data.get('Inventories', [])
    department = data.get('Department', None)


    #Check and ensure that the total issued qty is less than available qty
    for item in inventories:
        issuedQty = float(item.get('Quantity', 0))
        details = item.get('Details', [])

        availableQty = sum(float(detail.get('BalanceQty', 0)) for detail in details)

        if issuedQty > availableQty:
            raise ValueError('Issued Quantity cannot be more than available Quantity')


    samplingWO = models.WorkOrder.objects.get(OrderNumber=SAMPLING_WORK_WORKER)

    try:
        department = models.Department.objects.get(Name = department)
    except:
        raise LookupError('Invalid Department')
    
    requisition = models.Requisition.objects.all().first()

    issuance = {
        'Department': department,
        'Supplier': None,
        'ReceivedBy': department.Name,
        'InventoryRequisition': requisition
    }
    try:
        issuance = models.Issuance(**issuance)
    except Exception as e:
        raise ValueError(e)
    
    dfIssueInventories = pd.DataFrame(inventories)
    del inventories

    fields = ['id', 'Inventory', 'Variant', 'StockQuantity', 'StockValue']
    stockStatus = models.InventoryStock.objects.filter(
        Inventory__in=dfIssueInventories['Inventory'].unique(),
        Variant__in=dfIssueInventories['Variant'].unique(),
    ).values(*fields)
    dfPreviousStock = pd.DataFrame(stockStatus) if stockStatus else pd.DataFrame(columns=fields)
    del stockStatus

    dfIssueInventories['FulfilledBy'] = dfIssueInventories.apply(consumeFIFO, axis=1)
    dfIssueInventories.drop(inplace=True, columns=['Details'])
    dfIssuedStock = dfIssueInventories.explode('FulfilledBy').reset_index(drop=True)

    receiptsList = [d['ReceiptNumber'] for sublist in dfIssueInventories['FulfilledBy'] for d in sublist if 'ReceiptNumber' in d]
    dfIssueInventories.drop(inplace=True, columns=['FulfilledBy'])
    
    fields = ['id', 'PONumber']
    purchaseOrders = models.InventoryReciept.objects.filter(id__in=receiptsList).values(*fields)
    dfPurchaseOrders = pd.DataFrame(purchaseOrders) if purchaseOrders else pd.DataFrame(columns=fields)
    del purchaseOrders

    fields = ['PONumber', 'Inventory', 'Variant', 'Price', 'Forex']
    poInventories = models.POInventory.objects.filter(PONumber__in=dfPurchaseOrders['PONumber'].to_list()).values(*fields)
    dfPOInventories = pd.DataFrame(poInventories) if poInventories else pd.DataFrame(columns=fields)
    del poInventories

    dfPurchaseOrders.rename(inplace=True, columns={'id': 'ReceiptNumber'})

    dfPurchaseOrders = pd.merge(left=dfPurchaseOrders, right=dfPOInventories, on='PONumber', how='left')
    del dfPOInventories

    dfFulfilledBy = pd.json_normalize(dfIssuedStock["FulfilledBy"])
    dfIssuedStock = pd.concat(
        [dfIssuedStock.drop(columns=["FulfilledBy"]), dfFulfilledBy], axis=1
    )

    dfIssuedStock = pd.merge(left=dfIssuedStock, right=dfPurchaseOrders, on=["ReceiptNumber", "Inventory", "Variant"], how='left')

    dfIssuedStock["Value"] = dfIssuedStock["TakenQty"] * dfIssuedStock["Price"] * dfIssuedStock['Forex']

    dfIssuedStock = dfIssuedStock.groupby(["Inventory", "Variant"]).agg(
        Quantity=("TakenQty", "sum"),
        Value=("Value", "sum"),
    ).reset_index()

    dfIssuedStock = pd.merge(left=dfIssuedStock, right=dfPreviousStock, on=['Inventory', 'Variant'], how='left')
    del dfPreviousStock

    dfIssuedStock['StockQuantity'] = dfIssuedStock['StockQuantity'].astype(float).sub(dfIssuedStock['Quantity'], fill_value=0)
    dfIssuedStock['StockValue'] = dfIssuedStock['StockValue'].astype(float).sub(dfIssuedStock['Value'], fill_value=0)
    dfIssuedStock.drop(inplace=True, columns=['Quantity', 'Value'])

    dfIssueInventories['Inventory'] = convertTexttoObject(models.Inventory, dfIssueInventories['Inventory'], 'Code')
    dfIssueInventories['Issuance'] = issuance

    dfIssuedStock['Inventory'] = convertTexttoObject(models.Inventory, dfIssuedStock['Inventory'], 'Code')

    issueInventories = []
    issueAllocations = []
    for _, row in dfIssueInventories.iterrows():
        issueInventory = models.IssueInventory(**row)
        issueInventories.append(issueInventory)

        issueAllocation = models.IssueAllocation(
            IssueInventory=issueInventory,
            WorkOrder=samplingWO,
            Quantity=row['Quantity']
        )
        issueAllocations.append(issueAllocation)
    
    with transaction.atomic():
        issuance.save()

        for inv in issueInventories:
            inv.save()

        models.IssueAllocation.objects.bulk_create(issueAllocations)

        updateModelWithDF(models.InventoryStock, dfIssuedStock, dfIssuedStock[['id']].dropna())

    return issuance.id

def GetDataForInventoryIssuance(selectedCodes: List[str]):
    fields = ['id', 'ReceiptNumber', 'ReceiptNumber__ReceiptDate', 'InventoryCode', 'InventoryCode__Name', 'InventoryCode__Unit', 'Variant', 'Quantity']
    receivedInventories = models.RecInventory.objects.filter(InventoryCode__in=selectedCodes).values(*fields)
    dfReceivedInventories = pd.DataFrame(receivedInventories) if receivedInventories else pd.DataFrame(columns=fields)
    del receivedInventories

    fields = ['RecInvId', 'Quantity']
    receiptAllocations = models.RecAllocation.objects.filter(RecInvId__in=dfReceivedInventories['id'].unique().tolist())
    dfReceiptAllocations = pd.DataFrame(receiptAllocations) if receiptAllocations else pd.DataFrame(columns=fields)
    del receiptAllocations

    fields = ['id', 'Inventory', 'Variant', 'Quantity']
    issuedInventories = models.IssueInventory.objects.filter(Inventory__in=selectedCodes).values(*fields)
    dfIssuedInventories = pd.DataFrame(issuedInventories) if issuedInventories else pd.DataFrame(columns=fields)
    del issuedInventories

    fields = ['IssueInventory', 'Quantity']
    issuedAllocations = models.IssueAllocation.objects.filter(IssueInventory__in=dfIssuedInventories['id'].unique().tolist()).values(*fields)
    dfIssuedAllocations = pd.DataFrame(issuedAllocations) if issuedAllocations else pd.DataFrame(columns=fields)
    del issuedAllocations

    dfReceivedInventories.rename(inplace=True, columns={
        'ReceiptNumber__ReceiptDate': 'ReceiptDate',
        'InventoryCode': 'Inventory',
        'InventoryCode__Name': 'InventoryName',
        'InventoryCode__Unit': 'Unit',
    })
    dfReceiptAllocations.rename(inplace=True, columns={'RecInvId': 'id', 'Quantity': 'AllocatedQty'})
    dfReceiptAllocations = dfReceiptAllocations.groupby('id')['AllocatedQty'].sum().reset_index()

    dfReceivedInventories = pd.merge(left=dfReceivedInventories, right=dfReceiptAllocations, on='id', how='left') 
    del dfReceiptAllocations

    dfReceivedInventories['AllocatedQty'] = dfReceivedInventories['AllocatedQty'].fillna(0).infer_objects(copy=False)
    dfReceivedInventories['Quantity'] = dfReceivedInventories['Quantity'] - dfReceivedInventories['AllocatedQty']
    dfReceivedInventories.drop(inplace=True, columns=['id', 'AllocatedQty'])

    dfIssuedAllocations.rename(inplace=True, columns={'IssueInventory': 'id', 'Quantity': 'AllocatedQty'})
    dfIssuedAllocations = dfIssuedAllocations.groupby('id')['AllocatedQty'].sum().reset_index()

    dfIssuedInventories = pd.merge(left=dfIssuedInventories, right=dfIssuedAllocations, on='id', how='left') 
    del dfIssuedAllocations

    dfIssuedInventories['AllocatedQty'] = dfIssuedInventories['AllocatedQty'].fillna(0).infer_objects(copy=False)
    dfIssuedInventories['Quantity'] = dfIssuedInventories['Quantity'] - dfIssuedInventories['AllocatedQty']
    dfIssuedInventories.drop(inplace=True, columns=['id', 'AllocatedQty'])

    #FIFO calculations for issuances against received
    dfReceivedInventories['ReceiptDate'] = pd.to_datetime(dfReceivedInventories['ReceiptDate'])
    dfReceivedInventories = dfReceivedInventories.sort_values(['Inventory', 'Variant', 'ReceiptDate'])

    dfIssuedInventories = dfIssuedInventories.groupby(['Inventory', 'Variant'])['Quantity'].sum().reset_index()

    dfReceivedInventories = pd.merge(left=dfReceivedInventories, right=dfIssuedInventories, on=['Inventory', 'Variant'], how='left', suffixes=['_Received', '_Issued'])
    del dfIssuedInventories

    dfReceivedInventories['Quantity_Issued'] = dfReceivedInventories['Quantity_Issued'].fillna(0).infer_objects(copy=False)
    dfReceivedInventories['CumSum_Received'] = dfReceivedInventories.groupby(['Inventory', 'Variant'])['Quantity_Received'].cumsum()
    dfReceivedInventories['Prior_CumSum_Received'] = dfReceivedInventories['CumSum_Received'] - dfReceivedInventories['Quantity_Received']
    dfReceivedInventories['Quantity'] = dfReceivedInventories['Quantity_Received'] - np.clip(
        dfReceivedInventories['Quantity_Issued'] - dfReceivedInventories['Prior_CumSum_Received'],
        0,
        dfReceivedInventories['Quantity_Received']
    )
    dfReceivedInventories = dfReceivedInventories.drop(
        columns=['Quantity_Received', 'Quantity_Issued', 'CumSum_Received', 'Prior_CumSum_Received']
    )

    dfReceivedInventories = dfReceivedInventories[dfReceivedInventories['Quantity'] != 0]
    dfReceivedInventories['URL'] = '/mmc/inventory-receipt/'+dfReceivedInventories['ReceiptNumber'].astype(str)+'/edit'
    dfReceivedInventories['Details'] = dfReceivedInventories.apply(
        lambda row: {
            'ReceiptNumber': row['ReceiptNumber'],
            'ReceiptDate': row['ReceiptDate'],
            'BalanceQty': row['Quantity'],
            'URL': row['URL'],
        },
        axis=1
    )

    dfReceivedInventories = dfReceivedInventories.groupby(['Inventory', 'Variant']).agg({
        'Quantity': 'sum',
        'InventoryName': 'first',
        'Unit': 'first',
        'Details': list
    }).reset_index()

    return dfToListOfDicts(dfReceivedInventories)

def AddInventoryIssuance(data: Dict[str, str | List[Dict[str, str|int]]]):
    inventories = data.get('Inventories', [])
    department = data.get('Department', None)

    #Check and ensure that the total issued qty is less than available qty
    for item in inventories:
        issuedQty = float(item.get('Quantity', 0))
        details = item.get('Details', [])

        availableQty = sum(float(detail.get('BalanceQty', 0)) for detail in details)

        if issuedQty > availableQty:
            raise ValueError('Issued Quantity cannot be more than available Quantity')
    
    try:
        department = models.Department.objects.get(Name = department)
    except:
        raise LookupError('Invalid Department')
    
    requisition = models.Requisition.objects.all().first()
    issuance = {
        'Department': department,
        'Supplier': None,
        'ReceivedBy': department.Name,
        'InventoryRequisition': requisition
    }
    try:
        issuance = models.Issuance(**issuance)
    except Exception as e:
        raise ValueError(e)
    
    dfIssueInventories = pd.DataFrame(inventories)
    del inventories

    fields = ['id', 'Inventory', 'Variant', 'StockQuantity', 'StockValue']
    stockStatus = models.InventoryStock.objects.filter(
        Inventory__in=dfIssueInventories['Inventory'].unique(),
        Variant__in=dfIssueInventories['Variant'].unique(),
    ).values(*fields)
    dfPreviousStock = pd.DataFrame(stockStatus) if stockStatus else pd.DataFrame(columns=fields)
    del stockStatus

    dfIssueInventories['FulfilledBy'] = dfIssueInventories.apply(consumeFIFO, axis=1)
    dfIssueInventories.drop(inplace=True, columns=['Details'])
    dfIssuedStock = dfIssueInventories.explode('FulfilledBy').reset_index(drop=True)

    receiptsList = [d['ReceiptNumber'] for sublist in dfIssueInventories['FulfilledBy'] for d in sublist if 'ReceiptNumber' in d]
    dfIssueInventories.drop(inplace=True, columns=['FulfilledBy'])
    
    fields = ['id', 'PONumber']
    purchaseOrders = models.InventoryReciept.objects.filter(id__in=receiptsList).values(*fields)
    dfPurchaseOrders = pd.DataFrame(purchaseOrders) if purchaseOrders else pd.DataFrame(columns=fields)
    del purchaseOrders

    fields = ['PONumber', 'Inventory', 'Variant', 'Price', 'Forex']
    poInventories = models.POInventory.objects.filter(PONumber__in=dfPurchaseOrders['PONumber'].to_list()).values(*fields)
    dfPOInventories = pd.DataFrame(poInventories) if poInventories else pd.DataFrame(columns=fields)
    del poInventories

    dfPurchaseOrders.rename(inplace=True, columns={'id': 'ReceiptNumber'})

    dfPurchaseOrders = pd.merge(left=dfPurchaseOrders, right=dfPOInventories, on='PONumber', how='left')
    del dfPOInventories

    dfFulfilledBy = pd.json_normalize(dfIssuedStock["FulfilledBy"])
    dfIssuedStock = pd.concat(
        [dfIssuedStock.drop(columns=["FulfilledBy"]), dfFulfilledBy], axis=1
    )

    dfIssuedStock = pd.merge(left=dfIssuedStock, right=dfPurchaseOrders, on=["ReceiptNumber", "Inventory", "Variant"], how='left')

    dfIssuedStock["Value"] = dfIssuedStock["TakenQty"] * dfIssuedStock["Price"] * dfIssuedStock['Forex']

    dfIssuedStock = dfIssuedStock.groupby(["Inventory", "Variant"]).agg(
        Quantity=("TakenQty", "sum"),
        Value=("Value", "sum"),
    ).reset_index()

    dfIssuedStock = pd.merge(left=dfIssuedStock, right=dfPreviousStock, on=['Inventory', 'Variant'], how='left')
    del dfPreviousStock

    dfIssuedStock['StockQuantity'] = dfIssuedStock['StockQuantity'].astype(float).sub(dfIssuedStock['Quantity'], fill_value=0)
    dfIssuedStock['StockValue'] = dfIssuedStock['StockValue'].astype(float).sub(dfIssuedStock['Value'], fill_value=0)
    dfIssuedStock.drop(inplace=True, columns=['Quantity', 'Value'])

    dfIssueInventories['Inventory'] = convertTexttoObject(models.Inventory, dfIssueInventories['Inventory'], 'Code')
    dfIssueInventories['Issuance'] = issuance

    dfIssuedStock['Inventory'] = convertTexttoObject(models.Inventory, dfIssuedStock['Inventory'], 'Code')

    issueInventories = []
    for _, row in dfIssueInventories.iterrows():
        issueInventory = models.IssueInventory(**row)
        issueInventories.append(issueInventory)

    with transaction.atomic():
        issuance.save()
        models.IssueInventory.objects.bulk_create(issueInventories)

        updateModelWithDF(models.InventoryStock, dfIssuedStock, dfIssuedStock[['id']].dropna())
    
    return issuance.id