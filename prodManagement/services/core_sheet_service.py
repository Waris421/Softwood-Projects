import pandas as pd

from django.db import transaction
from django.forms import model_to_dict

from .. import models
from . import generic_services

def GetCoreSheetList(workOrder: models.WorkOrder):
    fields = ['OrderNumber','StyleCode','Customer','Merchandiser','ExcessCut']
    if workOrder:
        workOrders = models.WorkOrder.objects.fitler(OrderNumber=workOrder.OrderNumber).values(*fields)
    else:
        workOrders = models.WorkOrder.objects.all().values(*fields)
    
    dfWorkOrders = pd.DataFrame(workOrders)
    del workOrders, workOrder

    fields = ['OrderNumber','Quantity']
    variants = models.OrderVariant.objects.filter(OrderNumber__in=dfWorkOrders['OrderNumber']).values(*fields)
    if variants:
        dfVariants = pd.DataFrame(variants)
    else:
        dfVariants = pd.DataFrame(columns=fields)
    del variants

    fields = ['id', 'first_name','last_name']
    users = models.User.objects.all().values(*fields)
    dfUsers = pd.DataFrame(users)
    del users
 
    fields = ['id', 'WorkOrder', 'NoOfPlies']    
    cuts = models.Cut.objects.filter(WorkOrder__in=dfWorkOrders['OrderNumber'].to_list()).values(*fields)
    if cuts:
        dfCuts = pd.DataFrame(cuts)
    else:
        dfCuts = pd.DataFrame(columns=fields)
    del cuts

    fields = ['Cut', 'Size', 'Bundle']
    bundles = models.Bundle.objects.filter(Cut__in=dfCuts['id'].to_list()).values(*fields)
    if bundles:
        dfBundles = pd.DataFrame(bundles)
    else:
        dfBundles = pd.DataFrame(columns=fields)
    del bundles, fields

    dfWorkOrders = pd.merge(left=dfWorkOrders, right=dfUsers, left_on='Merchandiser', right_on='id', how='left')
    del dfUsers
    dfWorkOrders['Merchandiser'] = dfWorkOrders['first_name'].astype(str)+' '+dfWorkOrders['last_name'].astype(str)
    dfWorkOrders.drop(inplace=True, columns=['id','first_name','last_name'])

    dfVariants = dfVariants.groupby('OrderNumber')['Quantity'].sum().reset_index()

    dfWorkOrders = pd.merge(left=dfWorkOrders, right=dfVariants, on='OrderNumber', how='left')
    del dfVariants
    dfWorkOrders.rename(inplace=True, columns={'Quantity':'POQuantity'})

    dfWorkOrders = pd.merge(left=dfWorkOrders, right=dfCuts, left_on='OrderNumber', right_on='WorkOrder', how='left')
    del dfCuts
    dfWorkOrders.drop(inplace=True, columns=['WorkOrder'])
    dfWorkOrders.rename(inplace=True, columns={'id':'Cut'})   

    dfWorkOrders = pd.merge(left=dfWorkOrders, right=dfBundles, on='Cut', how='left') 
    del dfBundles
    
    dfWorkOrders['WillCut'] = dfWorkOrders['POQuantity']
    dfWorkOrders['WillCut'] += (dfWorkOrders['POQuantity'] * dfWorkOrders['ExcessCut']/100).round(0)

    dfWorkOrders = dfWorkOrders.groupby('OrderNumber').agg(
        StyleCode=('StyleCode','first'),
        Customer=('Customer','first'),
        Merchandiser=('Merchandiser','first'),
        WillCut=('WillCut','mean'),
        Cuts=('Cut', 'nunique'),
        Sizes=('Size', 'nunique'),
        Bundles=('Bundle', 'count'),
        CutQuantity=('NoOfPlies', 'sum')
    ).reset_index()
    
    return generic_services.dfToListOfDicts(dfWorkOrders)

@transaction.atomic
def CompleteCardGroup(cardId: int):
    try:
        groupNumber = models.RFIDCard.objects.get(CardId=cardId).GroupNumber
    except:
        raise LookupError('Card not added in system')
    
    models.RFIDCard.objects.filter(GroupNumber=groupNumber).update(GroupStatus='Complete')

def AssignCardGroup(dfAssignment: pd.DataFrame):
    dfAssignment['Bundle'] = dfAssignment['Bundle'].astype(int)
    dfAssignment['Group'] = dfAssignment['Group'].astype(int)
    
    dfAssignment['Bundle'] = generic_services.convertTexttoObject(models.Bundle, dfAssignment['Bundle'], 'Bundle')
    
    for _, row in dfAssignment.iterrows():
        bundle = row['Bundle']
        cards = models.RFIDCard.objects.filter(GroupNumber=row['Group'])

        for card in cards:
            card.GroupStatus = 'InComplete'
            card.save()

            models.BundleCardAssignment(
                RFIDCard=card,
                Bundle = bundle
            ).save()

def GetOrderCuttingDetail(workOrder: models.WorkOrder):
    cuts = models.Cut.objects.filter(WorkOrder=workOrder).values('id','CutNumber')

    variants = models.OrderVariant.objects.filter(OrderNumber=workOrder).values('Name')
    sizes = []
    for item in variants:
        name = item['Name']
        if '-' in name:
            parts = name.split('-', 1)  # Split only on the first dash
            sizes.append(parts[1])
        else:
            sizes.append(name)
    
    return cuts, sizes

def GetCutDetails(cut: models.Cut):
    cutDetails = model_to_dict(cut, fields=['Shade','WarpShrinkage','WeftShrinkage','Inseam','NoOfPlies'])

    bundles = models.Bundle.objects.filter(Cut=cut).values('id','Size','Bundle')

    cutDetails['Bundles'] = list(bundles)

    return cutDetails