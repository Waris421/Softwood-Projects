import pandas as pd
import numpy as np

from django.db.models import Q
from django.db import transaction

from .. import models

from core.services.generic_services import dfToListOfDicts, dfToJSON, convertTextToBool, concatenateValues

def filterWorkOrderRoute(dfResults: pd.DataFrame, dfAddedPlans: pd.DataFrame, ignore: str|None):
    addPlansMask = dfResults['ProductionPlan'].isin(dfAddedPlans['ProductionPlan'])
    ignoreMask = pd.Series([False] * len(dfResults))

    #Remove route entries that are already planned
    if ignore:
        ignore = int(ignore)
        idTognore = models.OutSourceJobContractDetails.objects.get(id=ignore).ProductionPlan.id
        ignoreMask = (dfResults['ProductionPlan'] == idTognore)
    
    mask = (~addPlansMask) | ignoreMask
    dfResults = dfResults[mask]

    return dfResults

def GetOutsourceContracts(workOrder: str, source: str, contractNumber: str, approvalStr: str):
    filters = Q()
    if contractNumber:
        filters &= Q(id=contractNumber)
    
    if approvalStr:
        approval = convertTextToBool(approvalStr)
        filters &= Q(Approval=approval)
    
    fields = ['id', 'StartDate', 'EndDate','Approval', 'ApprovedBy__first_name', 'Comments']
    contracts = models.OutSourceJobContract.objects.filter(filters).values(*fields)
    dfContracts = pd.DataFrame(contracts) if contracts else pd.DataFrame(columns=fields)
    del contracts

    filters = Q(OutSourceJobContract__in=dfContracts['id'].to_list())
    if workOrder:
        filters &= Q(ProductionPlan__WorkOrder=workOrder)
    if source:
        filters &= Q(ProductionPlan__Source=source)
    
    fields = ['OutSourceJobContract', 'ProductionPlan__WorkOrder', 'ProductionPlan__Source__Source', 'ProductionPlan__StyleRoute__Stage']
    contractDetails = models.OutSourceJobContractDetails.objects.filter(filters).values(*fields)
    dfContractDetails = pd.DataFrame(contractDetails) if contractDetails else pd.DataFrame(columns=fields)
    del contractDetails
    
    dfContracts.rename(inplace=True, columns={
        'ApprovedBy__first_name': 'ApprovedBy'
    })
    
    dfContractDetails.rename(inplace=True, columns={
        'ProductionPlan__WorkOrder': 'WorkOrder',
        'ProductionPlan__Source__Source': 'Source',
        'ProductionPlan__StyleRoute__Stage': 'Stage',
        'OutSourceJobContract': 'id',
    })

    dfContractDetails = dfContractDetails.groupby('id').agg({
        'WorkOrder': concatenateValues,
        'Source': 'first',
        'Stage': concatenateValues,
    }).reset_index()
    
    dfContracts['ApprovedBy'] = dfContracts['ApprovedBy'].fillna('')
    dfContracts['Comments'] = dfContracts['Comments'].fillna('')

    conditions = [
        dfContracts['Approval'] == True,
        dfContracts['Approval'] == False,
    ]

    choices = [
        'Approved by ' + dfContracts['ApprovedBy'] + '. Note to follow ' + dfContracts['Comments'],
        'Rejected by ' + dfContracts['ApprovedBy'] + ' due to ' + dfContracts['Comments'],
    ]

    dfContracts['ApprovalText'] = np.select(conditions, choices, default='Pending')
    del conditions, choices
    dfContracts.drop(inplace=True, columns=['ApprovedBy', 'Comments'])

    dfContracts = pd.merge(left=dfContracts, right=dfContractDetails, on='id', how='left')
    del dfContractDetails
    
    return dfToListOfDicts(dfContracts)

def GetWorkOrderRoute(styleCard: models.StyleCard, source: str, ignore: str|None):
    routes = models.StyleRoute.objects.filter(Style=styleCard)

    fields = ['id', 'Stage']
    route = routes.values(*fields)
    dfRoute = pd.DataFrame(route) if route else pd.DataFrame(columns=fields)
    del route

    filters = Q(Source = source) & Q(StyleRoute__in=routes)
    fields = ['id', 'StyleRoute']
    productionPlans = models.ProductionPlan.objects.filter(filters).values(*fields)
    dfProductionPlans = pd.DataFrame(productionPlans) if productionPlans else pd.DataFrame(columns=fields)
    del productionPlans, routes
    
    fields = ['ProductionPlan', 'ProductionPlan__StyleRoute']
    addedPlans = models.OutSourceJobContractDetails.objects.filter(ProductionPlan__in=dfProductionPlans['id'].to_list()).values(*fields)
    dfAddedPlans = pd.DataFrame(addedPlans) if addedPlans else pd.DataFrame(columns=fields)
    del addedPlans, fields

    dfResults = pd.merge(left=dfProductionPlans, right=dfRoute, left_on='StyleRoute', right_on='id', how='left')
    del dfProductionPlans, dfRoute
    dfResults.drop(inplace=True, columns=['id_y'])
    dfResults.rename(inplace=True, columns={'id_x': 'ProductionPlan'})

    dfResults = filterWorkOrderRoute(dfResults, dfAddedPlans, ignore)

    dfResults.rename(inplace=True, columns={'StyleRoute':'value', 'Stage':'text'})    
    return dfToListOfDicts(dfResults)

def AddContract(dfHeading: pd.DataFrame, dfDetails: pd.DataFrame):
    heading = dfHeading.iloc[0].to_dict()
    
    for key, value in heading.items():
        if not value:
            raise ValueError(f'Missing {key}')
    
    source = heading.pop('Source')
    contract = models.OutSourceJobContract(**heading)
    
    source = models.Capacity.objects.get(id=source)

    lookupKeys = dfDetails[['WorkOrder', 'Operation']].to_records(index=False).tolist()

    productionPlans = models.ProductionPlan.objects.filter(
        WorkOrder__in=[k[0] for k in lookupKeys],
        StyleRoute__in=[k[1] for k in lookupKeys],
        Source=source
    ).select_related('StyleRoute')

    planMapping = {
        (plan.WorkOrder.OrderNumber, plan.StyleRoute_id): plan for plan in productionPlans
    }
    
    #This ensures atomicity in saving the data. If there is an error in any specific part,
    #all db transactions are reversed
    with transaction.atomic():
        contract.save()
        details = []
        for _, row in dfDetails.iterrows():
            workOrder=int(row['WorkOrder'])
            styleRoute = int(row['Operation'])
            price = row['Price']

            productionPlan = planMapping.get((workOrder, styleRoute))
            if not productionPlan:
                stage = models.StyleRoute.objects.get(id=styleRoute).Stage
                raise ImportError(f'Order:{workOrder}, Operation:{stage} is not currently planned.')
            
            contractDetails = models.OutSourceJobContractDetails(
                OutSourceJobContract=contract,
                ProductionPlan=productionPlan,
                Price=price,
            )
            details.append(contractDetails)
        
        if details:
            models.OutSourceJobContractDetails.objects.bulk_create(details)
        return contract.id
    
def ProcessContractData(contract: models.OutSourceJobContract):
    fields = ['id', 'ProductionPlan', 'Price']
    details = models.OutSourceJobContractDetails.objects.filter(OutSourceJobContract=contract).values(*fields)
    dfDetails = pd.DataFrame(details) if details else pd.DataFrame(columns=fields)
    del details

    fields = ['id', 'WorkOrder', 'StyleRoute', 'Source']
    productionPlans = models.ProductionPlan.objects.filter(id__in=dfDetails['ProductionPlan'].to_list()).values(*fields)
    dfProductionPlans = pd.DataFrame(productionPlans) if productionPlans else pd.DataFrame(columns=fields)
    del productionPlans

    source = dfProductionPlans['Source'].unique()

    if len(source) > 1:
        raise ValueError('Invalid Source')
    
    source = source[0]

    dfProductionPlans.rename(inplace=True, columns={'id': 'ProductionPlan'})
    dfProductionPlans.drop(inplace=True, columns=['Source'])

    dfDetails = pd.merge(left=dfDetails, right=dfProductionPlans, on='ProductionPlan', how='left')
    del dfProductionPlans
    dfDetails.drop(inplace=True, columns=['ProductionPlan'])

    return source, dfToListOfDicts(dfDetails), dfToJSON(dfDetails)

def UpdateContract(dfHeading: pd.DataFrame, dfDetails: pd.DataFrame):
    heading = dfHeading.iloc[0].to_dict()
    for key, value in heading.items():
        if not value:
            raise ValueError(f'Missing {key}')
    
    try:
        id = heading.pop('id')
        contract = models.OutSourceJobContract.objects.get(id=id)
    except:
        raise LookupError('Could not find contract')

    source = heading.pop('Source')

    contract.StartDate = heading['StartDate']
    contract.EndDate = heading['EndDate']
    contract.Approval = None
    contract.ApprovedBy = None
    contract.Comments = None
    
    source = models.Capacity.objects.get(id=source)

    lookupKeys = dfDetails[['WorkOrder', 'Operation']].to_records(index=False).tolist()
    productionPlans = models.ProductionPlan.objects.filter(
        WorkOrder__in=[k[0] for k in lookupKeys],
        StyleRoute__in=[k[1] for k in lookupKeys],
        Source=source
    ).select_related('StyleRoute')

    planMapping = {
        (plan.WorkOrder.OrderNumber, plan.StyleRoute_id): plan for plan in productionPlans
    }

    existingContractDetails = models.OutSourceJobContractDetails.objects.filter(OutSourceJobContract=contract)

    #This ensures atomicity in saving the data. If there is an error in any specific part,
    #all db transactions are reversed
    with transaction.atomic():
        contract.save()
        detailsToUpdate = []
        detailsToAdd = []
    
        for _, row in dfDetails.iterrows():
            id = row['id']
            workOrder=int(row['WorkOrder'])
            styleRoute = int(row['Operation'])
            price = row['Price']
            
            productionPlan = planMapping.get((workOrder, styleRoute))
            
            if not productionPlan:
                stage = models.StyleRoute.objects.get(id=styleRoute).Stage
                raise ImportError(f'Order:{workOrder}, Operation:{stage} is not currently planned.')
            
            if id:
                id = int(id)
            else:
                id = None
            
            try:
                contractDetails = models.OutSourceJobContractDetails.objects.get(id=id)
                contractDetails.ProductionPlan = productionPlan
                contractDetails.Price = price

                detailsToUpdate.append(contractDetails)
            except models.OutSourceJobContractDetails.DoesNotExist:
                contractDetails = models.OutSourceJobContractDetails(
                    OutSourceJobContract=contract,
                    ProductionPlan=productionPlan,
                    Price=price,
                )
                detailsToAdd.append(contractDetails)
            except Exception as e:
                raise ValueError(e)
        
        detailsToDelete = list(set(existingContractDetails) - set(detailsToUpdate))
        
        if detailsToUpdate:
            models.OutSourceJobContractDetails.objects.bulk_update(detailsToUpdate, fields=['ProductionPlan', 'Price'])
        
        if detailsToAdd:
            models.OutSourceJobContractDetails.objects.bulk_create(detailsToAdd)
        
        for details in detailsToDelete:
            details.delete()