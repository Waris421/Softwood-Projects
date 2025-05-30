from pandas import DataFrame, merge
from numpy import where

from .. import models
from ..theme import theme
from . import generic_services

def getScanData(
        startDate = None,
        endDate = None
) -> DataFrame:
    '''
    Generic function to retreive scanning data from database.
    Returns data for today if date range isn't given
    '''
    if not startDate:
        startDate = generic_services.TODAY
    if not endDate:
        endDate = generic_services.TODAY
    
    fields = ['Worker','Operation','Bundle','TimeDate']
    serials = models.Serial.objects.filter(TimeDate__date__range=(startDate, endDate)).values(*fields)
    if serials:
        dfSerials = DataFrame(serials)
    else:
        dfSerials = DataFrame(columns=fields)
    del serials

    fields = ['WorkerCode','WorkerName','SubDepartment']
    workers = models.Worker.objects.filter(WorkerCode__in=dfSerials['Worker'].to_list()).values(*fields)
    if workers:
        dfWorkers = DataFrame(workers)
    else:
        dfWorkers = DataFrame(columns=fields)
    del workers

    dfSections = DataFrame(generic_services.operationSections)

    fields = ['id','Name','SMV','Rate']
    operations = models.Operation.objects.filter(id__in=dfSerials['Operation'].to_list()).values(*fields)
    if operations:
        dfOperations = DataFrame(operations)
    else:
        dfOperations = DataFrame(columns=fields)
    del operations

    fields = ['id','Cut']
    bundles = models.Bundle.objects.filter(id__in=dfSerials['Bundle'].to_list()).values(*fields)
    if bundles:
        dfBundles = DataFrame(bundles)
    else:
        dfBundles = DataFrame(columns=fields)
    del bundles

    fields = ['id','NoOfPlies','WorkOrder']
    cuts = models.Cut.objects.filter(id__in=dfBundles['Cut'].to_list()).values(*fields)
    if cuts:
        dfCuts = DataFrame(cuts)
    else:
        dfCuts = DataFrame(columns=fields)
    del cuts

    dfSerials = merge(left=dfSerials, right=dfWorkers, left_on='Worker', right_on='WorkerCode', how='left')
    del dfWorkers
    dfSerials.drop(inplace=True, columns=['Worker'])

    dfSerials = merge(left=dfSerials, right=dfSections, left_on='SubDepartment', right_on='value', how='left')
    del dfSections
    dfSerials.drop(inplace=True, columns=['SubDepartment'])
    dfSerials.rename(inplace=True, columns={'text':'Section','value':'SectionCode'})

    dfSerials = merge(left=dfSerials, right=dfOperations, left_on='Operation', right_on='id', how='left')
    del dfOperations
    dfSerials.drop(inplace=True, columns=['id'])
    dfSerials.rename(inplace=True, columns={'Operation':'OperationCode','Name':'OperationName'})

    dfSerials = merge(left=dfSerials, right=dfBundles, left_on='Bundle', right_on='id',how='left')
    del dfBundles
    dfSerials.drop(inplace=True, columns=['Bundle','id'])

    dfSerials = merge(left=dfSerials, right=dfCuts, left_on='Cut', right_on='id', how='left')
    del dfCuts
    dfSerials.drop(inplace=True, columns=['id','Cut'])
    dfSerials.rename(inplace=True, columns={'NoOfPlies':'Quantity'})

    return dfSerials

def applyWorkerFilter(df: DataFrame, worker: str):
    if worker:
        worker = int(worker)
        df = df[df['WorkerCode']==worker]
    return df

def GetWorkSummary(startDate, endDate, worker:str):
    dfScan = getScanData(startDate, endDate)

    dfScan['ValidWork'] = dfScan['SMV'] * dfScan['Quantity'] / 60
    dfScan['Wage'] = dfScan['Rate'] * dfScan['Quantity']

    dfScan = dfScan.groupby(['WorkerCode', 'WorkerName','Section'])[['ValidWork', 'Wage']].sum().reset_index()

    dfScan['Color'] = where(dfScan['ValidWork']<6, theme['red'],
                               where(dfScan['ValidWork']>10, theme['redSecondary'], theme['green']))

    dfScan = applyWorkerFilter(dfScan, worker)

    return dfScan.to_dict(orient='list')

def GetScanTable(startDate, endDate, worker: str):
    dfScan = getScanData(startDate, endDate)

    dfScan['TimeDate'] = dfScan['TimeDate'].astype('datetime64[ns, UTC]')
    dfScan['Day'] = dfScan['TimeDate'].dt.tz_convert(generic_services.LOCAL_TIMEZONE).dt.date

    dfScan['ValidWork'] = dfScan['SMV'] * dfScan['Quantity'] / 60
    dfScan['Wage'] = dfScan['Rate'] * dfScan['Quantity']

    dfScan = dfScan.groupby(
        ['OperationCode', 'WorkerCode', 'WorkerName','Section','SectionCode','OperationName','SMV','Rate','WorkOrder','Day']
    )[['Quantity','ValidWork', 'Wage']].sum().reset_index()
    
    dfScan = applyWorkerFilter(dfScan, worker)
    
    return generic_services.dfToListOfDicts(dfScan.head(15))

def GetWageSummary(startDate, endDate, worker):
    dfScan = getScanData(startDate, endDate)

    dfScan['Wage'] = dfScan['Rate'] * dfScan['Quantity']

    dfScan = dfScan.groupby(['WorkerCode', 'WorkerName'])[['Wage']].sum().reset_index()
    print(dfScan)

    dfScan = applyWorkerFilter(dfScan, worker)

    return dfScan.to_dict(orient='list')