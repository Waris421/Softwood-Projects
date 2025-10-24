import pandas as pd
import numpy as np

from django.db.models import Q

from typing import Dict

from .. import models
from core.services.generic_services import dfToListOfDicts

def calculateReceivedFreeStock (dfReceivings: pd.DataFrame):
    dfReceiptWiseQty = dfReceivings.groupby(['InventoryCode', 'Variant', 'ReceiptNumber'])['TotalReceivedQty'].first().reset_index()
    
    dfReceiptsQty = dfReceiptWiseQty.groupby(['InventoryCode', 'Variant'])['TotalReceivedQty'].sum().reset_index(name='TotalReceivedInventoryQty')
    
    dfAllocatedQty = dfReceivings.groupby(['InventoryCode', 'Variant', 'Approval'])['AllocatedQty'].sum().reset_index(name='TotalAllocatedQty')
    
    dfResults = pd.merge(dfAllocatedQty, dfReceiptsQty, on=['InventoryCode', 'Variant'])

    dfResults['FreeQty'] = dfResults['TotalReceivedInventoryQty'] - dfResults['TotalAllocatedQty']
    dfResults.drop(inplace=True, columns=['TotalReceivedInventoryQty', 'TotalAllocatedQty'])

    return dfResults

def calculateIssueFreeStock(dfRecevings: pd.DataFrame, dfIssuances: pd.DataFrame):
    dfIssuances.rename(inplace=True, columns={'Inventory':'InventoryCode', 'Quantity':'AllocatedQty'})

    dfRecevings = dfRecevings.groupby(['WorkOrder', 'InventoryCode', 'Variant'])['AllocatedQty'].sum().reset_index()
    dfIssuances = dfIssuances.groupby(['WorkOrder', 'InventoryCode', 'Variant'])['AllocatedQty'].sum().reset_index()

    dfResults = pd.merge(left=dfRecevings, right=dfIssuances, on=['WorkOrder', 'InventoryCode', 'Variant'], how='right', suffixes=('_received', '_issued'))
    dfResults.fillna(0, inplace=True)

    dfResults['FreeQty'] = dfResults['AllocatedQty_received'] - dfResults['AllocatedQty_issued']

    dfResults.drop(inplace=True, columns=['AllocatedQty_received', 'AllocatedQty_issued', 'WorkOrder'])

    return dfResults

def getApprovalStatus(row: pd.Index):
    if row['Approval'] == True:
        return 'Approved'
    
    if pd.isna(row['QualityComments']):
        return 'Pending'

    return f"Rejected - {row['QualityComments']}"

def GetInventories (group: str, stockFilter: str):
    if group:
        inventories = models.Inventory.objects.filter(Group=group)
    else:
        inventories = models.Inventory.objects.all()
    inventories = inventories.filter(InUse=True).values('Code','Name','Group','Unit','InUse')
    
    if inventories:
        dfInventory = pd.DataFrame(inventories)
    else:
        dfInventory = pd.DataFrame(columns=['Code','Name','Group','Unit','InUse'])
    del inventories

    receiptInventories = models.RecInventory.objects.filter(InventoryCode__in=dfInventory['Code'].to_list())
    receiptInventories = receiptInventories.values('InventoryCode','Quantity')
    if receiptInventories:
        dfReceiptInventories = pd.DataFrame(receiptInventories)
    else:
        dfReceiptInventories = pd.DataFrame(columns=['InventoryCode','Quantity'])
    del receiptInventories

    issuanceInventories = models.IssueInventory.objects.filter(Inventory__in=dfInventory['Code'].to_list())
    issuanceInventories = issuanceInventories.values('Inventory','Quantity')
    if issuanceInventories:
        dfIssuanceInventories = pd.DataFrame(issuanceInventories)
    else:
        dfIssuanceInventories = pd.DataFrame(columns=['Inventory','Quantity'])
    del issuanceInventories

    dfReceiptInventories = dfReceiptInventories.groupby('InventoryCode')['Quantity'].sum().reset_index()

    dfInventory = pd.merge(left=dfInventory, right=dfReceiptInventories, left_on='Code', right_on='InventoryCode', how='left')
    del dfReceiptInventories
    dfInventory.drop(inplace=True, columns=['InventoryCode'])
    dfInventory.rename(inplace=True, columns={'Quantity':'Received'})

    dfIssuanceInventories.groupby('Inventory')['Quantity'].sum().reset_index()

    dfInventory = pd.merge(left=dfInventory, right=dfIssuanceInventories, left_on='Code', right_on='Inventory', how='left')
    del dfIssuanceInventories
    dfInventory.drop(inplace=True, columns=['Inventory'])
    dfInventory.rename(inplace=True, columns={'Quantity':'Issued'})

    dfInventory['StockLevel'] = dfInventory['Received'] - dfInventory['Issued']
    dfInventory.drop(inplace=True, columns=['Received','Issued'])
    dfInventory['StockLevel'] = np.where(dfInventory['StockLevel'].isna(), 0, dfInventory['StockLevel'])

    #TODO: Also make data for free stock quantity
    
    if stockFilter == 'InStock':
        dfInventory = dfInventory[dfInventory['StockLevel'] > 0]

    if dfInventory.empty:
        return []
   
    dfInventory = dfInventory.sort_values (by='Code')
    dfInventory = dfInventory.sort_values (by='Group')
    
    return dfToListOfDicts(dfInventory)

def AddInventory (data: Dict[str, str]):
    '''
    Creates a new inventory card based on the provided data in dataframe.
    '''
    code = data['Code']

    if '/' in code:
        raise ValueError('No Slashes are allowed in Code')

    try:
        models.Inventory.objects.get(Code=code)
        raise NameError('Inventory Code already exists')
    except:
        pass

    data['Unit'] = models.Unit.objects.get(Name=data['Unit'])
    data['Currency'] = models.Currency.objects.get(Code=data['Currency'])

    inventory = models.Inventory(**data)
    del data
    inventory.save()
    return inventory.Code

def EditInventory (
        data: Dict[str, str],
        inventory: models.Inventory
):
    '''
    To update the given inventory card based on the provided dataframe.
    '''
    data['Unit'] = models.Unit.objects.get(Name=data['Unit'])
    data['Currency'] = models.Currency.objects.get(Code=data['Currency'])

    inventory = models.Inventory(**data)
    inventory.save()

def getInventoryCardDropDowns ():
    groups = models.InvGroups
    groups = [{'value': item[0], 'text': item[1]} for item in groups]
    
    unitTypes = models.UnitGroup.objects.all().values('Name')
    temp = []
    for item in unitTypes:
        temp.append({'value':item['Name'],'text':item['Name'],})
    unitTypes = temp
    del temp

    auditReq = [
        {'value': True, 'text': 'Yes'},
        {'value': False, 'text': 'No'},
    ]

    inUse = [
        {'value': True, 'text': 'Yes'},
        {'value': False, 'text': 'No'},
    ]

    currencies = models.Currency.objects.all().values('Code','Name')
    temp = []
    for item in currencies:
        temp.append({'value':item['Code'],'text':item['Name'],})
    currencies = temp
    del temp

    codeP1 = models.InventoryCodePart1.objects.all().values('Code','Name')
    temp = []
    for item in codeP1:
        temp.append({'value':item['Code'],'text':item['Name'],})
    codeP1 = temp
    del temp

    return groups, unitTypes, auditReq, inUse, currencies,  codeP1

def GenenrateCode (jsonData: Dict[str, str]):
    part1 = jsonData['part_0']
    part2 = jsonData['part_1']
    part3 = jsonData['part_2']

    if not part1:
        raise ValueError('Part 1 of the code is required')
    
    data = {}
    
    part2s = models.InventoryCodePart2.objects.filter(Part1=part1).values('Code','Name')
    temp = []
    for item in part2s:
        temp.append({'value':item['Code'],'text':item['Name'],})
    part2s = temp
    del temp

    data['part2s'] = part2s

    if not part2:
        try:
            part2 = part2s[0]['value']
        except:
            part2 = None

    if part2:
        data['part2'] = part2
        try:
            part2 = models.InventoryCodePart2.objects.get(Code=part2, Part1=part1)
        except:
            part2 = models.InventoryCodePart2.objects.filter(Part1=part1).first()
        part3s = models.InventoryCodePart3.objects.filter(Part2=part2).values('Code','Name')
        temp = []
        for item in part3s:
            temp.append({'value':item['Code'],'text':item['Name'],})
        part3s = temp
        del temp
        data['part3s'] = part3s
    
    if part3:
        data['part3'] = part3

    return data

def GetFreeStockQuantity(type: str, minStockLvl: str|None, approvalStr: str):
    filters = Q(InventoryCode__Group=type)

    if approvalStr:
        approval = True if approvalStr == 'true' else False
        filters &= Q(Approval=approval)
    
    fields = ['id', 'ReceiptNumber', 'InventoryCode', 'Variant', 'Quantity', 'Approval']
    receivedInventories = models.RecInventory.objects.filter(filters).values(*fields)
    dfRecInventories = pd.DataFrame(receivedInventories) if receivedInventories else pd.DataFrame(columns=fields)
    del receivedInventories

    fields = ['RecInvId','WorkOrder', 'Quantity']
    receiptAllocations = models.RecAllocation.objects.filter(RecInvId__in=dfRecInventories['id'].to_list()).values(*fields)
    dfReceiptAllocations = pd.DataFrame(receiptAllocations) if receiptAllocations else pd.DataFrame(columns=fields)
    del receiptAllocations
    
    fields = ['id', 'Inventory', 'Variant']
    issueInventory = models.IssueInventory.objects.filter(Inventory__Group=type).values(*fields)
    dfIssueInventory = pd.DataFrame(issueInventory) if issueInventory else pd.DataFrame(columns=fields)
    del issueInventory

    fields = ['IssueInventory', 'WorkOrder', 'Quantity']
    issueAllocation = models.IssueAllocation.objects.filter(IssueInventory__in=dfIssueInventory['id'].to_list()).values(*fields)
    dfIssueAllocaiton = pd.DataFrame(issueAllocation) if issueAllocation else pd.DataFrame(columns=fields)
    del issueAllocation
    
    dfRecInventories = pd.merge(left=dfRecInventories, right=dfReceiptAllocations, left_on='id', right_on='RecInvId', how='left')
    del dfReceiptAllocations
    dfRecInventories.drop(inplace=True, columns=['id', 'RecInvId'])
    dfRecInventories.rename(inplace=True, columns={'Quantity_x': 'TotalReceivedQty', 'Quantity_y': 'AllocatedQty'})
    
    dfIssueInventory = pd.merge(left=dfIssueInventory, right=dfIssueAllocaiton, left_on='id', right_on='IssueInventory', how='left')
    del dfIssueAllocaiton
    dfIssueInventory.drop(inplace=True, columns=['id', 'IssueInventory'])

    dfFreeAtReceipts = calculateReceivedFreeStock(dfRecInventories[['ReceiptNumber', 'InventoryCode', 'Variant', 'TotalReceivedQty', 'AllocatedQty', 'Approval']])
    dfFreeAtIssuance = calculateIssueFreeStock(dfRecInventories[['InventoryCode', 'Variant', 'WorkOrder', 'AllocatedQty']], dfIssueInventory)
    del dfRecInventories, dfIssueInventory

    dfResults = pd.merge(left=dfFreeAtReceipts, right=dfFreeAtIssuance, on=['InventoryCode', 'Variant'], how='outer', suffixes=('_received', '_issued'))
    del dfFreeAtReceipts, dfFreeAtIssuance

    dfResults.fillna(0, inplace=True)

    dfResults['FreeQty'] = dfResults['FreeQty_received'] + dfResults['FreeQty_issued']
    if not dfResults.empty:
        dfResults['FreeQty'] = dfResults['FreeQty'].round(2)
    dfResults.drop(inplace=True, columns=['FreeQty_received', 'FreeQty_issued'])

    if minStockLvl:
        qtyThreshold = int(minStockLvl)
        qtyThreshold = max(qtyThreshold, 1)
    else:
        qtyThreshold = 1
    dfResults = dfResults[dfResults['FreeQty'] >= qtyThreshold]

    fields = ['Code', 'Name', 'Unit']
    inventories = models.Inventory.objects.filter(Code__in=dfResults['InventoryCode'].to_list()).values(*fields)
    dfInventories = pd.DataFrame(inventories) if inventories else pd.DataFrame(columns=fields)
    del inventories, fields

    dfResults = pd.merge(left=dfResults, right=dfInventories, left_on='InventoryCode', right_on='Code', how='left')
    del dfInventories

    dfResults.drop(inplace=True, columns=['Code'])

    dfResults.sort_values(inplace=True, by='FreeQty', ascending=False)

    return dfToListOfDicts(dfResults)

def GetFreeStockHistory(inventory: models.Inventory):
    fields = ['ReceiptNumber', 'id', 'InventoryCode', 'Variant', 'Quantity', 'Approval', 'QualityComments']
    recInventories = models.RecInventory.objects.filter(InventoryCode=inventory).values(*fields)
    dfRecInventories = pd.DataFrame(recInventories) if recInventories else pd.DataFrame(columns=fields)
    del recInventories

    fields = ['id', 'ReceiptDate', 'Supplier', 'PONumber']
    invReceipts = models.InventoryReciept.objects.filter(id__in=dfRecInventories['ReceiptNumber'].to_list()).values(*fields)
    dfInvReceipts = pd.DataFrame(invReceipts) if invReceipts else pd.DataFrame(columns=fields)
    del invReceipts

    fields = ['PONumber', 'Inventory', 'Variant', 'Price', 'Quantity']
    purchaseOrders = models.PurchaseOrder.objects.filter(id__in=dfInvReceipts['PONumber'].to_list())
    poInventories = models.POInventory.objects.filter(PONumber__in=purchaseOrders).values(*fields)
    dfPOInventories = pd.DataFrame(poInventories) if poInventories else pd.DataFrame(columns=fields)
    del purchaseOrders, poInventories
    
    dfRecInventories['ApprovalStatus'] = dfRecInventories.apply(getApprovalStatus, axis=1)
    dfRecInventories.drop(inplace=True, columns=['Approval', 'QualityComments'])

    dfRecInventories = pd.merge(left=dfRecInventories, right=dfInvReceipts, left_on='ReceiptNumber', right_on='id', how='left')
    del dfInvReceipts
    dfRecInventories.drop(inplace=True, columns=['ReceiptNumber', 'id_y'])
    dfRecInventories.rename(inplace=True, columns={'id_x': 'RecInvId'})

    #Group the same inventories within a PO together and get their qty weighted average price
    dfPOInventories['Value'] = dfPOInventories['Price'] * dfPOInventories['Quantity']
    dfPOInventories = dfPOInventories.groupby(by=['PONumber','Inventory','Variant']).agg(
        Quantity = ('Quantity', 'sum'),
        Value = ('Value', 'sum'),
    ).reset_index()
    dfPOInventories['Price'] = dfPOInventories['Value'] / dfPOInventories['Quantity']
    dfPOInventories.drop(inplace=True, columns=['Value', 'Quantity'])

    dfRecInventories = pd.merge(left=dfRecInventories,right=dfPOInventories,
                                left_on=['PONumber', 'InventoryCode', 'Variant'],
                                right_on=['PONumber', 'Inventory', 'Variant'], how='left')
    del dfPOInventories
    dfRecInventories.drop(inplace=True, columns=['Inventory'])

    #Set an estimated price of nearby deliveries for cases where the price is zero
    dfRecInventories['ReceiptDate'] = pd.to_datetime(dfRecInventories['ReceiptDate'])
    dfRecInventories.sort_values(by='ReceiptDate', inplace=True)

    zeroPriceFlag = (dfRecInventories['Price'] <= 0)

    dfRecInventories.loc[zeroPriceFlag, 'Price'] = np.nan
    dfRecInventories.set_index(keys='ReceiptDate', inplace=True)

    # Apply Time-Weighted Interpolation for na values. Doesn't work on first and last value
    dfRecInventories['Price'] = dfRecInventories['Price'].interpolate(method='time')
    dfRecInventories.reset_index(inplace=True)
    #If the first entry is without price, take the 2nd value
    dfRecInventories['Price'] = dfRecInventories['Price'].bfill()
    # If the last entry is without price, take the 2nd last value
    dfRecInventories['Price'] = dfRecInventories['Price'].ffill()

    print(dfRecInventories)

    return []