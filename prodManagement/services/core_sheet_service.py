import pandas as pd
import numpy as np

from typing import Dict, List

from django.db import transaction
from django.db.models import Max
from django.forms import model_to_dict

from .. import models
from core.services import generic_services

def areBundlesUnique(newBundles: pd.Series, workOrder: models.WorkOrder, currentCut: models.Cut):
    newBundles = newBundles.astype(int)
    #Don't go any further if the user has manually entered a duplicate bundle number
    if newBundles.duplicated().any():
        return False

    #check if any of the bundle numbers already exist in other cuts
    otherCuts = models.Cut.objects.filter(WorkOrder=workOrder).exclude(id=currentCut.id)
    otherBundles = models.Bundle.objects.filter(Cut__in=otherCuts).values_list('Bundle', flat=True)
    if newBundles.isin(otherBundles).any():
        return False

    return True

def assignCardGroup(cut: models.Cut, dfBundle: pd.DataFrame):
    bundles = models.Bundle.objects.filter(Cut=cut)
    fields = ['RFIDCard','Bundle']
    previousAssignments = models.BundleCardAssignment.objects.filter(Bundle__in=bundles).values(*fields)
    dfPreviousAssignemnts = pd.DataFrame(previousAssignments) if previousAssignments else pd.DataFrame(columns=fields)
    del previousAssignments

    fields = ['CardId', 'GroupNumber']
    availableCards = models.RFIDCard.objects.filter(GroupStatus='Complete').filter(GroupNumber__isnull=False).values(*fields)
    dfAvailableCards = pd.DataFrame(availableCards) if availableCards else pd.DataFrame(columns=fields)
    del availableCards

    dfBundle = pd.merge(left=dfBundle, right=dfPreviousAssignemnts, left_on='id', right_on='Bundle', how='left')
    del dfPreviousAssignemnts
    dfBundle = dfBundle[dfBundle['RFIDCard'].isna()]
    dfBundle.drop(inplace=True, columns=['Bundle', 'RFIDCard'])

    numOfBundles = dfBundle['id'].nunique()
    numOfAvialableGroups = dfAvailableCards['GroupNumber'].nunique()

    if numOfBundles > numOfAvialableGroups:
        raise ValueError('Not enough cards available in system')
    del numOfBundles, numOfAvialableGroups

    dfAvailableCards['CardId'] = generic_services.convertTexttoObject(models.RFIDCard, dfAvailableCards['CardId'], 'CardId')
    dfBundle['id'] = generic_services.convertTexttoObject(models.Bundle, dfBundle['id'], 'id')

    availableGroups = dfAvailableCards['GroupNumber'].unique()
    allAssignments = []
    groupsToUpdateStatus = []

    for i, bundle in enumerate(dfBundle['id']):
        groupNumberToAssign = availableGroups[i]

        groupsToUpdateStatus.append(groupNumberToAssign)

        cardsToAssign = dfAvailableCards[dfAvailableCards['GroupNumber'] == groupNumberToAssign]

        for card in cardsToAssign['CardId']:
            card.GroupStatus = 'Incomplete'
            allAssignments.append(
                models.BundleCardAssignment(
                    Bundle=bundle,
                    RFIDCard=card
                )
            )
    
    models.RFIDCard.objects.filter(GroupNumber__in=groupsToUpdateStatus).update(GroupStatus='Incomplete')
    models.BundleCardAssignment.objects.bulk_create(allAssignments)

def GetCoreSheetList(workOrder: models.WorkOrder):
    fields = ['OrderNumber','StyleCode','Customer','Merchandiser','ExcessCut']
    if workOrder:
        workOrders = models.WorkOrder.objects.filter(OrderNumber=workOrder.OrderNumber).values(*fields)
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

def CompleteCardGroup(cardId: int):
    try:
        groupNumber = models.RFIDCard.objects.get(CardId=cardId).GroupNumber
        if groupNumber is None:
            raise LookupError('Card not added in system')
    except:
        raise LookupError('Card not added in system')
    
    cards = models.RFIDCard.objects.filter(GroupNumber=groupNumber)

    currentGroupStatus = cards.values_list('GroupStatus',flat=True).first()
    
    if currentGroupStatus == 'Complete':
        raise ValueError('Group is already complete')
    
    with transaction.atomic():
        models.BundleCardAssignment.objects.filter(RFIDCard__in=cards).delete()
        cards.update(GroupStatus='Complete')

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

def GetHighestBundleNumber(workOrder: models.WorkOrder):
    highestCut = models.Cut.objects.filter(WorkOrder=workOrder).aggregate(Max('id'))['id__max']

    highestBundle = models.Bundle.objects.filter(Cut=highestCut).aggregate(Max('Bundle'))['Bundle__max']

    return int(highestBundle)

def EditCoreSheet(dfCut: pd.DataFrame, dfBundle: pd.DataFrame, workOrder: models.WorkOrder):
    dfBundle = dfBundle[dfBundle['Size'].str.len()>0]

    if (dfBundle.empty):
        raise ValueError('No Bundles Provided')

    dfCut.rename(inplace=True, columns={'Cut':'id','ShrinkageWarp':'WarpShrinkage','ShrinkageWeft':'WeftShrinkage'})
    cutDict = dfCut.iloc[0].to_dict()
    del dfCut

    if cutDict['id']:
        cut = models.Cut.objects.get(id=cutDict['id'])
        cutDict.pop('id')
        for key, value in cutDict.items():
            setattr(cut, key, value)
        
        previousBundles = models.Bundle.objects.filter(Cut=cut).values('id')
        dfPreviousBundles = pd.DataFrame(previousBundles)
        del previousBundles
    else:
        cutDict['WorkOrder'] = workOrder

        maxCutNumber = models.Cut.objects.filter(WorkOrder=workOrder).aggregate(Max('CutNumber'))['CutNumber__max']
        if maxCutNumber:
            cutDict['CutNumber'] = maxCutNumber+1
        else:
            cutDict['CutNumber'] = 1
        del maxCutNumber
        
        cutDict['id'] = None
        cut = models.Cut(**cutDict)
        dfPreviousBundles = pd.DataFrame(columns=['id'])

    if not areBundlesUnique(dfBundle['BundleNumber'], workOrder, cut):
        raise ValueError('Duplicate bundles numbers are provided')  

    with transaction.atomic():
        cut.save()
        
        dfBundle['id'] = dfBundle['id'].replace('', None).astype(pd.Int64Dtype())
        dfBundle.rename(inplace=True, columns={'BundleNumber':'Bundle'})
        dfBundle['Cut'] = cut
        
        try:
            generic_services.updateModelWithDF(models.Bundle, dfBundle, dfPreviousBundles)
            assignCardGroup(cut, dfBundle[['id']])
        except Exception as e:
            raise ValueError(e)

    return cut.id