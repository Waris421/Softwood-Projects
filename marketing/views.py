from django.shortcuts import render, redirect
from django.http import HttpRequest, HttpResponse
from django.contrib.auth.decorators import login_required
from django.urls import reverse

import json
from urllib.parse import urlencode

from core.constants.theme import theme
from . import models
from core.services import auth_service
from core.services.generic_services import refineJson, applySearch, paginate, showMessageResponse
from .services import correspondance_service, customer_service, export_data_serivce

APP_NAME = 'Mark'

@login_required(login_url='/login')
def Home(request: HttpRequest):
    context = {
        'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name)
    }

    return render (request, 'marketing/home.html', context)

@login_required(login_url='/login')
def CustomerData (request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=403)

    assignFilter = request.GET.get('assignFilter', 'Active')
    countryFilter = request.GET.get('countryFilter', None)
    page = request.GET.get('page', 1)
    search = request.GET.get('search', '')

    if countryFilter == 'None':
        countryFilter = None

    customers, countries = customer_service.GetCustomers(request, assignFilter, countryFilter)
    customers = applySearch(customers, search)
    customers = paginate(customers, page, 20)

    context = {
        'customers': customers.object_list, 'page_obj': customers,
        'assignFilter': assignFilter, 'search': search,
        'countries': countries, 'countryFilter': countryFilter,
        'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name)
    }
    return render (request, 'customers/home.html', context)

@login_required(login_url='/login')
def ExportData (request: HttpRequest):
    if request.method != 'GET':
        return showMessageResponse(request, 'Not Allowed', 403)
    
    startDate = request.GET.get('startDate')
    endDate = request.GET.get('endDate')
    search = request.GET.get('search', '')
    country = request.GET.get('country', '')
    page = request.GET.get('page', 1)

    exportData = export_data_serivce.GetExportDataTable(startDate, endDate)
    exportData = applySearch(exportData, search)
    exportData = paginate(exportData, page, 50)

    context = {
        'exportData': exportData.object_list, 'page_obj': exportData,
        'search': search, 'country': country,
        'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name)
    }
    return render (request, 'export_data/home.html', context)

@login_required(login_url='/login')
def UploadExportReport(request:HttpRequest):
    if request.method == 'POST':
        dataFile = request.FILES['exportDataFile']
        
        try:
            addedData = export_data_serivce.ExtractUploadedData(dataFile)
            request.session['addedData'] = addedData
            return redirect('marketing:confirmExportDataUpload')
        except Exception as e:
            print(e)
            context = {
                'error': str(e),
                'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name)
            }
            return render(request, 'export_data/upload.html', context)
    else:
        context = {
            'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name)
        }
        return render(request, 'export_data/upload.html', context)

@login_required(login_url='/login')
def UploadExportReportConfirmation(request:HttpRequest):
    if request.method == 'POST':
        pass
    else:
        try:
            addedData = request.session.get('addedData')
            del request.session['addedData']
        except:
            return showMessageResponse(request, 'Incorrect data provided', 403)

        context = {
            'addedData': addedData,
            'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name)
        }
        return render(request, 'export_data/confirm_upload.html', context)

@login_required(login_url='/login')
def AddCustomer (request: HttpRequest):
    if request.method == 'POST':
        #Convert the json to a dict
        jsonData = json.loads(request.body.decode('utf-8'))
        
        dfCustomer, dfCustomerDetails = refineJson(jsonData)
        del jsonData
        
        try:
            customerID = customer_service.AddCustomer(dfCustomer, dfCustomerDetails)
            return HttpResponse(customerID)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)
    else:
        context = {
            'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name)
            }

        return render(request, 'customers/add.html', context)

@login_required(login_url='/login')
def EditCustomer(request: HttpRequest, pk: int):
    try:
        customer = models.Customer.objects.get(id=pk)
    except:
        return HttpResponse('Resource not found', status=404)
    
    if request.method == 'POST':
        #Convert the json to a dict
        jsonData = json.loads(request.body.decode('utf-8'))

        dfCustomer, dfCustomerDetails = refineJson(jsonData)
        del jsonData

        try:
            customer_service.EditCustomer(customer, dfCustomer, dfCustomerDetails)
            return HttpResponse('OK')
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)
    else:
        customerData, contactData = customer_service.GetDataForCustomer(customer)

        context = {
            'customerData': customerData, 'contactData': contactData,
            'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name)
        }
        
        return render(request, 'customers/edit.html', context)

@login_required(login_url='/login')
def ToggleAssignment(request: HttpRequest, pk: int):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=403)
    
    try:
        customer = models.Customer.objects.get(id=pk)
    except:
        return HttpResponse('Customer not found', status=404)
    
    if not customer.AccountManager:
        customer.AccountManager = request.user
    elif customer.AccountManager == request.user:
        customer.AccountManager = None
    else:
        return HttpResponse('Access Denied', status=403)

    customer.save()

    assignFilter = request.GET.get('assignFilter', 'Active')
    countryFilter = request.GET.get('countryFilter', None)
    page = request.GET.get('page', 1)
    search = request.GET.get('search', '')

    searchParams = {
        'assignFilter': assignFilter,
        'countryFilter': countryFilter,
        'page': page,
        'search': search,
    }

    url = f"{reverse('marketing:customerData')}?{urlencode(searchParams)}"


    return redirect(url)

@login_required(login_url='/login')
def PendingCorrespondance(request: HttpRequest):
    if request.method == 'POST':
        pass
    else:
        customer = request.GET.get('customer', '')
        type = request.GET.get('type', '')
        dueDate = request.GET.get('dueDate', '')
        search = request.GET.get('search', '')
        
        pendingCorrespondance = correspondance_service.GetPendingCorrespondance(customer, type, dueDate, request.user)
        pendingCorrespondance = applySearch(pendingCorrespondance, search)
        
        context = {
            'correspondances': pendingCorrespondance,
            'customer': customer, 'type': type, 'dueDate': dueDate, 'search': search,
            'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name)
        }
        return render(request, 'correspondance/pending.html', context)

@login_required(login_url='/login')
def CorresponanceHistory(request: HttpRequest):
    if request.method == 'POST':
        pass
    else:
        startDate = request.GET.get('startDate')
        endDate = request.GET.get('endDate')
        customerFilter = request.GET.get('customerFilter')
        search = request.GET.get('search','')

        if customerFilter == 'None':
            customerFilter = None
        
        #callsHostory = calling_service.GetCallHistory(startDate, endDate, customerFilter, request.user)

        customers = models.Customer.objects.filter(AccountManager=request.user).values('id', 'Name')

        context = {
            'startDate': startDate, 'endDate': endDate, 'customerFilter': customerFilter, 'search':search,
            'customers': customers,
            'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name)
        }
        return showMessageResponse(request, 'This page is in process', 200)
        return render(request, 'correspondance/home.html', context)