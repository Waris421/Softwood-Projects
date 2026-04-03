import pandas as pd
from typing import Dict
import googlemaps

from django.db.models import Q
from django.utils import timezone as TZ

from HumanResource import models

from core.services.generic_services import dfToListOfDicts, calculateHaversineDistance
from core.constants.generic import TODAY

def getLocation(lat: str|float, lon: str|float):
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
        gmapsKey = 'AIzaSyChtTcMLnz4G6qJqXdvZx7msbB2Jsv1fDQ'
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

def GetAttendance(employee: models.Employee, startDate: str, endDate: str):
    filters = Q(TimeDate__date__gte=startDate) & Q(TimeDate__date__lte=endDate) & Q(Employee=employee)
    attendance = models.Attendance.objects.filter(filters)
    
    print(attendance)

    raise NotImplementedError('Under Construction')

def VerifyAttendance(employee: models.Employee, data: Dict[str, str]):
    attendanceType = data.get('Type')
    latitude = data.get('Latitude')
    longitude = data.get('Longitude')

    if None in (attendanceType, latitude, longitude):
        raise ValueError('Invalid Data')

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