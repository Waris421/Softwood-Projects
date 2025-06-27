from pandas import DataFrame, merge, to_datetime
from numpy import where

from typing import List, Union

from django.db.models import Q

from .. import models
from ..theme import theme
from core.services import generic_services
from core.constants import prod as prodConstants
from core.constants import generic as genericConnstants

def getScanData(
        startDate = None,
        endDate = None
) -> DataFrame:
    '''
    Generic function to retreive scanning data from database.
    Returns data for today if date range isn't given
    '''
    if not startDate:
        startDate = genericConnstants.TODAY
    if not endDate:
        endDate = genericConnstants.TODAY
    
    fields = ['Worker','Operation','Bundle','TimeDate', 'Line']
    serials = models.Serial.objects.filter(TimeDate__date__range=(startDate, endDate)).values(*fields)
    if serials:
        dfSerials = DataFrame(serials)
    else:
        dfSerials = DataFrame(columns=fields)
        dfSerials['TimeDate'] = to_datetime(dfSerials['TimeDate'], utc=True)
    del serials

    fields = ['WorkerCode','WorkerName','SubDepartment']
    workers = models.Worker.objects.filter(WorkerCode__in=dfSerials['Worker'].to_list()).values(*fields)
    if workers:
        dfWorkers = DataFrame(workers)
    else:
        dfWorkers = DataFrame(columns=fields)
    del workers

    dfLines = DataFrame(prodConstants.stitchingLines)
    dfSections = DataFrame(prodConstants.operationSections)

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

    dfSerials = merge(left=dfSerials, right=dfLines, left_on='Line', right_on='value', how='left')
    del dfLines
    dfSerials.drop(inplace=True, columns=['Line','value'])
    dfSerials.rename(inplace=True, columns={'text':'Line'})

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

    dfSerials['TimeDate'] = dfSerials['TimeDate'].dt.tz_convert(genericConnstants.LOCAL_TIMEZONE)

    return dfSerials

def getAttendanceData(workers: Union[str, List[str]], startDate=None, endDate=None):
    if not startDate:
        startDate = generic_services.TODAY
    if not endDate:
        endDate = generic_services.TODAY

    if isinstance(workers, str):
        filters = Q(Worker=workers)
    elif isinstance(workers, list):
        filters = Q(Worker__in=workers)
    else:
        filters = Q()
    
    fields = ['Worker','Date','LoginTime','LogoutTime']
    attendance = models.Attendance.objects.filter(Date__range=(startDate, endDate)).filter(filters).values(*fields)
    if attendance:
        dfAttendance = DataFrame(attendance)
    else:
        dfAttendance = DataFrame(columns=fields)
    del attendance

    dfAttendance['LoginTime'] = to_datetime(dfAttendance['Date'].astype(str) + ' ' + dfAttendance['LoginTime'].astype(str))
    dfAttendance['LogoutTime'] = to_datetime(dfAttendance['Date'].astype(str) + ' ' + dfAttendance['LogoutTime'].astype(str))

    dfAttendance['Duration'] = dfAttendance['LogoutTime']-dfAttendance['LoginTime']
    dfAttendance['Duration'] = dfAttendance['Duration'].dt.total_seconds()/(60*60)

    dfAttendance['LoginTime'] = dfAttendance['LoginTime'].dt.time
    dfAttendance['LogoutTime'] = dfAttendance['LogoutTime'].dt.time
    
    return dfAttendance

def applyWorkerFilter(df: DataFrame, worker: str, workerCol='WorkerCode'):
    worker = None if worker in ['', 'null', 'None'] else worker

    if worker:
        worker = int(worker)
        df = df[df[workerCol]==worker]
    return df

def applyOverTimeFilter(df: DataFrame, overTime: str, dateTimeCol='TimeDate'):
    #Convert overtime string to boolean. Use None if no filtering is required
    overTimeMapping = {'true': True, 'false': False}
    overTime = overTimeMapping.get(overTime)

    dutyStartTime = prodConstants.STITCHING_START
    dutyEndTime = prodConstants.STITCHING_END

    if overTime is True:
        condition = (df[dateTimeCol].dt.time < dutyStartTime) | (df[dateTimeCol].dt.time > dutyEndTime)
        df = df[condition]
    elif overTime is False:
        condition = (df[dateTimeCol].dt.time >= dutyStartTime) & (df[dateTimeCol].dt.time <= dutyEndTime)
        df = df[condition]

    return df

def applyWorkOrderFilter(df: DataFrame, workOrder: str, workOrderCol='WorkOrder'):
    workOrder = None if workOrder in ['', 'null', 'None'] else workOrder

    if workOrder:
        workOrder = int(workOrder)
        df = df[df[workOrderCol]==workOrder]

    return df

def applyLineFilter(df: DataFrame, line: str, lineCol='Line'):
    line = None if line in ['', 'null', 'None'] else line

    if line:
        df = df[df[lineCol]==line]

    return df

def applySectionFilter(df: DataFrame, section: str, sectionCol='SectionCode'):
    section = None if section in ['', 'null', 'None'] else section

    if section:
        df = df[df[sectionCol]==section]

    return df

def applyOperationFilter(df: DataFrame, operation: str, operationCol='OperationCode'):
    operation = None if operation in ['null', 'None'] else operation
    
    if operation:
        operation = int(operation)
        df = df[df[operationCol]==operation]

    return df

def GetWorkSummary(
        startDate, endDate, worker:str, overTime: str, line: str, section: str, workOrder: str, operation: str
):
    dfScan = getScanData(startDate, endDate)

    #Apply the filters
    filters = [
        (applyWorkerFilter, worker),
        (applyOverTimeFilter, overTime),
        (applyLineFilter, line),
        (applySectionFilter, section),
        (applyWorkOrderFilter, workOrder),
        (applyOperationFilter, operation),
    ]
    for func, filter in filters:
        dfScan = func(dfScan, filter)

    dfScan['ValidWork'] = dfScan['SMV'] * dfScan['Quantity'] / 60
    dfScan['Wage'] = dfScan['Rate'] * dfScan['Quantity']

    dfScan = dfScan.groupby(['WorkerCode', 'WorkerName','Section'])[['ValidWork', 'Wage']].sum().reset_index()

    dfScan['Color'] = where(dfScan['ValidWork']<6, theme['red'],
                               where(dfScan['ValidWork']>10, theme['redSecondary'], theme['green']))

    return dfScan.to_dict(orient='list')

def GetScanTable(
        startDate, endDate, worker: str, overTime: str, line: str, section: str, workOrder: str, operation: str
):
    dfScan = getScanData(startDate, endDate)

    #Apply the filters
    filters = [
        (applyWorkerFilter, worker),
        (applyOverTimeFilter, overTime),
        (applyLineFilter, line),
        (applySectionFilter, section),
        (applyWorkOrderFilter, workOrder),
        (applyOperationFilter, operation),
    ]
    for func, filter in filters:
        dfScan = func(dfScan, filter)

    dfScan['Day'] = dfScan['TimeDate'].dt.date

    dfScan['ValidWork'] = dfScan['SMV'] * dfScan['Quantity'] / 60
    dfScan['Wage'] = dfScan['Rate'] * dfScan['Quantity']

    dfScan = dfScan.groupby(
        ['OperationCode', 'WorkerCode', 'WorkerName', 'Line','Section','SectionCode','OperationName','SMV','Rate','WorkOrder','Day']
    )[['Quantity','ValidWork', 'Wage']].sum().reset_index()
    
    return generic_services.dfToListOfDicts(dfScan.head(15))

def GetWageSummary(
        startDate, endDate, worker: str, overTime: str, line: str, section: str, workOrder: str, operation: str
):
    dfScan = getScanData(startDate, endDate)
    #Apply the filters
    filters = [
        (applyWorkerFilter, worker),
        (applyOverTimeFilter, overTime),
        (applyLineFilter, line),
        (applySectionFilter, section),
        (applyWorkOrderFilter, workOrder),
        (applyOperationFilter, operation),
    ]
    for func, filter in filters:
        dfScan = func(dfScan, filter)

    dfScan['Wage'] = dfScan['Rate'] * dfScan['Quantity']

    dfScan['Day'] = dfScan['TimeDate'].dt.date

    dfScan = dfScan.groupby(['WorkerCode', 'WorkerName']).agg(
        Wage=('Wage', 'sum'),
        Days=('Day', 'nunique')
    ).reset_index()

    dfScan['WagePerDay'] = dfScan['Wage']/dfScan['Days']
    
    dfScan['WageColor'] = where(dfScan['WagePerDay']<genericConnstants.MIN_WAGE, theme['red'], theme['green'])
    dfScan['TimeSpentColor'] = where(dfScan['WagePerDay']<genericConnstants.MIN_WAGE, theme['red'], theme['green'])
    
    dfScan.sort_values(inplace=True, by='WagePerDay', ascending=True)
    dfScan.drop(inplace=True, columns=['WagePerDay'])

    return dfScan.to_dict(orient='list')

def GetAttendanceDetail(
        startDate, endDate, worker: str, line: str, section: str
):
    fields = ['WorkerCode','WorkerName','SubDepartment']
    if worker and worker != 'null':
        dfAttendance = getAttendanceData(worker, startDate, endDate)
        worker = models.Worker.objects.filter(WorkerCode=worker).values(*fields)
        if worker:
            dfWorkers = DataFrame(worker)
        else:
            dfWorkers = DataFrame(columns=fields)
    else:
        workers = models.Worker.objects.filter(Status='Working').values(*fields)
        if workers:
            dfWorkers = DataFrame(workers)
        else:
            dfWorkers = DataFrame(columns=fields)
        del workers
        
        dfAttendance = getAttendanceData(dfWorkers['WorkerCode'].to_list(), startDate, endDate)

    dfSections = DataFrame(prodConstants.operationSections)
    
    dfAttendance = merge(left=dfAttendance, right=dfWorkers, left_on='Worker', right_on='WorkerCode', how='left')
    del dfWorkers
    dfAttendance.drop(inplace=True, columns=['Worker'])
    
    dfAttendance = merge(left=dfAttendance, right=dfSections, left_on='SubDepartment', right_on='value', how='left')
    del dfSections
    dfAttendance.drop(inplace=True, columns=['SubDepartment'])
    dfAttendance.rename(inplace=True, columns={'text':'Section','value':'SectionCode'})

    filters = [
        (applyLineFilter, line),
        (applySectionFilter, section),
    ]
    for func, filter in filters:
        dfAttendance = func(dfAttendance, filter)

    dfAttendance['LoginTime'] = to_datetime(str(startDate.date())+' '+dfAttendance['LoginTime'].astype(str), format='%Y-%m-%d %H:%M:%S')
    dfAttendance['LogoutTime'] = to_datetime(str(startDate.date())+' '+dfAttendance['LogoutTime'].astype(str), format='%Y-%m-%d %H:%M:%S')
    dfAttendance['StandardLoginTime'] = to_datetime(str(startDate.date())+' '+str(prodConstants.STITCHING_START), format='%Y-%m-%d %H:%M:%S')
    dfAttendance['StandardLogoutTime'] = to_datetime(str(startDate.date())+' '+str(prodConstants.STITCHING_END), format='%Y-%m-%d %H:%M:%S')

    dfAttendance['LoginDelay'] = (dfAttendance['LoginTime'] - dfAttendance['StandardLoginTime']).dt.total_seconds()/3600
    dfAttendance['LogoutEarly'] = (dfAttendance['StandardLogoutTime'] - dfAttendance['LogoutTime']).dt.total_seconds()/3600

    dfAttendance['LoginDelay'] = where(dfAttendance['LoginDelay']>0,dfAttendance['LoginDelay'], 0)
    dfAttendance['LogoutEarly'] = where(dfAttendance['LogoutEarly']>0,dfAttendance['LogoutEarly'], 0)

    dfAttendance['Late'] = (dfAttendance['LoginDelay'] + dfAttendance['LogoutEarly'])

    dfAttendance.drop(inplace=True, columns=['LoginDelay','LogoutEarly','StandardLoginTime','StandardLogoutTime'])

    for col in ['LoginTime', 'LogoutTime']:
        dfAttendance[col] = dfAttendance[col].dt.time
    
    dfAttendance['DurationColor'] = where(dfAttendance['Late']>0, theme['red'], theme['green'])

    return dfAttendance.to_dict(orient='list')