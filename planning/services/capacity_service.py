import pandas as pd
import numpy as np

from django.db.models import Q, Min, Max

from planning import models
from core.services.generic_services import updateModelWithDF

def GetCapacities(minCapacity: str|int):
    filters = Q()
    if minCapacity:
        filters &= Q(Capacity__gte=minCapacity)

    capacties = models.Capacity.objects.all()

    aggregates = capacties.aggregate(
        capacityLowest=Min('Capacity'),
        capacityHighest=Max('Capacity')
    )
    
    capacties = capacties.filter(filters).values('id', 'Source','Capacity')

    subDepartments = models.SubDepartment.objects.all().values('Name','FullName')

    return capacties, float(aggregates['capacityLowest']), float(aggregates['capacityHighest']), subDepartments

def UpdateCapacities(dfCapacities: pd.DataFrame):
    dfCapacities = dfCapacities[dfCapacities['Source'].str.len() > 0]

    dfCapacities['id'] = np.where(dfCapacities['id']=='None', None, dfCapacities['id'])
    dfCapacities['id'] = np.where(dfCapacities['id'].str.len()==0, None, dfCapacities['id'])

    fields = ['id']
    previousCapacities = models.Capacity.objects.filter(id__in=dfCapacities['id'].to_list()).values(*fields)
    dfPreviousCapacities = pd.DataFrame(previousCapacities) if previousCapacities else pd.DataFrame(columns=fields)
    
    try:
        updateModelWithDF(models.Capacity, dfCapacities, dfPreviousCapacities)
    except Exception as e:
        raise ValueError(f'Error: {e}')