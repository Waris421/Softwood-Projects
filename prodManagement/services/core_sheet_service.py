import pandas as pd

from django.db import transaction

from .. import models
from . import generic_services

def GetCoreSheetList(workOrder: models.WorkOrder):
    fields = ['id', 'WorkOrder', 'NoOfPlies']
    
    if workOrder:
        cuts = models.Cut.objects.filter(WorkOrder=workOrder).values(*fields)
    else:
        cuts = models.Cut.objects.all().values(*fields)
    del workOrder
    
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

    dfBundles = pd.merge(left=dfBundles, right=dfCuts, left_on='Cut', right_on='id', how='left')
    del dfCuts
    dfBundles.drop(inplace=True, columns=['id'])

    dfBundles = dfBundles.groupby('WorkOrder').agg(
        Cuts=('Cut', 'nunique'),
        Sizes=('Size', 'nunique'),
        Bundles=('Bundle', 'count'),
        Quantity=('NoOfPlies', 'sum')
    ).reset_index()
    
    return generic_services.dfToListOfDicts(dfBundles)

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