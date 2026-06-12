from typing import List

from django.contrib.auth.models import User
from django.db.models import Q

from HumanResource import models

def getSubordinates(manager: models.Employee, filters: Q = Q(), fields: List[str] = []):
    '''
        fetches all the people reported diretly or indirectly by a manager.
        Applies any custom filters and returns the fields that are specified
    '''

    allEmployees = models.Employee.objects.all().values('id', 'Manager_id')

    hierarchy = {}
    for employee in allEmployees:
        managerId = employee['Manager_id']
        employeeId = employee['id']

        if managerId == employeeId:
            continue

        if managerId not in hierarchy:
            hierarchy[managerId] = []
        hierarchy[managerId].append(employeeId)

    subordinateIds = [manager.id]
    queue = list(hierarchy.get(manager.id, []))
    visited = {manager.id}

    while queue:
        currentId = queue.pop(0)

        if currentId in visited:
            continue

        subordinateIds.append(currentId)
        visited.add(currentId)

        if currentId in hierarchy:
            queue.extend(hierarchy[currentId])
    
    finalQueryset = models.Employee.objects.filter(id__in=subordinateIds).filter(filters).values(*fields)

    return finalQueryset