from django.shortcuts import render, redirect
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.urls import reverse
from django.contrib.auth.decorators import login_required

import pandas as pd
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import  AllowAny
from rest_framework.request import Request
from rest_framework.authtoken.models import Token
import rest_framework

import json
import os

from core.constants.theme import theme
from core.services import generic_services, auth_service
from .services import stitching_service, bulletin_service, core_sheet_service
from .services import  worker_service, serial_service, outsource_service

from . import models

# For energy consumption data visualization
from django.db.models import Min, Max, Avg, Sum
from django.db.models.functions import TruncHour
from datetime import datetime


@login_required(login_url='/login')
def Home (request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=401)

    context = {
        'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name)
        }
    return render(request, 'prodManagement/home.html', context)

@login_required(login_url='/login')
def Operations (request:HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=401)
    
    search = request.GET.get('search', '')
    sectionFilter = request.GET.get('sectionFilter', None)
    skillLevel = request.GET.get('skillLevel', None)
    machineType = request.GET.get('machineType', None)
    ratePerSAM = request.GET.get('ratePerSAM', None)
    pageNumber = request.GET.get('page', 1)

    sectionFilter = None if sectionFilter == 'null' else sectionFilter
    sectionFilter = None if sectionFilter == 'None' else sectionFilter
    machineType = None if machineType == 'null' else machineType
    machineType = None if machineType == 'None' else machineType
    skillLevel = None if skillLevel == 'null' else skillLevel
    skillLevel = None if skillLevel == 'None' else skillLevel
    
    operations = stitching_service.GetOperations(sectionFilter, machineType, skillLevel, ratePerSAM)
    operations = generic_services.applySearch(operations, search)
    page = generic_services.paginate(operations, pageNumber)

    context = {
        'operations': page.object_list, 'page_obj': page,
        'sectionFilter': sectionFilter, 'machineType': machineType, 'ratePerSAM': ratePerSAM,
        'skillLevel': skillLevel, 'search': search,
        'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name),
    }
    return render(request, 'operations/home.html', context)

@login_required(login_url='/login')
def AddOperation (request:HttpRequest):
    if request.method == 'POST':
        fields = ['Name', 'Section', 'Category', 'Level', 'SMV', 'Rate', 'Code', 'Type']
        data = {field: request.POST.get(field) for field in fields}
        
        try:
            opCode = stitching_service.AddOperation(data)
            return redirect(reverse('editOperation', kwargs={'pk': opCode}))
        except Exception as e:
            context = {
                'theme': theme, 'error': e,
            }
            return render(request, 'operations/add.html', context)
    else:
        context = {
            'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name),
        }
        return render(request, 'operations/add.html', context)

@login_required(login_url='/login')
def EditOperation (request: HttpRequest, pk: int):
    try:
        operation = models.Operation.objects.get(id=pk)
    except:
        return HttpResponse('Resource not found', status=404)
    
    if request.method == 'POST':
        fields = ['Name', 'Section', 'Category', 'Level', 'SMV', 'Rate', 'Code', 'Type']
        data = {field: request.POST.get(field) for field in fields}

        try:
            stitching_service.EditOperation(data, operation)
            url = reverse('operations') + f'?search={operation.Name}'
            return redirect(url)
        except Exception as e:
            data = stitching_service.GetDataForOperation(operation)
            context = {
                'data': data, 'error': e,
                'theme': theme,
            }
            return render(request, 'operations/edit.html', context)
        
    else:
        data = stitching_service.GetDataForOperation(operation)
        context = {
            'data': data,
            'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name),
        }
        return render(request, 'operations/edit.html', context)
    
@login_required(login_url='/login')
def Machines(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=401)
    
    search = request.GET.get('search', '')
    type = request.GET.get('type', None)
    status = request.GET.get('status', None)
    manufacturer = request.GET.get('manufacturer', None)
    department = request.GET.get('department', None)
    pageNumber = request.GET.get('page', 1)

    #Convert null in json to None for python handling
    type = None if type == 'null' else type
    status = None if status == 'null' else status
    manufacturer = None if manufacturer == 'null' else manufacturer
    department = None if department == 'null' else department

    machines = stitching_service.GetMachines(type, status, manufacturer, department)
    machines = generic_services.applySearch(machines, search)
    page = generic_services.paginate(machines, pageNumber)
    
    context = {
        'machines': page.object_list, 'page_obj': page,
        'type': type, 'status': status, 'manufacturer': manufacturer, 'search': search,
        'department': department,
        'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name)
    }
    return render(request, 'machines/home.html', context)

@login_required(login_url='/login')
def AddMachine(request: HttpRequest):
    if request.method == 'POST':
        fields = ['MachineId', 'Type', 'FunctionStatus', 'Manufacturer', 'ModelNumber', 'SerialNumber', 'Department']
        data = {field: request.POST.get(field) for field in fields}

        try:
            machineCode = stitching_service.AddMachine(data)
            return redirect(reverse('editMachine', kwargs={'pk': machineCode}))
        except Exception as e:
            context = {
                'theme': theme,'error': e,
            }
            return render(request, 'machines/add.html', context)
    else:
        context = {
            'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name),
        }
        return render(request, 'machines/add.html', context)

@login_required(login_url='/login')
def EditMachine(request: HttpResponse, pk: int):
    try:
        machine = models.Machine.objects.get(id=pk)
    except:
        return HttpResponse('Resource not found', status=404)
    
    if request.method == 'POST':
        fields = ['MachineId', 'Type', 'FunctionStatus', 'Manufacturer', 'ModelNumber', 'SerialNumber', 'Department']
        data = {field: request.POST.get(field) for field in fields}
        
        try:
            stitching_service.EditMachine(data, machine)
            url = reverse('machines') + f'?search={machine.MachineId}'
            return redirect(url)
        except Exception as e:
            data = stitching_service.GetDataForMachine(machine)
            context = {
                'data': data, 'error': e,
                'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name),
            }
            return render(request, 'operations/edit.html', context)
    else:
        data = stitching_service.GetDataForMachine(machine)
        
        context = {
            'data': data,
            'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name),
        }
        return render(request, 'machines/edit.html', context)

@login_required(login_url='/login')
def StyleBulletin(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=401)

    pageNumber = request.GET.get('page', 1)
    search = request.GET.get('search', '')
    minSAM = request.GET.get('minSAM', None)

    if minSAM:
        minSAM = float(minSAM)

    data = bulletin_service.GetBulletinList(minSAM)
    data = generic_services.applySearch(data, search)
    page = generic_services.paginate(data, pageNumber)

    context = {
        'bulletins': page.object_list, 'page_obj': page,
        'search': search, 'minSAM': minSAM,
        'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name),
    }

    return render(request, 'bulletin/home.html', context)

@login_required(login_url='/login')
def AddStyleBulletin(request: HttpRequest):
    if request.method == 'POST':
        jsonData = json.loads(request.body.decode('utf-8'))

        dfBulletin, dfBulletinDetails = generic_services.refineJson(jsonData)

        try:
            styleBulletinId = bulletin_service.AddStyleBulletin(dfBulletin, dfBulletinDetails)
            return HttpResponse(styleBulletinId, status=200)
        except Exception as e:
            return HttpResponse(e, status=401)
    else:
        context = {
            'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name),
        }

        return render(request, 'bulletin/add.html', context)

@login_required(login_url='/login')
def EditStyleBulletin(request: HttpRequest, pk: int):
    try:
        StyleBulletin = models.StyleBulletin.objects.get(id=pk)
    except:
        return HttpResponse('Resource not found', status=404)

    if request.method == 'POST':
        jsonData = json.loads(request.body.decode('utf-8'))

        dfBulletinDetails = generic_services.refineJson(jsonData)

        try:
            bulletin_service.UpdateStyleBulletin(StyleBulletin, dfBulletinDetails)
            return HttpResponse('Saved Successfully', status=200)
        except Exception as e:
            return HttpResponse(e, status=401)
    else:
        data, operations = bulletin_service.GetDataForBulletin(StyleBulletin)
        context = {
            'data': data,
            'operations': operations, 'operationsJson': json.dumps(list(operations)),
            'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name),
        }
        return render(request, 'bulletin/edit.html', context)

@login_required(login_url='/login')
def DuplicateStyleBulletin(request: HttpRequest, pk: int):
    try:
        styleBulletin = models.StyleBulletin.objects.get(id=pk)
    except:
        return HttpResponse('Resource not found', status=404)
    
    if request.method == 'POST':
        targetCode = request.POST.get('target')

        try:
            styleBulletinId = bulletin_service.DuplicateStyleBulletin(styleBulletin, targetCode)
            return redirect('editStyleBulletin', pk=styleBulletinId)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=401)
    else:
        context = {
            'source': styleBulletin,
            'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name)
        }
        return render(request, 'bulletin/duplicate.html', context)

@login_required(login_url='/login')
def SummariseStyleBulletin(request: HttpRequest):
    if request.method != 'POST':
        return HttpResponse('Not Allowed', status=403)

    jsonData = json.loads(request.body.decode('utf-8'))

    operations, id = generic_services.refineJson(jsonData)
    id = int(id.iloc[0, 0])

    try:
        StyleBulletin = models.StyleBulletin.objects.get(id=id)
    except:
        return HttpResponse('Resource Not Found', status=401)

    summary = bulletin_service.SummariseBulletin(StyleBulletin, operations)

    return JsonResponse(summary, safe=False)

@login_required(login_url='/login')
def CoreSheet (request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=401)
    
    pageNumber = request.GET.get('page', 1)
    search = request.GET.get('search', '')
    workOrder = request.GET.get('workOrder', None)

    try:
        workOrder = models.WorkOrder.objects.get(OrderNumber=workOrder)
    except:
        workOrder = None
    
    data = core_sheet_service.GetCoreSheetList(workOrder)
    data = generic_services.applySearch(data, search)
    page = generic_services.paginate(data, pageNumber)

    context = {
        'coreSheets': page.object_list, 'page_obj': page,
        'search': search,
        'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name),
    }
    if workOrder:
        context.update({'workOrder': workOrder.OrderNumber})
    else:
        context.update({'workOrder': ''})
    return render(request, 'CS/home.html', context)

@login_required(login_url='/login')
def EditCoreSheet(request: HttpRequest, workOrder: int):
    try:
        workOrder = models.WorkOrder.objects.get(OrderNumber=workOrder)
    except:
        return HttpResponse('Resource not found', status=404)

    if request.method == 'POST':
        jsonData = json.loads(request.body.decode('utf-8'))

        dfCut, dfBundles = generic_services.refineJson(jsonData)

        try:
            cutNumber = core_sheet_service.EditCoreSheet(dfCut, dfBundles, workOrder)
            return HttpResponse(cutNumber, status=200)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=401)
    
    else:
        cuts, sizes = core_sheet_service.GetOrderCuttingDetail(workOrder)
        context = {
            'cuts': cuts, 'sizes': sizes,
            'orderNumber': workOrder.OrderNumber,
            'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name),
        }
        return render(request, 'CS/edit.html', context)

@login_required(login_url='/login')
def GetCutDetails(request: HttpRequest, pk: int):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=403)
    
    try:
        cut = models.Cut.objects.get(id=pk)
    except:
        return HttpResponse('Resource not found', status=404)
    
    cutDetails = core_sheet_service.GetCutDetails(cut)
    return JsonResponse(cutDetails)

@login_required(login_url='/login')
def GetNextAvailableBundle(request: HttpRequest, pk: int):
    if request.method != 'GET':
            return HttpResponse('Not Allowed', status=403)
    
    workOrder = models.Cut.objects.get(id=pk).WorkOrder

    highestBundleNumber = core_sheet_service.GetHighestBundleNumber(workOrder)

    return HttpResponse(highestBundleNumber+1, status=200)

@login_required(login_url='/login')
def Workers(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=401)
    
    pageNumber = request.GET.get('page', 1)
    search = request.GET.get('search', '')
    department = request.GET.get('department', None)
    status = request.GET.get('status',None)

    if status == 'null':
        status = None
    
    data = worker_service.GetWorkers(department, status)
    data = generic_services.applySearch(data, search)
    page = generic_services.paginate(data, pageNumber)

    context = {
        'workers': page.object_list, 'page_obj': page,
        'search': search, 'department': department, 'status': status,
        'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name),
    }
    return render(request, 'workers/home.html', context)

@login_required(login_url='/login')
def AddWorker(request: HttpRequest):
    if request.method == 'POST':
        fields = ['WorkerCode', 'WorkerName', 'DateOfBirth', 'FatherSpouseName', 'Department', 'SubDepartment', 'CNIC', 'Status', 'Gender', 'User']
        data = {field: request.POST.get(field) for field in fields}

        try:
            workerCode = worker_service.AddWoker(data)
            return redirect(reverse('editWorker', kwargs={'pk': workerCode}))
        except Exception as e:
            print(e)
            context = {
                'error': e, 'data': data,
                'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name),
            }
            return render(request, 'workers/add.html', context)
    else:
        context = {
            'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name),
        }
        return render(request, 'workers/add.html', context)

@login_required(login_url='/login')
def EditWorker(request:HttpRequest, pk: int):
    try:
        worker = models.Worker.objects.get(WorkerCode=pk)
    except:
        return HttpResponse('Resource not found', status=404)

    if request.method == 'POST':
        fields = ['WorkerCode', 'WorkerName', 'DateOfBirth', 'FatherSpouseName', 'Department', 'SubDepartment', 'CNIC', 'Status', 'Gender', 'User', 'DateOfJoining']
        data = {field: request.POST.get(field) for field in fields}

        try:
            worker_service.EditWorker(worker, data)
            url = reverse('workers') + f'?search={worker.WorkerCode}'
            return redirect(url)
        except Exception as e:
            print(e)
            context = {
                'error': e, 'data': data,
                'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name),
            }
            return render(request, 'workers/edit.html', context)
    else:
        data = worker_service.GetDataForWorker(worker)
        context = {
            'data': data,
            'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name)
        }
        return render(request, 'workers/edit.html', context)

class MarkGroupCompletion(APIView):
    permission_classes = [AllowAny]

    def post(self, request:Request):
        try:        
            user = auth_service.getAPIUser(request)
        except:
            response = {'error': 'Access Denied'}
            status=  rest_framework.status.HTTP_401_UNAUTHORIZED
            return Response(data=response, status=status)            

        print(user)

        cardId = int(request.data.get('bundleId'))

        try:
            core_sheet_service.CompleteCardGroup(cardId)
            
            response = {'message': 'Saved Successfully'}
            status = rest_framework.status.HTTP_200_OK
        except LookupError as e:
            response = {'error': str(e)}
            status = rest_framework.status.HTTP_404_NOT_FOUND
        except ValueError as e:
            response = {'error': str(e)}
            status = rest_framework.status.HTTP_409_CONFLICT
        except Exception as e:
            response = {'error': str(e)}
            status=  rest_framework.status.HTTP_400_BAD_REQUEST
        
        
        return Response(data=response, status=status)

class AssignWorkerCard(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request):
        try:
            user = generic_services.getAPIUser(request)
        except:
            response = {'error': 'Access Denied'}
            status=  rest_framework.status.HTTP_401_UNAUTHORIZED
            return Response(data=response, status=status) 
        
        cardId = request.data.get('cardId')
        workerCode = request.data.get('workerCode')

        try:
            worker_service.AssignCardToWorker(cardId, workerCode)
            response = {'message': 'In Process'}
            status=  rest_framework.status.HTTP_200_OK

            return Response(data=response, status=status)
        except Exception as e:
            response = {'error': str(e)}
            status=  rest_framework.status.HTTP_400_BAD_REQUEST
            return Response(data=response, status=status)

@login_required(login_url='/login')
def Serials(request:HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=403)
    
    worker = request.GET.get('worker', None)
    line = request.GET.get('line', None)
    section = request.GET.get('section', None)
    workOrder = request.GET.get('workOrder', None)
    overTime = request.GET.get('overTime', None)
    operation = request.GET.get('operation', None)
    startDate = request.GET.get('startDate',None)
    endDate = request.GET.get('endDate',None)
    
    if overTime == 'true':
        overTime = True
    elif overTime == 'false':
        overTime = False
    else:
        overTime = None
    
    context = {
        'worker': worker, 'line': line, 'section': section, 'overTime': overTime,
        'workOrder': workOrder,'operation': operation, 'startDate':startDate, 'endDate':endDate,
        'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name)
    }
    return render(request, 'serials/home.html', context)

@login_required(login_url='/login')
def GetWorkSummary(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=403)

    worker = request.GET.get('worker', None)
    line = request.GET.get('line', None)
    section = request.GET.get('section', None)
    workOrder = request.GET.get('workOrder', None)
    overTime = request.GET.get('overTime', None)
    operation = request.GET.get('operation', None)
    startDate = request.GET.get('startDate',None)
    endDate = request.GET.get('endDate', None)
    
    if startDate in ['None','']:
        startDate = generic_services.TODAY
    else:
        startDate = generic_services.convertStrToDateTime(startDate, "%Y-%m-%d")
    if endDate in ['None','']:
        endDate = generic_services.TODAY
    else:
        endDate = generic_services.convertStrToDateTime(endDate, "%Y-%m-%d")

    data = serial_service.GetWorkSummary(startDate, endDate, worker, overTime, line, section, workOrder, operation)

    return JsonResponse(data)

@login_required(login_url='/login')
def GetWorkDetails(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=403)
    
    worker = request.GET.get('worker', None)
    line = request.GET.get('line', None)
    section = request.GET.get('section', None)
    workOrder = request.GET.get('workOrder', None)
    overTime = request.GET.get('overTime', None)
    operation = request.GET.get('operation', None)
    startDate = request.GET.get('startDate',None)
    endDate = request.GET.get('endDate',None)

    if startDate in ['None','']:
        startDate = generic_services.TODAY
    else:
        startDate = generic_services.convertStrToDateTime(startDate, "%Y-%m-%d")
    if endDate in ['None','']:
        endDate = generic_services.TODAY
    else:
        endDate = generic_services.convertStrToDateTime(endDate, "%Y-%m-%d")

    data = serial_service.GetScanTable(startDate, endDate, worker, overTime, line, section, workOrder, operation)

    return JsonResponse(data, safe=False)

@login_required(login_url='/login')
def GetWagesSummary(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=403)
    
    worker = request.GET.get('worker', None)
    line = request.GET.get('line', None)
    section = request.GET.get('section', None)
    workOrder = request.GET.get('workOrder', None)
    overTime = request.GET.get('overTime', None)
    operation = request.GET.get('operation', None)
    startDate = request.GET.get('startDate',None)
    endDate = request.GET.get('endDate', None)
    
    if startDate in ['None','']:
        startDate = generic_services.TODAY
    else:
        startDate = generic_services.convertStrToDateTime(startDate, "%Y-%m-%d")
    if endDate in ['None','']:
        endDate = generic_services.TODAY
    else:
        endDate = generic_services.convertStrToDateTime(endDate, "%Y-%m-%d")

    data = serial_service.GetWageSummary(startDate, endDate, worker, overTime, line, section, workOrder, operation)
    
    return JsonResponse(data)

@login_required(login_url='/login')
def GetAttendanceDetails(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=403)
    
    worker = request.GET.get('worker', None)
    line = request.GET.get('line', None)
    section = request.GET.get('section', None)
    startDate = request.GET.get('startDate',None)
    endDate = request.GET.get('endDate', None)

    if startDate in ['None','']:
        startDate = generic_services.TODAY
    else:
        startDate = generic_services.convertStrToDateTime(startDate, "%Y-%m-%d")
    if endDate in ['None','']:
        endDate = generic_services.TODAY
    else:
        endDate = generic_services.convertStrToDateTime(endDate, "%Y-%m-%d")
    
    data = serial_service.GetAttendanceDetail(startDate, endDate, worker, line, section)

    return JsonResponse(data)

@login_required(login_url='/login')
def GetOutSourceContracts(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=403)
    
    workOrder = request.GET.get('workOrder', '')
    source = request.GET.get('source', '')
    contractNumber = request.GET.get('contractNumber', '')
    approval = request.GET.get('approval', 'pending')

    workOrder = None if workOrder=='null' else workOrder
    source = None if source=='null' else source

    contracts = outsource_service.GetOutsourceContracts(workOrder, source, contractNumber, approval)
    contracts = generic_services.paginate(contracts, 1)

    context = {
        'contracts': contracts.object_list, 'page_obj': contracts,
        'workOrder': workOrder, 'source': source, 'contractNumber': contractNumber, 'approval': approval,
        'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name),
    }
    return render(request, 'outsource/contracts.html', context)

@login_required(login_url='/login')
def AddOutSourceContract(request: HttpRequest):
    if request.method == 'POST':
        jsonData = json.loads(request.body.decode('utf-8'))
        dfContract, dfDetails = generic_services.refineJson(jsonData) 

        try:
            contractNumebr = outsource_service.AddContract(dfContract, dfDetails)        
        except Exception as e:
            generic_services.printExceptionInDetail(e)
            return HttpResponse(e, status=400)
        
        return HttpResponse(contractNumebr, status=200)
    else:
        context = {
            'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name),
        }
        return render(request, 'outsource/contract_add.html', context)

@login_required(login_url='/login')
def EditOutSourceContract(request: HttpRequest, pk: int):
    try:
        contract = models.OutSourceJobContract.objects.get(id=pk)
    except:
        return generic_services.showMessageResponse(request, 'Resource Not Found', 400)

    if request.method == 'POST':
        jsonData = json.loads(request.body.decode('utf-8'))
        dfContract, dfDetails = generic_services.refineJson(jsonData) 
        
        try:
            outsource_service.UpdateContract(dfContract, dfDetails)
            return HttpResponse('OK', status=200)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)
    else:
        try:
            source, details, detailsJSON = outsource_service.ProcessContractData(contract)

            context = {
                'contract': contract, 'source': source, 
                'details': details, 'detailsJSON': detailsJSON,
                'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name),
            }
            return render(request, 'outsource/contract_edit.html', context)
        except Exception as e:
            print(e)
            return generic_services.showMessageResponse(request, str(e), 400)

@login_required(login_url='/login')
def ApproveOuteSourceContract(request: HttpRequest, pk: int):
    try:
        contract = models.OutSourceJobContract.objects.get(id=pk)
    except:
        return generic_services.showMessageResponse(request, 'Resource Not Found', 400)
    
    if contract.Approval is not None:
        return generic_services.showMessageResponse(request, 'This resource is already closed', statusCode=403)
    
    if request.method == 'POST':
        approval = request.POST.get('Approval', '')
        comments = request.POST.get('Comments', '')

        try:
            outsource_service.ApproveContract(request.user, contract, approval, comments)
            url = f"{reverse('PM:outSourceContracts')}?approval=approved&contractNumber={pk}"
            return redirect(url)
        except Exception as e:
            print(e)
            data = outsource_service.GetDataForContractApproval(contract)
            context = {
                'message': str(e), 'contract': data, 'contractObj': contract,
                'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name),
            }
            return render(request, 'outsource/contract_approve.html', context)
    else:
        try:
            data = outsource_service.GetDataForContractApproval(contract)
        except Exception as e:
            print(e)
            return generic_services.showMessageResponse(request, str(e))
    
        context = {
            'contract': data, 'contractObj': contract,
            'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name),
        }
        return render(request, 'outsource/contract_approve.html', context)

@login_required(login_url='/login')
def PrintContract(request: HttpRequest, pk: int):
    if request.method != 'POST':
        return HttpResponse('Not Allowed', status=405)
    
    data = json.loads(request.body.decode('utf-8'))
    varFilter = data['format']
    
    try:
        contract = models.OutSourceJobContract.objects.get(id=pk)
    except:
        return HttpResponse('Contract not found', status=404)
    
    if contract.Approval is not True:
        return HttpResponse('This contract is not approved', status=403)

    data, details, summary = outsource_service.PrintContract(contract, varFilter)

    context = {'contract':data, 'details':details, 'summary': summary, 'theme': theme}
    try:
        response = generic_services.convertContextToPDFResponse(context, 'outsource/contract_print.html')
        return response
    except Exception as e:
        print(e)
        return HttpResponse(e, status=400)

@login_required(login_url='/login')
def GetWorkOrderRoute(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=403)
    
    workOrder = request.GET.get('workOrder', None)
    source = request.GET.get('source', None)
    ignore = request.GET.get('ignore', None)

    if not workOrder:
        return HttpResponse('Missing Work Order', status=400)
   
    try:
        workOrder = models.WorkOrder.objects.get(OrderNumber=workOrder)
    except:
        return HttpResponse('Invalid Work Order', status=400)
    
    route = outsource_service.GetWorkOrderRoute(workOrder, source, ignore)
    return JsonResponse(route, safe=False)

# View to upload energy consumption data from excel file. 
class EnergyUpload(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request):
        # Step 1 — Verify the user is logged in
        try:
            user = auth_service.authenticateUser(request, None, None, None)
        except Exception as e:
            return Response({'message': str(e)}, status=rest_framework.status.HTTP_401_UNAUTHORIZED)

        # Step 2 — Make sure a file was included
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({'message': 'No file provided'}, status=rest_framework.status.HTTP_400_BAD_REQUEST)

        try:
            # Step 3 — Read directly from memory into pandas — no disk involved
            df = pd.read_excel(uploaded_file)

            # Step 4 — Rename first column to Timestamp, parse into proper datetime
            df = df.rename(columns={df.columns[0]: 'Timestamp'})
            df['Timestamp'] = pd.to_datetime(df['Timestamp'], format="%a %d/%m/%y %H:%M", errors='coerce')
            df = df.dropna(subset=['Timestamp'])

            # Step 5 — Check if data for this exact day already exists, but keep going either way
            upload_date = df['Timestamp'].dt.date.min()
            duplicate_day = models.EnergyReading.objects.filter(Timestamp__date=upload_date).exists()

            # Step 6 — Log the upload (who uploaded and when) — no file stored
            upload = models.EnergyConsumption.objects.create(UploadedBy=user)

            # Step 7 — Melt: convert wide format (many columns) to long format (one row per machine per minute)
            machine_cols = df.columns[1:].tolist()
            df = df.melt(id_vars=['Timestamp'], value_vars=machine_cols, var_name='MachineName', value_name='Value_kW')
            df['Value_kW'] = df['Value_kW'].fillna(0)

            # Step 8 — Create any new machines in one pass
            machine_names = df['MachineName'].unique()
            machines = {}
            for name in machine_names:
                machine, _ = models.EnergyMachine.objects.get_or_create(Name=name)
                machines[name] = machine

            # Step 9 — Fetch ALL existing timestamp+machine combos in ONE query
            existing = set(
                (name, ts.replace(tzinfo=None))
                for name, ts in models.EnergyReading.objects
                .filter(Machine__Name__in=machine_names)
                .values_list('Machine__Name', 'Timestamp')
            )

            # Step 10 — Filter duplicates and bulk save all new readings
            readings = []
            for row in df.itertuples(index=False):
                key = (row.MachineName, row.Timestamp.to_pydatetime().replace(tzinfo=None))
                if key not in existing:
                    readings.append(models.EnergyReading(
                        Machine=machines[row.MachineName],
                        Upload=upload,
                        Timestamp=row.Timestamp,
                        Value_kW=row.Value_kW
                    ))

            models.EnergyReading.objects.bulk_create(readings, ignore_conflicts=True)

        except Exception as e:
            return Response({'message': f'File processing failed: {str(e)}'}, status=rest_framework.status.HTTP_400_BAD_REQUEST)

        if duplicate_day:
            return Response({'message': f'Data for {upload_date.strftime("%d %B %Y")} has already been uploaded'}, status=rest_framework.status.HTTP_400_BAD_REQUEST)
        return Response({'message': 'File uploaded successfully'}, status=rest_framework.status.HTTP_200_OK)


# Returns the earliest and latest date we have readings for
class EnergyDateRange(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request):
        # Step 1 — Verify the user is logged in
        try:
            auth_service.authenticateUser(request, None, None, None)
        except Exception as e:
            return Response({'message': str(e)}, status=rest_framework.status.HTTP_401_UNAUTHORIZED)

        # Step 2 — Ask the database for the earliest and latest timestamp in one query
        result = models.EnergyReading.objects.aggregate(
            min_date=Min('Timestamp'),
            max_date=Max('Timestamp')
        )

        # Step 3 — If no data exists at all, tell the frontend
        if not result['min_date']:
            return Response({'message': 'No data available'}, status=rest_framework.status.HTTP_404_NOT_FOUND)

        # Step 4 — Return just the date part as a plain string eg "2026-04-18"
        return Response({
            'min_date': result['min_date'].date().isoformat(),
            'max_date': result['max_date'].date().isoformat()
        })


# Returns raw readings per machine for a chosen date range
class EnergyReadings(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request):
        # Step 1 — Verify the user is logged in
        try:
            auth_service.authenticateUser(request, None, None, None)
        except Exception as e:
            return Response({'message': str(e)}, status=rest_framework.status.HTTP_401_UNAUTHORIZED)

        # Step 2 — Read the from and to dates from the URL eg ?from=2026-04-18&to=2026-04-23
        from_date = request.query_params.get('from')
        to_date = request.query_params.get('to')

        if not from_date or not to_date:
            return Response({'message': 'from and to parameters are required'}, status=rest_framework.status.HTTP_400_BAD_REQUEST)

        # Step 3 — Convert the date strings into real Python datetime objects the database understands
        try:
            from_dt = datetime.strptime(from_date, '%Y-%m-%d')
            to_dt = datetime.strptime(to_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        except ValueError:
            return Response({'message': 'Invalid date format. Use YYYY-MM-DD'}, status=rest_framework.status.HTTP_400_BAD_REQUEST)

        # Step 4 — Get all machines from the database
        machines = models.EnergyMachine.objects.all()
        result = []

        for machine in machines:
            # Step 5 — Fetch all readings for this machine within the selected range
            readings = (
                models.EnergyReading.objects
                .filter(Machine=machine, Timestamp__range=(from_dt, to_dt))
                .values('Timestamp', 'Value_kW')
                .order_by('Timestamp')
            )

            # Step 6 — Skip this machine if it has no data in the selected range
            if not readings.exists():
                continue

            # Step 7 — Add this machine's data to the result list
            result.append({
                'machine': machine.Name,
                'readings': [
                    {'timestamp': r['Timestamp'].isoformat(), 'value_kw': r['Value_kW']}
                    for r in readings
                ]
            })

        # Step 8 — Return the full list, one entry per machine
        return Response(result)
