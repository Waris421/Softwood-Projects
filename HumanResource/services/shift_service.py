from datetime import timedelta
from typing import Dict
import pandas as pd

from django.db.models import Q
from django.db import transaction

from HumanResource import models
from core.services.generic_services import convertStrToDateTime, dfToListOfDicts

def GetDataForShiftUpdate(department: str|None):
    fields = ['Name', 'FullName']
    departments = models.Department.objects.all().values(*fields)
    dfDepartments = pd.DataFrame(departments) if departments else pd.DataFrame(columns=fields)
    del departments

    dfDepartments.rename(inplace=True, columns={'Name': 'value', 'FullName': 'label'})

    fields = ['id', 'WorkerName']
    if department:
        employees = models.Employee.objects.filter(Department = department).values(*fields)        
        dfEmployees = pd.DataFrame(employees) if employees else pd.DataFrame(columns=fields)
        del employees, fields
    else:
        dfEmployees = pd.DataFrame(columns=fields)
    
    dfEmployees.rename(inplace=True, columns={'id': 'value', 'WorkerName': 'label'})
    
    results =  {
        'departments': dfToListOfDicts(dfDepartments),
        'employees': dfToListOfDicts(dfEmployees),
    }

    return results

def UpdateShift(data: Dict[str, any]):
    #Convert the date and time strings to objects
    tasks = [
        (['StartDate', 'EndDate'], '%Y-%m-%d', 'date'),
        (['StartTime', 'EndTime'], '%H:%M', 'time')
    ]

    for keys, format, attribute in tasks:
        for key in keys:
            dateTimeObj = convertStrToDateTime(data[key], format)
            data[key] = getattr(dateTimeObj, attribute)()
    
    employees = data['Employees']
    startDate = data['StartDate']
    endDate = data['EndDate']
    startTime = data['StartTime']
    endTime = data['EndTime']

    #Fetch the previously added shits, with no ending dates, set them their new ending dates
    filters = (Q(EndDate__isnull=True) | Q(EndDate__gt=startDate)) & Q(Employee__in=employees)
    previousShifts = models.WorkingShift.objects.filter(filters)
    endDateForPreviousShifts = startDate - timedelta(days=1)
    
    with transaction.atomic():
        previousShifts.update(EndDate=endDateForPreviousShifts)

        newShifts = []
        for employeeId in employees:
            try:
                employee = models.Employee.objects.get(id=employeeId)
            except:
                raise ValueError(f'Invalid employee with code {employeeId}')

            shift = models.WorkingShift(
                Employee=employee,
                StartDate=startDate,
                EndDate=endDate,
                StartTime=startTime,
                EndTime=endTime
            )
            newShifts.append(shift)

        models.WorkingShift.objects.bulk_create(newShifts)