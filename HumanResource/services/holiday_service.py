import pandas as pd
from typing import Dict

from django.db.models import Q

from HumanResource import models
from core.services.generic_services import dfToListOfDicts, convertStrToDateTime

def GetDataForHolidayDefine():
    fields = ['Name', 'FullName']
    departments = models.Department.objects.all().values(*fields)
    dfDepartments = pd.DataFrame(departments) if departments else pd.DataFrame(columns=fields)
    del departments

    dfDepartments.rename(inplace=True, columns={'Name': 'value', 'FullName': 'label'})

    results =  {
        'departments': dfToListOfDicts(dfDepartments),
    }

    return results

def GetDataForOffSaturday(employeeCode: str|None) -> Dict[str, any]:
    if employeeCode:
        try:
            offSaturday = models.OffSaturday.objects.get(Employee=employeeCode).OffSaturdayDate
        except:
            offSaturday = None
        return {
            'offSaturday': offSaturday,
            'employees': [],
        }
    else:
        fields = ['id', 'WorkerName', 'Department']
        employees = models.Employee.objects.exclude(Status='Left').values(*fields)
        dfEmployees = pd.DataFrame(employees) if employees else pd.DataFrame(columns=fields)
        del employees

        dfEmployees['WorkerName'] = dfEmployees['WorkerName'] + ' (' + dfEmployees['Department'] + ')'
        dfEmployees.drop(inplace=True, columns=['Department'])

        dfEmployees.rename(inplace=True, columns={'id': 'value', 'WorkerName': 'label'})

        return {
            'offSaturday': None,
            'employees': dfToListOfDicts(dfEmployees),
        } 

def AddHoliday(data: Dict[str, any]):
    #Convert the date strings to objects
    tasks = [
        (['StartDate', 'EndDate'], '%Y-%m-%d', 'date'),
    ]
    for keys, format, attribute in tasks:
        for key in keys:
            dateTimeObj = convertStrToDateTime(data[key], format)
            data[key] = getattr(dateTimeObj, attribute)()
    
    departments, startDate, endDate, description = (
        data.get(k) for k in ['Departments', 'StartDate', 'EndDate', 'Description']
    )
    
    newHolidays = []

    for department in departments:
        try:
            department = models.Department.objects.get(Name=department)
        except:
            raise LookupError(f'Invalid Department: {department}')
        
        alreadyExistingFlag = models.Holiday.objects.filter(
            Department=department,
            StartDate__lte=endDate,
            EndDate__gte=startDate
        ).exists()

        if alreadyExistingFlag:
            raise ValueError(f'There is an existing holiday in this time frame for: {department.FullName}')

        holiday = models.Holiday(
            Department = department,
            StartDate = startDate,
            EndDate = endDate,
            Description = description,
        )
        newHolidays.append(holiday)

    models.Holiday.objects.bulk_create(newHolidays)

def DefineOffSaturday(data: Dict[str, str]):
    saturdayDate = convertStrToDateTime(data['OffSaturday'], '%Y-%m-%d').date()
    
    try:
        previouslyOffSaturday = models.OffSaturday.objects.get(Employee=data['Employee'])
    except models.OffSaturday.DoesNotExist:
        previouslyOffSaturday = None
    except:
        raise SystemError('Settings Issue. Check with Administrator')
    
    if previouslyOffSaturday:
        offSaturday = previouslyOffSaturday
        offSaturday.OffSaturdayDate = saturdayDate
    else:
        try:
            employee = models.Employee.objects.get(id=data['Employee'])
        except:
            raise LookupError('Could not find any employee')
        
        offSaturday = models.OffSaturday(
            Employee=employee,
            OffSaturdayDate=saturdayDate
        )
    
    offSaturday.save()