from typing import Dict
from datetime import date

from django.shortcuts import get_object_or_404
from django.forms.models import model_to_dict

from HumanResource import models
from core.services.generic_services import convertStrToDateTime

def verifyEmployeeAccess(user: models.User, employeeId: int|str|None) -> models.Employee:
    # Get the employee from the user, if it exists
    requestEmployee = getattr(user, 'employeeUser', None)
    
    # Check if the user has admin rights
    isAdmin = user.is_staff or user.is_superuser

    if employeeId:
        #Admin can add correction for anyone, without needing an employee coard
        if isAdmin:
            return get_object_or_404(models.Employee, id=employeeId)
        
        # Non-admins must have an employee card and it must match the ID
        if not requestEmployee:
            raise PermissionError("You are not a registered employee.")

        #Employee card from user must match with one from request
        if str(requestEmployee.id) != str(employeeId):
            raise PermissionError("You do not have permission to access another employee's data.")        
        
        return requestEmployee
    
    if not requestEmployee:
        raise PermissionError("You are not a registered employee.")
    
    return requestEmployee

def getDataForAdjustment(employee: models.Employee, date: date):
    result = {}
    try:
        attendance = models.Attendance.objects.get(Employee=employee, TimeDate__date=date)
        result['attendance'] = model_to_dict(attendance)
    except:
        attendance = None

    addedAdjustment = models.AttendanceAdjustmentHeader.objects.filter(
        Header__Employee=employee,
        Date=date
    )

    for adjustment in addedAdjustment:
        print(adjustment)
    
    return result

def GetDataForCorrection(user: models.User, data: Dict[str, str]):
    targetEmployeeId = data.pop('employee', None)
    try:
        employee = verifyEmployeeAccess(user, targetEmployeeId)
    except Exception as e:
        raise Exception(str(e))
    
    type = data.pop('type', None)
    if not type:
        raise ValueError('Pleae specify a correction type')
    
    date = data.pop('date', None)
    if not date:
        raise ValueError('Please specify an attendance date')
    date = convertStrToDateTime(date, "%Y-%m-%d")
    if not date:
        raise ValueError('Please provide a valid date')
    
    match type:
        case 'adjustment':
            formData = getDataForAdjustment(employee, date.date())
        case 'leave':
            print(type)
            raise NotImplementedError('Under Construction')
        case 'travel':
            print(type)
            raise NotImplementedError('Under Construction')
        case 'over-time':
            print('type')
            raise NotImplementedError('Under Construction')
        case _:
            raise ValueError('Invalid Correction type')

    return formData