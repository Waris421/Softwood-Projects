from django.shortcuts import render, redirect
from django.http import HttpRequest, HttpResponse
from django.contrib.auth.decorators import login_required
from django.urls import reverse

import json

from .theme import theme
from . import models
from .services.generic_services import refineJson, applySearch, paginate
from .services import customer_service, calling_service

@login_required(login_url='/login')
def Home(request: HttpRequest):
    context = {
        'theme': theme
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
        'theme': theme
    }
    return render (request, 'customers/home.html', context)

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
        context = {'theme': theme}

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
            'theme': theme
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

    return redirect(reverse('customerData'))

@login_required(login_url='/login')
def PendingCalls(request: HttpRequest):
    if request.method == 'POST':
        pass
    else:
        return HttpResponse('In Progress')

@login_required(login_url='/login')
def CallHistory(request: HttpRequest):
    if request.method == 'POST':
        pass
    else:
        startDate = request.GET.get('startDate')
        endDate = request.GET.get('endDate')
        customerFilter = request.GET.get('customerFilter')
        search = request.GET.get('search','')

        if customerFilter == 'None':
            customerFilter = None
        
        callsHostory = calling_service.GetCallHistory(startDate, endDate, customerFilter, request.user)

        customers = models.Customer.objects.filter(AccountManager=request.user).values('id', 'Name')

        context = {
            'startDate': startDate, 'endDate': endDate, 'customerFilter': customerFilter, 'search':search,
            'customers': customers,
            'theme': theme
        }
        return render(request, 'calls/home.html', context)