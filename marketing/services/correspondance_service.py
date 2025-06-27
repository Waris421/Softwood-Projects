import pandas as pd

from datetime import date

from django.contrib.auth.models import User
from django.db.models import Q

from .. import models
from core.services.generic_services import askAI, dfToListOfDicts, updateModelWithDF

def GetCallHistory(startDateText: str, endDateText: str, customerFilter: str, user: User):
    if startDateText:
        startDate = date.fromisoformat(startDateText)
    else:
        startDate = date.today()
    
    if endDateText:
        endDate = date.fromisoformat(endDateText)
    else:
        endDate = date.today()
    
    fields = ['id','Caller','Customer','Date','Conversation']
    calls = models.Correspondance.objects.filter(Date__range=(startDate, endDate))
    if customerFilter:
        calls = calls.filter(Customer=customerFilter)
    calls = calls.values(*fields)
    
    if calls:
        dfCalls = pd.DataFrame(calls)
    else:
        dfCalls = pd.DataFrame(columns=fields)
    del calls,fields

    fields = ['id', 'Name']
    customers = models.Customer.objects.filter(AccountManager=user).filter(id__in=dfCalls['Customer'].to_list()).values(*fields)
    if customers:
        dfCustomers = pd.DataFrame(customers)
    else:
        dfCustomers = pd.DataFrame(columns=fields)
    del customers, fields

    fields = ['id', 'first_name']
    callers = User.objects.filter(id__in=dfCalls['Caller'].to_list()).values(*fields)
    if callers:
        dfCallers = pd.DataFrame(callers)
    else:
        dfCallers = pd.DataFrame(columns=fields)
    del callers, fields

    print(dfCallers)

def GetPendingCorrespondance(customer: str, type:str, dueDateText:str, user:User):
    if dueDateText:
        dueDate = date.fromisoformat(dueDateText)
    else:
        dueDate = date.today()
    
    filters = Q(NextCorrespondanceDate__lte=dueDate) & Q(IsClosed=False)
    if customer:
        filters &= Q(Customer=customer)
    if type:
        filters &= Q(Type=type)
    fields = ['id','Name']
    customers = models.Customer.objects.filter(AccountManager=user).values(*fields)
    if customers:
        dfCustomers = pd.DataFrame(customers)
    else:
        dfCustomers = pd.DataFrame(columns=fields)
    del customers

    fields = ['User','Customer','Type','Date','Conversation']
    correspondances = models.Correspondance.objects.filter(filters).values(*fields)
    if correspondances:
        dfCorrespondances = pd.DataFrame(correspondances)
    else:
        dfCorrespondances = pd.DataFrame(columns=fields)
    del correspondances

    fields = ['id','first_name', 'last_name']
    users = User.objects.filter(id__in=dfCorrespondances['User'].to_list()).values(*fields)
    if users:
        dfUsers = pd.DataFrame(users)
    else:
        dfUsers = pd.DataFrame(columns=fields)
    del users

    fields = ['id','Name']
    customers = models.Customer.objects.filter(id__in=dfCorrespondances['Customer'].to_list()).values(*fields)
    if customers:
        dfCustomers = pd.DataFrame(customers)
    else:
        dfCustomers = pd.DataFrame(columns=fields)
    del customers
    
    dfCorrespondances = pd.merge(left=dfCorrespondances, right=dfUsers, left_on='User', right_on='id', how='left')
    del dfUsers
    dfCorrespondances.drop(inplace=True, columns=['User','id'])
    dfCorrespondances['User'] = dfCorrespondances['first_name']+' '+dfCorrespondances['last_name']
    dfCorrespondances.drop(inplace=True, columns=['first_name', 'last_name'])

    dfCorrespondances = pd.merge(left=dfCorrespondances, right=dfCustomers, left_on='Customer', right_on='id', how='left')
    del dfCustomers
    dfCorrespondances.drop(inplace=True, columns=['Customer','id'])

    print(dfCorrespondances)