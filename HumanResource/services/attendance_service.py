import pandas as pd
import numpy as np
from typing import Dict
import googlemaps
from datetime import date

from django.db.models import Q
from django.utils import timezone as TZ
from django.conf import settings

from HumanResource import models

from core.services.generic_services import dfToListOfDicts, calculateHaversineDistance, convertTexttoObject
from core.constants.generic import TODAY, LOCAL_TIMEZONE

def getLocation(lat: str|float, lon: str|float):
    '''
    Get the location from the coordinates, either from the offices locations or cached locations
    If no location is found, then create a new cached location and return that
    '''
    if pd.isna(lat) or pd.isna(lon):
        return None

    latitude, longitude = float(lat), float(lon)

    def findNearby(modelClass, radius=None):
        #22km radius circle
        roughMargin = 0.2

        querySet = modelClass.objects.filter(
            Latitude__range=(latitude - roughMargin, latitude + roughMargin),
            Longitude__range=(longitude - roughMargin, longitude + roughMargin)
        )

        for location in querySet:
            limit = float(location.Radius) if hasattr(location, 'Radius') else (radius or 0.1)
            dist = calculateHaversineDistance(longitude, latitude, float(location.Longitude), float(location.Latitude))
            if dist <= limit:
                return location

    #First check office location, then cached location
    result = findNearby(models.Location) or findNearby(models.CachedLocation, radius=0.1)
    
    if result:
        return result
    
    try:
        gmapsKey = settings.GMAPS_KEY
        client = googlemaps.Client (key=gmapsKey)
        reverseGeocodeResult = client.reverse_geocode((latitude, longitude))
    except Exception as e:
        raise BufferError(e)
    
    if not reverseGeocodeResult:
        raise LookupError('Could not find your location. Check your settings')
    
    # Find the most detailed address address
    locationName = max([r['formatted_address'] for r in reverseGeocodeResult], key=len)

    return models.CachedLocation.objects.create(
        LocationName=locationName,
        Latitude=latitude,
        Longitude=longitude,
    )

def expandAttendance(dfAttendance: pd.DataFrame, dfDateRange: pd.DataFrame, baseSchema: Dict[str, str]):
    '''
        Convert the log of attendance to a Login/Logout table format.
        Also gracefully handle cases of empty values and missing attendances
    '''
    anchorCols = {'Date', 'Type'}
    valueCols = [col for col in dfAttendance.columns if col not in anchorCols]
    attendanceTypes = ['In', 'Out']
    targetCols = [f'{t}{v}' for v in valueCols for t in attendanceTypes]
    
    if dfAttendance.empty:
        dfPivoted = pd.DataFrame(columns=['Date'] + targetCols)
        for v in valueCols:
            dtype = baseSchema.get(v, 'object')
            for t in attendanceTypes:
                dfPivoted[f'{t}{v}'] = dfPivoted[f'{t}{v}'].astype(dtype)
    else:
        dfPivoted = dfAttendance.pivot(index='Date', columns='Type', values=valueCols)
        dfPivoted.columns = dfPivoted.columns.swaplevel(0, 1).map("".join)
        dfPivoted = dfPivoted.reset_index()

    #map attendance for the given range of dates.
    dfResults = pd.merge(dfDateRange, dfPivoted, on='Date', how='left')

    typeMapping = {}
    for col in dfResults.columns:
        baseColName = col[2:] if (col.startswith('In') or col.startswith('Out')) else col
        if baseColName in baseSchema:
            typeMapping[col] = baseSchema[baseColName]
        elif col != 'Date':
            typeMapping[col] = 'object'
    return dfResults.astype(typeMapping)

def formulateShift(employee: models.Employee, startDate: str, endDate: str):
    '''
        Get the employee valid shifts in the given date range
    '''
    filters = (Q(Employee=employee) & Q(StartDate__lte=endDate) & (Q(EndDate__gte=startDate) | Q(EndDate__isnull=True)))
    fields = ['StartDate', 'EndDate', 'StartTime', 'EndTime']
    shifts = models.WorkingShift.objects.filter(filters).values(*fields)
    
    if not shifts:
        raise ValueError(f"No valid shifts defined between {startDate} and {endDate}. Check with HR")

    dfDateRanges = pd.DataFrame(shifts)
    del shifts
    

    #Assume the shift with no end date as the active shift. Rest are for past dates
    dfDateRanges['EndDate'] = dfDateRanges['EndDate'].fillna(endDate)

    #Pre-process Dates
    dfDateRanges['StartDate'] = pd.to_datetime(dfDateRanges['StartDate'])
    dfDateRanges['EndDate'] = pd.to_datetime(dfDateRanges['EndDate'])
    reqStart = pd.to_datetime(startDate).normalize()
    reqEnd = pd.to_datetime(endDate).normalize()

    #Clip shifts to the requested range
    dfDateRanges['StartDate'] = dfDateRanges['StartDate'].clip(lower=pd.to_datetime(startDate))
    dfDateRanges['EndDate'] = dfDateRanges['EndDate'].clip(upper=pd.to_datetime(endDate))
    dfDateRanges = dfDateRanges.sort_values('StartDate').copy()

    #If current StartDate < the latest EndDate seen so far, they overlap and should raise an error.
    overlaps = dfDateRanges['StartDate'] < dfDateRanges['EndDate'].shift(1).cummax()
    if overlaps.any():
        firstError = dfDateRanges[overlaps].iloc[0]['StartDate']
        raise ValueError(f"Shift Overlap detected. First conflict at {firstError.date()}")
    
    #The date range must start from the given start date
    if dfDateRanges['StartDate'].min() > pd.to_datetime(startDate):
        raise ValueError(f"No shift defined for {startDate}. Check with HR")

    #The range must end till the given end data
    if dfDateRanges['EndDate'].max() < pd.to_datetime(endDate):
        raise ValueError(f"No shift defined for {endDate}. Check with HR")
    
    #Check for any gaps in the date range of the shifts.
    prevEnd = dfDateRanges['EndDate'].shift(1)
    gaps = (dfDateRanges['StartDate'] > (prevEnd + pd.Timedelta(days=1)))
    if gaps.any():
        gapDate = prevEnd[gaps].iloc[0] + pd.Timedelta(days=1)
        raise ValueError(f"No shift defined for {gapDate.date()}. Check with HR")
    
    #Calculate duration of each shift in days
    dfDateRanges['Duration'] = (dfDateRanges['EndDate'] - dfDateRanges['StartDate']).dt.days + 1

    #Repeat rows based on duration
    dfShifts = dfDateRanges.loc[dfDateRanges.index.repeat(dfDateRanges['Duration'])].copy()

    #Calculate the individual dates
    dfShifts['Date'] = dfShifts['StartDate'] + pd.to_timedelta(dfShifts.groupby(level=0).cumcount(), unit='D')

    #Verify the total unique date count matches the requested date range length
    expectedDays = (reqEnd - reqStart).days + 1
    if dfShifts['Date'].nunique() != expectedDays:
        expectedRange = pd.date_range(start=reqStart, end=reqEnd)
        missingDates = expectedRange.difference(dfShifts['Date'])
        if not missingDates.empty:
            raise ValueError(f"No shift defined for {missingDates[0].date()}. Check with HR")

    dfShifts.drop(inplace=True, columns=['StartDate', 'EndDate', 'Duration'])
    dfShifts.rename(inplace=True, columns={'StartTime': 'StandardInTime', 'EndTime': 'StandardOutTime'})
    
    return dfShifts

def verifyAttendaceTimes(dfAttendance: pd.DataFrame, dfStandardTimes: pd.DataFrame):
    IN_TIME_ALLOWANCE_IN_MINUTES = 15
    OUT_TIME_ALLOWANCE_IN_MINUTES = 0
    today = pd.to_datetime(TODAY)

    df = pd.merge(dfAttendance, dfStandardTimes, on='Date', how='left', sort=False)
    
    #Sometimes merge may change the sequence of data. This ensures the data is in the same sequence as the input
    df = df.set_index(dfAttendance.index)

    def combineDateTime(dateCol, timeCol):
        combined = dateCol.astype(str) + ' ' + timeCol.astype(str)
        return pd.to_datetime(combined, errors='coerce')

    colsToConvert = ['StandardInTime', 'StandardOutTime', 'InTime', 'OutTime']
    for col in colsToConvert:
        df[col] = combineDateTime(df['Date'], df[col])

    df['InTimeDiff'] = (df['InTime'] - df['StandardInTime']).dt.total_seconds() / 60
    df['OutTimeDiff'] = (df['StandardOutTime'] - df['OutTime']).dt.total_seconds() / 60

    df['InTimeFlag'] = (df['InTimeDiff'] <= IN_TIME_ALLOWANCE_IN_MINUTES) | (df['InTime'].isna()) | (df['StandardInTime'].isna())
    df['OutTimeFlag'] = (df['OutTimeDiff'] <= OUT_TIME_ALLOWANCE_IN_MINUTES) | (df['OutTime'].isna()) | (df['StandardOutTime'].isna())

    isPastDate = df['Date'] < today
    df.loc[isPastDate & df['InTime'].isna(), 'InTimeFlag'] = False
    df.loc[isPastDate & df['OutTime'].isna(), 'OutTimeFlag'] = False

    df.drop(inplace=True, columns=['Date', 'InTime', 'OutTime', 'StandardInTime', 'StandardOutTime'])

    for col in['InTimeDiff', 'OutTimeDiff']:
        df[col] = df[col].fillna(0)
        df[col] = df[col].clip(lower=0)

    return df

def adjustWeekend(df: pd.DataFrame, offSaturday: date|None):
    isWeekend = df['Date'].dt.dayofweek == 6
    
    if offSaturday is not None:
        offSatDT = pd.to_datetime(offSaturday)
        daysDiff = (df['Date'] - offSatDT).dt.days
        isOffSaturday = (df['Date'].dt.dayofweek == 5) & (daysDiff % 14 == 0)
        isWeekend |= isOffSaturday
    
    return isWeekend
        
def adjustHolidays(dfAttendance: pd.DataFrame, dfHolidays: pd.DataFrame):
    if dfHolidays.empty:
        dfResults = dfAttendance.copy()

        dfResults['HolidayFlag'] = False
        dfResults['HolidayDetails'] = None

        return dfResults[['HolidayFlag', 'HolidayDetails']]

    dfHolidays['StartDate'] = pd.to_datetime(dfHolidays['StartDate'])
    dfHolidays['EndDate'] = pd.to_datetime(dfHolidays['EndDate'])

    dfHolidays = dfHolidays.sort_values('StartDate')

    dfResults = pd.merge_asof(
        dfAttendance.sort_values('Date'), 
        dfHolidays, 
        left_on='Date', 
        right_on='StartDate', 
        direction='backward'
    )

    isHoliday = (dfResults['Date'] >= dfResults['StartDate']) & (dfResults['Date'] <= dfResults['EndDate'])
    dfResults['HolidayFlag'] = isHoliday
    dfResults['HolidayDetails'] = dfResults['Description'].where(isHoliday, None) 
    
    return dfResults[['HolidayFlag', 'HolidayDetails']]

def adjustLoginTimeCorrections(dfAttendance: pd.DataFrame, employee: models.Employee):
    startDate = dfAttendance['Date'].min()
    endDate = dfAttendance['Date'].max()

    fields = [
        #From the main header
        'id',
        'Approval',
        'ManagerComments',
        
        #From the sub header
        'AttendanceAdjustmentInfo__Date',

        #From the actual table
        'AttendanceAdjustmentInfo__TimeAdjustmentInfo__InTimeAdjustmentInfo__InTime',
        'AttendanceAdjustmentInfo__TimeAdjustmentInfo__InTimeAdjustmentInfo__Reason',
    ]
    adjustments = models.AdjustmentHeader.objects.filter(
        Employee=employee,
        AttendanceAdjustmentInfo__Date__range=(startDate, endDate),
        AttendanceAdjustmentInfo__TimeAdjustmentInfo__InTimeAdjustmentInfo__isnull=False
    ).values(*fields)
    dfAdjustments = pd.DataFrame(adjustments) if adjustments else pd.DataFrame(columns=fields)
    del adjustments

    dfAdjustments.rename(inplace=True, columns={
        'AttendanceAdjustmentInfo__Date': 'Date',
        'id': 'InTimeAdjustmentId',
        'Approval': 'InTimeAdjustmentApproval',
        'ManagerComments': 'InTimeAdjustmentManagerComments',
        'AttendanceAdjustmentInfo__TimeAdjustmentInfo__InTimeAdjustmentInfo__InTime': 'InTimeRequested',
        'AttendanceAdjustmentInfo__TimeAdjustmentInfo__InTimeAdjustmentInfo__Reason': 'InTimeAdjustmentReason'
    })

    dfAdjustments["Date"] = pd.to_datetime(dfAdjustments["Date"])
    dfAttendance = pd.merge(dfAttendance, dfAdjustments, on="Date", how="left")
    del dfAdjustments

    dfAttendance["InTime"] = np.where(
        dfAttendance["InTimeAdjustmentApproval"] == True,
        dfAttendance["InTimeRequested"],
        dfAttendance["InTime"],
    )

    dfAttendance.drop(inplace=True, columns=['InTimeRequested'])

    return dfAttendance

def adjustLogoutTimeCorrections(dfAttendance: pd.DataFrame, employee: models.Employee):
    startDate = dfAttendance['Date'].min()
    endDate = dfAttendance['Date'].max()

    fields = [
        #From the main header
        'id',
        'Approval',
        'ManagerComments',
        
        #From the sub header
        'AttendanceAdjustmentInfo__Date',

        #From the actual table
        'AttendanceAdjustmentInfo__TimeAdjustmentInfo__OutTimeAdjustmentInfo__OutTime',
        'AttendanceAdjustmentInfo__TimeAdjustmentInfo__OutTimeAdjustmentInfo__Reason',
    ]
    adjustments = models.AdjustmentHeader.objects.filter(
        Employee=employee,
        AttendanceAdjustmentInfo__Date__range=(startDate, endDate),
        AttendanceAdjustmentInfo__TimeAdjustmentInfo__OutTimeAdjustmentInfo__isnull=False
    ).values(*fields)
    dfAdjustments = pd.DataFrame(adjustments) if adjustments else pd.DataFrame(columns=fields)
    del adjustments

    dfAdjustments.rename(inplace=True, columns={
        'AttendanceAdjustmentInfo__Date': 'Date',
        'id': 'OutTimeAdjustmentId',
        'Approval': 'OutTimeAdjustmentApproval',
        'ManagerComments': 'OutTimeAdjustmentManagerComments',
        'AttendanceAdjustmentInfo__TimeAdjustmentInfo__OutTimeAdjustmentInfo__OutTime': 'OutTimeRequested',
        'AttendanceAdjustmentInfo__TimeAdjustmentInfo__OutTimeAdjustmentInfo__Reason': 'OutTimeAdjustmentReason'
    })

    dfAdjustments["Date"] = pd.to_datetime(dfAdjustments["Date"])
    dfAttendance = pd.merge(dfAttendance, dfAdjustments, on="Date", how="left")
    del dfAdjustments

    dfAttendance["OutTime"] = np.where(
        dfAttendance["OutTimeAdjustmentApproval"] == True,
        dfAttendance["OutTimeRequested"],
        dfAttendance["OutTime"],
    )

    dfAttendance.drop(inplace=True, columns=['OutTimeRequested'])

    return dfAttendance

def adjustLoginLocationCorrection(dfAttendance: pd.DataFrame, employee: models.Employee):
    startDate = dfAttendance['Date'].min()
    endDate = dfAttendance['Date'].max()

    fields = [
        #From the main header
        'id',
        'Approval',
        'ManagerComments',
        
        #From the sub header
        'AttendanceAdjustmentInfo__Date',

        #From the actual table
        'AttendanceAdjustmentInfo__LocationAdjustmentInfo__InLocationAdjustmentInfo__InLocation',
        'AttendanceAdjustmentInfo__LocationAdjustmentInfo__InLocationAdjustmentInfo__Reason',
    ]
    adjustments = models.AdjustmentHeader.objects.filter(
        Employee=employee,
        AttendanceAdjustmentInfo__Date__range=(startDate, endDate),
        AttendanceAdjustmentInfo__LocationAdjustmentInfo__InLocationAdjustmentInfo__isnull=False
    ).values(*fields)
    dfAdjustments = pd.DataFrame(adjustments) if adjustments else pd.DataFrame(columns=fields)
    del adjustments

    dfAdjustments.rename(inplace=True, columns={
        'AttendanceAdjustmentInfo__Date': 'Date',
        'id': 'InLocationAdjustmentId',
        'Approval': 'InLocationAdjustmentApproval',
        'ManagerComments': 'InLocationAdjustmentManagerComments',
        'AttendanceAdjustmentInfo__LocationAdjustmentInfo__InLocationAdjustmentInfo__InLocation': 'InLocationRequested',
        'AttendanceAdjustmentInfo__LocationAdjustmentInfo__InLocationAdjustmentInfo__Reason': 'InLocationAdjustmentReason'
    })

    dfAdjustments["Date"] = pd.to_datetime(dfAdjustments["Date"])
    dfAttendance = pd.merge(dfAttendance, dfAdjustments, on="Date", how="left")
    del dfAdjustments

    dfAttendance.drop(inplace=True, columns=['InLocationRequested'])

    return dfAttendance

def adjustLogoutLocationCorrection(dfAttendance: pd.DataFrame, employee: models.Employee):
    startDate = dfAttendance['Date'].min()
    endDate = dfAttendance['Date'].max()
    
    fields = [
        #From the main header
        'id',
        'Approval',
        'ManagerComments',
        
        #From the sub header
        'AttendanceAdjustmentInfo__Date',

        #From the actual table
        'AttendanceAdjustmentInfo__LocationAdjustmentInfo__OutLocationAdjustmentInfo__OutLocation',
        'AttendanceAdjustmentInfo__LocationAdjustmentInfo__OutLocationAdjustmentInfo__Reason',
    ]
    adjustments = models.AdjustmentHeader.objects.filter(
        Employee=employee,
        AttendanceAdjustmentInfo__Date__range=(startDate, endDate),
        AttendanceAdjustmentInfo__LocationAdjustmentInfo__OutLocationAdjustmentInfo__isnull=False
    ).values(*fields)
    dfAdjustments = pd.DataFrame(adjustments) if adjustments else pd.DataFrame(columns=fields)
    del adjustments

    dfAdjustments.rename(inplace=True, columns={
        'AttendanceAdjustmentInfo__Date': 'Date',
        'id': 'OutLocationAdjustmentId',
        'Approval': 'OutLocationAdjustmentApproval',
        'ManagerComments': 'OutLocationAdjustmentManagerComments',
        'AttendanceAdjustmentInfo__LocationAdjustmentInfo__OutLocationAdjustmentInfo__OutLocation': 'OutLocationRequested',
        'AttendanceAdjustmentInfo__LocationAdjustmentInfo__OutLocationAdjustmentInfo__Reason': 'OutLocationAdjustmentReason'
    })
    dfAdjustments["Date"] = pd.to_datetime(dfAdjustments["Date"])
    dfAttendance = pd.merge(dfAttendance, dfAdjustments, on="Date", how="left")
    del dfAdjustments

    dfAttendance.drop(inplace=True, columns=['OutLocationRequested'])

    return dfAttendance

def adjustFullLeaves(dfAttendance: pd.DataFrame, employee: models.Employee):
    startDate = dfAttendance['Date'].min()
    endDate = dfAttendance['Date'].max()

    sickLeaveQuery = Q(LeaveInfo__SickLeaveInfo__StartDate__lte=endDate) & Q(LeaveInfo__SickLeaveInfo__EndDate__gte=startDate)
    casualLeaveQuery = Q(LeaveInfo__CasualLeaveInfo__StartDate__lte=endDate) & Q(LeaveInfo__CasualLeaveInfo__EndDate__gte=startDate)
    annualLeaveQuery = Q(LeaveInfo__AnnualLeaveInfo__StartDate__lte=endDate) & Q(LeaveInfo__AnnualLeaveInfo__EndDate__gte=startDate)   

    fields = [
        'id',
        'Approval',
        'ManagerComments',

        'LeaveInfo__LeaveType',

        'LeaveInfo__SickLeaveInfo__StartDate',
        'LeaveInfo__SickLeaveInfo__EndDate',

        'LeaveInfo__CasualLeaveInfo__StartDate',
        'LeaveInfo__CasualLeaveInfo__EndDate',
        'LeaveInfo__CasualLeaveInfo__Reason',

        'LeaveInfo__AnnualLeaveInfo__StartDate',
        'LeaveInfo__AnnualLeaveInfo__EndDate',
        'LeaveInfo__AnnualLeaveInfo__Reason',
    ]
    leaves = models.AdjustmentHeader.objects.filter(
        sickLeaveQuery | casualLeaveQuery | annualLeaveQuery
    ).values(*fields)
    dfLeaves = pd.DataFrame(leaves) if leaves else pd.DataFrame(columns=fields)
    del leaves

    dfLeaves.rename(inplace=True, columns={
        'id': 'LeaveAdjustmentId',
        'Approval': 'LeaveAdjustmentApproval',
        'ManagerComments': 'LeaveAdjustmentManagerComments',
        'LeaveInfo__LeaveType': 'LeaveType',
        'LeaveInfo__SickLeaveInfo__StartDate': 'SickLeaveStartDate',
        'LeaveInfo__SickLeaveInfo__EndDate': 'SickLeaveEndDate',
        'LeaveInfo__CasualLeaveInfo__StartDate': 'CasualLeaveStartDate',
        'LeaveInfo__CasualLeaveInfo__EndDate': 'CasualLeaveEndDate',
        'LeaveInfo__CasualLeaveInfo__Reason': 'CasualLeaveReason',
        'LeaveInfo__AnnualLeaveInfo__StartDate': 'AnnualLeaveStartDate',
        'LeaveInfo__AnnualLeaveInfo__EndDate': 'AnnualLeaveEndDate',
        'LeaveInfo__AnnualLeaveInfo__Reason': 'AnnualLeaveReason',
    })

    #Melt all the leave types into a long date by date schedule
    commonCols = ['LeaveAdjustmentId', 'LeaveType', 'LeaveAdjustmentApproval', 'LeaveAdjustmentManagerComments']

    startDates = dfLeaves.melt(
        id_vars=commonCols,
        value_vars=['SickLeaveStartDate', 'CasualLeaveStartDate', 'AnnualLeaveStartDate'],
        var_name='LeaveAdjustmentType',
        value_name='StartDate'
    )
    endDates = dfLeaves.melt(
        id_vars=commonCols,
        value_vars=['SickLeaveEndDate', 'CasualLeaveEndDate', 'AnnualLeaveEndDate'],
        var_name='LeaveAdjustmentType',
        value_name='EndDate'
    )

    startDates['LeaveAdjustmentType'] = startDates['LeaveAdjustmentType'].str.replace('StartDate', '')
    endDates['LeaveAdjustmentType'] = endDates['LeaveAdjustmentType'].str.replace('EndDate', '')
    
    dfLeaves = pd.merge(startDates, endDates, on=commonCols + ['LeaveAdjustmentType'])
    del startDates, endDates

    dfLeaves = dfLeaves.dropna(subset=['StartDate'])

    dfLeaves['StartDate'] = pd.to_datetime(dfLeaves['StartDate'])
    dfLeaves['EndDate'] = pd.to_datetime(dfLeaves['EndDate'])

    dfLeaves['Date'] = [
        pd.date_range(start, end) for start, end in zip(dfLeaves['StartDate'], dfLeaves['EndDate'])
    ]
    dfLeaves = dfLeaves.explode('Date')

    dfLeaves = dfLeaves[[
        'Date',
        'LeaveAdjustmentId',
        'LeaveType',
        'LeaveAdjustmentApproval',
        'LeaveAdjustmentManagerComments',
    ]].reset_index(drop=True)

    dfAttendance = pd.merge(dfAttendance, dfLeaves, on="Date", how="left")
    del dfLeaves

    dfAttendance['LeaveFlag'] = (dfAttendance['LeaveAdjustmentApproval'] == True)

    return dfAttendance

def markAbsentism(dfAttendance: pd.DataFrame):
    absentFlag = (
        dfAttendance['InTime'].isna() & 
        dfAttendance['OutTime'].isna() & 
        (dfAttendance['WeekendFlag'] == False) & 
        (dfAttendance['HolidayFlag'] == False) &
        (dfAttendance['Date'].dt.date < TODAY.date())
    )
    return absentFlag

def GetAttendance(employee: models.Employee, startDate: str, endDate: str):
    dateRange = pd.date_range(start=startDate, end=endDate)
    dfDateRange = pd.DataFrame({'Date': dateRange})

    filters = Q(TimeDate__date__range=(startDate, endDate)) & Q(Employee=employee)
    attSchema = {
        'TimeDate': 'datetime64[ns, UTC]',
        'Type': 'string',
        'Latitude': 'float64',
        'Longitude': 'float64',
        'Details': 'string'
    }
    attendance = list(models.Attendance.objects.filter(filters).values(*attSchema.keys()))
    dfAttendance = pd.DataFrame(attendance) if attendance else pd.DataFrame(columns=attSchema.keys()).astype(attSchema)
    del attendance

    assignedLocations = models.Location.objects.filter(locationassignment__Employee=employee).distinct()

    dfShifts = formulateShift(employee, startDate,endDate)

    try:
        offSaturday = models.OffSaturday.objects.get(Employee=employee).OffSaturdayDate
    except:
        offSaturday = None

    schema = {
        'StartDate': 'datetime64[ns, UTC]',
        'EndDate': 'datetime64[ns, UTC]',
        'Description': 'string',
    }
    filters = Q(StartDate__lte=endDate) & Q(EndDate__gte=startDate) & Q(Department=employee.Department)
    holidays = models.Holiday.objects.filter(filters).values(*schema.keys())
    dfHolidays = pd.DataFrame(holidays) if holidays else pd.DataFrame(columns=schema.keys()).astype(schema)
    del holidays, filters, schema

    #Separate the date and time from datetime.
    dfAttendance['TimeDate'] = dfAttendance['TimeDate'].dt.tz_convert(LOCAL_TIMEZONE)
    dfAttendance['Date'] = pd.to_datetime(dfAttendance['TimeDate'].dt.date)
    dfAttendance['Time'] = dfAttendance['TimeDate'].dt.time
    dfAttendance.drop(inplace=True, columns=['TimeDate'])

    #Make sure the first lates of in/out is capitalised
    dfAttendance['Type'] = dfAttendance['Type'].str.capitalize()
    
    #Vectorize the get location function, this reduces over head for large number of rows
    vectorizedGetLocation = np.vectorize(getLocation, otypes=[models.Location])
    dfAttendance['Location'] = vectorizedGetLocation(dfAttendance['Latitude'], dfAttendance['Longitude'])
    dfAttendance['LocationFlag'] = dfAttendance['Location'].isin(assignedLocations)
    del assignedLocations

    #Convert attendance log to separate cols and all rows in the date range
    dfResults = expandAttendance(dfAttendance, dfDateRange, attSchema)
    del dfAttendance, dfDateRange

    #Apply Adjustments
    dfResults[['Date', 'InTime', 'InTimeAdjustmentId', 'InTimeAdjustmentApproval', 'InTimeAdjustmentManagerComments', 'InTimeAdjustmentReason']] = adjustLoginTimeCorrections(dfResults[['Date', 'InTime']], employee)
    dfResults[['Date', 'OutTime', 'OutTimeAdjustmentId', 'OutTimeAdjustmentApproval', 'OutTimeAdjustmentManagerComments', 'OutTimeAdjustmentReason']] = adjustLogoutTimeCorrections(dfResults[['Date', 'OutTime']], employee)
    dfResults[['Date', 'InLocation', 'InLocationAdjustmentId', 'InLocationAdjustmentApproval', 'InLocationAdjustmentManagerComments', 'InLocationAdjustmentReason']] = adjustLoginLocationCorrection(dfResults[['Date', 'InLocation']], employee)
    dfResults[['Date', 'OutLocation', 'OutLocationAdjustmentId', 'OutLocationAdjustmentApproval', 'OutLocationAdjustmentManagerComments', 'OutLocationAdjustmentReason']] = adjustLogoutLocationCorrection(dfResults[['Date', 'OutLocation']], employee)


    #Check the login/logout times and share any descripancies
    dfResults[['InTimeDiff', 'OutTimeDiff', 'InTimeFlag', 'OutTimeFlag']] = verifyAttendaceTimes(dfResults[['Date', 'InTime', 'OutTime']], dfShifts)

    #Apply leaves data
    dfResults[['Date', 'FullLeaveAdjustmentId', 'FullLeaveType', 'FullLeaveAdjustmentApproval', 'FullLeaveAdjustmentManagerComments', 'FullLeaveFlag']] = adjustFullLeaves(dfResults[['Date']], employee)

    #Add the flag for weekends and off saturdays
    dfResults['WeekendFlag'] = adjustWeekend(dfResults, offSaturday)
    del offSaturday

    dfResults[['HolidayFlag', 'HolidayDetails']] = adjustHolidays(dfResults, dfHolidays)

    #TODO: Take adjustments in to account

    dfResults['AbsentFlag'] = markAbsentism(dfResults)
    
    #Data formatting for front end
    locationCols = ['InLocation', 'OutLocation']
    for col in locationCols:
        dfResults[col] = [
            location.LocationName if pd.notna(location) else None
            for location in dfResults[col]
        ]
    
    timeCols = ['InTime', 'OutTime']
    for col in timeCols:
        #For the data from app
        tempDt = pd.to_datetime(dfResults[col], format='%H:%M:%S.%f', errors='coerce')
        
        #For the data from machines
        tempDt = tempDt.fillna(pd.to_datetime(dfResults[col], format='%H:%M:%S', errors='coerce'))
        
        #Format the time to AM/PM format
        dfResults[col] = tempDt.dt.strftime('%I:%M %p')

    return dfToListOfDicts(dfResults)

def VerifyAttendance(employee: models.Employee, data: Dict[str, str]):
    attendanceType = data.get('Type')
    latitude = data.get('Latitude')
    longitude = data.get('Longitude')

    if None in (attendanceType, latitude, longitude):
        raise ValueError('Invalid Data')
    
    if attendanceType not in ['in', 'out']:
        raise ValueError('Invalid data')

    filters = Q(Employee=employee) & Q(Type=attendanceType) & Q(TimeDate__date=TODAY)
    existingAttendance = models.Attendance.objects.filter(filters).first()
    if existingAttendance:
        attendanceTime = TZ.localtime(existingAttendance.TimeDate).strftime("%I:%M %p")
        raise ValueError(f"You already have marked your attendance for today at: {attendanceTime}")
    
    location = getLocation(latitude, longitude)
    
    locationFlag = False
    if isinstance(location, models.Location):
        assignedLocations = models.LocationAssignment.objects.filter(Employee=employee).values_list('Location', flat=True)
        
        if location.id in assignedLocations:
            locationFlag = True

    return {
        'Location': location.LocationName,
        'Validity': locationFlag,
        'Latitude': latitude,
        'Longitude': longitude,
        'Type': attendanceType
    }

def AddAttendance(employee: models.Employee, data: Dict[str, str]):
    attendanceType = data.get('Type')
    latitude = data.get('Latitude')
    longitude = data.get('Longitude')
    details = data.get('Details')

    if None in (attendanceType, latitude, longitude, details):
        raise ValueError('Invalid Data')
    
    if attendanceType not in ['in', 'out']:
        raise ValueError('Invalid data')

    attendance = models.Attendance(
        Employee=employee,
        Type=attendanceType,
        Latitude=latitude,
        Longitude= longitude,
        Details= details,
    )

    attendance.save()