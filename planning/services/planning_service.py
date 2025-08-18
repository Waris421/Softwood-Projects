import pandas as pd
from datetime import datetime

from planning import models
from apparelManagement.services.work_order_service import getWorkOrders
from core.services.generic_services import dfToListOfDicts, convertTexttoObject, updateModelWithDF, convertStrToDateTime

def GetOrdersPlanning(startingDD, endingDD, sortingMethod:str):
    dfWorkOrders = getWorkOrders(startingDD, endingDD)

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
    dfWorkOrders['Quantity'] = dfWorkOrders['Quantity'].round(0)

    dfWorkOrders = pd.merge(left=dfWorkOrders, right=dfStyleRoutes, left_on='StyleCode', right_on='Style', how='left')
    del dfStyleRoutes
    dfWorkOrders.drop(inplace=True, columns=['Style'])

    dfProductionPlans = pd.merge(left=dfProductionPlans, right=dfPlannedRoutes, left_on='StyleRoute', right_on='id', how='left')
    del dfPlannedRoutes
    dfProductionPlans.drop(inplace=True, columns=['StyleRoute','id_y'])
    dfProductionPlans.rename(inplace=True, columns={'WorkOrder':'OrderNumber','id_x':'id'})
    
    dfWorkOrders = pd.merge(left=dfWorkOrders, right=dfProductionPlans, on=['OrderNumber', 'Stage'], how='left')
    del dfProductionPlans

    #TODO: Calculate the ready date for each stage

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