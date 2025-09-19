import pandas as pd
import numpy as np

from typing import Dict, Any

from .. import models
from core.services.generic_services import dfToListOfDicts

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

def GenenrateCode (jsonData: Dict[str, Any]):
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
    del part2s

    if part2:
        data['part2'] = part2
        try:
            part2 = models.InventoryCodePart2.objects.get(Code=part2, Part1=part1)
        except:
            part2 = models.InventoryCodePart2()
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