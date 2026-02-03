from typing import Dict
import pandas as pd
import numpy as np
from dateutil.relativedelta import relativedelta

from django.contrib.auth.models import User

from HumanResource import models
from core.services.generic_services import dfToListOfDicts, convertStrToDateTime, convertFullNametoNameParts
from core.constants.generic import EMPLOYEMENT_AGE_IN_YEARS, TODAY

def GetDataForEmployeeAddition():
    fields = ['Name', 'FullName']
    departments = models.Department.objects.all().values(*fields)
    dfDepartments = pd.DataFrame(departments) if departments else pd.DataFrame(columns=fields)
    del departments
    
    fields = ['id', 'WorkerName']
    managers = models.Employee.objects.all().values(*fields)
    dfManagers = pd.DataFrame(managers) if managers else pd.DataFrame(columns=fields)
    del managers, fields

    dfDepartments.rename(inplace=True, columns={'Name': 'value', 'FullName': 'label'})

    dfManagers.rename(inplace=True, columns={'id': 'value', 'WorkerName': 'label'})
    
    data = {
        'departments': dfToListOfDicts(dfDepartments),
        'managers': dfToListOfDicts(dfManagers),
    }

    return data

def AddEmployee(data: Dict[str, any]):
    dateOfBirth = convertStrToDateTime(data.pop('DateOfBirth'), '%Y-%m-%dT%H:%M:%S.%fZ')
    if not dateOfBirth:
        raise ValueError('Invalid Date of Birth')
    dateOfBirth = dateOfBirth.date()
    today = TODAY.date()
    age = relativedelta(today, dateOfBirth).years
    if age < EMPLOYEMENT_AGE_IN_YEARS:
        raise ValueError(f'Minimum age for employement is {EMPLOYEMENT_AGE_IN_YEARS} years')
    
    createAccountFlag = data.pop('CreateAccount')
    userName = data.pop('Username')
    email = data.pop('Email')
    if createAccountFlag:
        if User.objects.filter(username=userName).exists():
            raise ValueError('Username already exists')
        
        if User.objects.filter(email=email).exists():
            raise ValueError('Email already exists')
    
        firstname, _, lastname = convertFullNametoNameParts(data['Name'])

        user = User.objects.create(
            username=userName,
            email=email,
            first_name=firstname,
            last_name=lastname,
        )
    else:
        user = None
    
    data['WorkerName'] = data.pop('Name')
    data['FatherSpouseName'] = data.pop('FatherSpouse')
    data['DateOfBirth'] = dateOfBirth
    data['DateOfLeaving'] = None
    data['Status'] = 'Active'
    data['User'] = user

    data['Department'] = models.Department.objects.get(Name=data['Department'])
    if data['Manager']:
        data['Manager'] = models.Employee.objects.get(id=data['Manager'])
    else:
        data['Manager'] = None
    
    employee = models.Employee(**data)
    employee.save();

    return employee.id