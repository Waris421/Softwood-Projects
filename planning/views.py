from django.shortcuts import render
from django.http import HttpRequest, HttpResponse
from django.contrib.auth.decorators import login_required

import json
from datetime import timedelta

from core.constants.theme import theme
from core.services import auth_service, generic_services
from core.constants.generic import TODAY
from .services import capacity_service, planning_service

@login_required(login_url='/login')
def Home(request: HttpRequest):
    context = {
        'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name)
    }

    return render (request, 'planning/home.html', context)

@login_required(login_url='/login')
def Capacity(request: HttpRequest):
    if request.method == 'POST':
        #Convert the json to a dict
        data = json.loads(request.body.decode('utf-8'))

        dfCapacities = generic_services.refineJson(data)
        del data
        try:
            capacity_service.UpdateCapacities(dfCapacities)
            return HttpResponse('Ok', status=200)
        except Exception as e:
            return HttpResponse(e, status=400)        
    else:
        search = request.GET.get('search', '')
        minCapacity = request.GET.get('minCapacity', 0)
        
        capacties, capacityLowest, capacityHighest, subDepartments = capacity_service.GetCapacities(minCapacity)
        capacties = generic_services.applySearch(capacties, search)
        
        context = {
            'capacities': capacties, 'capacitiesJson': json.dumps(list(capacties)),
            'subDepartments': json.dumps(list(subDepartments)),
            'search': search,
            'minCapacity': minCapacity, 'capacityLowest': capacityLowest, 'capacityHighest': capacityHighest,
            'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name)
        }

        return render(request, 'capacity/home.html', context)

@login_required(login_url='/login')
def SetSource(request: HttpRequest):
    if request.method == 'POST':
        #Convert the json to a dict
        data = json.loads(request.body.decode('utf-8'))

        dfPlanning = generic_services.refineJson(data)
        del data
        
        try:
            planning_service.UpdateOrdersPlanning(dfPlanning)
            return HttpResponse('In Process', status=501)
        except Exception as e:
            return HttpResponse(e, status=400)
    else:
        startingDD = request.GET.get('startingDD', '')
        endingDD = request.GET.get('endingDD', '')
        sortingMethod = request.GET.get('sortingMethod','orderWise')

        if startingDD:
            startingDD = generic_services.convertStrToDateTime(startingDD, '%Y-%m-%d').date()
        else:
            startingDD = TODAY.date()
        
        if endingDD:
            endingDD = generic_services.convertStrToDateTime(endingDD, '%Y-%m-%d').date()
        else:
            endingDD = startingDD + timedelta(days=14)

        ordersPlanning = planning_service.GetOrdersPlanning(startingDD, endingDD, sortingMethod)

        planningJSON = [
            {key: value for key, value in item.items() if key == 'Source'}
            for item in ordersPlanning
        ]
        context = {
            'ordersPlanning': ordersPlanning, 'planningJSON': json.dumps(list(planningJSON)),
            'startingDD': startingDD, 'endingDD': endingDD, 'sortingMethod': sortingMethod,
            'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name)
        }
        return render(request, 'planning/sources.html', context)
