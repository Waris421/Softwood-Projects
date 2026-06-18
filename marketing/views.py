from django.shortcuts import render, redirect
from django.http import HttpRequest, HttpResponse, JsonResponse, StreamingHttpResponse
from django.contrib.auth.decorators import login_required
from django.urls import reverse

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework.permissions import  AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework import status

import json
from urllib.parse import urlencode

from core.constants.theme import theme
from . import models
from core.services import auth_service
from core.services.generic_services import refineJson, applySearch, paginate, showMessageResponse
from core.services.auth_service import AppModelPermissions, hasPermission
from .services import correspondance_service, customer_service, export_data_serivce

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

class ExportDataMonths(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'marketing'
    modelName = 'ExportData'
    permissionType = 'view'

    def get(self, request: Request):
        countries = request.query_params.getlist('countries[]', [])
        importers = request.query_params.getlist('importers[]', [])
        exporters = request.query_params.getlist('exporters[]', [])
        categories = request.query_params.getlist('categories[]', [])

        try:
            monthWiseData = export_data_serivce.GetMonthSummary(
                importers, exporters, categories, countries
            )
            return Response(data=monthWiseData, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

@login_required(login_url='/login')
def ExportData (request: HttpRequest):
    if request.method != 'GET':
        return showMessageResponse(request, 'Not Allowed', 403)

    countries = request.GET.getlist('countries[]', [])
    importers = request.GET.getlist('importers[]', [])
    exporters = request.GET.getlist('exporters[]', [])
    categories = request.GET.getlist('categories[]', [])
    months = request.GET.getlist('months[]')
    
    try:
        months = export_data_serivce.GetMonthWiseQty(months, countries, importers, exporters)
    except Exception as e:
        print(f'Main Page: {e}')
        return showMessageResponse(request, 'An Error Occured', 400)
    
    try:
        checks = export_data_serivce.CalculateChecks(months, importers, exporters, categories, countries)
    except Exception as e:
        print(f'Main Page: {e}')
        return showMessageResponse(request, 'An Error Occured', 400)
    
    context = {
        'settingsIconViewName': 'marketing:exportDataSettings',
        'countries': countries, 'countriesJson': json.dumps(countries),
        'importers': importers, 'importersJson': json.dumps(importers),
        'exporters': exporters, 'exportersJson': json.dumps(exporters),
        'categories': categories, 'categoriesJson': json.dumps(categories),
        'months': months, 'monthsJson': json.dumps(months),
        'checks': checks,
        'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name)
    }
    return render (request, 'export_data/home.html', context)

class ExportDataCountriesAPI(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'marketing'
    modelName = 'ExportData'
    permissionType = 'view'

    def get(self, request: Request):
        months = request.query_params.getlist('months', [])
        importers = request.query_params.getlist('importers', [])
        exporters = request.query_params.getlist('exporters', [])
        categories = request.query_params.getlist('categories', [])
        countries = request.query_params.getlist('countries', [])

        try:
            countryData = export_data_serivce.GetCountrySummaryAPI(
                months, importers, exporters, categories, countries
            )
            return Response(data=countryData, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

@login_required(login_url='/login')
def ExportDataCountries(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=403)
    
    months = request.GET.getlist('months[]', [])
    importers = request.GET.getlist('importers[]', [])
    exporters = request.GET.getlist('exporters[]', [])
    categories = request.GET.getlist('categories[]', [])
    countries = request.GET.getlist('countries[]', [])
    
    minQty = request.GET.get('minQty', None)
    maxQty = request.GET.get('maxQty', None)
    minPrice = request.GET.get('minPrice', None)
    maxPrice = request.GET.get('maxPrice', None)
    search = request.GET.get('search', None)

    if minQty == 'None':
        minQty = None
    if maxQty == 'None':
        maxQty = None
    if minPrice == 'None':
        minPrice = None
    if maxPrice == 'None':
        maxPrice = None

    try:
        countrySummary = export_data_serivce.GetCountrySummary(
            months, importers, exporters, categories, countries, search,
            minQty, maxQty, minPrice, maxPrice
        )
        return JsonResponse(countrySummary, safe=False)
    except Exception as e:
        print(f'Countries: {e}')
        return HttpResponse('An error occured. Check with your administrator', status=400)

@login_required(login_url='/login')
def ExportDataCategories(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=403)
    
    months = request.GET.getlist('months[]', [])
    importers = request.GET.getlist('importers[]', [])
    exporters = request.GET.getlist('exporters[]', [])
    countries = request.GET.getlist('countries[]', [])
    
    minQty = request.GET.get('minQty', None)
    maxQty = request.GET.get('maxQty', None)
    minPrice = request.GET.get('minPrice', None)
    maxPrice = request.GET.get('maxPrice', None)

    if minQty == 'None':
        minQty = None
    if maxQty == 'None':
        maxQty = None
    if minPrice == 'None':
        minPrice = None
    if maxPrice == 'None':
        maxPrice = None

    try:
        categorySummary = export_data_serivce.GetCategorySummary(
            months, importers, exporters, countries,
            minQty, maxQty, minPrice, maxPrice
        )
        return JsonResponse(categorySummary, safe=False)
    except Exception as e:
        print(f'Categories: {e}')
        return HttpResponse('An error occured. Check with your administrator', status=400)

@login_required(login_url='/login')
def ExportDataImporters(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=403)
    
    months = request.GET.getlist('months[]', [])
    countries = request.GET.getlist('countries[]', [])
    exporters = request.GET.getlist('exporters[]', [])
    categories = request.GET.getlist('categories[]', [])
    importers = request.GET.getlist('importers[]', [])
    
    minQty = request.GET.get('minQty', None)
    maxQty = request.GET.get('maxQty', None)
    minPrice = request.GET.get('minPrice', None)
    maxPrice = request.GET.get('maxPrice', None)
    search = request.GET.get('search', None)

    if minQty == 'None':
        minQty = None
    if maxQty == 'None':
        maxQty = None
    if minPrice == 'None':
        minPrice = None
    if maxPrice == 'None':
        maxPrice = None

    try:
        importerSummary = export_data_serivce.GetImporterSummary(
            months, countries, exporters, categories, importers, search,
            minQty, maxQty, minPrice, maxPrice
        )
    except Exception as e:
        print(f'Importers: {e}')
        return HttpResponse('An error occured. Check with your administrator', status=400)

    return JsonResponse(importerSummary, safe=False)

@login_required(login_url='/login')
def ExportDataExporters(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=403)
    
    months = request.GET.getlist('months[]', [])
    countries = request.GET.getlist('countries[]', [])
    importers = request.GET.getlist('importers[]', [])
    categories = request.GET.getlist('categories[]', [])
    exporters = request.GET.getlist('exporters[]', [])
    
    minQty = request.GET.get('minQty', None)
    maxQty = request.GET.get('maxQty', None)
    minPrice = request.GET.get('minPrice', None)
    maxPrice = request.GET.get('maxPrice', None)
    search = request.GET.get('search', None)

    if minQty == 'None':
        minQty = None
    if maxQty == 'None':
        maxQty = None
    if minPrice == 'None':
        minPrice = None
    if maxPrice == 'None':
        maxPrice = None

    try:
        exporterSummary = export_data_serivce.GetExporterSummary(
            months, countries, importers, categories, exporters, search,
            minQty, maxQty, minPrice, maxPrice
        )
        return JsonResponse(exporterSummary, safe=False)
    except Exception as e:
        print(f'Exporters: {e}')
        return HttpResponse('An error occured. Check with your administrator', status=400)

@login_required(login_url='/login')
def ExportDataTable(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=403)
    
    months = request.GET.getlist('months[]', [])
    countries = request.GET.getlist('countries[]', [])
    importers = request.GET.getlist('importers[]', [])
    exporters = request.GET.getlist('exporters[]', [])
    categories = request.GET.getlist('categories[]', [])
    
    minQty = request.GET.get('minQty', None)
    maxQty = request.GET.get('maxQty', None)
    minPrice = request.GET.get('minPrice', None)
    maxPrice = request.GET.get('maxPrice', None)
    
    page = request.GET.get('page', '1')

    if minQty == 'None':
        minQty = None
    if maxQty == 'None':
        maxQty = None
    if minPrice == 'None':
        minPrice = None
    if maxPrice == 'None':
        maxPrice = None

    try:
        dataTable, numberOfPages = export_data_serivce.GetDetailsTable(
            months, countries, exporters, importers, categories, page,
            minQty, maxQty, minPrice, maxPrice
        )
        data = {
            'data': dataTable, 'numberOfPages': numberOfPages,
        }
        return JsonResponse(data, safe=False)    
    except Exception as e:
        print(f'Data Table: {e}')
        return HttpResponse('An error occured. Check with your administrator', status=400)

@login_required(login_url='/login')
def ExportDataStats(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=403)
    
    months = request.GET.getlist('months[]', [])
    countries = request.GET.getlist('countries[]', [])
    importers = request.GET.getlist('importers[]', [])
    exporters = request.GET.getlist('exporters[]', [])
    categories = request.GET.getlist('categories[]', [])

    minQty = request.GET.get('minQty', None)
    maxQty = request.GET.get('maxQty', None)
    minPrice = request.GET.get('minPrice', None)
    maxPrice = request.GET.get('maxPrice', None)

    if minQty == 'None':
        minQty = None
    if maxQty == 'None':
        maxQty = None
    if minPrice == 'None':
        minPrice = None
    if maxPrice == 'None':
        maxPrice = None

    try:
        stats = export_data_serivce.GetStats(
            months, countries, exporters, importers, categories,
            minQty, maxQty, minPrice, maxPrice
        )
        return JsonResponse(stats, safe=False)
    except Exception as e:
        print(f'Stats: {e}')
        return HttpResponse('An error occured. Check with your administrator', status=400)

@login_required(login_url='/login')
def ExportDataSliders(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=403)
    
    months = request.GET.getlist('months[]', [])
    countries = request.GET.getlist('countries[]', [])
    importers = request.GET.getlist('importers[]', [])
    exporters = request.GET.getlist('exporters[]', [])
    categories = request.GET.getlist('categories[]', [])
    
    try:
        paramters = export_data_serivce.GetSliderParamters(
            months, countries, exporters, importers, categories
        )
        return JsonResponse(paramters, safe=False)
    except Exception as e:
        print(f'Quantity: {e}')
        return HttpResponse('An error occurred', status=400)

@login_required(login_url='/login')
def ExportDataDownload(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=403)
    
    months = request.GET.getlist('months[]', [])
    countries = request.GET.getlist('countries[]', [])
    importers = request.GET.getlist('importers[]', [])
    exporters = request.GET.getlist('exporters[]', [])
    categories = request.GET.getlist('categories[]', [])

    minQty = request.GET.get('minQty', None)
    maxQty = request.GET.get('maxQty', None)
    minPrice = request.GET.get('minPrice', None)
    maxPrice = request.GET.get('maxPrice', None)

    if minQty == 'None':
        minQty = None
    if maxQty == 'None':
        maxQty = None
    if minPrice == 'None':
        minPrice = None
    if maxPrice == 'None':
        maxPrice = None

    try:
        dfData = export_data_serivce.DownLoadExportData(
            months, countries, exporters, importers, categories,
            minQty, maxQty, minPrice, maxPrice
        )
    except Exception as e:
        print(e)
        return HttpResponse(e, status=400)

    response = HttpResponse(
        content_type='text/csv',
        headers={'Content-Disposition': 'attachment; filename="data.csv"'},
        status=200,
    )
    dfData.to_csv(path_or_buf=response, index=False, encoding='utf-8', float_format='%.2f')
    
    return response

@login_required(login_url='/login')
def ExportDataSettings(request: HttpRequest):
    if not hasPermission(request.user, 'marketing', 'ExportDataDraft','add'):
        return showMessageResponse(request, 'Access Denied', statusCode=403)
    
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=403)    

    context = {
        'settingsIconViewName': 'marketing:exportDataSettings',
        'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name)
    }
    return render(request, 'export_data/settings.html', context)

@login_required(login_url='/login')
def RefineImporters(request: HttpRequest):
    if not hasPermission(request.user, 'marketing', 'ImporterAlias', 'change'):
        return showMessageResponse(request, 'Access Denied', statusCode=403)

    if request.method == 'POST':
        jsonData = json.loads(request.body.decode('utf-8'))

        dfAliases = refineJson(jsonData)
        
        try:
            export_data_serivce.SaveImportersAlias(dfAliases)
            return HttpResponse('OK', status=200)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)
    else:
        filterMethod = request.GET.get('filterMethod', None)
        search = request.GET.get('search', '')
        
        importersData, currentCount, totalCount = export_data_serivce.GetImportersForRefinement(filterMethod, search)
        context = {
            'importersData': importersData,
            'currentCount': currentCount, 'totalCount': totalCount,
            'filterMethod': filterMethod, 'search': search,
            'settingsIconViewName': 'marketing:exportDataSettings',
            'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name)
        }
        return render (request, 'export_data/importer_alias.html', context)

@login_required(login_url='/login')
def RefineExporters(request: HttpRequest):
    if not hasPermission(request.user, 'marketing', 'ExporterAlias', 'change'):
        return showMessageResponse(request, 'Access Denied', statusCode=403)
    
    if request.method == 'POST':
        jsonData = json.loads(request.body.decode('utf-8'))

        dfAliases = refineJson(jsonData)

        try:
            export_data_serivce.SaveExportersAlias(dfAliases)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)

        return HttpResponse('Ok', status=200)
    else:
        filterMethod = request.GET.get('filterMethod', None)
        search = request.GET.get('search', '')

        try:
            exportersData, currentCount, totalCount  = export_data_serivce.GetExportersForRefinement(filterMethod, search)
        except Exception as e:
            print(e)
            return showMessageResponse(request, str(e), 400)

        context = {
            'exportersData': exportersData,
            'currentCount': currentCount, 'totalCount': totalCount,
            'filterMethod': filterMethod, 'search': search,
            'settingsIconViewName': 'marketing:exportDataSettings',
            'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name)
        }

        return render(request, 'export_data/exporter_alias.html', context)

@login_required(login_url='/login')
def UploadExportReport(request:HttpRequest):
    if request.method == 'POST':
        dataFile = request.FILES['exportDataFile']        
        try:
            export_data_serivce.ExtractUploadedData(dataFile)
            return showMessageResponse(request, 'Data Submitted for approval', 200, 'marketing:exportDataSettings')
        except Exception as e:
            print(e)
            context = {
                'error': str(e),
                'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name)
            }
            return render(request, 'export_data/upload.html', context, status=400)
    else:
        context = {
            'settingsIconViewName': 'marketing:exportDataSettings',
            'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name)
        }
        return render(request, 'export_data/upload.html', context)

@login_required(login_url='/login')
def UploadExportReportConfirmation(request:HttpRequest):
    if not hasPermission(request.user, 'marketing', 'ExportData','add'):
        return showMessageResponse(request, 'Access Denied', statusCode=403)

    if request.method == 'POST':
        action = request.POST.get('action')
        
        try:
            export_data_serivce.ConfirmPendingUploads(action)
            return redirect(reverse('marketing:exportData'))
        except Exception as e:
            print(e)
            return showMessageResponse(request, str(e), 400)
    else:
        try:
            pendingUploads, addedMonths = export_data_serivce.GetPendingUploads()
            context = {
                'pendingUploads': pendingUploads, 'addedMonths': addedMonths,
                'settingsIconViewName': 'marketing:exportDataSettings',
                'theme': theme, 'navLinks': auth_service.getNavLinks(request.user, request.resolver_match.app_name)
            }
            return render(request, 'export_data/confirm_upload.html', context)
        except Exception as e:
            print(e)
            return showMessageResponse(request, str(e), 400, 'marketing:exportDataSettings')

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