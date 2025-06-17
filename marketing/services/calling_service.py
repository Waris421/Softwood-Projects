import pandas as pd

from datetime import date

from django.contrib.auth.models import User

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
    calls = models.Call.objects.filter(Date__range=(startDate, endDate))
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