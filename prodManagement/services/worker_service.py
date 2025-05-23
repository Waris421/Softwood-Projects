import pandas as pd

from django.db.models import Q
from django.contrib.auth.models import User
from django.forms.models import model_to_dict

from typing import Dict

from .. import models
from . import generic_services

def calculateTimePassed(row: pd.Series):
    if row['YearsPassed'] > 0:
        return f"{row['YearsPassed']} years"
    elif row['MonthsPassed'] > 0:
        return f"{row['MonthsPassed']} months"
    else:
        return f"{row['DaysPassed']} days"

def AddWoker(data: Dict):
    if models.Worker.objects.filter(WorkerCode=data['WorkerCode']).exists():
        raise ValueError('Code Already Exists')
    
    data = {key: None if value == 'null' else value for key, value in data.items()}

    #Convert department and user from string to  object if is provided
    if data['Department']:
        data['Department'] = models.Department.objects.get(Name=data['Department'])
    if data['User']:
        data['User'] = User.objects.get(id=data['User'])

    worker = models.Worker(**data)
    worker.save()

    return worker.WorkerCode

def GetDataForWorker(worker: models.Worker):
    data = model_to_dict(worker)
    data['DateOfBirth'] = data['DateOfBirth'].strftime('%Y-%m-%d')

    data['DateOfJoining'] = worker.DateOfJoining.strftime('%Y-%m-%d')

    return data

def EditWorker(worker: models.Worker, data: Dict):
    data['Department'] = models.Department.objects.get(Name=data['Department'])
    try:
        for key, value in data.items():
            setattr(worker, key, value) 
        worker.save()
    except Exception as e:
        raise Exception(e)

def GetWorkers(department: str, status:str):
    filters = Q()
    if department:
        filters &= Q(Department=department)
    if status:
        filters &= Q(Status=status)
    
    fields = ['WorkerCode','WorkerName','Department','SubDepartment','DateOfJoining','Status']
    if filters:
        workers = models.Worker.objects.filter(filters).values(*fields)
    else:
        workers = models.Worker.objects.all().values(*fields)
    
    if workers:
        dfWorkers = pd.DataFrame(workers)
    else:
        dfWorkers = pd.DataFrame(columns=fields)
    del workers, fields

    dfSections = pd.DataFrame(generic_services.operationSections)

    dfWorkers = pd.merge(left=dfWorkers, right=dfSections, left_on='SubDepartment', right_on='value', how='left')
    del dfSections
    dfWorkers.drop(inplace=True, columns=['value', 'SubDepartment'])
    dfWorkers.rename(inplace=True, columns={'text':'Section'})

    #Calculate days/months/years passed since joining
    dfWorkers['DateOfJoining'] = pd.to_datetime(dfWorkers['DateOfJoining'], format='%Y-%m-%d')
    dfWorkers['TimePassed'] = pd.to_timedelta(generic_services.NOW.date() - dfWorkers['DateOfJoining'].dt.date)
    dfWorkers['DaysPassed']  = dfWorkers['TimePassed'].dt.days
    dfWorkers['MonthsPassed'] = (dfWorkers['DaysPassed'] / 30.44).round().astype(int)
    dfWorkers['YearsPassed'] = (dfWorkers['DaysPassed'] / 365.25).round().astype(int)
    dfWorkers['TimePassed'] = dfWorkers.apply(calculateTimePassed, axis=1)

    dfWorkers.drop(inplace=True, columns=['DateOfJoining','DaysPassed','MonthsPassed','YearsPassed'])
    
    return generic_services.dfToListOfDicts(dfWorkers)

def AssignCardToWorker(cardId: int, workerCode: int):
    try:
        card = models.RFIDCard.objects.get(CardId=cardId)
    except:
        raise LookupError('Card not added in system')
    
    try:
        worker = models.Worker.objects.get(WorkerCode=workerCode)
    except:
        raise LookupError('Worker Code Not Found.')

    if card.GroupNumber:
        raise ValueError('This card is reserved for bundles.')

    try:
        previousAssignment = models.WorkerCardAssignment.objects.get(Worker=worker)
        previousAssignment.delete()
    except:
        pass

    models.WorkerCardAssignment(
        RFIDCard = card,
        Worker = worker
    ).save()