import pandas as pd
import numpy as np

from typing import Dict, List

from django.db.models import Q
from django.db import transaction

from .. import models

from core.services.generic_services import concatenateValues, dfToListOfDicts, convertTexttoObject
from core.constants.prod import SAMPLING_WORK_WORKER

def calculateBalance(df: pd.DataFrame) -> pd.Series:
    '''Checks the balance qty that can be issued.'''
    minQty = np.minimum(df['Required'], df['Received'])

    balance = minQty - df['Issued']

    return balance

def calculateMaxBalance(df: pd.DataFrame) -> pd.Series:
    partA = (1.02 * df['Required']) - df['Issued']
    partB = df['Received'] - df['Issued']

    maxBalance = np.minimum(partA, partB)

    return maxBalance

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

    dfReceipts['Details'] = dfReceipts.apply(
        lambda row: {'ReceiptNumber': row['ReceiptNumber'], 'ReceiptDate': row['ReceiptDate'], 'BalanceQty': row['Quantity']}, 
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

    dfIssueInventories['Inventory'] = convertTexttoObject(models.Inventory, dfIssueInventories['Inventory'], 'Code')
    dfIssueInventories['Issuance'] = issuance

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

    return issuance.id