import pandas as pd
import numpy as np

from django.db.models import Q
from django.contrib.auth.models import User
from django.forms import model_to_dict
from django.db import transaction

from .. import models

from core.services.generic_services import dfToListOfDicts, dfToJSON, convertTextToBool, concatenateValues, formatCurrencyAmount
from core.constants.generic import GST_RATE

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

def summarizeVariants(dfVariants: pd.DataFrame, varFilter: str):
    dfVariants['Name'] = dfVariants['Name'].astype(str)

    dfVariants[['Variant1', 'Variant2']] = dfVariants['Name'].str.split('-', n=1, expand=True)
    dfVariants.drop(inplace=True, columns=['Name'])

    aggDict = {
        'Quantity': 'sum',
    }

    if varFilter == 'V1':
        dfVariants = dfVariants.groupby(['OrderNumber', 'Variant1']).agg(aggDict).reset_index()
        dfVariants.rename(inplace=True, columns={'Variant1': 'Variant'})
    elif varFilter == 'V2':
        dfVariants = dfVariants.groupby(['OrderNumber', 'Variant2']).agg(aggDict).reset_index()
        dfVariants.rename(inplace=True, columns={'Variant2': 'Variant'})
    else:
        dfVariants = dfVariants.groupby(['OrderNumber']).agg(aggDict).reset_index()
        dfVariants['Variant'] = ''

    return dfVariants

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
    if contract.Approval is not None:
        raise PermissionError('This resource is already closed')

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

def GetDataForContractApproval(contract: models.OutSourceJobContract):
    fields = [
        'ProductionPlan__WorkOrder', 'ProductionPlan__Source__Source', 'ProductionPlan__StyleRoute__Stage',
        'ProductionPlan__StyleRoute__Style', 'Price'
    ]
    contractDetails = models.OutSourceJobContractDetails.objects.filter(OutSourceJobContract=contract).values(*fields)
    dfContractDetails = pd.DataFrame(contractDetails) if contractDetails else pd.DataFrame(columns=fields)
    del contractDetails, fields
    
    dfContractDetails.rename(inplace=True, columns={
        'ProductionPlan__WorkOrder': 'WorkOrder',
        'ProductionPlan__Source__Source': 'Source',
        'ProductionPlan__StyleRoute__Stage': 'Stage',
        'ProductionPlan__StyleRoute__Style': 'Style',
    })

    return dfToListOfDicts(dfContractDetails)

def ApproveContract(user: User, contract: models.OutSourceJobContract, approvalStr: str, comments: str):
    contract.Approval = convertTextToBool(approvalStr)
    contract.ApprovedBy = user
    contract.Comments = comments

    contract.save()

def PrintContract(contract: models.OutSourceJobContract, varFilter: str):
    '''
    Get the data to print the contract.
    '''
    fields = ['ProductionPlan', 'Price']
    contractDetails = models.OutSourceJobContractDetails.objects.filter(OutSourceJobContract=contract).values(*fields)
    dfContractDetails = pd.DataFrame(contractDetails) if contractDetails else pd.DataFrame(columns=fields)
    del contractDetails
    
    fields = ['id', 'WorkOrder', 'StyleRoute', 'Source']
    productionPlans = models.ProductionPlan.objects.filter(id__in=dfContractDetails['ProductionPlan'].to_list()).values(*fields)
    dfProductionPlans = pd.DataFrame(productionPlans) if productionPlans else pd.DataFrame(columns=fields)
    del productionPlans

    sourceId = dfProductionPlans['Source'].iloc[0]
    source = models.Capacity.objects.get(id=sourceId).Source
    del sourceId

    approvedBy = (contract.ApprovedBy.first_name)+' '+(contract.ApprovedBy.last_name)

    fields = ['id', 'Style', 'Stage']
    styleRoutes = models.StyleRoute.objects.filter(id__in=dfProductionPlans['StyleRoute'].to_list()).values(*fields)
    dfStyleRoutes = pd.DataFrame(styleRoutes) if styleRoutes else pd.DataFrame(columns=fields)
    del styleRoutes

    fields = ['OrderNumber','Name', 'Quantity']
    variants = models.OrderVariant.objects.filter(OrderNumber__in=dfProductionPlans['WorkOrder'].to_list()).values(*fields)
    dfVariants = pd.DataFrame(variants) if variants else pd.DataFrame(columns=fields)    
    del variants

    fields = ['OrderNumber', 'ExcessCut']
    workOrders = models.WorkOrder.objects.filter(OrderNumber__in=dfProductionPlans['WorkOrder'].to_list()).values(*fields)
    dfWorkOrders = pd.DataFrame(workOrders) if workOrders else pd.DataFrame(columns=fields)
    del workOrders, fields

    dfVariants = pd.merge(left=dfVariants, right=dfWorkOrders, on='OrderNumber', how='left')
    del dfWorkOrders
    dfVariants['ExcessCut'] = 1 + (dfVariants['ExcessCut'] / 100)
    dfVariants['Quantity'] = (dfVariants['Quantity'] * dfVariants['ExcessCut']).apply(np.ceil).astype(int)
    dfVariants.drop(inplace=True, columns=['ExcessCut'])
    
    dfVariants = summarizeVariants(dfVariants, varFilter)

    dfVariants.rename(inplace=True, columns={'OrderNumber':'WorkOrder'})

    dfProductionPlans.rename(inplace=True, columns={'id': 'ProductionPlan'})

    dfProductionPlans = pd.merge(left=dfProductionPlans, right=dfVariants, on='WorkOrder', how='left')
    del dfVariants
    
    dfProductionPlans = pd.merge(left=dfProductionPlans, right=dfStyleRoutes, left_on=['StyleRoute'], right_on=['id'], how='left')
    del dfStyleRoutes
    dfProductionPlans.drop(inplace=True, columns=['StyleRoute', 'id', 'Source'])

    dfContractDetails = pd.merge(left=dfContractDetails, right=dfProductionPlans, on='ProductionPlan', how='left')
    del dfProductionPlans
    dfContractDetails.drop(inplace=True, columns=['ProductionPlan'])

    dfContractDetails['Value'] = dfContractDetails['Price'] * dfContractDetails['Quantity']

    heading = model_to_dict(contract)
    heading['ApprovedBy'] = approvedBy
    heading['Source'] = source
    heading['GSTRate'] = GST_RATE

    summary = {}
    summary['ValueBeforeTax'] = dfContractDetails['Value'].astype(float).sum().round(0).astype(int)
    summary['TaxAmount'] = int(summary['ValueBeforeTax'] * (GST_RATE/100))
    summary['GrandTotal'] = summary['ValueBeforeTax'] + summary['TaxAmount']

    for key,value in summary.items():
        summary[key] = formatCurrencyAmount(value)
    
    dfContractDetails['Value'] = dfContractDetails['Value'].apply(formatCurrencyAmount)
    dfContractDetails['Price'] = dfContractDetails['Price'].apply(formatCurrencyAmount)
    
    return heading, dfToListOfDicts(dfContractDetails), summary