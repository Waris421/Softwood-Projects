import pandas as pd

from typing import Dict

from HumanResource import models
from core.services.generic_services import calculateHaversineDistance

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