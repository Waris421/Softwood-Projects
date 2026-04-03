import pandas as pd
import numpy as np

from django.db.models import Q

from typing import Dict, List

from .. import models
from core.services.generic_services import dfToListOfDicts, formatCurrencyAmount, convertStrToDateTime, roundFloatCols
from core.constants.generic import TODAY

def calculateReceivedFreeStockForAllInvs (dfReceivings: pd.DataFrame):
    dfReceiptWiseQty = dfReceivings.groupby(['InventoryCode', 'Variant', 'ReceiptNumber'])['TotalReceivedQty'].first().reset_index()
    
    dfReceiptsQty = dfReceiptWiseQty.groupby(['InventoryCode', 'Variant'])['TotalReceivedQty'].sum().reset_index(name='TotalReceivedInventoryQty')
    
    dfAllocatedQty = dfReceivings.groupby(['InventoryCode', 'Variant', 'Approval'])['AllocatedQty'].sum().reset_index(name='TotalAllocatedQty')

    dfResults = pd.merge(dfAllocatedQty, dfReceiptsQty, on=['InventoryCode', 'Variant'])

    dfResults['FreeQty'] = dfResults['TotalReceivedInventoryQty'] - dfResults['TotalAllocatedQty']
    dfResults.drop(inplace=True, columns=['TotalReceivedInventoryQty', 'TotalAllocatedQty'])

    dfResults = dfResults[dfResults['FreeQty']>0]
    
    return dfResults

def calculateReceiptFreeStockForOneInv(dfReceivings: pd.DataFrame):
    dfReceiptWiseQty = dfReceivings.groupby(['ReceiptNumber'])['ReceivedQty'].first().reset_index()

    dfAllocatedQty = dfReceivings.groupby(['ReceiptNumber'])['AllocatedQty'].sum().reset_index(name='AllocatedQty')    

    dfResults = pd.merge(dfAllocatedQty, dfReceiptWiseQty, on='ReceiptNumber')

    dfResults['FreeQty'] = dfResults['ReceivedQty'] - dfResults['AllocatedQty']
    dfResults.drop(inplace=True, columns=['ReceivedQty', 'AllocatedQty'])

    dfResults = dfResults[dfResults['FreeQty']>0]
    
    return dfResults

def calculateIssueFreeStockforAllInvs(dfRecevings: pd.DataFrame, dfIssuances: pd.DataFrame):
    dfIssuances.rename(inplace=True, columns={'Inventory':'InventoryCode', 'Quantity':'AllocatedQty'})

    dfRecevings = dfRecevings.groupby(['WorkOrder', 'InventoryCode', 'Variant'])['AllocatedQty'].sum().reset_index()
    dfIssuances = dfIssuances.groupby(['WorkOrder', 'InventoryCode', 'Variant'])['AllocatedQty'].sum().reset_index()

    dfResults = pd.merge(left=dfRecevings, right=dfIssuances, on=['WorkOrder', 'InventoryCode', 'Variant'], how='right', suffixes=('_received', '_issued'))
    dfResults.fillna(0, inplace=True)

    dfResults['FreeQty'] = dfResults['AllocatedQty_received'] - dfResults['AllocatedQty_issued']

    dfResults.drop(inplace=True, columns=['AllocatedQty_received', 'AllocatedQty_issued', 'WorkOrder'])

    dfResults = dfResults.groupby(['InventoryCode', 'Variant'])['FreeQty'].sum().reset_index()

    return dfResults

def calculateIssueFreeStockForOneInv(dfReceivings: pd.DataFrame, dfIssuances: pd.DataFrame):
    dfReceivings = dfReceivings.groupby(['WorkOrder', 'ReceiptNumber'])['AllocatedQty'].sum().reset_index()
    dfIssuances = dfIssuances.groupby(['Issuance', 'WorkOrder'])['AllocatedQty'].sum().reset_index()

    dfResults = pd.merge(left=dfReceivings, right=dfIssuances, on=['WorkOrder'], how='right', suffixes=('_received', '_issued'))
    dfResults.fillna(0, inplace=True)

    dfResults['FreeQty'] = dfResults['AllocatedQty_received'] - dfResults['AllocatedQty_issued']

    dfResults.drop(inplace=True, columns=['AllocatedQty_received', 'AllocatedQty_issued', 'WorkOrder'])

    dfResults = dfResults.groupby(['ReceiptNumber'])['FreeQty'].sum().reset_index()
    
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

    dfFreeAtReceipts = calculateReceivedFreeStockForAllInvs(dfRecInventories[['ReceiptNumber', 'InventoryCode', 'Variant', 'TotalReceivedQty', 'AllocatedQty', 'Approval']])
    dfFreeAtIssuance = calculateIssueFreeStockforAllInvs(dfRecInventories[['InventoryCode', 'Variant', 'WorkOrder', 'AllocatedQty']], dfIssueInventory)
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

def GetFreeStockHistory(inventory: models.Inventory, variant: str):
    fields = ['ReceiptNumber', 'id', 'Quantity', 'Approval', 'QualityComments']
    recInventories = models.RecInventory.objects.filter(InventoryCode=inventory, Variant=variant).values(*fields)
    dfRecInventories = pd.DataFrame(recInventories) if recInventories else pd.DataFrame(columns=fields)
    del recInventories

    fields = ['id', 'ReceiptDate', 'Supplier', 'PONumber']
    invReceipts = models.InventoryReciept.objects.filter(id__in=dfRecInventories['ReceiptNumber'].to_list()).values(*fields)
    dfInvReceipts = pd.DataFrame(invReceipts) if invReceipts else pd.DataFrame(columns=fields)
    del invReceipts

    fields = ['RecInvId', 'Quantity', 'WorkOrder']
    recAllocations = models.RecAllocation.objects.filter(RecInvId__in=dfRecInventories['id']).values(*fields)
    dfRecAllocations = pd.DataFrame(recAllocations) if recAllocations else pd.DataFrame(columns=fields)
    del recAllocations

    fields = ['PONumber', 'Price', 'Quantity']
    purchaseOrders = models.PurchaseOrder.objects.filter(id__in=dfInvReceipts['PONumber'].to_list())
    poInventories = models.POInventory.objects.filter(PONumber__in=purchaseOrders).values(*fields)
    dfPOInventories = pd.DataFrame(poInventories) if poInventories else pd.DataFrame(columns=fields)
    del purchaseOrders, poInventories

    fields = ['Issuance', 'id']
    issueInventories = models.IssueInventory.objects.filter(Inventory=inventory, Variant=variant).values(*fields)
    dfIssueInventries = pd.DataFrame(issueInventories) if issueInventories else pd.DataFrame(columns=fields)
    del issueInventories

    fields = ['IssueInventory', 'Quantity', 'WorkOrder']
    issueAllocations = models.IssueAllocation.objects.filter(IssueInventory__in=dfIssueInventries['id'].to_list()).values(*fields)
    dfIssueAllocations = pd.DataFrame(issueAllocations) if issueAllocations else pd.DataFrame(columns=fields)
    del issueAllocations
    
    dfRecInventories['ApprovalStatus'] = dfRecInventories.apply(getApprovalStatus, axis=1)
    dfRecInventories.drop(inplace=True, columns=['Approval', 'QualityComments'])

    dfRecInventories = pd.merge(left=dfRecInventories, right=dfInvReceipts, left_on='ReceiptNumber', right_on='id', how='left')
    del dfInvReceipts
    dfRecInventories.drop(inplace=True, columns=['id_y'])
    dfRecInventories.rename(inplace=True, columns={'id_x': 'RecInvId'})

    #Group the same inventories within a PO together and get their qty weighted average price
    dfPOInventories['Value'] = dfPOInventories['Price'] * dfPOInventories['Quantity']
    dfPOInventories = dfPOInventories.groupby(by=['PONumber']).agg(
        Quantity = ('Quantity', 'sum'),
        Value = ('Value', 'sum'),
    ).reset_index()
    dfPOInventories['Price'] = dfPOInventories['Value'] / dfPOInventories['Quantity']
    dfPOInventories.drop(inplace=True, columns=['Value', 'Quantity'])

    dfRecInventories = pd.merge(left=dfRecInventories,right=dfPOInventories, on='PONumber', how='left')
    del dfPOInventories

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

    dfRecAllocations = dfRecAllocations.groupby(['RecInvId', 'WorkOrder'])['Quantity'].sum().reset_index()
    dfRecInventories = pd.merge(left=dfRecInventories, right=dfRecAllocations, on='RecInvId', how='left')
    del dfRecAllocations
    dfRecInventories.drop(inplace=True, columns=['RecInvId'])
    dfRecInventories.rename(inplace=True, columns={'Quantity_x':'ReceivedQty','Quantity_y':'AllocatedQty'})
    if not dfRecInventories.empty:
        dfRecInventories['AllocatedQty'] = (dfRecInventories['AllocatedQty'].fillna(0)).round(0)

    dfIssueAllocations = dfIssueAllocations.groupby(['IssueInventory', 'WorkOrder'])['Quantity'].sum().reset_index()
    dfIssueInventries.rename(inplace=True, columns={'id': 'IssueInventory'})
    dfIssueInventries = pd.merge(left=dfIssueInventries, right=dfIssueAllocations, on='IssueInventory', how='left')
    del dfIssueAllocations
    dfIssueInventries.drop(inplace=True, columns=['IssueInventory'])
    dfIssueInventries.rename(inplace=True, columns={'Quantity':'AllocatedQty'})
    if not dfIssueInventries.empty:
        dfIssueInventries['AllocatedQty'] = (dfIssueInventries['AllocatedQty'].fillna(0)).round(0)

    dfFreeAtReceipt = calculateReceiptFreeStockForOneInv(dfRecInventories)
    dfFreeAtIssuance = calculateIssueFreeStockForOneInv(dfRecInventories, dfIssueInventries)

    dfResults = pd.merge(left=dfFreeAtReceipt, right=dfFreeAtIssuance, on='ReceiptNumber', how='outer',
                         suffixes=['_received', '_issued'])
    return dfToListOfDicts(dfFreeAtReceipt)

def GetUnorderedInventories(
        merchandiser:str, customer:str, type:str, startDateStr:str|None, endDateStr:str|None, inventory: str
):
    orderFilters = Q()
    styleFilters = Q()
    if merchandiser:
        orderFilters &= Q(Merchandiser=merchandiser)
    
    if customer:
        orderFilters &= Q(Customer=customer)
    
    if startDateStr:
        startDate = convertStrToDateTime(startDateStr, '%Y-%m-%d')
        orderFilters &= Q(DeliveryDate__gte=startDate)
    
    if endDateStr:
        endDate = convertStrToDateTime(endDateStr, '%Y-%m-%d')
        orderFilters &= Q(DeliveryDate__lte=endDate)
    
    if type:
        styleFilters &= Q(Type=type)

    fields = ['OrderNumber', 'StyleCode', 'Customer']
    workOrders = models.WorkOrder.objects.filter(orderFilters).values(*fields)
    dfWorkOrders = pd.DataFrame(workOrders) if workOrders else pd.DataFrame(columns=fields)
    del workOrders, orderFilters

    styleFilters &= Q(Style__in=dfWorkOrders['StyleCode'].to_list())
    
    fields = ['InventoryCode']
    invCodes = list(models.StyleConsumption.objects.filter(styleFilters).values_list(*fields))
    reqFilter = Q(OrderNumber__in=dfWorkOrders['OrderNumber'].to_list()) & Q(InventoryCode__in=invCodes)
    
    fields = ['OrderNumber', 'InventoryCode', 'Variant', 'Quantity']
    invRequirement = models.InvRequirement.objects.filter(reqFilter).values(*fields)
    dfInvRequirement = pd.DataFrame(invRequirement) if invRequirement else pd.DataFrame(columns=fields)
    del invRequirement, reqFilter, invCodes

    fields = ['POInvId', 'WorkOrder', 'Quantity']
    poAllocations = models.POAllocation.objects.filter(WorkOrder__in=dfWorkOrders['OrderNumber'].to_list()).values(*fields)
    dfPOAllocations = pd.DataFrame(poAllocations) if poAllocations else pd.DataFrame(columns=fields)
    del poAllocations

    poInvFilter = Q(id__in=dfPOAllocations['POInvId'].to_list())
    fields = ['id', 'Inventory', 'Variant']
    poInventories = models.POInventory.objects.filter(poInvFilter).values(*fields)
    dfPOInventories = pd.DataFrame(poInventories) if poInventories else pd.DataFrame(columns=fields)
    del poInventories, poInvFilter, fields
    
    dfInvRequirement = pd.merge(left=dfWorkOrders, right=dfInvRequirement, on=['OrderNumber'], how='left')
    del dfWorkOrders
    dfInvRequirement.rename(inplace=True, columns={'OrderNumber':'WorkOrder', 'InventoryCode':'Inventory', 'Quantity':'RequiredQty'})
    
    dfInvOrdered = pd.merge(left=dfPOInventories, right=dfPOAllocations, left_on='id', right_on='POInvId', how='right')
    del dfPOInventories, dfPOAllocations
    dfInvOrdered.drop(inplace=True, columns=['id', 'POInvId'])
    dfInvOrdered.rename(inplace=True, columns={'Quantity': 'OrderedQty'})
    
    dfInvRequirement = pd.merge(left=dfInvRequirement, right=dfInvOrdered, on=['WorkOrder', 'Inventory', 'Variant'], how='left')
    del dfInvOrdered

def GetInventoryStockStatus():
    twoYearsAgo = TODAY.replace(year=TODAY.year - 2)
    filters = Q(ReceiptNumber__ReceiptDate__gte=twoYearsAgo)
    fields = ['id', 'InventoryCode', 'InventoryCode__Name', 'InventoryCode__Group', 'InventoryCode__Unit', 'Variant', 'Quantity', 'ReceiptNumber__Invoice', 'ReceiptNumber__PONumber', 'ReceiptNumber__ReceiptDate']
    receiptInventories = models.RecInventory.objects.filter(filters).values(*fields)
    dfReceiptInventories = pd.DataFrame(receiptInventories) if receiptInventories else pd.DataFrame(columns=fields)
    del receiptInventories
    dfReceiptInventories.rename(inplace=True, columns={
        'InventoryCode__Name': 'InventoryName',
        'ReceiptNumber__Invoice': 'InvoiceNumber',
        'ReceiptNumber__PONumber': 'PONumber',
        'ReceiptNumber__ReceiptDate': 'ReceiptDate',
        'InventoryCode__Group':'Group',
        'InventoryCode__Unit': 'Unit',
    })

    #TODO: remove this line
    #dfReceiptInventories = dfReceiptInventories[dfReceiptInventories['Group']=='FABRIC'].sort_values(by='Quantity', ascending=False).reset_index().head(100).reset_index() 
    
    filters = Q(RecInvId__in=dfReceiptInventories['id'].to_list())
    fields = ['RecInvId', 'WorkOrder', 'WorkOrder__StyleCode']
    receiptAllocations = models.RecAllocation.objects.filter(filters).values(*fields)
    dfReceiptAllocations = pd.DataFrame(receiptAllocations) if receiptAllocations else pd.DataFrame(columns=fields)
    del receiptAllocations
    dfReceiptAllocations.rename(inplace=True, columns={
        'RecInvId': 'id',
        'WorkOrder__StyleCode': 'StyleCode'
    })

    filters = Q(Issuance__IssuanceDate__gt=twoYearsAgo) & Q(Inventory__in=dfReceiptInventories['InventoryCode'].to_list())
    fields = ['id', 'Inventory', 'Variant', 'Quantity']
    issueInventories = models.IssueInventory.objects.filter(filters).values(*fields)
    dfIssueInventories = pd.DataFrame(issueInventories) if issueInventories else pd.DataFrame(columns=fields)
    del issueInventories
    dfIssueInventories.rename(inplace=True, columns={
        'Inventory': 'InventoryCode',
        'Quantity': 'IssueQty',
    })

    filters = Q(PONumber__in=dfReceiptInventories['PONumber'].to_list())
    fields = ['PONumber', 'Inventory', 'Variant', 'Quantity', 'Price', 'Forex', 'PONumber__Supplier']
    poInventories = models.POInventory.objects.filter(filters).values(*fields)
    dfPOInventories = pd.DataFrame(poInventories) if poInventories else pd.DataFrame(columns=fields)
    del poInventories, fields, filters
    dfPOInventories.rename(inplace=True, columns={
        'PONumber__Supplier': 'Supplier',
        'Inventory': 'InventoryCode',
    })

    def combineValues(dfSubset:pd.DataFrame, cols:List[str]):
        return dfSubset[cols].to_dict(orient='records')
    
    dfReceiptInventories = pd.merge(left=dfReceiptInventories, right=dfReceiptAllocations, on='id', how='left')
    del dfReceiptAllocations
    dfReceiptInventories.drop(inplace=True, columns=['id'])
    dfReceiptInventories['WorkOrder'] = dfReceiptInventories['WorkOrder'].astype('Int64').astype(str).replace('<NA>', '')
    dfReceiptInventories = dfReceiptInventories.groupby(['InventoryCode', 'InventoryName', 'Group', 'Unit', 'Variant', 'InvoiceNumber', 'PONumber', 'ReceiptDate']).apply(lambda x: pd.Series({
        'Quantity': x['Quantity'].iloc[0],
        'WorkOrders': x['WorkOrder'].unique().tolist(),
        'Styles': x['StyleCode'].unique().tolist(),
    })).reset_index()

    #Get the quantity weighted price of each inventory in a po
    dfPOInventories['TotalCost'] = dfPOInventories['Quantity'] * dfPOInventories['Price'] * dfPOInventories['Forex']
    dfPOInventories = dfPOInventories.groupby(['PONumber', 'InventoryCode', 'Variant']).agg({
        'Quantity': 'sum',
        'TotalCost': 'sum',
        'Supplier': 'first'
    }).reset_index()

    dfPOInventories['Price'] = np.where(
        dfPOInventories['Quantity'] > 0, 
        dfPOInventories['TotalCost'] / dfPOInventories['Quantity'], 
        0
    )
    dfPOInventories.drop(inplace=True, columns=['TotalCost', 'Quantity'])

    dfReceiptInventories = pd.merge(left=dfReceiptInventories, right=dfPOInventories, on=['PONumber', 'InventoryCode', 'Variant'], how='left')
    del dfPOInventories

    dfReceiptInventories['Value'] = dfReceiptInventories['Quantity'] * dfReceiptInventories['Price']
    dfReceiptInventories.drop(inplace=True, columns=['Price'])

    dfReceiptInventories = dfReceiptInventories.groupby(['InventoryCode','Variant']).apply(lambda x: pd.Series({
        'InventoryName': x['InventoryName'].iloc[0],
        'Group': x['Group'].iloc[0],
        'Unit': x['Unit'].iloc[0],
        'Quantity': x['Quantity'].sum(),
        'Value': x['Value'].sum(),
        'TransactionDetails': combineValues(x, ['InventoryName', 'ReceiptDate','InvoiceNumber', 'PONumber', 'Supplier', 'WorkOrders', 'Styles', 'Quantity'])
    })).reset_index()
    
    dfReceiptInventories['AveragePrice'] = np.where(
        dfReceiptInventories['Quantity'] > 0, 
        dfReceiptInventories['Value'] / dfReceiptInventories['Quantity'], 
        0
    )

    dfReceiptInventories.drop(inplace=True, columns=['Value'])
    
    dfIssueInventories = dfIssueInventories.groupby(['InventoryCode', 'Variant']).agg({
        'IssueQty': 'sum'
    }).reset_index()

    dfReceiptInventories = pd.merge(left=dfReceiptInventories, right=dfIssueInventories, on=['InventoryCode', 'Variant'], how='left')
    del dfIssueInventories

    dfReceiptInventories['Quantity'] = dfReceiptInventories['Quantity'] - dfReceiptInventories['IssueQty'].fillna(0)
    dfReceiptInventories['Value'] = dfReceiptInventories['Quantity'] * dfReceiptInventories['AveragePrice']
    dfReceiptInventories.drop(inplace=True, columns=['AveragePrice', 'IssueQty'])

    dfReceiptInventories = dfReceiptInventories[dfReceiptInventories['Quantity']>0]
    
    dfReceiptInventories = dfReceiptInventories.groupby('InventoryCode').apply(lambda x: pd.Series({
        'InventoryName': x['InventoryName'].iloc[0],
        'Group': x['Group'].iloc[0],
        'Unit': x['Unit'].iloc[0],
        'Balance': x['Quantity'].sum(),
        'Value': x['Value'].sum(),
        'VariantDetails': combineValues(x, ['Variant', 'Quantity']),
        'TransactionDetails': x['TransactionDetails'].iloc[0],
    })).reset_index()

    dfReceiptInventories['Group'] = dfReceiptInventories['Group'].str.lower().str.capitalize()

    return dfToListOfDicts(roundFloatCols(dfReceiptInventories))