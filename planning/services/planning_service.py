import pandas as pd
import numpy as np

from planning import models
from apparelManagement.models import StyleCard, StyleRoute
from apparelManagement.services.work_order_service import getWorkOrders
from core.services.generic_services import dfToListOfDicts

def GetOrdersPlanning(startingDD, endingDD, sortingMethod:str):
    dfWorkOrders = getWorkOrders(startingDD, endingDD)

    fields = ['Style','Stage']
    styleCards = StyleCard.objects.filter(StyleCode__in=dfWorkOrders['StyleCode'].to_list())
    styleRoutes = StyleRoute.objects.filter(Style__in=styleCards).values(*fields)
    dfStyleRoutes = pd.DataFrame(styleRoutes) if styleRoutes else pd.DataFrame(columns=fields)
    del styleCards, styleRoutes, fields

    dfWorkOrders['Quantity'] = dfWorkOrders['POQuantity'] * (1+(dfWorkOrders['ExcessCut'])/100)
    dfWorkOrders.drop(inplace=True, columns=['POQuantity','ExcessCut'])
    dfWorkOrders['Quantity'] = dfWorkOrders['Quantity'].round(0)

    dfWorkOrders = pd.merge(left=dfWorkOrders, right=dfStyleRoutes, left_on='StyleCode', right_on='Style', how='left')
    del dfStyleRoutes
    dfWorkOrders.drop(inplace=True, columns=['Style'])

    #TODO: Add source, MDate and Actual Date

    dfWorkOrders.sort_values(by='DeliveryDate', inplace=True, ascending=True)
    
    if sortingMethod == 'orderWise':
        dfWorkOrders.sort_values(by='OrderNumber', inplace=True)
    else:
        dfWorkOrders.sort_values(by='Stage', inplace=True)

    return dfToListOfDicts(dfWorkOrders)

def UpdateOrdersPlanning(dfOrderPlanning: pd.DataFrame):
    dfOrderPlanning.drop(inplace=True, columns=['StyleCode','Customer','Quantity','DeliveryDate'])
    
    dfOrderPlanning.dropna(inplace=True, subset=['Source'])

    print(dfOrderPlanning)