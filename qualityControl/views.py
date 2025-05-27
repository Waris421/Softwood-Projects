from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse, HttpRequest

import json

from .services import trim_audit_service
from .theme import theme
from .services.generic_services import paginate, applySearch, refineJson

login_required(login_url='/login')
def Home(request: HttpRequest):
    context = {'theme': theme}
    
    return render (request, 'quality_home.html', context)

@login_required(login_url='/login')
def TrimsAudit (request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not allowed', status=403)
    
    supplier = request.GET.get('supplier', None)
    inventory = request.GET.get('inventory', None)
    startDate = request.GET.get('startDate', None)
    endDate = request.GET.get('endDate', None)
    approval = request.GET.get('approval')
    pageNumber = int(request.GET.get('pageNumber', 1))

    if startDate == 'None':
        startDate = None
    
    if endDate == 'None':
        endDate = None
    
    if inventory == 'null':
        inventory = None
    
    if supplier == 'null':
        supplier = None
    
    if approval == 'true':
        approval = True
    elif approval == 'null':
        approval = None
    else:
        approval = False

    data = trim_audit_service.GetAuditHistory(supplier, inventory, approval, startDate, endDate)
    data = paginate(data, pageNumber)

    if not endDate:
        endDate = ''
    
    context = {
        'audits': data.object_list, 'pageObj': data,
        'supplier': supplier, 'inventory': inventory, 'approval': approval,
        'startDate': startDate, 'endDate': endDate,
        'theme': theme,
    }
    return render(request, 'trim/audit_history.html', context)

@login_required(login_url='/login')
def PendingTrimsAudit (request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not allowed', status=403)
    
    searchTerm = request.GET.get('searchTerm', '')
    workOrder = request.GET.get('workOrder', None)
    pageNumber = request.GET.get('pageNumber', 1)
    
    if workOrder == 'null':
        workOrder = None

    data = trim_audit_service.GetPendingAudits(workOrder)
    data = applySearch(data, searchTerm)
    data = paginate(data, pageNumber)

    context = {
        'inv': data.object_list, 'pageObj': data,
        'searchTerm': searchTerm, 'workOrder': workOrder,
        'theme': theme
    }
    return render(request, 'trim/home.html', context)

@login_required(login_url='/login')
def AddTrimsAudit (request: HttpRequest):
    if request.method == 'POST':    
        #Convert the json to a dict
        jsonData = json.loads(request.body.decode('utf-8'))
        
        try:
            trim_audit_service.AddTrimsAudit(jsonData)
            return HttpResponse('OK')
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)
    else:
        recInvs = request.GET.getlist('ref')
        
        inv, options = trim_audit_service.PrepareDataForAudit(recInvs)
        context = {
            'inv': inv, 'checkListOptions': options,
            'theme':theme,
        }

        return render(request, 'trim/audit.html', context)

@login_required(login_url='/login')
def EditTrimsAudit (request: HttpRequest, pk: int):
    if request.method == 'POST':  
        #Convert the json to a dict
        jsonData = json.loads(request.body.decode('utf-8'))

        dfData = refineJson(jsonData)
        
        try:
            trim_audit_service.EditTrimsAudit(dfData, pk)
            return redirect('trimAudit')
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400) 
    else:
        try:
            data, checkListOptions = trim_audit_service.GetAuditsData(pk)
            context = {'audit': data, 'checkListOptions': checkListOptions, 'theme': theme}
            return render(request, 'trim/edit_audit.html', context)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)