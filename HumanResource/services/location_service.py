import pandas as pd
from typing import Dict

from django.forms import model_to_dict
from django.db.models import Q

from HumanResource import models
from core.services.generic_services import calculateHaversineDistance, dfToListOfDicts, updateModelWithDF, convertTexttoObject

def GetOffices():
    fields = ['id', 'LocationName', 'Latitude', 'Longitude', 'Radius']
    locations = models.Location.objects.all().values(*fields)
    dfLocations = pd.DataFrame(locations) if locations else pd.DataFrame(columns=fields)
    del locations

    fields = ['Employee', 'Location']
    assignments = models.LocationAssignment.objects.filter(Location__in=dfLocations['id'].to_list()).values(*fields)
    dfAssignments = pd.DataFrame(assignments) if assignments else pd.DataFrame(columns=fields)
    del assignments, fields

    dfAssignments.rename(inplace=True, columns={'Location': 'id'})
    counts = dfAssignments['id'].value_counts().rename('Employees')
    dfLocations['Employees'] = dfLocations['id'].map(counts).fillna(0).astype(int)
    del dfAssignments, counts
    
    return dfToListOfDicts(dfLocations)

def AddOffice(data: Dict[str, str]):
    location = data.pop('Location')

    latitude, longitude = [float(x.strip()) for x in location.split(',')]

    precision = 4
    latitude = round(latitude, precision)
    longitude = round(longitude, precision)

    data['Latitude'] = latitude
    data['Longitude'] = longitude

    #1 degree is approx 111km
    radius = float(data['Radius'])
    radiusDegrees = radius / 111.0
    existingLocations = models.Location.objects.filter(
        Latitude__range=(latitude - radiusDegrees, latitude + radiusDegrees),
        Longitude__range=(longitude - radiusDegrees, longitude + radiusDegrees)
    )
    
    for loc in existingLocations:
        distance = calculateHaversineDistance(longitude, latitude, loc.Longitude, loc.Latitude)
        if distance <= radius:
            raise ValueError(f'Location already exists with name: {loc.LocationName}')
    
    location = models.Location(**data)
    location.save()

def GetDataForOfficeUpdate(office: models.Location):
    return model_to_dict(office)

def updateOffice(office: models.Location, data: Dict[str, str]):
    location = data.pop('Location')

    latitude, longitude = [float(x.strip()) for x in location.split(',')]

    precision = 4
    latitude = round(latitude, precision)
    longitude = round(longitude, precision)

    data['Latitude'] = latitude
    data['Longitude'] = longitude

    #1 degree is approx 111km
    radius = float(data['Radius'])
    radiusDegrees = radius / 111.0
    existingLocations = models.Location.objects.filter(
        Latitude__range=(latitude - radiusDegrees, latitude + radiusDegrees),
        Longitude__range=(longitude - radiusDegrees, longitude + radiusDegrees)
    ).exclude(id=office.id)
    
    for loc in existingLocations:
        distance = calculateHaversineDistance(longitude, latitude, loc.Longitude, loc.Latitude)
        if distance <= radius:
            raise ValueError(f'Location already exists with name: {loc.LocationName}')
    
    #Update the office
    for key, value in data.items():
        if hasattr(office, key):
            print(f'{key}: {value}')
    office.save()

def GetDataForOfficeAssign(managerId: models.User, employeeCode: str|None):
    filters = Q()
    if not managerId.is_staff:
        manager = models.Employee.objects.get(User=managerId)
        filters &= Q(Manager=manager)
    fields = ['id', 'WorkerName', 'Department']
    employees = models.Employee.objects.filter(filters).values(*fields)
    dfEmployees = pd.DataFrame(employees) if employees else pd.DataFrame(columns=fields)
    del employees

    fields = ['id', 'LocationName']
    allOffices = models.Location.objects.all().values(*fields)
    dfAllOffices = pd.DataFrame(allOffices) if allOffices else pd.DataFrame(columns=fields)
    del allOffices, fields

    assignedOffices = []
    if employeeCode:
        fields = ['Location']
        assignedOffices = models.LocationAssignment.objects.filter(Employee=employeeCode).values_list(*fields, flat=True)

    dfEmployees['WorkerName'] = dfEmployees['WorkerName'] + ' (' + dfEmployees['Department'] + ')'
    dfEmployees.rename(inplace=True, columns={'id': 'value', 'WorkerName': 'label'})
    dfEmployees.drop(inplace=True, columns=['Department'])

    dfAllOffices.rename(inplace=True, columns={'id': 'value', 'LocationName': 'label'})

    results = {
        'employees': dfToListOfDicts(dfEmployees),
        'offices': dfToListOfDicts(dfAllOffices),
        'selectedOffices': assignedOffices,
    }

    return results

def AssignOffices(managerId: models.User, data: Dict[str, any]):
    employee = int(data.pop('Employee'))
    offices = list(map(int, data.pop('Offices')))
    del data

    #Check if the selected employee is a valid employee
    try:
        employee = models.Employee.objects.get(id=employee)
    except:
        raise LookupError('Invalid employee code')

    #Check if the person making the changes has access or not
    if managerId.is_staff:
        accessFlag = True
    else:
        try:
            manager = models.Employee.objects.get(User=managerId)
        except:
            raise LookupError('You are not a registered employee')
        accessFlag = (employee.Manager == manager)
    
    if not accessFlag:
        raise PermissionError('Access denied')
    del accessFlag, managerId
    
    dfData = pd.DataFrame(offices, columns=['Location'])
    
    fields = ['id', 'Location']
    previousData = models.LocationAssignment.objects.filter(Employee=employee).values(*fields)
    dfPreviousData = pd.DataFrame(previousData) if previousData else pd.DataFrame(columns=fields)
    del previousData, fields
    
    dfData = pd.merge(left=dfData, right=dfPreviousData, on='Location', how='left')

    dfData['Employee'] = employee
    dfData['Location'] = convertTexttoObject(models.Location, dfData['Location'], 'id')

    try:
        updateModelWithDF(models.LocationAssignment, dfData, dfPreviousData)
    except Exception as e:
        raise ValueError(e)