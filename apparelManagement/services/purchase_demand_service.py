import pandas as pd
import numpy as np

from typing import List

from django.forms import model_to_dict
from django.http import HttpRequest
from django.db.models import Window, F
from django.db.models.functions import RowNumber

from .. import models
from core.services.generic_services import updateModelWithDF, convertTexttoObject, concatenateValues, dfToListOfDicts
from core.services.auth_service import canApprovePD

def getContextForPDApproval(inventoryCodes: List[str]):
    fields = ['PONumber', 'Inventory', 'Quantity', 'Price', 'Forex']
    poInventories = models.POInventory.objects.filter(Inventory__in=inventoryCodes).values(*fields)
    dfPOInventories = pd.DataFrame(poInventories) if poInventories else pd.DataFrame(columns=fields)
    del poInventories

    fields = ['id', 'OrderDate', 'Supplier']
    purchaseOrders = models.PurchaseOrder.objects.filter(id__in=dfPOInventories['PONumber'].to_list()).values(*fields)
    dfPurchaseOrders = pd.DataFrame(purchaseOrders) if purchaseOrders else pd.DataFrame(columns=fields)
    del purchaseOrders

    fields = ['Code', 'Name', 'Unit', 'StandardPrice']  
    inventories = models.Inventory.objects.filter(Code__in=inventoryCodes).values(*fields)
    dfInventories = pd.DataFrame(inventories) if inventories else pd.DataFrame(columns=fields)
    del inventories

    dfPurchaseOrders = pd.merge(left=dfPurchaseOrders, right=dfPOInventories, left_on='id', right_on='PONumber', how='left')
    del dfPOInventories
    dfPurchaseOrders.drop(inplace=True, columns=['id'])

    dfPurchaseOrders['Price'] = dfPurchaseOrders['Price'] * dfPurchaseOrders['Forex']
    dfPurchaseOrders.drop(inplace=True, columns=['Forex'])

    dfPurchaseOrders = pd.merge(left=dfPurchaseOrders, right=dfInventories, left_on='Inventory', right_on='Code', how='left')
    del dfInventories
    dfPurchaseOrders.drop(inplace=True, columns=['Code', 'Inventory'])

    dfPurchaseOrders['Quantity'] = dfPurchaseOrders['Quantity'].astype(int).astype(str) + ' ' + dfPurchaseOrders['Unit']
    dfPurchaseOrders.drop(inplace=True, columns=['Unit'])

    dfPurchaseOrders['OrderDate'] = pd.to_datetime(dfPurchaseOrders['OrderDate'])
    dfPurchaseOrders = dfPurchaseOrders.sort_values(by='OrderDate', ascending=False)

    noOfInventories = dfPurchaseOrders['Name'].nunique()

    if noOfInventories == 1:
        dfPurchaseOrders = dfPurchaseOrders.head(3)
    
    elif noOfInventories == 2:
        dfTop3 = dfPurchaseOrders.head(3)

        if dfTop3['Name'].nunique() < 2:
            firstInv = dfTop3['Name'].iloc[0]
            otherInvLatest = dfPurchaseOrders[dfPurchaseOrders['Name'] != firstInv].head(1)

            dfPurchaseOrders = pd.concat([dfPurchaseOrders[dfPurchaseOrders['Name'] == firstInv].head(2), otherInvLatest])
        else:
            dfPurchaseOrders = dfTop3
    else:
        dfPurchaseOrders = dfPurchaseOrders.groupby('Name').head(1)

    return dfToListOfDicts(dfPurchaseOrders)

def GetPurchaseDemandList (
    searchTerm: str,
    department: str,
    pdNumber: int,
    statusFilter: str
):
    '''
    Get the list of all purchase orders
    '''
    demands = models.PurchaseDemand.objects.all()
    
    demands = demands.values('id','DemandDate','Department','Demandee','Approval','PONumber')
    
    if demands:
        dfDemands = pd.DataFrame(demands)
        del demands
    else:
        return []
    
    inventories = models.PDInventory.objects.filter(PDNumber__in=dfDemands['id'].to_list())
    inventories = inventories.values('id','PDNumber','Inventory')
    dfInventories = pd.DataFrame(inventories)
    del inventories

    inventoryCards = models.Inventory.objects.filter(Code__in=dfInventories['Inventory'].to_list())
    inventoryCards = inventoryCards.values('Code','Name')
    dfInventoryCards = pd.DataFrame(inventoryCards)
    del inventoryCards
    
    if department:
        dfDemands = dfDemands[dfDemands['Department']==department]
    if pdNumber:
        dfDemands = dfDemands[dfDemands['id'] == int(pdNumber)]
    if statusFilter:
        match statusFilter:
            case 'OnApp':
                dfDemands = dfDemands[dfDemands['Approval'].isna()]
            case 'OnPO':
                dfDemands = dfDemands[(dfDemands['Approval'].astype(bool) == True) & (dfDemands['PONumber'].isna())]
            case 'Rej':
                dfDemands['Temp'] = dfDemands['Approval'].map(lambda x: 'True' if x is None else x)
                dfDemands = dfDemands[dfDemands['Temp'].astype(bool) == False]
                dfDemands.drop(inplace=True, columns=['Temp'])
            case 'Close':  
                dfDemands['Temp'] = dfDemands['Approval'].map(lambda x: 'True' if x is None else x)
                dfTemp1 = dfDemands[dfDemands['Temp'].astype(bool) == False]
                dfDemands.drop(inplace=True, columns=['Temp'])

                dfTemp2 = dfDemands[dfDemands['Approval'].astype(bool)]
                dfTemp2 = dfTemp2[~dfTemp2['PONumber'].isna()]

                dfDemands = pd.concat([dfTemp1, dfTemp2])
                del dfTemp1, dfTemp2
            case _:
                raise ValueError('Invalid Input')
    if dfDemands.empty:
        return []

    #Give verbose name to the id column
    dfDemands.rename(inplace=True, columns={'id':'PDNumber'})

    dfDemands = pd.merge(left=dfDemands, right=dfInventories, left_on='PDNumber', right_on='PDNumber', how='left')
    del dfInventories

    dfDemands = pd.merge(left=dfDemands, right=dfInventoryCards, left_on='Inventory', right_on='Code', how='left')
    dfDemands.drop(inplace=True, columns=['Inventory','Code'])
    del dfInventoryCards

    #Concate rows who have same Inventory Name in common
    dfDemands = dfDemands.groupby('PDNumber').agg({
        'DemandDate': 'first',
        'Department': 'first',
        'Demandee': 'first',
        'Approval': 'first',
        'PONumber': 'first',
        'Name': concatenateValues,
    }).reset_index()

    map = {True: 'Approved', False: 'Rejected', None: 'Pending'}
    dfDemands['Approval'] = dfDemands['Approval'].map(map)

    searchTerm = searchTerm.lower()
    mask = dfDemands.apply(lambda row: any(searchTerm in str(val).lower() for val in row.values), axis=1)
    dfDemands = dfDemands[mask]

    dfDemands = dfDemands.sort_values(by='PDNumber', ascending=False)
    return dfToListOfDicts(dfDemands)

def AddPurchaseDemand(
        dfDemand: pd.DataFrame,
        dfInventory: pd.DataFrame,
) -> int:
    '''Save a new PD'''
    demand = dfDemand.iloc[0].to_dict()
    del dfDemand

    if not demand['Department']:
        raise ValueError ('No department is Provided')
    
    if not demand['Demandee']:
        raise ValueError ('No name is Provided')
    
    dfInventory = dfInventory[dfInventory['InventoryCode'].str.len() > 0]
    dfInventory = dfInventory[dfInventory['Quantity'].str.len() > 0]
    dfInventory['Quantity'] = dfInventory['Quantity'].astype(float)
    dfInventory = dfInventory[dfInventory['Quantity'] > 0]
    
    if dfInventory.empty:
        raise ValueError ('Please select an inventory')
    
    demand['Department'] = models.Department.objects.get(Name=demand['Department'])
    for col in ['ApprovedBy','PONumber','Approval']:
        demand[col] = None
    
    try:
        demand = models.PurchaseDemand(**demand)
        demand.save()
    except Exception as e:
        raise ValueError(f"Error saving Demand: {e}")
    
    dfInventory['Currency'] = np.where(dfInventory['Currency'].str.len() == 0, 'PKR', dfInventory['Currency'])
    dfInventory['Forex'] = np.where(dfInventory['Forex'].str.len() == 0, 1, dfInventory['Forex'])

    try:
        dfInventory['Price'] = dfInventory['Price'].astype(float)
    except Exception as e:
        raise ValueError(e)

    dfInventory['Inventory'] = convertTexttoObject(models.Inventory, dfInventory['InventoryCode'], 'Code')
    dfInventory.drop(inplace=True, columns=['InventoryCode', 'InventoryName'])
    dfInventory.rename(inplace=True, columns={'VariantCode':'Variant'})

    dfInventory['Currency'] = convertTexttoObject(models.Currency, dfInventory['Currency'], 'Code')

    dfInventory['PDNumber'] = demand  
    
    for _, row in dfInventory.iterrows():
        newEntry = models.PDInventory(**row.to_dict())
        newEntry.save()

    return demand.id

def EditPurchaseDemand(
        purchaseDemand: models.PurchaseDemand,
        dfDemand: pd.DataFrame,
        dfPDInventory: pd.DataFrame
) -> None:
    if purchaseDemand.Approval != None:
        raise PermissionError('This demand is closed')
    
    demand = dfDemand.iloc[0].to_dict()
    del dfDemand

    if not demand['Department']:
        raise ValueError ('No department is Provided')
    
    if not demand['Demandee']:
        raise ValueError ('No name is Provided')
    
    dfPDInventory = dfPDInventory.replace('null', '')
    dfPDInventory = dfPDInventory[dfPDInventory['InventoryCode'].str.len() > 0]
    if dfPDInventory.empty:
        raise ValueError ('Please select an inventory')
    
    fields = ['id']
    previousInventores = models.PDInventory.objects.filter(PDNumber=purchaseDemand).values(*fields)
    if previousInventores:
        dfPrevioiusInventories = pd.DataFrame(previousInventores)
    else:
        dfPrevioiusInventories = pd.DataFrame(columns=fields)
    del previousInventores, fields
    
    demand['Department'] = models.Department.objects.get(Name=demand['Department'])
    demand.pop('id')
    demand.pop('DemandDate')

    for key, value in demand.items():
        setattr(purchaseDemand, key, value)
    del demand
    purchaseDemand.save()
    
    dfPDInventory['id'] = np.where(dfPDInventory['id'].str.len()==0, np.nan, dfPDInventory['id'])
    dfPDInventory['id'] = dfPDInventory['id'].astype('Int64')
    dfPDInventory.drop(inplace=True, columns=['InventoryName'])
    dfPDInventory.rename(inplace=True, columns={'InventoryCode':'Inventory','VariantCode':'Variant'})
    dfPDInventory = pd.merge(left=dfPDInventory, right=dfPrevioiusInventories, on='id', how='left')

    try:
        dfPDInventory[['Quantity','Price']] = dfPDInventory[['Quantity','Price']].astype(float)
    except Exception as e:
        raise ValueError(e)

    dfPDInventory['Currency'] = np.where(dfPDInventory['Currency'].str.len() == 0, 'PKR', dfPDInventory['Currency'])
    dfPDInventory['Forex'] = np.where(dfPDInventory['Forex'].str.len() == 0, 1, dfPDInventory['Forex'])

    dfPDInventory['Inventory'] = convertTexttoObject(models.Inventory, dfPDInventory['Inventory'], 'Code')

    dfPDInventory['Currency'] = convertTexttoObject(models.Currency, dfPDInventory['Currency'], 'Code')

    dfPDInventory['PDNumber'] = purchaseDemand 

    try:
        updateModelWithDF(models.PDInventory, dfPDInventory, dfPrevioiusInventories)
    except Exception as e:
        raise ValueError(e)

def ProcessDemandData(purchaseDemand: models.PurchaseDemand):
    demand = model_to_dict(purchaseDemand)

    demand['DemandDate'] = purchaseDemand.DemandDate

    if not demand['ApprovedBy']:
        demand['ApprovedBy'] = ''
    
    if not demand['PONumber']:
        demand['PONumber'] = ''

    fields = ['id','Inventory','Variant','Quantity','Price','Currency','Forex']
    pdInventories = models.PDInventory.objects.filter(PDNumber=purchaseDemand).values(*fields)
    if pdInventories:
        dfPDInventories = pd.DataFrame(pdInventories)
    else:
        dfPDInventories = pd.DataFrame(columns=fields)
    del pdInventories

    fields = ['Code', 'Name']
    inventories = models.Inventory.objects.filter(Code__in=dfPDInventories['Inventory'].to_list()).values(*fields)
    if inventories:
        dfInventories = pd.DataFrame(inventories)
    else:
        dfInventories = pd.DataFrame(columns=fields)
    del inventories, fields

    dfPDInventories = pd.merge(left=dfPDInventories, right=dfInventories, left_on='Inventory', right_on='Code', how='left')
    del dfInventories
    dfPDInventories.drop(inplace=True, columns=['Code'])
    dfPDInventories.rename(inplace=True, columns={'Name':'InventoryName'})

    return demand, dfToListOfDicts(dfPDInventories)

def GetDataForPDApproval (demand: models.PurchaseDemand):
    if not demand.Approval == None:
        raise ValueError ('This resource is closed')
    
    inventories = models.PDInventory.objects.filter(PDNumber=demand).values('Inventory','Variant','Quantity','Price','Currency')
    dfInventories = pd.DataFrame(inventories)
    del inventories

    inventoryCards = models.Inventory.objects.filter(Code__in = dfInventories['Inventory'].to_list())
    inventoryCards = inventoryCards.values('Code','Name','Unit')
    dfInventoryCards = pd.DataFrame(inventoryCards)
    del inventoryCards
    
    demandDict = {
        'Department': demand.Department.FullName,
        'Demandee': demand.Demandee,
    }
    del demand
    dfDemand = pd.DataFrame(demandDict, index=[0])
    del demandDict

    inventoriesForContext = dfInventories['Inventory'].to_list()

    dfInventories = pd.merge(left=dfInventories, right=dfInventoryCards, left_on='Inventory', right_on='Code', how='left')
    dfInventories.drop(inplace=True, columns=['Inventory','Code'])

    dfInventories['Value'] = dfInventories['Quantity'] * dfInventories['Price']

    dfInventories['Name'] = dfInventories['Name']+ ' ' + dfInventories['Variant']+ ' (' + dfInventories['Quantity'].astype(str) + ' '+dfInventories['Unit']+')'
    dfInventories.drop(inplace=True, columns=['Quantity','Price','Variant','Unit'])

    dfInventories = dfInventories.groupby(lambda x: 'all').agg({
        'Name': concatenateValues,
        'Currency': 'first',
        'Value': 'sum',
    }).reset_index()

    dfInventories['Value'] = dfInventories['Currency']+'. '+dfInventories['Value'].astype(str)+'/-'
    dfInventories.drop(inplace=True, columns=['Currency'])
    
    dfDemand['Details'] = dfInventories['Name'][0]
    dfDemand['Value'] = dfInventories['Value'][0]

    data = dfDemand.iloc[0].to_dict()

    data['Description'] = f"Request by {data['Demandee']} from {data['Department']} for {data['Details']} with value of {data['Value']}"

    context = getContextForPDApproval(inventoriesForContext)

    return data, context

def ApprovePD (request: HttpRequest, demand: models.PurchaseDemand, approval: str):
    if not canApprovePD(request.user):
        raise PermissionError('Not Allowed')

    if approval == 'None':
        return
    elif approval == 'true':
        approval = True
    else:
        approval = False

    demand.Approval = approval
    demand.ApprovedBy = request.user

    demand.save()
    return

def ConvertPDtoPO (demand: models.PurchaseDemand, dfDemand: pd.DataFrame, dfPOInventory: pd.DataFrame):
    '''
    Convert a PD to PO and return the PO Number
    '''

    try:
        supplier = dfDemand['Supplier'].iloc[0]
        supplier = models.Supplier.objects.get(Name=supplier)
    except:
        raise LookupError('Invalid Supplier')
        
    fields = ['id', 'Inventory', 'Variant','Quantity','Price', 'Currency', 'Forex']
    pdInventories = models.PDInventory.objects.filter(PDNumber=demand).values(*fields)
    if pdInventories:
        dfPDInventories = pd.DataFrame(pdInventories)
    else:
        dfPDInventories = pd.DataFrame(columns=fields)
    del pdInventories

    dfPOInventory[['id']] = dfPOInventory[['id']].astype(int)
    dfPOInventory[['Quantity', 'Price']] = dfPOInventory[['Quantity', 'Price']].astype('float64')
    #make sure the price and quatity is not more than approved values.
    dfApprovals = dfPDInventories[['id','Quantity','Price']]
    dfTemp = pd.merge(left=dfPOInventory, right=dfApprovals, on='id', suffixes=('Requested', 'Approved'))
    
    qtyMismatchFlag = dfTemp['QuantityRequested'] > dfTemp['QuantityApproved']
    if qtyMismatchFlag.any():
        raise PermissionError('PO Quantity is more than approved quantity')
    
    priceMismatchFlag = dfTemp['PriceRequested'] > dfTemp['PriceApproved']
    if priceMismatchFlag.any():
        raise PermissionError('PO Price is more than approved price')
    del dfTemp, qtyMismatchFlag, priceMismatchFlag, dfApprovals

    orderCard = {
        'DeliveryDate': demand.DemandDate,
        'Supplier': supplier,
        'Tax': 0.0
    }
    orderCard = models.PurchaseOrder (**orderCard)
    orderCard.save()

    dfPOInventory = pd.merge(left=dfPOInventory, right=dfPDInventories, on='id', how='left')
    del dfPDInventories
    dfPOInventory.drop(inplace=True, columns=['Quantity_y', 'Price_y'])
    dfPOInventory.rename(inplace=True, columns={'Quantity_x':'Quantity', 'Price_x': 'Price'})

    dfPOInventory['Inventory'] = convertTexttoObject(models.Inventory, dfPOInventory['Inventory'], 'Code')
    dfPOInventory['Currency'] = convertTexttoObject(models.Currency, dfPOInventory['Currency'], 'Code')
    dfPOInventory.drop(inplace=True, columns=['id'])

    dfPOInventory['PONumber'] = orderCard

    for _, row in dfPOInventory.iterrows():
        newEntry = models.POInventory(**row.to_dict())
        newEntry.PONumber = orderCard
        newEntry.save()

    demand.PONumber = orderCard
    demand.save()

    return orderCard.id