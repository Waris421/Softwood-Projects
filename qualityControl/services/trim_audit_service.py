import pandas as pd
import numpy as np
import math
from datetime import date
from typing import Dict, Any, List

from apparelManagement import models as appModels
from .. import models
from core.services.generic_services import concatenateValues, convertTexttoObject, updateModelWithDF

pd.options.mode.chained_assignment = None
pd.set_option('display.max_columns', None)

SAMPLE_SIZE = 0.05

def combineAuditRows (row: pd.Series): 
    '''
    Combine rows of Variant, Quality, Name, AudityQuantity and RecInvId to one dict of same keys
    '''   
    finalList = []
    for i in range(len(row['Name'])):
        valuesDict = {
            'Variant': row['Variant'][i],
            'Quantity': row['Quantity'][i],
            'Name': row['Name'][i],
            'AuditQuantity': row['AuditQuantity'][i],
            'RecInvId': row['RecInvId'][i],
        }
        finalList.append(valuesDict)
    
    return finalList

def getCheckList ():
    '''
    Get audit checklist as list of dicts
    '''
    checkList = [
        'Color', 'Strength', 'Twist', 'Artwork', 'Meterial', 'Printing', 'Fray', 'Wash Trial', 'Tape color',
        'Metal color', 'Puller size', 'Width', 'Weight', 'Weave', 'Dimension', 'Pull Test', 'Nickle Test',
        'Barcode', 'Stickness', 'Length', 'Tipping', 'waeave', 'Craft Pasting', 'Quality', 'Drop test', 'Micron', 'Size'
    ]

    checkListOptions = [{}]
    for option in checkList:
        checkListOptions.append({'value':option, 'text': option})
    
    return checkListOptions

def SummariseRecInv (group: pd.Series):
    recInventory = group['RecInventory'].iloc[0]
    allApproved = group['Approval'].all()

    if not allApproved:
        # Filter for rows where Approval is False
        rejectedRows = group[~group['Approval']]
        # Concatenate 'CheckList: Comments'
        concatenatedString = rejectedRows.apply(
            lambda row: f"{row['CheckList']}: {row['Comments']}", axis=1
        ).str.cat(sep='; ') # You can choose your separator here (e.g., '; ')
    else:
        concatenatedString = None

    return pd.Series({
        'Approval': allApproved,
        'QualityComments': concatenatedString
    })

def updateApprovalForAudit(dfData: pd.DataFrame):
    '''
    Update the approval in inventory receipt, based on it's audit report
    '''
    
    summaryDf = pd.DataFrame(dfData.groupby('RecInventory').apply(SummariseRecInv).reset_index())

    for _, row in summaryDf.iterrows():
        recInventory = row['RecInventory']
        recInventory.Approval = row['Approval']
        recInventory.QualityComments = row['QualityComments']
        recInventory.save()

def GetAuditHistory (supplier: str, inventory: str, approval: bool, startDate: str, endDate: str):
    '''
    Get the data for all the audits, with the mentioned filters
    '''
    if not startDate:
        startDate = date(date.today().year, 1, 1)
    
    receipts = appModels.InventoryReciept.objects.filter(ReceiptDate__gte=startDate)
    if endDate:
        receipts = appModels.InventoryReciept.objects.filter(ReceiptDate__lte=endDate)
    if supplier:
        receipts = receipts.filter(Supplier=supplier)
    fields = ['id','ReceiptDate','Supplier']
    receipts = receipts.values(*fields)
    if receipts:
        dfReceipts = pd.DataFrame(receipts)
    else:
        dfReceipts = pd.DataFrame(columns=fields)
    del receipts, fields

    receiptInventories = appModels.RecInventory.objects.filter(ReceiptNumber__in=dfReceipts['id'].to_list())

    if approval is not None:
        receiptInventories = receiptInventories.filter(Approval=approval)

    if inventory:
        receiptInventories = receiptInventories.filter(InventoryCode=inventory)
    fields = ['id','ReceiptNumber','InventoryCode','Quantity','Approval','QualityComments']
    receiptInventories = receiptInventories.values(*fields)
    if receiptInventories:
        dfReceiptInventories = pd.DataFrame(receiptInventories)
    else:
        dfReceiptInventories = pd.DataFrame(columns=fields)
    del receiptInventories, fields

    fields = ['RecInventory']
    trimAudits = models.TrimAudit.objects.filter(RecInventory__in=dfReceiptInventories['id'].to_list()).values(*fields)
    if trimAudits:
        dfTrimAudits = pd.DataFrame(trimAudits)
    else:
        dfTrimAudits = pd.DataFrame(columns=fields)
    del trimAudits, fields

    fields = ['Code','Name']
    inventories = appModels.Inventory.objects.filter(Code__in=dfReceiptInventories['InventoryCode'].to_list()).values(*fields)
    if inventories:
        dfInventories = pd.DataFrame(inventories)
    else:
        dfInventories = pd.DataFrame(columns=fields)
    del inventories, fields

    dfTrimAudits = pd.merge(left=dfTrimAudits, right=dfReceiptInventories, left_on='RecInventory', right_on='id', how='left')
    del dfReceiptInventories
    dfTrimAudits.drop(inplace=True, columns=['id'])

    dfTrimAudits = pd.merge(left=dfTrimAudits, right=dfInventories, left_on='InventoryCode', right_on='Code', how='left')
    del dfInventories
    dfTrimAudits.drop(inplace=True, columns=['InventoryCode','Code'])
    
    dfTrimAudits = pd.merge(left=dfTrimAudits, right=dfReceipts, left_on='ReceiptNumber', right_on='id', how='left')
    del dfReceipts
    dfTrimAudits.drop(inplace=True, columns=['id'])
    
    dfTrimAudits = dfTrimAudits.groupby('RecInventory').agg({
        'ReceiptNumber': 'first',
        'Quantity': 'first',
        'Approval': 'first',
        'QualityComments': 'first',
        'Name': 'first',
        'ReceiptDate': 'first',
        'Supplier': 'first'
    }).reset_index()

    cols = [i for i in dfTrimAudits]
    data = [dict(zip(cols, i)) for i in dfTrimAudits.values]
    return data

def GetPendingAudits (workOrder: int):
    '''
    Get all inventories whose audits are not done yet. If order number is provided, then filter data based on that
    '''
    fields = ['id','ReceiptNumber','InventoryCode','Variant','Quantity']
    receiptInventores = appModels.RecInventory.objects.filter(Approval=False).filter(QualityComments = None).values(*fields)
    if receiptInventores:
        dfReceiptInventories = pd.DataFrame(receiptInventores)
    else:
        return []
    del receiptInventores

    fields = ['id','ReceiptDate','Supplier']
    receipts = appModels.InventoryReciept.objects.filter(id__in=dfReceiptInventories['ReceiptNumber'].to_list()).values(*fields)
    if receipts:
        dfReceipts = pd.DataFrame(receipts)
    else:
        dfReceipts = pd.DataFrame(columns=fields)
    del receipts

    fields = ['RecInvId','WorkOrder']
    receiptAllocations = appModels.RecAllocation.objects.filter(RecInvId__in=dfReceiptInventories['id'].to_list()).values(*fields)
    if receiptAllocations:
        dfReceiptAllocaitons = pd.DataFrame(receiptAllocations)
    else:
        dfReceiptAllocaitons = pd.DataFrame(columns=fields)
    del receiptAllocations

    fields = ['Code','Name','AuditReq']
    inventories = appModels.Inventory.objects.filter(Code__in=dfReceiptInventories['InventoryCode'].to_list()).values(*fields)
    if inventories:
        dfInventories = pd.DataFrame(inventories)
    else:
        dfInventories = pd.DataFrame(columns=fields)
    del inventories
    
    dfReceiptInventories = pd.merge(left=dfReceiptInventories, right=dfInventories, left_on='InventoryCode', right_on='Code', how='left')
    del dfInventories
    dfReceiptInventories.drop(inplace=True, columns=['InventoryCode','Code'])
    
    dfReceiptInventories = dfReceiptInventories[dfReceiptInventories['AuditReq']]
    dfReceiptInventories.drop(inplace=True, columns=['AuditReq'])
    
    dfReceiptInventories = pd.merge(left=dfReceiptInventories, right=dfReceiptAllocaitons, left_on='id', right_on='RecInvId', how='left')
    del dfReceiptAllocaitons
    dfReceiptInventories.drop(inplace=True, columns=['id'])

    dfReceiptInventories = pd.merge(left=dfReceiptInventories, right=dfReceipts, left_on='ReceiptNumber', right_on='id', how='left')
    del dfReceipts
    dfReceiptInventories.drop(inplace=True, columns=['id'])

    dfReceiptInventories['Name'] = np.where(dfReceiptInventories['Variant'].str.len() == 0, dfReceiptInventories['Name'],
                                            dfReceiptInventories['Name'].astype(str)+' - '+dfReceiptInventories['Variant'])
    dfReceiptInventories.drop(inplace=True, columns=['Variant'])

    #Apply the work order filter
    if workOrder:
        dfReceiptInventories = dfReceiptInventories[dfReceiptInventories['WorkOrder']==int(workOrder)]

    dfReceiptInventories = dfReceiptInventories.groupby(['ReceiptNumber','RecInvId','Name']).agg({
        'ReceiptDate': 'first',
        'Supplier': 'first',
        'Quantity': 'first',
        'WorkOrder': concatenateValues,
    }).reset_index()

    cols = [i for i in dfReceiptInventories]
    data = [dict(zip(cols, i)) for i in dfReceiptInventories.values]
    return data

def PrepareDataForAudit (recInvs: List[str]):
    '''
    Get the data for conducting inventory audit
    '''

    fields = ['id','ReceiptNumber','InventoryCode','Variant','Quantity']
    receiptInventories = appModels.RecInventory.objects.filter(id__in=recInvs).values(*fields)
    if receiptInventories:
        dfReceiptInventories = pd.DataFrame(receiptInventories)
    else:
        raise ValueError('Invalid Data.')
    del receiptInventories, fields

    fields = ['id','Supplier']
    receipts = appModels.InventoryReciept.objects.filter(id__in=dfReceiptInventories['ReceiptNumber'].to_list()).values(*fields)
    if receipts:
        dfReceipts = pd.DataFrame(receipts)
    else:
        dfReceipts = pd.DataFrame(columns=fields)
    del fields, receipts

    fields = ['Code','Name','Group']
    inventories = appModels.Inventory.objects.filter(Code__in=dfReceiptInventories['InventoryCode'].to_list()).values(*fields)
    if inventories:
        dfInventories = pd.DataFrame(inventories)
    else:
        dfInventories = pd.DataFrame(columns=fields)
    del inventories, fields

    dfReceiptInventories.rename(inplace=True, columns={'id':'RecInvId'})

    dfReceiptInventories = pd.merge(left=dfReceiptInventories, right=dfReceipts, left_on='ReceiptNumber', right_on='id', how='left')
    del dfReceipts
    dfReceiptInventories.drop(inplace=True, columns=['id'])
    
    dfReceiptInventories = pd.merge(left=dfReceiptInventories, right=dfInventories, left_on='InventoryCode', right_on='Code', how='left')
    del dfInventories
    dfReceiptInventories.drop(inplace=True, columns=['InventoryCode','Code'])
    
    dfReceiptInventories = dfReceiptInventories[dfReceiptInventories['Group'] != 'Fabric']
    dfReceiptInventories.drop(inplace=True, columns=['Group'])

    dfReceiptInventories['AuditQuantity'] = (dfReceiptInventories['Quantity'] * SAMPLE_SIZE).apply(math.ceil)

    #Group the dataframe for each delivery separately, as they'll need separate audit
    dfReceiptInventories = dfReceiptInventories.groupby(['ReceiptNumber','Supplier']).agg({
        'Variant': list,
        'Quantity': list,
        'Name': list,
        'AuditQuantity': list,
        'RecInvId': list,
    }).reset_index()

    #Combine the Variant, Qty, Inv and AudityQty to one one list of dicts.
    dfReceiptInventories['Details'] = dfReceiptInventories[['Variant', 'Quantity', 'Name', 'AuditQuantity','RecInvId']].apply(combineAuditRows, axis=1)

    dfReceiptInventories.drop(inplace=True, columns=['Variant','Quantity','Name','AuditQuantity','RecInvId'])

    checkListOptions = getCheckList()

    cols = [i for i in dfReceiptInventories]
    data = [dict(zip(cols, i)) for i in dfReceiptInventories.values]
    return data, checkListOptions

def AddTrimsAudit (dataDict: Dict[str, Any]):
    '''
    Save data for a new trims audit
    '''
    groupedData = {}
    for key, value in dataDict.items():
        parts = key.split('_')
        columnName, recInvId, recId, rowNum = parts[0], int(parts[1]), parts[2], parts[3]
        compositeKey = (recInvId, recId, rowNum)

        if compositeKey not in groupedData:
            groupedData[compositeKey] = {'RecInventory': recInvId, 'RecId': recId, 'RowNum': rowNum}
        groupedData[compositeKey][columnName] = value
    
    dfData = pd.DataFrame(list(groupedData.values()))
    del groupedData

    dfData['Approval'] = np.where(dfData['Approval'] == 'null', None, dfData['Approval'])

    if dfData['Approval'].isna().any() or (dfData['CheckList'].str.len() == 0).any():
        raise ValueError('Incomplete data Provided')

    dfData['Approval'] = np.where(dfData['Approval'] == 'true', True, False)

    if ((dfData['Approval'] == False) & (dfData['Comments'].str.len() == 0)).any():
        raise ValueError('Comments are needed for rejected items.')
    
    dfData.drop(inplace=True, columns=['RowNum','RecId'])

    dfData['RecInventory'] = convertTexttoObject(appModels.RecInventory, dfData['RecInventory'], 'id')
    
    for _,row in dfData.iterrows():
        newEntry = models.TrimAudit(**row)
        newEntry.save()

    updateApprovalForAudit(dfData)

def EditTrimsAudit (dfNewData: pd.DataFrame, receiptInvNumber: int):
    '''
    Update a trims audit based on the provided data
    '''

    if dfNewData['CheckList'].duplicated().any():
        raise ValueError('Duplicate Data')
    
    dfNewData['Approval'] = np.where(dfNewData['Approval'] == 'true', True, False)

    if ((dfNewData['Approval'] == False) & (dfNewData['Comments'].str.len() == 0)).any():
        raise ValueError('Comments are needed for rejected items.')

    previousData = models.TrimAudit.objects.filter(RecInventory=receiptInvNumber).values('id')
    if previousData:
        dfPreviousData = pd.DataFrame(previousData)
    else:
        dfPreviousData = pd.DataFrame(columns=['id'])
    del previousData

    dfNewData['id'] = pd.to_numeric(dfNewData['id'], errors='coerce')

    recInventory = appModels.RecInventory.objects.get(id=receiptInvNumber)
    dfNewData['RecInventory'] = recInventory

    updateModelWithDF(models.TrimAudit, dfNewData, dfPreviousData)

    updateApprovalForAudit(dfNewData)

def GetAuditsData (receiptInvNumber: int):
    '''
    Get the data for the audit of a particular inventory
    '''
    try:
        recInventory = appModels.RecInventory.objects.get(id=receiptInvNumber)
    except:
        raise LookupError('Resource not found')

    fields = ['id','CheckList','Approval','Comments']
    audits = models.TrimAudit.objects.filter(RecInventory=recInventory).values(*fields)

    data = {
        'audit': audits,
        'supplier': recInventory.ReceiptNumber.Supplier.Name,
        'ReceiptNumber': recInventory.ReceiptNumber.id,
        'Inventory': recInventory.InventoryCode.Name,
        'Variant': recInventory.Variant,
        'Quantity': recInventory.Quantity,
        'AuditQuantity': math.ceil(recInventory.Quantity * SAMPLE_SIZE),
    }

    checkListOptions = getCheckList()

    return data, checkListOptions