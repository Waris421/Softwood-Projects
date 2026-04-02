import pandas as pd
import numpy as np

from typing import List

from planning import models
from apparelManagement.services.work_order_service import getWorkOrders
from core.services.generic_services import dfToListOfDicts, convertTexttoObject, updateModelWithDF, convertStrToDateTime
from core.constants.generic import TODAY

def getInventoryPlan(workOrders: List[int]):
    TOLERANCE = 0.97

    fields = ['WorkOrder','FabricETA','BWTrimETA','AWTrimETA']
    initialPlans = models.WorkOrderInitialPlan.objects.filter(WorkOrder__in=workOrders).values(*fields)
    dfInitialPlans = pd.DataFrame(initialPlans) if initialPlans else pd.DataFrame(columns=fields)
    del initialPlans

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

    dfInitialPlans.rename(inplace=True, columns={'FabricETA':'Fab','BWTrimETA':'BW','AWTrimETA':'AW'})

    dfResults = pd.merge(left=dfResults, right=dfInitialPlans, left_on=['OrderNumber'], right_on=['WorkOrder'], how='left')
    del dfInitialPlans
    dfResults.drop(inplace=True, columns=['WorkOrder'])

    if not dfResults.empty:
        dfResults['DeliveryDate'] = dfResults.apply(applyInitialPlan, axis=1)
    dfResults.drop(inplace=True, columns=['Fab', 'BW', 'AW'])

    dfResults = dfResults[~dfResults['DeliveryDate'].isna()]

    dfResults = dfResults.groupby(['OrderNumber', 'Type'])['DeliveryDate'].max().reset_index()

    dfResults.rename(inplace=True, columns={'DeliveryDate':'IHDate'})

    return dfResults

def applyInitialPlan(row: pd.Series):
    if pd.isna(row['DeliveryDate']):
        lookupColumn = row['Type']
        return row[lookupColumn]
    else:
        return row['DeliveryDate']

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

    fields = ['id','WorkOrder','RoutePresetStage','Source','MDate','ActualDate']
    addedPlans = models.ProductionPlan.objects.filter(WorkOrder__in=dfWorkOrders['OrderNumber'].to_list()).values(*fields)
    dfAddedPlans = pd.DataFrame(addedPlans) if addedPlans else pd.DataFrame(columns=fields)
    del addedPlans
    
    fields = ['StyleCode','RoutePreset']
    styleRoutes = models.StyleCard.objects.filter(StyleCode__in=dfWorkOrders['StyleCode'].to_list()).values(*fields)
    dfStyleRoutes = pd.DataFrame(styleRoutes) if styleRoutes else pd.DataFrame(columns=fields)
    del styleRoutes

    fields = ['id', 'RoutePreset', 'Stage']
    requiredPlans = models.RoutePresetStage.objects.filter(RoutePreset__in=dfStyleRoutes['RoutePreset'].to_list()).values(*fields)
    dfRequiredPlans = pd.DataFrame(requiredPlans) if requiredPlans else pd.DataFrame(columns=fields)
    del requiredPlans

    dfRequiredPlans = pd.merge(left=dfStyleRoutes, right=dfRequiredPlans, on='RoutePreset', how='left')
    del dfStyleRoutes
    dfRequiredPlans.drop(inplace=True, columns=['RoutePreset'])
    
    dfRequiredPlans = pd.merge(left=dfWorkOrders, right=dfRequiredPlans, on='StyleCode', how='left')
    dfRequiredPlans.drop(inplace=True, columns=['DeliveryDate', 'ExcessCut', 'POQuantity', 'Customer'])
    dfRequiredPlans.rename(inplace=True, columns={'OrderNumber':'WorkOrder', 'id':'RoutePresetStage'})
    
    dfOrdersPlan = pd.merge(left=dfRequiredPlans, right=dfAddedPlans, on=['WorkOrder', 'RoutePresetStage'], how='left')
    del dfRequiredPlans, dfAddedPlans
    dfOrdersPlan.drop(inplace=True, columns=['RoutePresetStage'])

    dfOrdersPlan.fillna(inplace=True, value='')

    if stageFilter:
        dfOrdersPlan = dfOrdersPlan[dfOrdersPlan['Stage'] == stageFilter]

    return dfToListOfDicts(dfOrdersPlan)

def UpdateOrdersPlanning(dfOrderPlanning: pd.DataFrame):    
    dfCurrentPlanning = dfOrderPlanning.dropna(subset=['Source'])

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
    del dfOrderPlanning

    fields = ['StyleCode', 'RoutePreset']
    routePresets = models.StyleCard.objects.filter(StyleCode__in=dfCurrentPlanning['StyleCode']).values(*fields)
    dfRoutePresets = pd.DataFrame(routePresets) if routePresets else pd.DataFrame(columns=fields)
    del routePresets

    fields = ['id', 'RoutePreset', 'Stage']
    stages = models.RoutePresetStage.objects.filter(RoutePreset__in=dfRoutePresets['RoutePreset'].to_list()).values(*fields)
    dfStages = pd.DataFrame(stages) if stages else pd.DataFrame(columns=fields)
    del stages

    dfRoutePresets = pd.merge(left=dfRoutePresets, right=dfStages, on='RoutePreset', how='left')
    del dfStages
    dfRoutePresets.drop(inplace=True, columns=['RoutePreset'])
    dfRoutePresets.rename(inplace=True, columns={'id': 'RoutePresetStage'})
    
    dfCurrentPlanning = pd.merge(left=dfCurrentPlanning, right=dfRoutePresets, on=['StyleCode', 'Stage'], how='left')
    del dfRoutePresets    
    dfCurrentPlanning.drop(inplace=True, columns=['Quantity', 'DeliveryDate', 'ReadyDate','StyleCode', 'Customer', 'Stage'])
    dfCurrentPlanning.rename(inplace=True, columns={'OrderNumber': 'WorkOrder'})

    dfCurrentPlanning['WorkOrder'] = convertTexttoObject(models.WorkOrder, dfCurrentPlanning['WorkOrder'], 'OrderNumber')
    dfCurrentPlanning['Source'] = convertTexttoObject(models.Capacity, dfCurrentPlanning['Source'], 'id')
    dfCurrentPlanning['RoutePresetStage'] = convertTexttoObject(models.RoutePresetStage, dfCurrentPlanning['RoutePresetStage'], 'id')    

    dfCurrentPlanning['MDate'] = dfCurrentPlanning['MDate'].apply(convertStrToDateTime, format='%d-%b')
    dfCurrentPlanning['MDate'] = dfCurrentPlanning['MDate'].replace({pd.NaT: None})
    dfCurrentPlanning['ActualDate'] = dfCurrentPlanning['ActualDate'].apply(convertStrToDateTime, format='%d-%b')
    dfCurrentPlanning['ActualDate'] = dfCurrentPlanning['ActualDate'].replace({pd.NaT: None})

    try:
        updateModelWithDF(models.ProductionPlan, dfCurrentPlanning, dfPreviousPlanning)  
    except Exception as e:
        raise ValueError(e)