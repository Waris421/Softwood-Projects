import pandas as pd

from django.db.models import Q

from .. import models
from core.services.generic_services import dfToListOfDicts

def GetPOAllocations(type: str|None):
    filters = Q()

    if type:
        filters &= Q(Inventory__Code__startswith=type)
    
    fields = ['id','PONumber','Inventory']
    poInventories = models.POInventory.objects.filter(filters).values(*fields)
    dfPOInventories = pd.DataFrame(poInventories) if poInventories else pd.DataFrame(columns=fields)
    del poInventories

    fields = ['POInvId','WorkOrder','Quantity']
    poAllocations = models.POAllocation.objects.filter(POInvId__in=dfPOInventories['id'].to_list()).values(*fields)
    dfPOAllocations = pd.DataFrame(poAllocations) if poAllocations else pd.DataFrame(columns=fields)
    del poAllocations

    fields = ['Code', 'Name']
    inventories = models.Inventory.objects.filter(Code__in=dfPOInventories['Inventory'].to_list()).values(*fields)
    dfInventories = pd.DataFrame(inventories) if inventories else pd.DataFrame(columns=fields)
    del inventories, fields

    dfPOAllocations = pd.merge(left=dfPOAllocations, right=dfPOInventories, left_on='POInvId', right_on='id', how='left')
    del dfPOInventories
    dfPOAllocations.drop(inplace=True, columns=['id','POInvId'])

    dfPOAllocations = pd.merge(left=dfPOAllocations, right=dfInventories, left_on='Inventory', right_on='Code', how='left')
    del dfInventories
    dfPOAllocations.drop(inplace=True, columns=['Inventory'])

    columnOrder = ['PONumber', 'WorkOrder', 'Code', 'Name', 'Quantity']
    dfPOAllocations = dfPOAllocations[columnOrder]

    return dfToListOfDicts(dfPOAllocations)