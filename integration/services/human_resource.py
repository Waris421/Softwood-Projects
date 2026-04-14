import pandas as pd
from typing import Dict, List
import json

from django.db.models import Q
from django.db import transaction

from integration import models
from core.constants.generic import LOCAL_TIMEZONE
from core.services.generic_services import convertTexttoObject

def AddAttendanceFromMachines(location: models.Location, data: List[Dict[str, str]]):
    dfData = pd.DataFrame(json.loads(data))

    #Standardize and Clean
    dfData['TimeDate'] = pd.to_datetime(dfData['Date'] + ' ' + dfData['Time']).dt.tz_localize(LOCAL_TIMEZONE)
    dfData['Employee'] = convertTexttoObject(models.Employee, dfData['EmployeeCode'], 'id')
    dfData = dfData[~dfData['Employee'].isna()]
    dfData['Date'] = pd.to_datetime(dfData['Date']).dt.date

    #Fetch Existing Attendance
    fields = ['Employee', 'Type', 'TimeDate__date']
    filters = Q(Employee__in=dfData['Employee'].unique(), TimeDate__date__in=dfData['Date'].unique())
    existingAttendance = models.Attendance.objects.filter(filters).values(*fields)
    dfExistingAttendance = pd.DataFrame(existingAttendance) if existingAttendance else pd.DataFrame(columns=fields)
    del existingAttendance

    #Get the dataframes ready for merge
    dfExistingAttendance.rename(inplace=True, columns={'TimeDate__date': 'Date', 'Employee': 'EmployeeCode'})
    dfData['EmployeeCode'] = dfData['EmployeeCode'].astype(int)

    if not dfExistingAttendance.empty:
        dfData = pd.merge(left=dfData, right=dfExistingAttendance, on=['EmployeeCode', 'Type', 'Date'], how='left', indicator=True)

        # Keep only the rows that were 'left_only' (not found in existing)
        dfData = dfData[dfData['_merge'] == 'left_only'].drop(columns=['_merge'])
    
    if dfData.empty:
        return
    
    dfData.drop(inplace=True, columns=['EmployeeCode', 'Date', 'Time'])

    #Setting up the fixed values
    dfData[['Latitude', 'Longitude']] = location.Latitude, location.Longitude
    dfData['Details'] = 'From Machine'

    newAttendances = []
    for _, row in dfData.iterrows():
        attendance = models.Attendance(**row)

        newAttendances.append(attendance)
    
    with transaction.atomic():
        models.Attendance.objects.bulk_create(newAttendances)