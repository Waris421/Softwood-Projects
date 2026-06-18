from typing import Any, Dict
from datetime import date, datetime, time, timedelta

from django.shortcuts import get_object_or_404
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from HumanResource import models
from HumanResource.services.attendance_service import getLocation
from core.services.generic_services import convertStrToDateTime
from core.constants.generic import LOCAL_TIMEZONE

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

def getDataForAdjustment(employee: models.Employee, referenceDate: date):
    fields = ['TimeDate', 'Type', 'Latitude', 'Longitude', 'Details']
    attendance = models.Attendance.objects.filter(Employee=employee, TimeDate__date=referenceDate).values(*fields)

    addedAdjustment = models.AttendanceAdjustmentHeader.objects.filter(
        Header__Employee=employee,
        Date=referenceDate
    )

    filters = Q(Employee=employee) & Q(StartDate__lte=referenceDate) & (Q(EndDate__gte=referenceDate) | Q(EndDate__isnull=True))
    
    try:
        activeShift = models.WorkingShift.objects.get(filters)
    except models.WorkingShift.DoesNotExist:
        raise ValueError(f"No active shift found for employee on {referenceDate}.")
    except models.WorkingShift.MultipleObjectsReturned:
        raise LookupError("Multiple active shifts found for this date. Data integrity issue.")
    
    assignedLocations = set(
        models.LocationAssignment.objects.filter(Employee=employee)
        .values_list('Location', flat=True)
    )

    #TODO: Merge adjustment with attendance

    IN_TIME_ALLOWANCE = timedelta(minutes=15)
    result = {}
    
    shiftStartDt = timezone.make_aware(datetime.combine(referenceDate, activeShift.StartTime), LOCAL_TIMEZONE)
    shiftEndDt = timezone.make_aware(datetime.combine(referenceDate, activeShift.EndTime), LOCAL_TIMEZONE)
    allowedStartDt = shiftStartDt + IN_TIME_ALLOWANCE
    
    presentAttendanceTypes = set()

    for attData in attendance:
        attType = attData['Type']
        presentAttendanceTypes.add(attType)
        
        localDatetime = attData['TimeDate'].astimezone(LOCAL_TIMEZONE)

        if attType == 'In':
            attData['TimeFlag'] = localDatetime > allowedStartDt
        else:
            attData['TimeFlag'] = localDatetime < shiftEndDt
        
        location = getLocation(attData['Latitude'], attData['Longitude'])
        isValidLocation = isinstance(location, models.Location) and location.id in assignedLocations
        
        result.update({
            f"{attType}TimeFlag": attData['TimeFlag'],
            f"{attType}LocationFlag": not(isValidLocation),
            f"{attType}Location": location.LocationName if isinstance(location, models.Location) else None,
            f"{attType}Latitude": attData['Latitude'],
            f"{attType}Longitude": attData['Longitude'],
            f"{attType}Details": attData['Details'],
            f"{attType}Time": localDatetime.strftime("%I:%M %p"),
        })
    
    #Handle Missing Attendances
    expectedTypes = ['In', 'Out']
    for attType in expectedTypes:
        if attType not in presentAttendanceTypes:
            result.update({
                f"{attType}TimeFlag": True,
                f"{attType}LocationFlag": True,
                f"{attType}Location": None,
                f"{attType}Latitude": None,
                f"{attType}Longitude": None,
                f"{attType}Details": "Missing punch record",
                f"{attType}Time": None,
            })
    
    return result

def getDataForLeave(employee:models.Employee, referenceDate: date):
    fields = ['TimeDate', 'Type', 'Details']
    attendance = models.Attendance.objects.filter(Employee=employee, TimeDate__date=referenceDate).values(*fields)

    addedAdjustment = models.AttendanceAdjustmentHeader.objects.filter(
        Header__Employee=employee,
        Date=referenceDate
    )

    addedLeaves = models.AdjustmentHeader.objects.filter(
        Employee=employee
    ).filter(
        # Check Sick Leaves
        Q(
            LeaveInfo__SickLeaveInfo__StartDate__lte=referenceDate,
            LeaveInfo__SickLeaveInfo__EndDate__gte=referenceDate
        ) | 
        # Check Casual Leaves
        Q(
            LeaveInfo__CasualLeaveInfo__StartDate__lte=referenceDate,
            LeaveInfo__CasualLeaveInfo__EndDate__gte=referenceDate
        ) | 
        # Check Annual Leaves
        Q(
            LeaveInfo__AnnualLeaveInfo__StartDate__lte=referenceDate,
            LeaveInfo__AnnualLeaveInfo__EndDate__gte=referenceDate
        ) | 
        # Check Short Leaves (ShortLeave uses DateTime, so we extract the date)
        Q(
            LeaveInfo__ShortLeaveInfo__StartDateTime__date=referenceDate
        )
    ).select_related(
        'LeaveInfo', 
        'LeaveInfo__SickLeaveInfo', 
        'LeaveInfo__CasualLeaveInfo', 
        'LeaveInfo__AnnualLeaveInfo', 
        'LeaveInfo__ShortLeaveInfo'
    ).distinct()

    #TODO: Merge leaves and adjustments with attendance
    
    allowAbleOptions = [
        {'value': 'CPL', 'label': 'Avail CPL'}
    ]
    leavesRange = {'from': referenceDate, 'to': None}
    if attendance:
        #TODO: make this more customised by comparing with employee's time
        allowAbleOptions.extend([
            {'value': 'HCL', 'label': 'Half Casual Leave'},
            {'value': 'HSL', 'label': 'Half Sick Leave'},
            {'value': 'SHL', 'label': 'Short Leave'},
        ])
    else:
        allowAbleOptions.extend([
            {'value': 'FCL', 'label': 'Full Casual Leave'},
            {'value': 'FSL', 'label': 'Full Sick Leave'},
            {'value': 'AL', 'label': 'Annual Leave'},
        ])
        
        #TODO: make this more dynamic based on the attendances before and after the date
        leavesRange['to'] = referenceDate
    
    return {
        'AllowableOptions': allowAbleOptions,
        'LeavesRange': leavesRange,
        'LeaveDate': leavesRange['from']
    }

def getDataForTravel(employee: models.Employee, referenceDate: date):
    fields = ['TimeDate', 'Type', 'Details']
    attendance = models.Attendance.objects.filter(Employee=employee, TimeDate__date=referenceDate).values(*fields)
    
    addedAdjustment = models.AttendanceAdjustmentHeader.objects.filter(
        Header__Employee=employee,
        Date=referenceDate
    )

    addedLeaves = models.AdjustmentHeader.objects.filter(
        Employee=employee
    ).filter(
        # Check Sick Leaves
        Q(
            LeaveInfo__SickLeaveInfo__StartDate__lte=referenceDate,
            LeaveInfo__SickLeaveInfo__EndDate__gte=referenceDate
        ) | 
        # Check Casual Leaves
        Q(
            LeaveInfo__CasualLeaveInfo__StartDate__lte=referenceDate,
            LeaveInfo__CasualLeaveInfo__EndDate__gte=referenceDate
        ) | 
        # Check Annual Leaves
        Q(
            LeaveInfo__AnnualLeaveInfo__StartDate__lte=referenceDate,
            LeaveInfo__AnnualLeaveInfo__EndDate__gte=referenceDate
        ) | 
        # Check Short Leaves (ShortLeave uses DateTime, so we extract the date)
        Q(
            LeaveInfo__ShortLeaveInfo__StartDateTime__date=referenceDate
        )
    ).select_related(
        'LeaveInfo', 
        'LeaveInfo__SickLeaveInfo', 
        'LeaveInfo__CasualLeaveInfo', 
        'LeaveInfo__AnnualLeaveInfo', 
        'LeaveInfo__ShortLeaveInfo'
    ).distinct()

    #TODO: Merge leaves and adjustments with attendance

    leavesRange = {'from': referenceDate, 'to': None}
    if not attendance:        
        #TODO: make this more dynamic based on the attendances before and after the date
        leavesRange['to'] = referenceDate

    return {
        'TravelDateRange': leavesRange
    }

def getDataForOverTime(employee:models.Employee, referenceDate: date):
    fields = ['TimeDate', 'Type']
    attendance = models.Attendance.objects.filter(Employee=employee, TimeDate__date=referenceDate).values(*fields)

    addedAdjustment = models.AttendanceAdjustmentHeader.objects.filter(
        Header__Employee=employee,
        Date=referenceDate
    )

    filters = Q(Employee=employee) & Q(StartDate__lte=referenceDate) & (Q(EndDate__gte=referenceDate) | Q(EndDate__isnull=True))
    
    try:
        activeShift = models.WorkingShift.objects.get(filters)
    except models.WorkingShift.DoesNotExist:
        raise ValueError(f"No active shift found for employee on {referenceDate}.")
    except models.WorkingShift.MultipleObjectsReturned:
        raise LookupError("Multiple active shifts found for this date. Data integrity issue.")
    
    shiftStartDt = timezone.make_aware(datetime.combine(referenceDate, activeShift.StartTime), LOCAL_TIMEZONE)
    shiftEndDt = timezone.make_aware(datetime.combine(referenceDate, activeShift.EndTime), LOCAL_TIMEZONE)
    
    loginTime = None
    logoutTime = None

    for attData in attendance:
        if attData['Type'] == 'In':
            loginTime = attData['TimeDate']
        else:
            logoutTime = attData['TimeDate']
    
    if not loginTime or not logoutTime:
        raise ValueError('Missing Login or Logout time')  
    
    loginTime = loginTime.astimezone(LOCAL_TIMEZONE)
    logoutTime = logoutTime.astimezone(LOCAL_TIMEZONE)

    totalWork = logoutTime - loginTime
    shiftDuration = shiftEndDt - shiftStartDt
    
    overTime = 0
    if totalWork > shiftDuration:
        overTime = (totalWork - shiftDuration).total_seconds() / 3600
    
    overTime = round(overTime, 2)

    return {
        'OverTimeDuration': overTime
    }

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
    date = convertStrToDateTime(date, "%d/%m/%Y")
    if not date:
        raise ValueError('Please provide a valid date')
    
    match type:
        case 'adjustment':
            formData = getDataForAdjustment(employee, date.date())
        case 'leave':
            formData = getDataForLeave(employee, date.date())
        case 'travel':
            formData = getDataForTravel(employee, date.date())
        case 'over-time':
            formData = getDataForOverTime(employee, date.date())
        case _:
            raise ValueError('Invalid Correction type')

    return formData

def addAdjustment(employee: models.Employee, adjustmentDate: date, data: Dict[str, Any]):
    dataToCorrect = {}
    for key, value in data.items():
        if key.endswith('Flag') and value is True:
            baseKey = key.replace('Flag', '')
            reasonKey = baseKey + 'Reason'

            dataToCorrect[baseKey] = {
                baseKey: data.get(baseKey),
                reasonKey: data.get(reasonKey)
            }

    with transaction.atomic():
        for key, value in dataToCorrect.items():
            adjHeader = models.AdjustmentHeader.objects.create(
                Employee = employee,
                Type = 'Attendance',
                Approval = None,
                ManagerComments = None
            )

            if key.endswith('Location'):
                attAdjHeader = models.AttendanceAdjustmentHeader.objects.create(
                    Header = adjHeader,
                    AdjustmentType = 'Location',
                    Date = adjustmentDate
                )
                
                locAdjHeader = models.LocationAdjustmentHeader.objects.create(
                    Header=attAdjHeader,
                    LocationType=key
                )
                if key.startswith('In'):
                    models.InLocationAdjustment.objects.create(
                        Header = locAdjHeader,
                        InLocation = value['InLocation'],
                        Reason = value['InLocationReason']
                    )
                else:
                    models.OutLocationAdjustment.objects.create(
                        Header = locAdjHeader,
                        OutLocation = value['OutLocation'],
                        Reason = value['OutLocationReason']
                    )
            else:
                attAdjHeader = models.AttendanceAdjustmentHeader.objects.create(
                    Header = adjHeader,
                    AdjustmentType = 'Time',
                    Date = adjustmentDate
                )

                attTimeAdjHeader = models.TimeAdjustmentHeader.objects.create(
                    Header = attAdjHeader,
                    TimeType = key
                )

                if key.startswith('In'):
                    models.InTimeAdjustment.objects.create(
                        Header = attTimeAdjHeader,
                        InTime = value['InTime'],
                        Reason = value['InTimeReason'],
                    )
                else:
                    models.OutTimeAdjustment.objects.create(
                        Header = attTimeAdjHeader,
                        OutTime = value['OutTime'],
                        Reason = value['OutTimeReason'],
                    )

def addLeave(
    employee: models.Employee, startDate: date|None, endDate: date|None,
    leaveType: str|None, reason: str,
    shlStartTime: time|None, shlDuration: int
):
    if startDate is None or leaveType is None:
        raise ValueError('Incomplete data: Start date and Leave Type are required.')
    
    if leaveType in ['FSL', 'FCL', 'AL'] and endDate is None:
        raise ValueError('Incomplete data: End date is required for this leave type.')
    
    if leaveType in ['FCL', 'SHL', 'HCL', 'AL'] and not reason:
        raise ValueError('Incomplete data: Reason is required for this leave type.')
    
    #Remove any end date if user added it mistakenly for half day leaves
    if leaveType in ['HSL', 'HCL']:
        endDate = None
    
    if leaveType == 'SHL':
        if shlStartTime is None or shlDuration is None:
            raise ValueError('InComplete data')

        if shlDuration < 0:
            raise ValueError('Invalid Duration')
        
        if shlDuration > 120:
            raise ValueError('Invalid Duration')

    #No errors in the data
    with transaction.atomic():
        adjHeader = models.AdjustmentHeader.objects.create(
            Employee = employee,
            Type = 'Leave',
            Approval = None,
            ManagerComments = None
        )

        leaveAdjHeader = models.LeaveAdjustmentHeader.objects.create(
            Header=adjHeader,
            LeaveType=leaveType,
        )

        if leaveType in ['FSL', 'HSL']:
            models.SickLeaveAdjustment.objects.create(
                Header=leaveAdjHeader,
                StartDate=startDate,
                EndDate=endDate
            )

        elif leaveType in ['FCL', 'HCL']:        
            models.CasualLeaveAdjustment.objects.create(
                Header=leaveAdjHeader,
                StartDate=startDate,
                EndDate=endDate,
                Reason=reason,
            )
        
        elif leaveType == 'AL':
            leaveDuration = (endDate - startDate).days + 1

            if (leaveDuration % 6) != 0:
                raise ValueError('Annual leaves must be multiple of 6 days')
            
            models.AnnualLeaveAdjustment.objects.create(
                Header=leaveAdjHeader,
                StartDate=startDate,
                EndDate=endDate,
                Reason=reason,
            )
        elif leaveType == 'SHL':
            print(shlStartTime)
            raise NotImplementedError('Under Construction')
        else:        
            raise NotImplementedError('Under Construction')

def AddCorrection(user: models.User, data: Dict[str, Any]):
    targetEmployeeId = data.pop('employee', None)
    try:
        employee = verifyEmployeeAccess(user, targetEmployeeId)
    except Exception as e:
        raise Exception(str(e))
    
    correctionType = data.pop('CorrectionType', None)
    if not correctionType:
        raise ValueError('Please specify a correction type')
    
    match correctionType:
        case 'adjustment':
            adjustmentDate = data.pop('Date', None)
            adjustmentDate = convertStrToDateTime(adjustmentDate, "%d/%m/%Y")
            addAdjustment(employee, adjustmentDate.date(), data)
        case 'leave':
            leaveDateRange = data.pop('LeavesRange', None)
            leaveType = data.pop('SelectedLeaveType', None)
            leaveReason = data.pop('LeaveReason', None)
            leaveDate = data.pop('LeaveDate', None)
            shlStartTime = data.pop('SHLStartTime', None)
            shlDuration = data.pop('SHLDuration', 0)
            
            leaveStartDate = leaveDateRange['from']
            if leaveType in ['HSL', 'HCL', 'SHL']:
                leaveStartDate = leaveDate

            leaveStartDate = convertStrToDateTime(leaveStartDate, "%Y-%m-%d")
            leaveEndDate = convertStrToDateTime(leaveDateRange['to'], "%Y-%m-%d")
            shlStartTime = convertStrToDateTime(shlStartTime, "%H:%M")

            leaveStartDate = leaveStartDate.date() if leaveStartDate else None
            leaveEndDate = leaveEndDate.date() if leaveEndDate else None
            shlStartTime = shlStartTime.time() if shlStartTime else None
            addLeave(employee, leaveStartDate, leaveEndDate, leaveType, leaveReason, shlStartTime, shlDuration)
        case 'travel':
            print(data)
            raise NotImplementedError('Under Construction')
        case 'over-time':
            print(data)
            raise NotImplementedError('Under Construction')
        case _:
            raise ValueError('Invalid Correction type')
    
def GetDataForAdjustmentUpdate(user: models.User, adjustment: models.AttendanceAdjustmentHeader):
    if adjustment.Header.Approval is not None:
        raise PermissionError('This resource is already closed')

    verifyEmployeeAccess(user, adjustment.Header.Employee.id)

    result = {
        'Date': adjustment.Date.strftime("%d/%m/%Y")
    }
    
    
    timeAdjustment = getattr(adjustment, 'TimeAdjustmentInfo', None)
    locationAdjustment = getattr(adjustment, 'LocationAdjustmentInfo', None)

    if timeAdjustment:
        inTime: models.InTimeAdjustment = getattr(timeAdjustment, 'InTimeAdjustmentInfo', None)
        outTime: models.OutTimeAdjustment = getattr(timeAdjustment, 'OutTimeAdjustmentInfo', None)

        if inTime:
            result.update({
                'Time': inTime.InTime.strftime("%H:%M"),
                'Reason': inTime.Reason
            })
        
        elif outTime:
            result.update({
                'Time': outTime.OutTime.strftime("%H:%M"),
                'Reason': outTime.Reason
            })
        else:
            raise ValueError('Invalid adjustment')
    elif locationAdjustment:
        inLoc: models.InLocationAdjustment = getattr(locationAdjustment, 'InLocationAdjustmentInfo', None)
        outLoc: models.OutLocationAdjustment = getattr(locationAdjustment, 'OutLocationAdjustmentInfo', None)

        if inLoc:
            result.update({
                'Location': inLoc.InLocation,
                'Reason': inLoc.Reason,
            })
        elif outLoc:
            result.update({
                'Location': outLoc.OutLocation,
                'Reason': outLoc.Reason
            })
        else:
            raise ValueError('Invalid adjustment')
    else:
        raise ValueError('Invalid adjustment')
    
    return result

def UpdateAdjustment(user: models.User, adjustment: models.AttendanceAdjustmentHeader, data: Dict[str, str]):
    if adjustment.Header.Approval is not None:
        raise PermissionError('This resource is already closed')
    
    verifyEmployeeAccess(user, adjustment.Header.Employee.id)

    timeAdjustment = getattr(adjustment, 'TimeAdjustmentInfo', None)
    locationAdjustment = getattr(adjustment, 'LocationAdjustmentInfo', None)
    
    updatedReason = data.get('Reason')

    if timeAdjustment:
        inTime: models.InTimeAdjustment = getattr(timeAdjustment, 'InTimeAdjustmentInfo', None)
        outTime: models.OutTimeAdjustment = getattr(timeAdjustment, 'OutTimeAdjustmentInfo', None)
        
        updatedTime = datetime.strptime(data.get('Time'), "%H:%M").time()

        if inTime:
            inTime.InTime = updatedTime
            inTime.Reason = updatedReason
            inTime.save()
        elif outTime:
            outTime.OutTime = updatedTime
            outTime.Reason = updatedReason
            outTime.save()
        else:
            raise ValueError('Invalid adjustment')
    elif locationAdjustment:
        inLoc: models.InLocationAdjustment = getattr(locationAdjustment, 'InLocationAdjustmentInfo', None)
        outLoc: models.OutLocationAdjustment = getattr(locationAdjustment, 'OutLocationAdjustmentInfo', None)

        updatedLocation = data.get('Location')

        if inLoc:
            inLoc.InLocation = updatedLocation
            inLoc.Reason = updatedReason
            inLoc.save()
        elif outLoc:
            outLoc.OutLocation = updatedLocation
            outLoc.Reason = updatedReason
            outLoc.save()
        else:
            raise ValueError('Invalid adjustment')
    else:
        raise ValueError('Invalid adjustment')