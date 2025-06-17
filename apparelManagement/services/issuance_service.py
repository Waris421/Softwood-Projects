import pandas as pd
import numpy as np

from .. import models

from core.services.generic_services import concatenateValues

pd.options.mode.chained_assignment = None
pd.set_option('display.max_columns', None)

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

    cols = [i for i in dfIssuances]
    data = [dict(zip(cols, i)) for i in dfIssuances.values]
    return data

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

    cols = [i for i in dfResults]
    data = [dict(zip(cols, i)) for i in dfResults.values]
    return data