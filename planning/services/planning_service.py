import pandas as pd
import numpy as np

from typing import List

from planning import models
from apparelManagement.services.work_order_service import getWorkOrders
from core.services.generic_services import dfToListOfDicts, convertTexttoObject, updateModelWithDF, convertStrToDateTime
from core.constants.generic import TODAY

def getInventoryPlan(workOrders: List[int]):
    TOLERANCE = 0.97

    fields = ['OrderNumber','InventoryCode','Quantity']
    inventoryRequirements = models.InvRequirement.objects.filter(OrderNumber__in=workOrders).values(*fields)
    dfInventoryRequirements = pd.DataFrame(inventoryRequirements) if inventoryRequirements else pd.DataFrame(columns=fields)
    del inventoryRequirements

    fields = ['OrderNumber', 'StyleCode','DeliveryDate']
    styles = models.WorkOrder.objects.filter(OrderNumber__in=workOrders).values(*fields)
    dfStyles = pd.DataFrame(styles) if styles else pd.DataFrame(columns=fields)
    del styles

    fields = ['Style','InventoryCode','Type']
    consumptions = models.StyleConsumption.objects.filter(Style__in=dfStyles['StyleCode'].to_list()).values(*fields)
    dfConsumptions = pd.DataFrame(consumptions) if consumptions else pd.DataFrame(columns=fields)
    del consumptions

    fields = ['Code','LeadTime']
    inventories = models.Inventory.objects.filter(Code__in=dfInventoryRequirements['InventoryCode'].to_list()).values(*fields)
    dfInventories = pd.DataFrame(inventories) if inventories else pd.DataFrame(columns=fields)
    del inventories

    fields = ['POInvId','WorkOrder','Quantity']
    poAllocations = models.POAllocation.objects.filter(WorkOrder__in=workOrders).values(*fields)
    dfPOAllocations = pd.DataFrame(poAllocations) if poAllocations else pd.DataFrame(columns=fields)
    del poAllocations

    fields = ['id','Inventory','PONumber']
    poInventory = models.POInventory.objects.filter(id__in=dfPOAllocations['POInvId'].to_list()).values(*fields)
    dfPOInventory = pd.DataFrame(poInventory) if poInventory else pd.DataFrame(columns=fields)
    del poInventory

    fields = ['id','DeliveryDate']
    purchaseOrders = models.PurchaseOrder.objects.filter(id__in=dfPOInventory['PONumber'].to_list()).values(*fields)
    dfPurchaseOrders = pd.DataFrame(purchaseOrders) if purchaseOrders else pd.DataFrame(columns=fields)
    del purchaseOrders

    fields = ['RecInvId', 'WorkOrder', 'Quantity']
    recAllocations = models.RecAllocation.objects.filter(WorkOrder__in=workOrders).values(*fields)
    dfRecAllocations = pd.DataFrame(recAllocations) if recAllocations else pd.DataFrame(columns=fields)
    del recAllocations

    fields = ['id','InventoryCode','ReceiptNumber']
    recInventory = models.RecInventory.objects.filter(id__in=dfRecAllocations['RecInvId'].to_list()).values(*fields)
    dfRecInventory = pd.DataFrame(recInventory) if recInventory else pd.DataFrame(columns=fields)
    del recInventory

    fields = ['id', 'ReceiptDate']
    inventoryReceipts = models.InventoryReciept.objects.filter(id__in=dfRecInventory['ReceiptNumber'].to_list()).values(*fields)
    dfInventoryReceipts = pd.DataFrame(inventoryReceipts) if inventoryReceipts else pd.DataFrame(columns=fields)
    del inventoryReceipts

    dfConsumptions = pd.merge(left=dfStyles, right=dfConsumptions, left_on='StyleCode', right_on='Style', how='left')
    del dfStyles
    dfConsumptions.drop(inplace=True, columns=['Style','StyleCode'])
    dfConsumptions.rename(inplace=True, columns={'DeliveryDate':'OrderDD'})

    dfResults = pd.merge(left=dfPOAllocations, right=dfPOInventory, left_on='POInvId', right_on='id', how='left')
    del dfPOAllocations, dfPOInventory
    dfResults.drop(inplace=True, columns=['POInvId','id'])

    dfResults = pd.merge(left=dfResults, right=dfPurchaseOrders, left_on='PONumber', right_on='id', how='left')
    del dfPurchaseOrders
    dfResults.drop(inplace=True, columns=['PONumber','id'])

    dfResults = dfResults.groupby(['WorkOrder', 'Inventory']).agg(
        DeliveryDate=('DeliveryDate', 'max'),
        Quantity=('Quantity', 'sum')
    ).reset_index()
    
    dfPurchaseOrders = dfResults.copy()
    del dfResults

    dfResults = pd.merge(left=dfRecAllocations, right=dfRecInventory, left_on='RecInvId', right_on='id', how='left')
    del dfRecAllocations, dfRecInventory
    dfResults.drop(inplace=True, columns=['RecInvId','id'])

    dfResults = pd.merge(left=dfResults, right=dfInventoryReceipts, left_on='ReceiptNumber', right_on='id', how='left')
    del dfInventoryReceipts
    dfResults.drop(inplace=True, columns=['ReceiptNumber','id'])

    dfResults = dfResults.groupby(['WorkOrder', 'InventoryCode']).agg(
        DeliveryDate=('ReceiptDate', 'max'),
        Quantity=('Quantity', 'sum')
    ).reset_index()

    dfReceipts = dfResults.copy()
    del dfResults

    dfResults = pd.merge(left=dfInventoryRequirements, right=dfPurchaseOrders, left_on=['OrderNumber','InventoryCode'],
                         right_on=['WorkOrder','Inventory'], how='left')
    del dfInventoryRequirements, dfPurchaseOrders
    dfResults.drop(inplace=True, columns=['WorkOrder', 'Inventory'])
    dfResults.rename(inplace=True, columns={'Quantity_x':'RequiredQty', 'Quantity_y':'OrderedQty', 'DeliveryDate':'PODate'})

    dfResults = pd.merge(left=dfResults, right=dfReceipts, left_on=['OrderNumber','InventoryCode'],
                         right_on=['WorkOrder','InventoryCode'], how='left')
    del dfReceipts
    dfResults.drop(inplace=True, columns=['WorkOrder'])
    dfResults.rename(inplace=True, columns={'Quantity':'ReceivedQty', 'DeliveryDate':'RecDate'})

    dfResults = pd.merge(left=dfResults, right=dfConsumptions, on=['OrderNumber', 'InventoryCode'], how='left')
    del dfConsumptions

    dfResults['DeliveryDate'] = pd.NaT

    condition1 = (dfResults['ReceivedQty'] / dfResults['RequiredQty'] >= TOLERANCE)
    condition2 = (dfResults['OrderedQty'] / dfResults['RequiredQty'] >= TOLERANCE)
    condition2 = (~condition1) & (condition2)

    dfResults['DeliveryDate'] = np.where(condition1, dfResults['RecDate'], dfResults['DeliveryDate'])
    dfResults['DeliveryDate'] = np.where(condition2, dfResults['PODate'], dfResults['DeliveryDate'])
    del condition1, condition2
    dfResults.drop(inplace=True, columns=['PODate', 'OrderedQty','RecDate','ReceivedQty','RequiredQty'])

    dfInventories['LeadTime'] = pd.to_timedelta(dfInventories['LeadTime'], unit='D')
    dfResults = pd.merge(left=dfResults, right=dfInventories, left_on='InventoryCode', right_on='Code', how='left')
    dfResults.drop(inplace=True, columns=['Code'])

    today = pd.to_datetime(TODAY)
    condition = pd.isna(dfResults['DeliveryDate'])
    print(dfResults)

    dfResults['DeliveryDate'] = np.where(condition, (today + dfResults['LeadTime']).dt.strftime('%Y-%m-%d'), dfResults['DeliveryDate'])
    dfResults['DeliveryDate'] = pd.to_datetime(dfResults['DeliveryDate'])

    dfResults.drop(inplace=True, columns=['LeadTime', 'InventoryCode'])

    dfResults = dfResults.groupby(['OrderNumber', 'Type'])['DeliveryDate'].max().reset_index()

    dfResults.rename(inplace=True, columns={'DeliveryDate':'IHDate'})

    return dfResults

def applyInvPlan(dfWorkOrders: pd.DataFrame, dfInventoryPlan: pd.DataFrame):
    stageInvPreReqs = {
        'Cutting':'Fab',
        'Stitching': 'BW',
        'Finishing': 'AW',
    }

    dfWorkOrders['PreReq'] = dfWorkOrders['Stage'].map(stageInvPreReqs)
    del stageInvPreReqs

    dfWorkOrders = pd.merge(left=dfWorkOrders, right=dfInventoryPlan, left_on=['OrderNumber','PreReq'],
                            right_on=['OrderNumber','Type'], how='left')
    del dfInventoryPlan

    dfWorkOrders.drop(inplace=True, columns=['PreReq','Type'])
    dfWorkOrders.rename(inplace=True, columns={'IHDate':'ReadyDate'})

    return dfWorkOrders
    
def GetOrdersPlanning(startingDD, endingDD, sortingMethod:str, orderFilter:int|None, stageFilter:str|None):
    dfWorkOrders = getWorkOrders(startingDD, endingDD)
    
    if orderFilter:
        dfWorkOrders = dfWorkOrders[dfWorkOrders['OrderNumber'] == orderFilter]

    fields = ['id','WorkOrder','StyleRoute','Source','MDate','ActualDate']
    productionPlans = models.ProductionPlan.objects.filter(WorkOrder__in=dfWorkOrders['OrderNumber'].to_list()).values(*fields)
    dfProductionPlans = pd.DataFrame(productionPlans) if productionPlans else pd.DataFrame(columns=fields)
    del productionPlans

    fields = ['Style','Stage']
    styleCards = models.StyleCard.objects.filter(StyleCode__in=dfWorkOrders['StyleCode'].to_list())
    styleRoutes = models.StyleRoute.objects.filter(Style__in=styleCards).values(*fields)
    dfStyleRoutes = pd.DataFrame(styleRoutes) if styleRoutes else pd.DataFrame(columns=fields)
    del styleCards, styleRoutes

    fields = ['id','Stage']
    plannedRoutes = models.StyleRoute.objects.filter(id__in=dfProductionPlans['StyleRoute'].to_list()).values(*fields)
    dfPlannedRoutes = pd.DataFrame(plannedRoutes) if plannedRoutes else pd.DataFrame(columns=fields)
    del plannedRoutes, fields

    dfWorkOrders['Quantity'] = dfWorkOrders['POQuantity'] * (1+(dfWorkOrders['ExcessCut'])/100)
    dfWorkOrders.drop(inplace=True, columns=['POQuantity','ExcessCut'])
    dfWorkOrders['Quantity'] = dfWorkOrders['Quantity'].astype(float).round(0)

    dfInventoryPlan = getInventoryPlan(dfWorkOrders['OrderNumber'].to_list())

    dfWorkOrders = pd.merge(left=dfWorkOrders, right=dfStyleRoutes, left_on='StyleCode', right_on='Style', how='left')
    del dfStyleRoutes
    dfWorkOrders.drop(inplace=True, columns=['Style'])

    dfProductionPlans = pd.merge(left=dfProductionPlans, right=dfPlannedRoutes, left_on='StyleRoute', right_on='id', how='left')
    del dfPlannedRoutes
    dfProductionPlans.drop(inplace=True, columns=['StyleRoute','id_y'])
    dfProductionPlans.rename(inplace=True, columns={'WorkOrder':'OrderNumber','id_x':'id'})
    
    dfWorkOrders = pd.merge(left=dfWorkOrders, right=dfProductionPlans, on=['OrderNumber', 'Stage'], how='left')
    del dfProductionPlans

    if stageFilter:
        dfWorkOrders = dfWorkOrders[dfWorkOrders['Stage'] == stageFilter]

    #dfWorkOrders = applyInvPlan(dfWorkOrders, dfInventoryPlan)

    dfWorkOrders.sort_values(by='DeliveryDate', inplace=True, ascending=True)
    
    if sortingMethod == 'orderWise':
        dfWorkOrders.sort_values(by='OrderNumber', inplace=True)
    else:
        dfWorkOrders.sort_values(by='Stage', inplace=True)

    return dfToListOfDicts(dfWorkOrders)

def UpdateOrdersPlanning(dfOrderPlanning: pd.DataFrame):    
    dfOrderPlanning.dropna(inplace=True, subset=['Source'])

    if dfOrderPlanning['id'].str.len().sum() > 0:
        convertedIdsStrs = dfOrderPlanning['id'].to_list()
        convertedIdsInts = []
        for id in convertedIdsStrs:
            if id:
                id = int(float(id))
                convertedIdsInts.append(id)
        
        previousPlanning = models.ProductionPlan.objects.filter(id__in=convertedIdsInts).values('id')
        dfPreviousPlanning = pd.DataFrame(previousPlanning) if previousPlanning else pd.DataFrame(columns=['id'])
        del previousPlanning
    else:
        dfPreviousPlanning = pd.DataFrame(columns=['id'])

    fields = ['id', 'Style', 'Stage']
    styleRoutes = models.StyleRoute.objects.filter(Style__in=dfOrderPlanning['StyleCode'].to_list()).values(*fields)
    dfStyleRoutes = pd.DataFrame(styleRoutes) if styleRoutes else pd.DataFrame(columns=fields)
    del styleRoutes, fields

    dfOrderPlanning.drop(inplace=True, columns=['Quantity', 'DeliveryDate', 'ReadyDate', 'Customer'])
    
    dfOrderPlanning = pd.merge(left=dfOrderPlanning, right=dfStyleRoutes, left_on=['StyleCode','Stage'],
                               right_on=['Style','Stage'], how='left')
    del dfStyleRoutes
    dfOrderPlanning.drop(inplace=True, columns=['Style','StyleCode','Stage'])
    dfOrderPlanning.rename(inplace=True, columns={'id_x':'id','id_y':'StyleRoute','OrderNumber':'WorkOrder'})

    dfOrderPlanning['WorkOrder'] = convertTexttoObject(models.WorkOrder, dfOrderPlanning['WorkOrder'], 'OrderNumber')
    dfOrderPlanning['Source'] = convertTexttoObject(models.Capacity, dfOrderPlanning['Source'], 'id')
    dfOrderPlanning['StyleRoute'] = convertTexttoObject(models.StyleRoute, dfOrderPlanning['StyleRoute'], 'id')

    dfOrderPlanning['MDate'] = dfOrderPlanning['MDate'].apply(convertStrToDateTime, format='%d-%b')
    dfOrderPlanning['MDate'] = dfOrderPlanning['MDate'].replace({pd.NaT: None})
    dfOrderPlanning['ActualDate'] = dfOrderPlanning['ActualDate'].apply(convertStrToDateTime, format='%d-%b')
    dfOrderPlanning['ActualDate'] = dfOrderPlanning['ActualDate'].replace({pd.NaT: None})

    try:
        updateModelWithDF(models.ProductionPlan, dfOrderPlanning, dfPreviousPlanning)  
    except Exception as e:
        raise ValueError(e)