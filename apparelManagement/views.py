from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse, HttpRequest
from django.urls import reverse
from django.db import transaction
from django.db.models.deletion import Collector, ProtectedError

import pandas as pd
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework import status
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework.parsers import MultiPartParser, FormParser

import json

from core.constants.theme import theme
from core.services import generic_services
from core.services.auth_service import authenticateUser, AppModelPermissions, hasPermission, getNavLinks, canApprovePD

from . import models
from .services import notifications_service
from .services import inventory_card_service, style_card_service, work_order_service
from .services import purchase_receipt_service, purchase_order_service, purchase_demand_service
from .services import requisition_service, issuance_service

@login_required(login_url='/login')
def home (request: HttpRequest):
    notifications = notifications_service.GetNotifications(request.user)
    
    context = {
        'data': json.dumps(list(notifications)),
        'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name),
    }
    return render(request, 'apparelManagement/home.html', context)

@login_required(login_url='/login')
def GetNotificationDetails(request: HttpRequest, pk: int):
    if request.method != 'GET':
        return HttpResponse('Not alloed', status=405)
    
    details = notifications_service.GetNotificationDetails(pk)
    return JsonResponse(details, safe=False)

@login_required(login_url='/login')
def ReadNotification (request: HttpRequest, pk:int):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=200)
    
    try:
        notifications_service.ReadNotification(pk, request.user)
        return HttpResponse('OK', status=200)
    except Exception as e:
        return HttpResponse(e, status=400)

@login_required (login_url='/login')
def Inventory (request: HttpRequest):
    if request.method != 'GET':
        return generic_services.showMessageResponse(request, 'Not allowed', 405)

    if not hasPermission(request.user, 'apparelManagement', 'Inventory', type='view'):
        return generic_services.showMessageResponse(request, 'Access Denied', 403)
    
    searchTerm = request.GET.get('search_term', '')
    groupFilter = request.GET.get('groupFilter', 'Trim')
    stockFilter = request.GET.get('stockFilter','All')
    pageNumber = request.GET.get('page',1)
    
    if not groupFilter:
        groupFilter = None
    
    inv = inventory_card_service.GetInventories(group=groupFilter, stockFilter=stockFilter)
    inv = generic_services.applySearch(inv, searchTerm)
    data = generic_services.paginate(inv, pageNumber)

    groups = sorted([group for group, in models.Inventory.objects.values_list('Group').distinct()])
    
    context = {'inv': data.object_list, 'page_obj': data,
               'searchTerm': searchTerm, 'groups': groups, 'selectedGroup': groupFilter,
               'stockFilter': stockFilter,
               'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)}
    return render (request, 'inventory/home.html',context)

class APIInvenotory(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request):
        try:
            inventoryData = inventory_card_service.GetInventories(group='', stockFilter='', inUseFilter=None)
            return Response(data=inventoryData, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

class APIInventoryAdd(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request):
        try:
            authenticateUser(request, 'apparelManagement', 'Inventory', 'add')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            formData = inventory_card_service.GetDataForInvCardAddition()
            return Response(data=formData, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)
    
    def post(self, request: Request):
        try:
            authenticateUser(request, 'apparelManagement', 'Inventory', 'add')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            addedCode = inventory_card_service.AddAPIInventory(request.data)
            response = {'code': addedCode}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)
        
@login_required(login_url = '/login')
def AddInv (request: HttpRequest): 
    if not hasPermission(request.user, 'apparelManagement', 'Inventory', type='add'):
        return generic_services.showMessageResponse(request, 'Access Denied', 403)
       
    if request.method == 'POST':
        fields = ['Code', 'Name', 'Group', 'Unit', 'AuditReq', 'Life', 'LeadTime', 'MinStockLvl', 'StandardPrice', 'Currency', 'InUse']
        data = {field: request.POST.get(field) for field in fields}

        try:
            inventoryCode = inventory_card_service.AddInventory(data)
            return redirect(reverse('apparelManagement:editInv', kwargs={'pk': inventoryCode}))
        except Exception as e:
            print(e)
            return generic_services.showMessageResponse(request, str(e), 405)
    else:
        groups, unitTypes, auditReq, inUse, currencies,  codeP1  = inventory_card_service.getInventoryCardDropDowns()
        context = {
            'groups': groups, 'unitTypes': unitTypes, 'auditReq': auditReq, 'inUse': inUse,'currencies': currencies,
            'codeP1': codeP1,
            'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)
            }
        
        return render (request, 'inventory/add.html', context)

class GenerateInventoryCodeAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request):
        try:
            authenticateUser(request, 'apparelManagement', 'WorkOrder', 'view')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)

        try:
            responseData = inventory_card_service.GenerateInvCode(request.data)
            return Response(data=responseData, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

@login_required(login_url='/login')
def GenerateInventoryCode (request: HttpRequest):
    if request.method != 'POST':
        return HttpResponse('Not allowed', status=405)
    
    jsonData = json.loads(request.body.decode('utf-8'))
    
    try:
        data = inventory_card_service.GenenrateCode(jsonData)
        return JsonResponse(data, safe=False)
    except Exception as e:
        print(e)
        return HttpResponse(e, status=400)

class CheckInventoryCodeForAddition(APIView):
    permission_classes = [AllowAny]
    def get(self, request: Request):
        try:
            authenticateUser(request, 'apparelManagement', 'WorkOrder', 'view')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)
        
        code = request.query_params.get('code', None)
        if code is None:
            response = {'message': 'Invalid Code'}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            models.Inventory.objects.get(Code=code)
            response = {'message': 'Code Exists'}
            return Response(data=response, status=status.HTTP_409_CONFLICT)
        except:
            response = {'message': 'OK'}
            return Response(data=response, status=status.HTTP_200_OK)

@login_required(login_url='/login')
def CheckInventoryCodeExists(request: HttpRequest, pk: str):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', code=405)
    
    try:
        models.Inventory.objects.get(Code=pk)
        return HttpResponse('Code already exists', status=400)
    except:
        return HttpResponse('OK', status=200)

class APIInventoryUpdate(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request, pk: str):
        try:
            authenticateUser(request, 'apparelManagement', 'Inventory', 'change')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            inventory = models.Inventory.objects.get(Code=pk)
        except:
            response = {'message': 'Resource not found'};
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)
        del pk

        try:
            formData = inventory_card_service.GetDataForInvCardUpdate(inventory)  
            return Response(data=formData, status=status.HTTP_200_OK) 
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)
    
    def post(self, request: Request, pk: str):
        try:
            authenticateUser(request, 'apparelManagement', 'Inventory', 'change')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            inventory = models.Inventory.objects.get(Code=pk)
        except:
            response = {'message': 'Resource not found'};
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)
        del pk

        try:
            inventory_card_service.UpdateInventory(inventory, request.data)
            response = {'message': 'Saved'}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

@login_required(login_url = '/login')
def UpdateInv(request: HttpRequest, pk: str):
    if not hasPermission(request.user, 'apparelManagement', 'Inventory', type='change'):
        return generic_services.showMessageResponse(request, 'Access Denied', 403)
    
    try:
        inv = models.Inventory.objects.get(Code=pk)
    except:
        return generic_services.showMessageResponse(request, 'Resource not Found', 400)

    if request.method == 'POST':
        fields = ['Code', 'Name', 'Group', 'Unit', 'AuditReq', 'Life', 'LeadTime', 'MinStockLvl', 'StandardPrice', 'Currency', 'InUse']
        data = {field: request.POST.get(field) for field in fields}
        try:
            inventory_card_service.EditInventory(data, inv)
            return redirect(reverse('apparelManagement:editInv', kwargs={'pk': pk}))
        except Exception as e:
            print(e)
            return generic_services.showMessageResponse(request, str(e))
    else:
        groups, unitTypes, auditReq, inUse, currencies,  codeP1  = inventory_card_service.getInventoryCardDropDowns()
        
        units = models.Unit.objects.filter(Group=inv.Unit.Group).values('Name')
        temp = []
        for item in units:
            temp.append({'value':item['Name'],'text':item['Name'],})
        units = temp
        del temp

        context = {
            'inv': inv, 'units': units,
            'groups': groups, 'unitTypes': unitTypes, 'auditReq': auditReq, 'inUse': inUse,'currencies': currencies,
            'codeP1': codeP1,
            'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)
        }
        return render (request, 'inventory/edit.html', context)

class APIInventoryDelete(APIView):
    permission_classes = [AllowAny]

    def delete(self, request: Request, pk: str):
        try:
            authenticateUser(request, 'apparelManagement', 'Inventory', 'add')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            inventory = models.Inventory.objects.get(Code=pk)
        except:
            response = {'message': 'Resource not found'}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

        try:
            inventory.delete()
            response = {'message': 'Saved successfully'}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)
        
@login_required(login_url = '/login')
def DeleteInv(request: HttpRequest, pk: int):
    if not hasPermission(request.user, 'apparelManagement', 'Inventory', type='delete'):
        return generic_services.showMessageResponse(request, 'Access Denied', 403)
    
    try:
        inv = models.Inventory.objects.get(Code=pk)
    except:
        return generic_services.showMessageResponse(request, 'Resource Not Found', 404)

    if request.method == 'POST':
        if 'confirm' in request.POST:
            try:
                inv.delete()
                return redirect('/inv')
            except Exception as e:
                context = {'object': inv, 'confirm': True, 'theme': theme, 'error': e, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)}
                return render(request, 'inventory/delete.html', context)
        else:
            return redirect('/inv')
    else:
        context = {'object':inv, 'confirm':True, 'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)}
        return render(request, 'inventory/delete.html', context)

class APIInventoryCopy(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request, pk: str):
        try:
            authenticateUser(request, 'apparelManagement', 'Inventory', 'add')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)
        
        sourceCode = request.data.get('Source', None)
        targetCode = request.data.get('Target', None)

        if None in [sourceCode, targetCode]:
            response = {'message': 'Incomplete Data Provided'}
            return Response(data=response, status=status.HTTP_409_CONFLICT)

        try:
            inventory_card_service.DuplicateInventory(sourceCode, targetCode)
            response = {'message': 'Added Successfully'}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

@login_required(login_url = '/login')
def CopyInv (request: HttpRequest, pk: str): 
    if not hasPermission(request.user, 'apparelManagement', 'Inventory', type='add'):
        return generic_services.showMessageResponse(request, 'Access Denied', 403)
    
    if request.method == 'POST':
        sourceCode = request.POST.get('source')
        targetCode = request.POST.get('target')

        if not targetCode:
            context = {'message': 'No Code provided','theme': theme, 'code': pk, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)}
            return render(request, 'inventory/copy.html', context)

        try:
            models.Inventory.objects.get(Code=targetCode)
            context = {'message': 'Code Already Exists','theme': theme, 'code': pk, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)}
            return render(request, 'inventory/copy.html', context)
        except:
            Inventory = models.Inventory.objects.get(Code=sourceCode)
            Inventory.Code = targetCode
            Inventory.save()

            return redirect(f'/inv/{targetCode}/edit')
    else:
        context = {'theme': theme, 'code': pk, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)}
        return render(request, 'inventory/copy.html', context)

@login_required(login_url='/login')
def InventoryReports(request: HttpRequest):
    if request.method != 'GET':
        return generic_services.showMessageResponse(request, 'Not allowed', 405)

    if not hasPermission(request.user, 'apparelManagement', 'Inventory', type='view'):
        return generic_services.showMessageResponse(request, 'Access Denied', 403)

    context = {'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)}
    return render(request, 'inventory/reports_home.html', context)

class InventoryStockStatus(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request):
        try:
            authenticateUser(request, 'apparelManagement', 'Inventory', type='view')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)
            
        try:
            stockStatus = inventory_card_service.GetInventoryStockStatus()
            return Response(data=stockStatus, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)
        
@login_required(login_url='/login')
def UnOrderedInventory(request: HttpRequest):
    if not hasPermission(request.user, 'apparelManagement', 'Inventory', type='view'):
        return generic_services.showMessageResponse(request, 'Access Denied', 403)
    
    if request.method == 'POST':
        return HttpResponse('Under Construction', status=503)
    else:
        merchandiser = request.GET.get('merchandiser', '')
        inventory = request.GET.get('inventory', '')
        customer = request.GET.get('customer', '')
        type = request.GET.get('type', '')
        startDate = request.GET.get('startDate', None)
        endDate = request.GET.get('endDate', None)

        inventory_card_service.GetUnorderedInventories(merchandiser, customer, type, startDate, endDate, inventory)

        context = {
            'merchandiser': merchandiser, 'inventory': inventory, 'customer': customer,
            'type': type, 'startDate':startDate, 'endDate': endDate,
            'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)
        }
        return render(request, 'inventory/report_unordered.html', context)

@login_required(login_url='/login')
def InventoryFreeStockReport(request: HttpRequest):
    if request.method != 'GET':
        return generic_services.showMessageResponse(request, 'Not allowed', 405)

    if not hasPermission(request.user, 'apparelManagement', 'Inventory', type='view'):
        return generic_services.showMessageResponse(request, 'Access Denied', 403)
    
    type = request.GET.get('type', 'FABRIC')
    minStockLvl = request.GET.get('minStockLvl', None)
    approval = request.GET.get('approval', '')

    try:
        freeStockQuantity = inventory_card_service.GetFreeStockQuantity(type, minStockLvl, approval)
    except Exception as e:
        print(e)
        return generic_services.showMessageResponse(
            request, 'An error occurred. Check with your administrator', 400
        )

    context = {
        'inv': freeStockQuantity,
        'type': type, 'minStockLvl': minStockLvl, 'approval': approval,
        'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)
    }
    return render(request, 'inventory/report_free_stock.html', context)

@login_required(login_url='/login')
def InventoryFreeStockHistory(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not allowed', status=405)

    if not hasPermission(request.user, 'apparelManagement', 'Inventory', type='view'):
        return HttpResponse('Not allowed', status=403)

    inventoryCode = request.GET.get('code', None)
    variant = request.GET.get('variant', None)
    if not inventoryCode:
        return HttpResponse('Invalid Input', status=400)
    
    if variant is None:
        return HttpResponse('Invalid Input', status=400)
    
    try:
        inventory = models.Inventory.objects.get(Code=inventoryCode)
        del inventoryCode
    except:
        return HttpResponse('Invalid Inventory Code', status=400)

    try:
        history = inventory_card_service.GetFreeStockHistory(inventory, variant)
    except Exception as e:
        print(e)
        return HttpResponse(e, status=400)
    
    return JsonResponse(history, safe=False)

class StyleCards(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request):
        try:
            styles = style_card_service.GetStyleCards()
            return Response(data=styles, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@login_required(login_url = '/login')
def Style (request: HttpRequest):
    if not hasPermission(request.user, 'apparelManagement', 'StyleCard', type='view'):
        return generic_services.showMessageResponse(request, 'Access Denied', 403)
    
    if request.method == 'GET':
        searchTerm = request.GET.get('searchTerm', '')
        customerFilter = request.GET.get('customerFilter', '')
        pageNumber = request.GET.get('pageNumber',1)

        styles = style_card_service.getStyleCard(customerFilter)
        customers = sorted([customer for customer, in models.StyleCard.objects.values_list('Customer_id').distinct()if customer is not None])

        styles = generic_services.applySearch(styles, searchTerm)
        data = generic_services.paginate(styles, pageNumber)

        context = {'style': data.object_list, 'page_obj': data
                ,'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)
                ,'customers': customers, 'searchTerm': searchTerm, 'selectedCustomer': customerFilter}

        return render(request, 'style/home.html', context)
    else:
        return generic_services.showMessageResponse(request, 'Not Allowed', 403)

@login_required(login_url = '/login')
def AddStyle (request: HttpRequest):
    if not hasPermission(request.user, 'apparelManagement', 'StyleCard', type='add'):
        return generic_services.showMessageResponse(request, 'Access Denied', 403)
    
    if request.method == 'POST':

        dfStyle, dfRoute, dfVariants = generic_services.refineFormData(request) 
        
        try:
            styleCode = style_card_service.AddStyleCard(dfStyle, dfVariants, dfRoute)       
            return HttpResponse(styleCode, status=200)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)
         
    else:
        context = {
            'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)
        }
        return render (request, 'style/add.html', context)

@login_required(login_url='/login')
def UpdateStyle (request: HttpRequest, pk: str):
    if not hasPermission(request.user, 'apparelManagement', 'StyleCard', type='change'):
        return generic_services.showMessageResponse(request, 'Access Denied', 403)

    try:
        style = models.StyleCard.objects.get(StyleCode=pk)
    except:
        return generic_services.showMessageResponse(request, 'Resource Not Found', 400)
    if request.method == 'POST':
        dfStyle, dfRoute, dfVariants, dfConsumption, dfAttachments = generic_services.refineFormData(request)

        try:
            style_card_service.UpdateStyleCard(dfStyle, dfVariants, dfConsumption, dfRoute, dfAttachments)
            return HttpResponse('OK', status=200)
        except Exception as e:
            print(e)
            return HttpResponse(str(e), status=400)
    else:
        try:
            style, variants, consumption, route, attachments = style_card_service.ProcessStyleData(style)
        except Exception as e:
            print(e)
            return generic_services.showMessageResponse(request, str(e))
        
        context = {'style':style,
                'var':variants,
                'cons':consumption, 'consJson': json.dumps(list(consumption)),
                'route':route, 'routeJson':json.dumps(list(route)),
                'attachments': attachments, 'attachmentsJson': json.dumps(attachments),
                'theme':theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)}
        return render(request, 'style/edit.html', context)

@login_required(login_url='/login')
def DeleteStyle(request: HttpRequest, pk: str):
    if not hasPermission(request.user, 'apparelManagement', 'StyleCard', type='delete'):
        return generic_services.showMessageResponse(request, 'Access Denied', 403)
    
    try:
        style = models.StyleCard.objects.get(StyleCode=pk)
    except:
        return generic_services.showMessageResponse(request, 'Resource Not Found', 404)

    if request.method == 'POST':
        if 'confirm' in request.POST:
            try:
                style.delete()
                return redirect('/style')
            except Exception as e:
                context = {'object':style, 'confirm':True, 'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name),
                           'error': e}
                return render(request, 'style/delete.html', context)
        else:
            return redirect('/style')
    
    else:
        context = {'object':style, 'confirm':True, 'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)}
        return render(request, 'style/delete.html', context)

@login_required(login_url='/login')
def CopyStyle(request: HttpRequest, pk: str):
    if not hasPermission(request.user, 'apparelManagement', 'StyleCard', type='add'):
        return generic_services.showMessageResponse(request, 'Access Denied', 403)

    try:
        style = models.StyleCard.objects.get(StyleCode=pk)
    except:
        return generic_services.showMessageResponse(request, 'Resource Not Found', 404)

    if request.method == 'POST':
        sourceCode = request.POST.get('source')
        targetCode = request.POST.get('target')

        if not targetCode:
            print('No target code provided')
            context = {'message': 'No Code provided','theme': theme, 'source':style.StyleCode, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)}
            return render(request, 'style/copy.html', context, status=400)

        try:
            models.StyleCard.objects.get(StyleCode=targetCode)
            print('Code already exisits')
            context = {'message': 'Code Already Exists','theme': theme, 'source':style.StyleCode, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)}
            return render(request, 'style/copy.html', context, status=400)
        except models.StyleCard.DoesNotExist:
            with transaction.atomic():
                styleObj = models.StyleCard.objects.get(StyleCode=sourceCode)
                styleObj.StyleCode = targetCode
                styleObj.save()

                styleObj = models.StyleCard.objects.get(StyleCode=targetCode)

                sourceVariants = models.StyleVariant.objects.filter(Style=sourceCode)
                targetVariants = []
                for variant in sourceVariants:
                    variant.pk = None
                    variant.Style = styleObj
                    targetVariants.append(variant)
                
                sourceConsumptions = models.StyleConsumption.objects.filter(Style=sourceCode)
                targetConsumptions = []
                for consumption in sourceConsumptions:
                    consumption.pk = None
                    consumption.Style = styleObj
                    targetConsumptions.append(consumption)
                
                sourceAttachments = models.StyleCard.objects.get(StyleCode=sourceCode).Attachments.all()
                targetAttachments = []
                for attachment in sourceAttachments:
                    newAttachment = models.Attachment(
                        File=attachment.File,
                        Description=attachment.Description,
                        Content = styleObj
                    )
                    targetAttachments.append(newAttachment)
                
                models.StyleVariant.objects.bulk_create(targetVariants)
                models.StyleConsumption.objects.bulk_create(targetConsumptions)
                models.Attachment.objects.bulk_create(targetAttachments)

                return redirect(f'/style/{targetCode}/edit')   
        except Exception as e:
            print(e)
            context = {'message': f'Error: {e}', 'theme': theme}
            return render(request, 'style/copy.html', context, status=400)
    else:
        context = {'source':style.StyleCode, 'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)}
        return render(request, 'style/copy.html', context)

def StyleRoutePrssetDetails(request: HttpRequest):
    if request.method != 'GET':
        return generic_services.showMessageResponse(request, 'Not allowed', 403)
    
    id = request.GET.get('id', None)

    if id:
        try:
            routePreset = models.RoutePreset.objects.get(id=id)
        except:
            return HttpResponse('Invalid Preset', status=400)

        data = style_card_service.GetRoutePresetStages(routePreset)
    else:
        data = []

    return JsonResponse(data, safe=False)

@login_required(login_url='/login')
def WorkOrder (request: HttpRequest):
    if not hasPermission(request.user, 'apparelManagement', 'WorkOrder', type='view'):
        return generic_services.showMessageResponse(request, 'Access Denied', 403)

    if request.method != 'GET':
        return generic_services.showMessageResponse(request, 'Not allowed', 403)
    
    searchTerm = request.GET.get('searchTerm', '')
    customerFilter = request.GET.get('customerFilter', '')
    pageNumber = request.GET.get('pageNumber',1)
    startDate = request.GET.get('startDate', None)
    endDate = request.GET.get('endDate', None)

    if customerFilter == 'null':
        customerFilter = ''

    orders = work_order_service.GetOrderList(customerFilter, startDate, endDate)
    orders = generic_services.applySearch(orders, searchTerm)

    data = generic_services.paginate(orders, pageNumber)

    context = {'order': data.object_list, 'page_obj': data,
               'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name),
               'startDate': startDate, 'endDate': endDate,
               'searchTerm': searchTerm, 'selectedCustomer': customerFilter}

    return render(request, 'work_order/home.html', context)

class WorkOrders(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request):
        currentOrders = request.data.get('currentOrders')
        try:
            orderData = work_order_service.GetOrdersForIntegration(currentOrders)
            return Response(data=orderData, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@login_required(login_url='/login')
def AddWorkOrder(request: HttpRequest):
    if not hasPermission(request.user, 'apparelManagement', 'WorkOrder', type='add'):
        return HttpResponse('Access Denied', status=403)

    if request.method == 'POST': 
        #Convert the json to a dict
        jsonData = json.loads(request.body.decode('utf-8'))

        dfOrder, dfVariants = generic_services.refineJson(jsonData)

        try:
            orderNumber = work_order_service.AddWorkOrder(dfOrder, dfVariants, request.user)
            notifications_service.AddWorkOrder(orderNumber)
            return HttpResponse(orderNumber, status=200)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)
    else:
        context = {
            'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)
        }
        return render(request, 'work_order/add.html', context)

@login_required(login_url='/login')
def UpdateWorkOrder(request: HttpRequest, pk: int):
    try:
        orderObject = models.WorkOrder.objects.get(OrderNumber=pk)
    except:
        return generic_services.showMessageResponse(request, 'Resouse not found', 401)

    if request.method == 'POST':
        if not hasPermission(request.user, 'apparelManagement', 'WorkOrder', type='change'):
            return generic_services.showMessageResponse(request, 'Access Denied', 403)

        if (orderObject.Merchandiser != request.user):
            return HttpResponse('Access Denied', status=403)

        dfOrder, dfVariants, dfRequirement, dfAttachments = generic_services.refineFormData(request)

        try:
            work_order_service.UpdateWorkOrder(orderObject, dfOrder, dfVariants, dfRequirement, dfAttachments)
            return HttpResponse('OK', status=200)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)
    else:
        if not hasPermission(request.user, 'apparelManagement', 'WorkOrder', type='view'):
            return generic_services.showMessageResponse(request, 'Access Denied', 403)
        
        order, variants, requirement, attachments = work_order_service.ProcessOrderData(orderObject)
        context = {'order':order,
                   'var':variants,
                   'req':requirement, 'reqJson':json.dumps(list(requirement)),
                   'attachments': attachments, 'attachmentsJson': json.dumps(attachments),
                   'theme':theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)}
        
        return render(request, 'work_order/edit.html', context)

@login_required(login_url='/login')
def CalculateVariants(request: HttpResponse):
    if request.method == 'POST':
        #Extract styleCode from the data.
        styleCode = json.loads(request.body.decode('utf-8'))

        variants = list(models.StyleVariant.objects.filter(Style=styleCode).values_list('VariantCode', flat=True))
      
        return JsonResponse(data=variants, safe=False)

@login_required(login_url='/login')
def CalculateRequirement(request: HttpRequest):
    if request.method != 'POST':
        return HttpResponse('Not allowed', status=405)
    
    #convert json to a dict.
    data = json.loads(request.body.decode('utf-8'))
    
    styleCode = data['styleCode']
    orderNumber = data['orderNumber']

    try:
        workOrder = models.WorkOrder.objects.get(OrderNumber=orderNumber)
        styleCard = models.StyleCard.objects.get(StyleCode=styleCode)
    except Exception as e:
        print(e)
        return HttpResponse('Invalid Input', status=400)

    if (workOrder.Merchandiser != request.user):
        return HttpResponse('Access Denied', status=403)

    work_order_service.CalculateRequirement(styleCard, workOrder)

    return HttpResponse('Ok', status=200)

@login_required(login_url='/login')
def GetRequirementHistory (request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=405)

    requirementId = request.GET.get('id', None)
    workOrder = request.GET.get('workOrder', None)
    
    if (not requirementId) or (not workOrder):
        return HttpResponse('Invalid Input', status=400)
    
    try:
        requirement = models.InvRequirement.objects.get(id=requirementId)
    except:
        return HttpResponse('Requirement not found', status=404)

    try:
        workOrder = models.WorkOrder.objects.get(OrderNumber=workOrder)
    except:
        return HttpResponse('Work Order not found', status=404)
    
    try:
        requirementHistory = work_order_service.GetRequirementHistory(requirement, workOrder)
        return JsonResponse(requirementHistory, safe=False)
    except Exception as e:
        print(e)
        return HttpResponse(e, status=400)

@login_required(login_url='/login')
def WorkOrderInitialPlan(request: HttpRequest):
    if request.method == 'POST':
        #Convert the json to a dict
        jsonData = json.loads(request.body.decode('utf-8'))

        dfInitialPlan = generic_services.refineJson(jsonData)

        try:
            work_order_service.UpdateInitialPlanning(dfInitialPlan)
            return HttpResponse('OK', status=200)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)
    else:
        typeFilter = request.GET.get('typeFilter','unplanned')
        customerFilter = request.GET.get('customerFilter', None)
        startDate = request.GET.get('startDate', None)
        endDate = request.GET.get('endDate', None)

        initialPlans = work_order_service.GetInitialPlanning(typeFilter, customerFilter, startDate, endDate)

        context = {
            'plan': initialPlans,
            'typeFilter': typeFilter, 'customerFilter': customerFilter,
            'startDate': startDate, 'endDate': endDate,
            'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)
        }
        return render(request, 'work_order/initial_plan.html', context)

@login_required(login_url='/login')
def GeneratePOFromWO (request: HttpRequest, pk):
    if not hasPermission(request.user, 'apparelManagement', 'PurchaseOrder', 'delete'):
        return HttpResponse('Access Denied', status=403)
    
    order = models.WorkOrder.objects.get(OrderNumber=pk)
    if request.method == 'POST':
        #convert json data to a dict.
        data = json.loads(request.body.decode('utf-8'))
        dfData = generic_services.refineJson(data)

        try:
            poNumber = purchase_order_service.GeneratePOfromWO(dfData, order)
        
            return HttpResponse(poNumber, status=200)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=500)
    else:
        return HttpResponse('Not Allowed', status=302)

@login_required(login_url='/login')
def DeleteWorkOrder(request: HttpRequest, pk: int):
    if not hasPermission(request.user, 'apparelManagement', 'WorkOrder', 'delete'):
        return HttpResponse('Access Denied', status=403)
    
    try:
        order = models.WorkOrder.objects.get(OrderNumber=pk)
    except:
        return HttpResponse('Resouse not found', status=400)

    if request.method == 'POST':
        if 'confirm' in request.POST:
            try:
                orderNumber = order.OrderNumber
                order.delete()
                notifications_service.DeleteWorkOrder(order, orderNumber)
                return redirect('/workorder')
            except Exception as e:
                context = {'object':order, 'confirm':True, 'theme': theme, 'error': e, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)}
                return render(request, 'work_order/delete.html', context)
        else:
            return redirect('/workorder')
    else:
        if order.poallocation_set.count() > 0:
            return generic_services.showMessageResponse(request, 'POs are issued for this order and it cannot be deleted')
        
        context = {'object':order, 'confirm':True, 'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)}
        return render(request, 'work_order/delete.html', context)

@login_required(login_url='/login')
def PrintWorkOrder(request: HttpRequest, pk: str):
    if not hasPermission(request.user, 'apparelManagement', 'WorkOrder', type='view'):
        return HttpResponse('Access Denied', status=403)

    try:
        orderObject = models.WorkOrder.objects.get(OrderNumber=pk)
    except:
        return HttpResponse('Order not found', status=404)
    
    if request.method == 'POST':
        data = json.loads(request.body.decode('utf-8'))
        requiredFormat = data['format']
        
        try:
            order, cutting, cuttingSummary, material, status = work_order_service.PrintWO(orderObject)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)

        try:
            match requiredFormat:
                case 'CUT':
                    context = {'order':order, 'cut':cutting, 'summary': cuttingSummary, 'theme': theme}
                    try:
                        response = generic_services.convertContextToPDFResponse(context, 'work_order/print_cut.html' )
                        return response
                    except Exception as e:
                        print(e)
                        return HttpResponse(e, status=400)
                case 'F&T':
                    context = {'order':order, 'cut':cuttingSummary,'material':material, 'theme': theme}
                    try:
                        response = generic_services.convertContextToPDFResponse(context, 'work_order/print_ft.html')
                        return response
                    except Exception as e:
                        print(e)
                        return HttpResponse(e, status=400)
                case 'PST':
                    print('Need to make production status format')
                    return HttpResponse('This page is under construction')
                case 'T&A':
                    print('Need to make planning format')
                    return HttpResponse('This page is under construction')
                case _:
                    return HttpResponse('Incorrect format', status=400)
        except Exception as e:
            return HttpResponse(e, status=400)
    else:
        return HttpResponse('Not Allowed', status=403)

@login_required(login_url='/login')
def CopyWorkOrder(request: HttpRequest, pk):
    if not hasPermission(request.user, 'apparelManagement', 'WorkOrder', type='add'):
        return HttpResponse('Access Denied', status=403)

    order = models.WorkOrder.objects.get(OrderNumber=pk)

    if request.method == 'POST':
        SourceNumber = request.POST.get('source')
        TargetNumber = request.POST.get('target')
        print(TargetNumber)

        if (not TargetNumber) or (not SourceNumber):
            context = {'message': 'Error: Missing source or target', 'source':order.OrderNumber, 'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)}
            return render(request, 'work_order/copy.html', context)

        try:
            models.WorkOrder.objects.get(OrderNumber=TargetNumber)
            return HttpResponse('Work order already exists', status=400)
        except models.WorkOrder.DoesNotExist:
            orderObj = models.WorkOrder.objects.get(OrderNumber=SourceNumber)
            orderObj.OrderNumber = TargetNumber
            orderObj.OrderDate = None
            orderObj.save()

            orderObj = models.WorkOrder.objects.get(OrderNumber=TargetNumber)

            sourceVariants = models.OrderVariant.objects.filter(OrderNumber=SourceNumber)
            for variant in sourceVariants:
                variant.pk = None
                variant.OrderNumber = orderObj
                variant.save()

            sourceRequirement = models.InvRequirement.objects.filter(OrderNumber=SourceNumber)
            for requirement in sourceRequirement:
                requirement.pk = None
                requirement.OrderNumber = orderObj
                requirement.save()

            notifications_service.AddWorkOrder(TargetNumber)
            return redirect(f'/workorder/{TargetNumber}/edit')
        except Exception as e:
            context = {'message': f'Error: {e}', 'source':order.OrderNumber, 'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)}
            return render(request, 'work_order/copy.html', context)

    else:
        context = {'source':order.OrderNumber, 'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)}
        return render(request, 'work_order/copy.html', context)

@login_required(login_url='/login')
def AutoInventoryRequirement(request: HttpRequest):
    if not hasPermission(request.user, 'apparelManagement', 'PurchaseOrder', type='add'):
        return HttpResponse('Access Denied', status=403)

    if request.method == 'POST':
        #convert json data to a dict.
        data = json.loads(request.body.decode('utf-8'))
        
        dfData, dfSupplier = generic_services.refineJson(data)

        try:
            poNumber = purchase_order_service.GeneratePOfromAutoReq(dfData, dfSupplier.iloc[0][0])   
            return HttpResponse(poNumber, status=200)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)
    else:
        startingOrder = request.GET.get('startingOrder',None)
        endingOrder = request.GET.get('endingOrder',None)
        customer = request.GET.get('customer', None)
        inventories = request.GET.get('inventories','').split(',')
        if not inventories[0]:
            inventories = inventories[1:]

        if startingOrder == 'null':
            startingOrder = None
        if endingOrder == 'null':
            endingOrder = None
        
        if not endingOrder:
            endingOrder = startingOrder

        requirement, invs = purchase_order_service.PrepareDataForAutoReq(startingOrder, endingOrder, customer)

        context = {
            'theme':theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name),
            'startingOrder':startingOrder, 'endingOrder':endingOrder, 'inventories':json.dumps(inventories),
            'customer': customer,
            'requirement':requirement}   
        #This is in response to a bug where the code was giving error when there was no inventory in the list.
        if invs:
            context.update({'invs':json.dumps(list(invs))})
        else:
            context.update({'invs':json.dumps([])})
        
        return render(request, 'purchase_order/auto_req.html', context)

@login_required(login_url='/login')
def PurchaseOrder(request:HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=405)
    
    if not hasPermission(request.user, 'apparelManagement', 'PurchaseOrder', type='view'):
        return HttpResponse('Access Denied', status=403)

    searchTerm = request.GET.get('searchTerm', '')
    supplierFilter = request.GET.get('supplierFilter', None)
    poFilter = request.GET.get('poFilter', None)
    pageNumber = request.GET.get('pageNumber',1)
    
    if supplierFilter == 'null':
        supplierFilter = None

    Order = purchase_order_service.GetOrderList(supplier=supplierFilter, poNumber=poFilter)
    Order = generic_services.applySearch(Order, searchTerm)
    data = generic_services.paginate(Order, pageNumber)

    context = {'order': data.object_list, 'page_obj': data
               ,'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)
               , 'searchTerm': searchTerm, 'selectedSupplier': supplierFilter, 'selectedPO':poFilter}
    
    return render(request, 'purchase_order/home.html', context)

@login_required(login_url='/login')
def AddPurchaseOrder(request: HttpRequest):
    if not hasPermission(request.user, 'apparelManagement', 'PurchaseOrder', type='add'):
        return HttpResponse('Access Denied', status=403)

    if request.method == 'POST':
        #convert json data to a dict.
        data = json.loads(request.body.decode('utf-8'))

        dfOrder, dfInventory = generic_services.refineJson(data)

        try:
            poNumber = purchase_order_service.AddPurchaseOrder(dfOrder, dfInventory)
            return HttpResponse(poNumber, status=200)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)
    else:
        context = {
            'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name),
        }
        return render(request, 'purchase_order/add.html', context)

@login_required(login_url='/login')
def EditPurchaseOrder(request: HttpRequest, pk):
    try:
        orderObject = models.PurchaseOrder.objects.get(id=pk)
    except:
        return generic_services.showMessageResponse(request, 'Order not found', 404)
    
    if request.method == 'POST':
        if not hasPermission(request.user, 'apparelManagement', 'PurchaseOrder', type='change'):
            return generic_services.showMessageResponse(request,'Access Denied', 403)
        #convert json data to a dict.
        data = json.loads(request.body.decode('utf-8'))

        dfOrder, dfInventory, dfAllocation = generic_services.refineJson(data)
        # Bridge: old form sends one allocId in the order header — stamp it on each allocation row
        if 'allocId' in dfOrder.columns and not dfAllocation.empty:
            dfAllocation['allocId'] = dfOrder['allocId'][0]
        elif dfAllocation.empty:
            dfAllocation['allocId'] = None

        try:
            purchase_order_service.EditPurchaseOrder(orderObject, dfOrder, dfInventory, dfAllocation)
            return HttpResponse('Saved Successfuly', status=200)
        except Exception as e:   
            print(e)         
            return HttpResponse(e, status=400)
    else:
        if not hasPermission(request.user, 'apparelManagement', 'PurchaseOrder', type='view'):
            return generic_services.showMessageResponse(request,'Access Denied', 403)
        order, inventory, allocations, workorders=purchase_order_service.ProcessOrderData(orderObject)
        context = {
            'order':order,
            'inv':inventory, 'invJson':json.dumps(list(inventory)),
            'alloc':allocations, 'workorders':workorders,
            'theme':theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name),
            }
        
        return render(request, 'purchase_order/edit.html', context)

# @login_required(login_url='/login')
@csrf_exempt
def getPOAllocation(request: HttpRequest):
    if request.method == 'POST':
        pk = json.loads(request.body.decode('utf-8'))['id']
        print(pk)

        try:
            poInventory = models.POInventory.objects.get(id=pk)
        except:
            return HttpResponse('Resource not found',status=401)

        allocation = purchase_order_service.getPOAllocation(poInventory)

        return JsonResponse(allocation, safe=False)
    else:
        return HttpResponse('Not allowed', status=302)

# @login_required(login_url='/login')
@csrf_exempt
def GetWODefaultQtyForPO (request: HttpRequest):
    if request.method != 'POST':
        return HttpResponse('Not Allowed', status=405)
    
    data = json.loads(request.body.decode('utf-8'))

    poInvId = data['allocId']
    
    try:
        poInventory = models.POInventory.objects.get(id=poInvId)
    except:
        return JsonResponse(0, safe=False)

    workOrder = data['workOrder']
    
    try:
        workOrder = models.WorkOrder.objects.get(OrderNumber=workOrder)
    except:
        return JsonResponse(0, safe=False)

    quantity = purchase_order_service.GetWorkOrderDefaultQty(workOrder, poInventory)

    return JsonResponse(quantity, safe=False)

# @login_required(login_url='/login')
@csrf_exempt
def getAllocatedQty (request: HttpRequest):
    if request.method == 'POST':
        data = json.loads(request.body.decode('utf-8'))
    
        try:
            inventory = models.Inventory.objects.get(Code=data['invCode'])
        except Exception as e:
            print(e)
            return HttpResponse('Inventory code not available', status=400)
        
        variant = data['variant']
        
        purchaseOrder = models.PurchaseOrder.objects.get(id=data['poNumber'])

        quantity = purchase_order_service.getAllocatedQty(purchaseOrder, inventory, variant)

        return JsonResponse(quantity, safe=False)
    else:
        return HttpResponse('Not Allowed', status=405)

@login_required(login_url='/login')
def PrintPurchaseOrder(request: HttpRequest, pk: str):
    if not hasPermission(request.user, 'apparelManagement', 'PurchaseOrder', type='view'):
        return HttpResponse('Access Denied', status=403)

    try:
        orderObject = models.PurchaseOrder.objects.get(id=pk)
    except:
        return HttpResponse('Order not found', status=404)
    
    if request.method == 'POST':
        data = json.loads(request.body.decode('utf-8'))
        requiredFormat = data['format']
        
        if requiredFormat == 'SUP':
            order, inventory, allocation, summary = purchase_order_service.PrintPO(orderObject)
            context = {'order':order, 'inv':inventory, 'summary': summary, 'theme': theme} 
            
            try:
                response = generic_services.convertContextToPDFResponse(context, 'purchase_order/print_supplier.html')
                return response
            except Exception as e:
                print(e)
                return HttpResponse(e, status=400)
        elif requiredFormat == 'SUPV1':
            order, inventory, allocation, summary = purchase_order_service.PrintPO(orderObject, 'V1')
            context = {'order':order, 'inv':inventory, 'summary': summary, 'theme': theme}
            
            try:
                response = generic_services.convertContextToPDFResponse(context, 'purchase_order/print_supplier.html')
                return response
            except Exception as e:
                print(e)
                return HttpResponse(e, status=400)
        elif requiredFormat == 'SUPV2':
            order, inventory, allocation, summary = purchase_order_service.PrintPO(orderObject, 'V2')
            context = {'order':order, 'inv':inventory, 'summary': summary, 'theme': theme}
            
            try:
                response = generic_services.convertContextToPDFResponse(context, 'purchase_order/print_supplier.html')
                return response
            except Exception as e:
                print(e)
                return HttpResponse(e, status=400)
        elif requiredFormat=='ACC':
            order, inventory, allocation, summary = purchase_order_service.PrintPO(orderObject)
            context = {'order':order, 'inv':inventory, 'alloc': allocation, 'summary': summary, 'theme': theme}
            
            try:
                response = generic_services.convertContextToPDFResponse(context, 'purchase_order/print_accounts.html')
                return response
            except Exception as e:
                print(e)
                return HttpResponse(e, status=400)
        else:
            return HttpResponse('Invalid print format.', status=400)
    else:
        return HttpResponse('Not Allowed', status=405)

@login_required(login_url='/login')
def CopyPurchaseOrder (request: HttpRequest, pk):
    if not hasPermission(request.user, 'apparelManagement', 'PurchaseOrder', type='add'):
        return HttpResponse('Access Denied', status=403)

    po = models.PurchaseOrder.objects.get(id=pk)

    if request.method == 'POST':
        SourceNumber = request.POST.get('source')
        po = models.PurchaseOrder.objects.get(id=SourceNumber)
        po.id = None
        po.save()

        poInventories = models.POInventory.objects.filter(PONumber=SourceNumber)
        for inventory in poInventories:
            oldId = inventory.id
            inventory.id = None
            inventory.PONumber = po
            inventory.save()

            invAllocations = models.POAllocation.objects.filter(POInvId=oldId)
            for allocation in invAllocations:
                allocation.id = None
                allocation.POInvId = inventory
                allocation.save()
        return redirect(f'/purchaseorder/{po.id}/edit')
    else: 
        context = {
            'source':po,
            'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)
            }
        return render(request, 'purchase_order/copy.html', context)

@login_required(login_url='/login')
def DeletePurchaseOrder(request: HttpRequest, pk: int):
    try:
        order = models.PurchaseOrder.objects.get(id=pk)
    except:
        return HttpResponse('Resource not found', status=400)
    
    if not hasPermission(request.user, 'apparelManagement', 'PurchaseOrder', type='delete'):
        return HttpResponse('Access Denied', status=403)
    
    if request.method == 'POST':
        if 'confirm' in request.POST:
            try:
                order.delete()
                return redirect('/purchaseorder')
            except Exception as e:
                context = {'object':order, 'confirm':True, 'error': e, 
                           'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name),
                           }
                return render(request, 'purchase_order/delete.html', context)
        else:
            return redirect('/purchaseorder')
    else:
        context = {
            'object':order, 'confirm':True,
            'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)
            }
        return render(request, 'purchase_order/delete.html', context)

@login_required(login_url='/login')
def PurchaseReceipt(request: HttpRequest):
    if not hasPermission(request.user, 'apparelManagement', 'InventoryReciept', type='view'):
        return HttpResponse('Access Denied', status=403)

    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=405)
    
    searchTerm = request.GET.get('searchTerm', '')
    supplierFilter = request.GET.get('supplierFilter', None)
    recFilter = request.GET.get('recFilter', None)
    pageNumber = request.GET.get('pageNumber',1)
    
    #Set receipt number of None if it is empty
    if not recFilter:
        recFilter = None
   
    #Correct supplier filter format
    if (supplierFilter == 'null') or (supplierFilter == 'None'):
        supplierFilter = None
    
    receipt = purchase_receipt_service.GetReceiptList(supplierFilter, recFilter)
    receipt = generic_services.applySearch(receipt, searchTerm)

    data = generic_services.paginate(receipt, pageNumber)
    
    context = {
        'receipt': data.object_list, 'receiptObj': data,
        'theme':theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name),
        'searchTerm': searchTerm, 'selectedSupplier': supplierFilter, 'selectedRec':recFilter}
    return render(request, 'purchase_receipt/home.html', context)

@login_required(login_url='/login')
def AddPurchaseReceipt(request: HttpRequest):
    if not hasPermission(request.user, 'apparelManagement', 'InventoryReciept', type='add'):
        return HttpResponse('Access Denied', status=403)

    if request.method == 'POST':
        #convert json data to a dict.
        data = json.loads(request.body.decode('utf-8'))

        dfReceipt, dfInventory = generic_services.refineJson(data)
        
        try:
            recNumber = purchase_receipt_service.AddPurchaseReceipt(dfReceipt, dfInventory)
            
            #Return the receipt Number that is generated.
            return HttpResponse(recNumber, status=200)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)
    else:
        poNumber = request.GET.get('poNumber', None)

        try:
            purchaseOrder = models.PurchaseOrder.objects.get(id=poNumber)
        except:
            pass
            
        try:
            inventory = purchase_receipt_service.GetPOData(purchaseOrder)
        except:
            inventory = []

        context = {
            'inventory': inventory,
            'poNumber': poNumber,
            'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name),
        }
        return render(request, 'purchase_receipt/add.html', context)

@login_required(login_url='/login')
def GetContextForPurchaseReceipt(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=405)
    
    poInvId = request.GET.get('poInvId','')

    try:
        poInventory = models.POInventory.objects.get(id=poInvId)
    except:
        return HttpResponse('Resource not found', status=404)

    try:
        poData = purchase_receipt_service.GetPOContext(poInventory)
        return JsonResponse(poData, safe=False)
    except Exception as e:
        print(e)
        return HttpResponse(e, status=400)

@login_required(login_url='/login')
def EditPurchaseReceipt(request: HttpRequest, pk:str):
    try:
        receiptObject = models.InventoryReciept.objects.get(id=pk)
    except:
        return HttpResponse('Resource not found', status=404)
    
    if request.method == 'POST':
        if not hasPermission(request.user, 'apparelManagement', 'InventoryReciept', type='change'):
            return HttpResponse('Access Denied', status=403)
    
        #convert json data to a dict.
        data = json.loads(request.body.decode('utf-8'))

        dfReceipt, dfInventory, dfAllocation = generic_services.refineJson(data)

        try:
            purchase_receipt_service.EditPurchaseReceipt(receiptObject, dfReceipt, dfInventory, dfAllocation)
            return HttpResponse('Saved Successfuly', status=200)
        except Exception as e: 
            print(e)           
            return HttpResponse(e, status=400)
    else:     
        if not hasPermission(request.user, 'apparelManagement', 'InventoryReciept', type='view'):
            return generic_services.showMessageResponse(request, 'Access Denied', 403)   
        receipt, inventory = purchase_receipt_service.ProcessReceiptData(receiptObject)

        context = {'receipt':receipt,
                   'inv':inventory, 'invJson':json.dumps(list(inventory)),
                   'theme':theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)}
        
        return render(request, 'purchase_receipt/edit.html', context)

@login_required(login_url='/login')
def ReAllocateReceiptInventory(request: HttpRequest, pk: int):
    if request.method != 'GET':
        return HttpResponse('Not allowed', status=405)
    
    try:
        recInventory = models.RecInventory.objects.get(id=pk)
    except:
        return HttpResponse('Invalid Input', status=404)
    
    allocationMethod = request.GET.get('allocationMethod', '')
    if not allocationMethod:
        return HttpResponse('Allocation Priority not defined', status=404)

    totalQty = request.GET.get('totalQty', None)

    try:
        allocation = purchase_receipt_service.ReAllocateReceiptInventory(recInventory, totalQty, allocationMethod)
    except Exception as e:
        print(e)
        return HttpResponse(e, status=400)

    return JsonResponse(allocation, safe=False)

@login_required(login_url='/login')
def GetReceiptAllocation(request: HttpRequest):
    if request.method != 'POST':
        return HttpResponse('No Allowed', status=405)

    pk = json.loads(request.body.decode('utf-8'))['id']

    try:
        recInventory = models.RecInventory.objects.get(id=pk)
    except:
        return HttpResponse('Resource not found',status=401)

    allocation = purchase_receipt_service.GetReceiptAllocation(recInventory)
    
    return JsonResponse(allocation, safe=False)

@login_required(login_url='/login')
def PrintPurchaseReceipt(request: HttpRequest, pk: str):
    if not hasPermission(request.user, 'apparelManagement', 'InventoryReciept', type='view'):
        return HttpResponse('Access Denied', status=403)
    
    try:
        inventoryReciept = models.InventoryReciept.objects.get(id=pk)
    except:
        return HttpResponse('Order not found', status=404)
    
    if request.method != 'POST':
        return HttpResponse('Not Allowed', status=405)

    data = json.loads(request.body.decode('utf-8'))
    requiredFormat = data['format']

    if requiredFormat == 'QC':
        return HttpResponse('This feature is under construction', status=503)
    elif requiredFormat == 'ACC':
        receipt, inventory, allocation = purchase_receipt_service.PrintRec(inventoryReciept)
        context = {'receipt':receipt, 'inv':inventory, 'allocation': allocation, 'theme': theme}

        try:
            response = generic_services.convertContextToPDFResponse(context, 'purchase_receipt/print_accounts.html' )
            return response
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)
    else:
        return HttpResponse('Invalid print format.', status=400)        

@login_required(login_url='/login')
def PurchaseDemand (request: HttpRequest):
    if not hasPermission(request.user, 'apparelManagement', 'PurchaseDemand', type='view'):
        return HttpResponse('Access Denied', status=403)

    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=405)
    
    searchTerm = request.GET.get('searchTerm', '')
    departmentFilter = request.GET.get('departmentFilter', '')
    statusFilter = request.GET.get('statusFilter', 'OnApp')
    pdNumber = request.GET.get('demandFilter', '')
    pageNumber = request.GET.get('pageNumber',1)

    if (departmentFilter == 'None') or (departmentFilter == 'null'):
        departmentFilter = None

    demand = purchase_demand_service.GetPurchaseDemandList(searchTerm, departmentFilter, pdNumber, statusFilter)
    
    data = generic_services.paginate(demand, pageNumber)
    
    context = {
        'demand': data.object_list, 'demandObj': data,
        'theme':theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name),
        'selectedDepartment': departmentFilter, 'searchTerm': searchTerm, 'selectedStatus': statusFilter,
        'selectedDemand': pdNumber
        }

    return render(request, 'purchase_demand/home.html', context)

@login_required(login_url='/login')
def AddPurchaseDemand (request: HttpRequest):
    if not hasPermission(request.user, 'apparelManagement', 'PurchaseDemand', type='add'):
        return HttpResponse('Access Denied', status=403)

    if request.method == 'POST':
        #convert json data to a dict.
        data = json.loads(request.body.decode('utf-8'))

        dfDemand, dfInventory = generic_services.refineJson(data)

        try:
            demandNumber = purchase_demand_service.AddPurchaseDemand(dfDemand, dfInventory)
            
            #Return the receipt Number that is generated.
            return HttpResponse(demandNumber, status=200)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)
    else:
        context = {
            'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)
        }
        return render(request, 'purchase_demand/add.html', context)

@login_required(login_url='/login')
def EditPurchaseDemand (request: HttpRequest, pk: int):
    if not hasPermission(request.user, 'apparelManagement', 'PurchaseDemand', type='change'):
        return generic_services.showMessageResponse(request, 'Access Denied', 403)

    try:
        demand = models.PurchaseDemand.objects.get(id=pk)
    except:
        return generic_services.showMessageResponse(request, 'Demand not found', 400)
    
    if demand.Approval != None:
        return generic_services.showMessageResponse(request, 'This demand is closed.', 405)
    
    if request.method == 'POST':
        dfDemand, dfInventory = generic_services.refineFormData(request)
        try:
            purchase_demand_service.EditPurchaseDemand(demand, dfDemand, dfInventory)
            return HttpResponse('OK', status=200)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)
    else:
        demand, inventories = purchase_demand_service.ProcessDemandData(demand)

        context = {'demand':demand,
                   'inv':inventories, 'invJson': json.dumps(list(inventories)),
                   'theme':theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)}
        
        return render(request, 'purchase_demand/edit.html', context)

@login_required(login_url='/login')
def CopyPurchaseDemand (request: HttpRequest, pk:int):
    if not hasPermission(request.user, 'apparelManagement', 'PurchaseDemand', type='add'):
        return HttpResponse('Access Denied', status=403)

    demand = models.PurchaseDemand.objects.get(id=pk)
    if request.method == 'POST':
        SourceNumber = request.POST.get('source')
        demand = models.PurchaseDemand.objects.get(id=SourceNumber)

        demand.id = None
        demand.DemandDate = None
        demand.Approval = None
        demand.ApprovedBy = None
        demand.PONumber = None
        demand.save()
        
        demandInventories = models.PDInventory.objects.filter(PDNumber=SourceNumber)

        for inventory in demandInventories:
            inventory.id = None
            inventory.PDNumber = demand
            inventory.save()
        return redirect(f'/purchasedemand/{demand.id}/edit')
    else:
       context = {
           'source':demand,
           'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)
           }
       return render(request, 'purchase_demand/copy.html', context)

@login_required(login_url='/login')
def DeletePurchaseDemand (request: HttpRequest, pk: int):
    if not hasPermission(request.user, 'apparelManagement', 'PurchaseDemand', type='delete'):
        return generic_services.showMessageResponse(request, 'Access Denied', 403)

    try:
        demand = models.PurchaseDemand.objects.get(id=pk)
    except:
        return generic_services.showMessageResponse(request, 'Demand not found', 400)
    
    if demand.Approval != None:
        return generic_services.showMessageResponse(request, 'This demand is closed.', 405)
    
    if request.method == 'POST':
        if ('confirm' in request.POST):
            try:
                demand.delete()
                return redirect(reverse('apparelManagement:purchaseDemand'))
            except Exception as e:
                context = {
                    'object':demand, 'confirm':True,
                    'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name), 
                    'error': e}
                return render(request, 'purchase_demand/delete.html', context)
        else:
            return redirect('/purchasedemand')
    else:
        context = {
            'object':demand, 'confirm':True,
            'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)
            }
        return render(request, 'purchase_demand/delete.html', context)

@login_required(login_url='/login')
def ApprovePurchaseDemand (request: HttpRequest, pk: int):
    try:
        demand = models.PurchaseDemand.objects.get(id=pk)
    except:
        return generic_services.showMessageResponse(request, 'Demand not found', 400)
    
    if not canApprovePD(request.user):
        return generic_services.showMessageResponse(request, 'You do not have access to this file', 405)

    if request.method == 'POST':
        approval = request.POST.get('Approval')

        try:
            purchase_demand_service.ApprovePD(request, demand, approval)
            return redirect(reverse('apparelManagement:purchaseDemand'))
        except PermissionError as e:
            print(e)
            return HttpResponse(e, status=405)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)
    else:
        try:
            demand, context = purchase_demand_service.GetDataForPDApproval(demand)
            
            context = {
                'demand': demand, 'context': context,
                'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)
                }
            
            return render(request, 'purchase_demand/approve.html', context)
        except Exception as e:
            print(e)
            return generic_services.showMessageResponse(request, str(e), 400)

@login_required(login_url='/login')
def ConvertPDtoPO (request: HttpRequest, pk: int):
    try:
        demand = models.PurchaseDemand.objects.get(id=pk)
    except:
        return generic_services.showMessageResponse(request, 'Demand not found', 400)

    if not hasPermission(request.user, 'apparelManagement', 'PurchaseDemand', type='add'):
        return generic_services.showMessageResponse(request, 'Access Denied', 403)

    if demand.Approval != True:
        return generic_services.showMessageResponse(request, 'Demand not approved', 403)

    if request.method == 'POST':
        dfInventory, dfDemand = generic_services.refineFormData(request)

        try:
            poNumber = purchase_demand_service.ConvertPDtoPO(demand, dfDemand, dfInventory)
            return HttpResponse(poNumber, status=200)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)
    else:
        demand, inventories = purchase_demand_service.ProcessDemandData(demand)
        context = {'demand':demand,
                   'inv':inventories, 'invJson': json.dumps(list(inventories)),
                   'theme':theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)}
        return render(request, 'purchase_demand/make_po.html', context)

@login_required(login_url='/login')
def Requisition (request: HttpRequest):
    if not hasPermission(request.user, 'apparelManagement', 'Requisition', type='view'):
        return HttpResponse('Access Denied', status=403)

    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=405)
    
    searchTerm = request.GET.get('searchTerm', '')
    departmentFilter = request.GET.get('departmentFilter', None)
    statusFilter = request.GET.get('statusFilter', 'Pending')
    requisitionNumber = request.GET.get('requisitionNumber')
    pageNumber = request.GET.get('pageNumber',1)

    if (departmentFilter == 'None') or (departmentFilter == 'null'):
        departmentFilter = None
    
    if not requisitionNumber:
        requisitionNumber = None

    requisition = requisition_service.GetRequisitionList(departmentFilter, statusFilter, requisitionNumber)
    requisition = generic_services.applySearch(requisition, searchTerm)
    
    data = generic_services.paginate(requisition, pageNumber)

    context = {
    'req': data.object_list, 'demandObj': data,
    'theme':theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name),
    'selectedDepartment': departmentFilter, 'searchTerm': searchTerm, 'selectedStatus': statusFilter,
    'selectedRequisition': requisitionNumber
    }

    return render(request, 'requisition/home.html', context)

@login_required(login_url='/login')
def AddRequisitionForOrder (request: HttpRequest):
    if not hasPermission(request.user, 'apparelManagement', 'Requisition', type='add'):
        return HttpResponse('Access Denied', status=403)

    if request.method == 'POST':
        #convert json data to a dict.
        data = json.loads(request.body.decode('utf-8'))

        dfInventory, dfRequisition = generic_services.refineJson(data)

        try:
            requisitionNumber = requisition_service.AddRequisitionForOrder(dfRequisition, dfInventory, request.user.username)
            return HttpResponse(requisitionNumber, status=200)
        except Exception as e:
            return HttpResponse(e, status=400)
    else:
        order = request.GET.get('order',None)
        searchTerm = request.GET.get('search','')
        department = request.GET.get('Department',None)

        if order == 'null':
            order = None
        
        context = {
                'order':order, 'search':searchTerm, 'department': department,
                'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)
            }
        
        if order:
            data, invs = requisition_service.PrepareDataForOrderRequitionAdd(order)
            data = generic_services.applySearch(data, searchTerm)
            context.update({'entries': data})

            #This is in response to a bug where the code was giving error when there was no inventory in the list.
            if invs:
                context.update({'invs':json.dumps(list(invs))})
            else:
                context.update({'invs':json.dumps([])})
        else:
            context.update({'entries':json.dumps([])})
            context.update({'invs':json.dumps([])})

        return render(request, 'requisition/add_order.html', context)

@login_required(login_url='/login')
def AddIssuanceForOrder(request: HttpRequest):
    if request.method == 'POST':
        data = json.loads(request.body.decode('utf-8'))
        dfInventory, dfWorkOrder = generic_services.refineJson(data)

        try:
            issuanceNumber = issuance_service.AddIsuanceForOrder(dfInventory, dfWorkOrder)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)

        return HttpResponse(issuanceNumber, status=200)
    else:
        order = request.GET.get('order',None)
        inventories = request.GET.getlist('inventories[]', [])
        type = request.GET.get('type',None)
        department = request.GET.get('department','')

        if order == 'null':
            order = None
        
        data, allInventories = issuance_service.GetDataForOrderIssuance(order, type, inventories)
        
        context = {
            'entries': data, 'allInventories': allInventories,
            'order': order, 'type': type,
            'department': department, 'selectedInventories': inventories,
            'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)
        }
        
        return render(request, 'issuance/add_order.html', context)

@login_required(login_url='/login')
def AddRequisitionForInv (request: HttpRequest):
    if not hasPermission(request.user, 'apparelManagement', 'Requisition', type='add'):
        return HttpResponse('Access Denied', status=403)

    if request.method == 'POST':
        #convert json data to a dict.
        data = json.loads(request.body.decode('utf-8'))
        
        dfDetails, dfRequisition = generic_services.refineJson(data)

        try:
            requisitionNumber = requisition_service.AddRequistionForInv(dfRequisition, dfDetails, request.user.username)
            return HttpResponse(requisitionNumber, status=200)
        except Exception as e:
            return HttpResponse(e, status=400)

    else:
        department = request.GET.get('Department',None)
        group = request.GET.get('Group','STATIONERY')
        inventory = request.GET.get('Inventory',None)

        if inventory == 'null':
            inventory = None

        data = requisition_service.PrepareDataForInvRequisitionAdd(inventory)

        context = {
            'entries': data,
            'department': department,'selectedGroup':group, 'selectedInv': inventory,
            'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)
        }

        return render(request, 'requisition/add_inv.html', context)

@login_required(login_url='/login')
def GetRequisitionAllocation(request: HttpRequest):
    if request.method == 'POST':
        data = json.loads(request.body.decode('utf-8'))

        inventoryCode = data['inventoryCode']
        variant = data['variant']
        urlPath = data['urlPath']
        del data

        allocation = requisition_service.GetReceiptAllocation(inventoryCode, variant, urlPath)
        
        return JsonResponse(allocation, safe=False)
    else:
        return HttpResponse('No Allowed', status=405)

@login_required(login_url='login')
def Issuance (request: HttpRequest):
    if not hasPermission(request.user,'apparelManagement', 'Issuance', type='view'):
        return HttpResponse('Access Denied', status=403)

    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=405)
    
    searchTerm = request.GET.get('searchTerm', '')
    departmentFilter = request.GET.get('departmentFilter', None)
    issuanceNumber = request.GET.get('issuanceNumber')

    if (departmentFilter == 'None') or (departmentFilter == 'null'):
        departmentFilter = None

    issuances = issuance_service.GetIssuanceList(searchTerm, departmentFilter, issuanceNumber)

    context = {
        'issue': issuances,
        'theme':theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name),
        'selectedDepartment': departmentFilter, 'searchTerm': searchTerm,
        'selectedIssuance': issuanceNumber
        }

    return render(request, 'issuance/home.html', context)
    
@login_required(login_url='/login')
def AddIssuance (request: HttpRequest):
    if not hasPermission(request.user, 'apparelManagement', 'Issuance', type='add'):
        return HttpResponse('Access Denied', status=403)
    
    requisition = request.GET.get('req',None)
    try:
        requisition = models.Requisition.objects.get(id=requisition)
    except:
        return HttpResponse('Requisition Not Found', status=400)
    
    if requisition.Confirmation:
        return HttpResponse ('This requisition is closed.', status=405)
    
    if request.method == 'POST':
        comments = request.POST.get('Comments')
        try:
            issuance_service.AddIssuance(requisition, comments)
            return redirect('apparelManagement:requisition')
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)
    else:
        invs = issuance_service.ProcessRequisitionData(requisition)
        context = {
            'req':requisition,'invs': invs,
            'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)
            }
        return render(request, 'issuance/add.html', context)

@login_required(login_url='/login')
def ThreadConsumptionRequests(request: HttpRequest):
    if not hasPermission(request.user,'apparelManagement', 'ThreadConsumptionRequest', type='view'):
        return generic_services.showMessageResponse(request, 'Access Denied', 403)
    
    if request.method != 'GET':
        return generic_services.showMessageResponse(request, 'Not allowed', 405)
    
    searchTerm = request.GET.get('search', '')
    status = request.GET.get('status', 'false')

    requests = style_card_service.GetThreadConsRequests(status)
    requests = generic_services.applySearch(requests, searchTerm)
    data = generic_services.paginate(requests, 1)

    context = {
        'requests': data.object_list, 'page_obj': data,
        'theme':theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name),
        'search': searchTerm, 'status': status,
    }
    return render(request, 'consumption/thread/home.html', context)

@login_required(login_url='/login')
def AddThreadConsumptionRequest(request: HttpRequest):
    if not hasPermission(request.user, 'apparelManagement', 'ThreadConsumptionRequest', type='add'):
        return generic_services.showMessageResponse(request, 'Access Denied', 403)
    
    if request.method == 'POST':
        data = json.loads(request.body.decode('utf-8'))
        dfRequest = generic_services.refineJson(data)
        
        try:
            requestId = style_card_service.AddRequestForThreadCons(dfRequest, request.user)
            return HttpResponse(requestId, status=200)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)
    else:
        context = {
            'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)
        }
        return render(request, 'consumption/thread/add.html', context)

@login_required(login_url='/login')
def EditThreadConsumptionRequest(request: HttpRequest, pk: int):
    if not hasPermission(request.user, 'apparelManagement', 'ThreadConsumptionRequest', type='change'):
        return generic_services.showMessageResponse(request, 'Access Denied', 403)
    
    try:
        consRequest = models.ThreadConsumptionRequest.objects.get(id=pk)
    except:
        return generic_services.showMessageResponse(request, 'Request not found', 400)

    if consRequest.IsClosed:
        return generic_services.showMessageResponse(request, 'This resource is closed.', 405)

    if not (consRequest.RequestBy == request.user or request.user.is_staff):
        return generic_services.showMessageResponse(request, 'Access Denied', 403)
    
    if request.method == 'POST':
        data = json.loads(request.body.decode('utf-8'))
        dfRequest = generic_services.refineJson(data)

        try:
            style_card_service.UpdateRequestForThreadCons(consRequest, dfRequest)
            return HttpResponse('Ok', status=200)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)
    else:
        consData = style_card_service.ProcessConsRequestData(consRequest)
        
        context = {
            'request': consRequest, 'consData': consData, 'consJson': json.dumps(list(consData)),
            'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)
        }
        return render(request, 'consumption/thread/edit.html', context)

class GetPendingThreadConsRequest(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request):
        try:
            authenticateUser(request, 'apparelManagement', 'ThreadConsumptionRequest', type='view')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)

        try:
            requests = style_card_service.GetThreadConsRequests('false')
            return Response(data=requests, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, statu=status.HTTP_400_BAD_REQUEST)

class UpdateThreadConsumption(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request, pk: int):
        try:
            authenticateUser(request, 'apparelManagement', 'ThreadConsumptionRequest', type='view')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            consRequest = models.ThreadConsumptionRequest.objects.get(id=pk)
        except:
            response = {'message', 'Resource Not Found'}
            return Response(data=response, status=status.HTTP_404_NOT_FOUND)

        if consRequest.IsClosed:
            response = {'message': 'This resource is closed'}
            return Response(data=response, status=status.HTTP_405_METHOD_NOT_ALLOWED)
        
        try:
            consRequest, consThreads, addedData, styles = style_card_service.ProcessThreadConsumptionData(consRequest)

            responseData = {
                'request': consRequest, 'threads': consThreads, 'addedData': addedData,
                'styles': styles,
            }
            return Response(data=responseData, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)
    
    def post(self, request:Request, pk: int):
        try:
            authenticateUser(request, 'apparelManagement', 'ThreadConsumption', type='change')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            consRequest = models.ThreadConsumptionRequest.objects.get(id=pk)
        except:
            response = {'message', 'Resource Not Found'}
            return Response(data=response, status=status.HTTP_404_NOT_FOUND)


        if consRequest.IsClosed:
            response = {'message': 'This resource is closed'}
            return Response(data=response, status=status.HTTP_405_METHOD_NOT_ALLOWED)

        isFinal = request.data.get('final', False)
        data = request.data.get('items')

        try:
            style_card_service.SaveThreadConsumption(consRequest, data, isFinal)
            return Response(data=[], status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

def ConvertThreadConsumption(request: HttpRequest, pk: int):
    if not hasPermission(request.user, 'apparelManagement', 'StyleCard', type='change'):
        return generic_services.showMessageResponse(request, 'Access Denied', 403)
    
    try:
        consRequest = models.ThreadConsumptionRequest.objects.get(id=pk)
    except:
        return generic_services.showMessageResponse(request, 'Request not found', 400)

    if not consRequest.IsClosed:
        return generic_services.showMessageResponse(request, 'Consumption not final yet.', 405)

    if request.method == 'POST':
        dfStyle, dfConsumption = generic_services.refineFormData(request)
        
        style = dfStyle.iloc[0, 0]
        try:
            requestStyle = models.ThreadConsumptionRequestStyles.objects.get(id=style)
        except:
            return HttpResponse('This style is removed from request', status=400)
        
        try:
            style_card_service.ConvertThreadConsumption(requestStyle, dfConsumption)
            return HttpResponse('Ok', status=200)
        except Exception as e:
            print(e)
            return HttpResponse(str(e), status=400)
    else:
        try:
            styles, consThreads, styleThreads = style_card_service.ProcessThreadConDataForConversion(consRequest)
        except Exception as e:
            print(e)
            return generic_services.showMessageResponse(request, str(e), 400)

        context = {
            'styles': styles, 'stylesJson': json.dumps(list(styles)),
            'consThreads': consThreads,
            'styleThreads': styleThreads, 'styleThreadsJson': json.dumps(list(styleThreads)),
            'theme': theme, 'navLinks': getNavLinks(request.user, request.resolver_match.app_name)
        }

        return render(request, 'consumption/thread/finalise.html', context)
    
class GetThreadConsumptions(APIView):
    permission_classes = [AllowAny]

    def get(serl, request: Request):
        try:
            authenticateUser(request, 'apparelManagement', 'ThreadConsumption', type='view')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)
        try:
            consumptions = style_card_service.GetThreadConsumptions()
            return Response(data=consumptions, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)
        
# Returns paginated work order list for the merchandising frontend
class MerchandisingWorkOrders(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request):
        search      = request.GET.get('search', '')
        customer    = request.GET.get('customer', '')
        startDate   = request.GET.get('startDate', None)
        endDate     = request.GET.get('endDate', None)
        page        = request.GET.get('page', 1)

        try:
            orders = work_order_service.GetOrderList(customer, startDate, endDate)
            orders = generic_services.applySearch(orders, search)
            data   = generic_services.paginate(orders, page)
            return Response({'orders': data.object_list, 'pages': data.paginator.num_pages})
        except Exception as e:
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# API for work orders
class WorkOrderDetailAPI(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request, pk: int):
        try:
            workOrder = models.WorkOrder.objects.get(OrderNumber=pk)
        except models.WorkOrder.DoesNotExist:
            return Response({'message': 'Work order not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            order, variants, requirement, attachments = work_order_service.ProcessOrderData(workOrder)
        except Exception as e:
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        currencies = [
            {'value': c, 'label': c}
            for c in models.Currency.objects.values_list('Code', flat=True)
        ]

        orderData = {
            'OrderNumber':  order['OrderNumber'],
            'StyleCode':    order['StyleCode'],
            'Customer':     order['Customer'],
            'DeliveryDate': order['DeliveryDate'].isoformat() if order['DeliveryDate'] else None,
            'Type':         order['Type'],
            'Currency':     order['Currency'],
            'Price':        order['Price'],
            'ExcessCut':    order['ExcessCut'],
        }

        return Response({
            'formData': {
                'Order':       orderData,
                'Variants':    list(variants),
                'Requirement': requirement,
                'Attachments': attachments,
            },
            'currencies': currencies,
        })


class AddStyleCardAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request):
        data = request.data

        try:
            dfStyle = pd.DataFrame([{
                'StyleCode': data.get('StyleCode', ''),
                'StyleName': data.get('StyleName', ''),
                'Customer':  data.get('Customer', ''),
                'Category':  data.get('Category', ''),
                'Notes':     data.get('Notes', ''),
            }])

            dfRoute = pd.DataFrame([{'RoutePreset': data.get('RoutePreset')}])

            variants = data.get('variants', [])
            dfVariants = pd.DataFrame(variants) if variants else pd.DataFrame(columns=['Variant1', 'Variant2'])

            styleCode = style_card_service.AddStyleCard(dfStyle, dfVariants, dfRoute)
            return Response({'StyleCode': styleCode}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class StyleCardDetailAPI(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request, pk: str):
        try:
            style = models.StyleCard.objects.get(StyleCode=pk)
        except models.StyleCard.DoesNotExist:
            return Response({'message': 'Style not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            styleDict, variants, consumption, route, attachments = style_card_service.ProcessStyleData(style)
        except Exception as e:
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        customerFields = ['Name', 'TradeName']
        customers = models.Customer.objects.all().values(*customerFields)[:50]
        customerOptions = [{'value': c['Name'], 'text': f"{c['Name']} - {c['TradeName']}"} for c in customers]

        categoryOptions = [{'value': v, 'text': t} for v, t in models.Categories]

        presetFields = ['id', 'Name']
        presets = models.RoutePreset.objects.all().values(*presetFields).order_by('id')
        presetOptions = [{'value': None, 'text': '-----------'}] + [{'value': p['id'], 'text': p['Name']} for p in presets]

        return Response({
            'style':       styleDict,
            'variants':    list(variants),
            'consumption': consumption,
            'route':       route,
            'attachments': attachments,
            'options': {
                'customers':  customerOptions,
                'categories': categoryOptions,
                'routes':     presetOptions,
            },
        })

# PO details endpoint for frontend:
# PO details viewed on the main page in frontend
class PurchaseOrderDetailAPI(APIView):
    permission_classes = [AllowAny]
    def get(self, request: Request, pk: int):
        try:
            orderObject = models.PurchaseOrder.objects.get(id=pk)
        except models.PurchaseOrder.DoesNotExist:
            return Response({'message': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            order, inventory, allocations, workorders = purchase_order_service.ProcessOrderData(orderObject)
            return Response({'order': order, 'inventory': inventory, 'allocations': allocations, 'workorders': workorders})

        except Exception as e:
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request: Request, pk: int):
        try:
            orderObject = models.PurchaseOrder.objects.get(id=pk)
        except models.PurchaseOrder.DoesNotExist:
            return Response({'message': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        try:
            purchase_order_service.EditPurchaseOrderFromData(orderObject, dict(request.data))
            return Response({'message': 'Saved successfully'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# Purchase order copy endpoint url
class PurchaseOrderCopyAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request, pk: int):
        try:
            po = models.PurchaseOrder.objects.get(id=pk)
        except models.PurchaseOrder.DoesNotExist:
            return Response({'message': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            po.id = None
            po.save()

            poInventories = models.POInventory.objects.filter(PONumber=pk)
            for inventory in poInventories:
                oldId = inventory.id
                inventory.id = None
                inventory.PONumber = po
                inventory.save()

                invAllocations = models.POAllocation.objects.filter(POInvId=oldId)
                for allocation in invAllocations:
                    allocation.id = None
                    allocation.POInvId = inventory
                    allocation.save()

            return Response({'PONumber': po.id}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# Purchase order delete endpoint URL
class PurchaseOrderDeleteAPI(APIView):
    permission_classes = [AllowAny]

    def delete(self, request: Request, pk: int):
        try:
            order = models.PurchaseOrder.objects.get(id=pk)
        except models.PurchaseOrder.DoesNotExist:
            return Response({'message': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)

        try:
            order.delete()
            return Response({'message': 'Deleted successfully'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

#  Complete Purchase order list
class PurchaseOrderListAPI(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request):
        supplier = request.GET.get('supplier', None)
        poNumber = request.GET.get('poNumber', None)
        search   = request.GET.get('search', '')
        page     = request.GET.get('page', 1)

        try:
            orders = purchase_order_service.GetOrderList(supplier=supplier, poNumber=poNumber)
            orders = generic_services.applySearch(orders, search)
            data   = generic_services.paginate(orders, page)
            return Response({'orders': data.object_list, 'pages': data.paginator.num_pages})
        except Exception as e:
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# Backend URL for editing the PO
class PurchaseOrderUpdateAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request, pk: int):
        try:
            orderObject = models.PurchaseOrder.objects.get(id=pk)
        except models.PurchaseOrder.DoesNotExist:
            return Response({'message': 'Order not found'}, status=status.HTTP_404_NOT_FOUND)
        try:
            purchase_order_service.EditPurchaseOrderFromData(orderObject, dict(request.data))
            return Response({'message': 'Saved successfully'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# Backend url for Adding PO option in the frontend
class PurchaseOrderAddAPI(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request):
        try:
            poNumber = purchase_order_service.AddPurchaseOrderFromData(dict(request.data))
            return Response({'PONumber': poNumber}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class AddStyleCard(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'apparelManagement'
    modelName = 'StyleCard'
    permissionType = 'add'

    def get(self, _: Request):
        try:
            formData = style_card_service.GetDataForStyleCardAddition()
            return Response(data=formData, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request: Request):
        try:
            style_card_service.AddStyleCardAPI(request.data)
            response = {'message': 'Saved Successfully'}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)


class UpdateStyleCard(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]
    parser_classes = (MultiPartParser, FormParser)

    appName = 'apparelManagement'
    modelName = 'StyleCard'
    permissionType = 'change'

    def get(self, _: Request, pk: str):
        try:
            style = models.StyleCard.objects.get(StyleCode=pk)
        except:
            response = {'message': 'Resource Not Found'}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

        try:
            formData = style_card_service.GetDataForStyleCardUpdate(style)
            return Response(data=formData, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request: Request, pk: str):
        try:
            style = models.StyleCard.objects.get(StyleCode=pk)
        except:
            response = {'message': 'Resource Not Found'}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

        try:
            data = generic_services.refineAPIJson(request)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

        try:
            styleData = data.pop('style')
            variantData = data.pop('variant')
            routeData = data.pop('route')
            consumptionData = data.pop('consumption')
            attachmentData = data.pop('attachment')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

        try:
            style_card_service.EditStyleCard(style, styleData, variantData, routeData, consumptionData, attachmentData)
            response = {'message': 'Saved Successfully'}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)


class DeleteStyleCard(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'apparelManagement'
    modelName = 'StyleCard'
    permissionType = 'change'

    def delete(self, _: Request, pk: str):
        try:
            style = models.StyleCard.objects.get(StyleCode=pk)
        except:
            response = {'message': 'Resource Not Found'}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

        try:
            style.delete()
            response = {'message': 'Deleted'}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)


class DuplicateStyleCard(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'apparelManagement'
    modelName = 'StyleCard'
    permissionType = 'add'

    def post(self, request: Request, pk: str):
        sourceCode = request.data.get('Source', None)
        targetCode = request.data.get('Target', None)

        if None in [sourceCode, targetCode]:
            response = {'message': 'Incomplete Data Provided'}
            return Response(data=response, status=status.HTTP_409_CONFLICT)

        try:
            style_card_service.DuplicateStyleCard(sourceCode, targetCode)
            response = {'message': 'Added Successfully'}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)


class StyleRoutePresetDetails(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'apparelManagement'
    modelName = 'StyleCard'
    permissionType = 'change'

    def get(self, request: Request):
        try:
            authenticateUser(request, 'apparelManagement', 'StyleCard', 'add')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)

        routeId = request.query_params.get('routeId', None)
        try:
            routePreset = models.RoutePreset.objects.get(id=routeId)
        except:
            return HttpResponse('Invalid Route', status=400)

        try:
            stages = style_card_service.GetRoutePresetStages(routePreset)
            return Response(data=stages, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)


class AddWorkOrderAPI(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'apparelManagement'
    modelName = 'WorkOrder'
    permissionType = 'add'

    def get(self, _: Request):
        try:
            formData = work_order_service.GetDataForOrderAddition()
            return Response(data=formData, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request: Request):
        try:
            data = generic_services.refineAPIJson(request)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

        try:
            work_order_service.AddWorkOrderAPI(data)
            response = {'message': 'Saved Successfully'}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)


class UpdateWorkOrderAPI(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'apparelManagement'
    modelName = 'WorkOrder'
    permissionType = {
        'GET': 'view',
        'POST': 'change'
    }

    def get(self, _: Request, pk: int):
        try:
            workOrder = models.WorkOrder.objects.get(OrderNumber=pk)
        except:
            response = {'message': 'Resource Not Found'}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

        try:
            formData = work_order_service.GetDataForWorkOrderUpdate(workOrder)
            return Response(data=formData, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request: Request, pk: int):
        try:
            workOrder = models.WorkOrder.objects.get(OrderNumber=pk)
        except:
            response = {'message': 'Resource Not Found'}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

        if workOrder.Merchandiser != request.user:
            response = {'message': 'Access Denied'}
            return Response(data=response, status=status.HTTP_403_FORBIDDEN)

        try:
            data = generic_services.refineAPIJson(request)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

        try:
            orderData = data.pop('Order')
            variantData = data.pop('Variant')
            requirementData = data.pop('Requirement')
            attachmentData = data.pop('attachment')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

        try:
            work_order_service.EditWorkOrder(workOrder, orderData, variantData, requirementData, attachmentData)
            response = {'message': 'Saved Successfully'}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)


class CalculateVariantsAPI(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'apparelManagement'
    modelName = 'WorkOrder'
    permissionType = 'add'

    def get(self, request: Request):
        styleCode = request.query_params.get('styleCode', None)
        if styleCode is None:
            response = {'message': 'Need Style Code'}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

        try:
            style = models.StyleCard.objects.get(StyleCode=styleCode)
        except:
            response = {'message': 'Invalid Style Code'}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

        variants = list(models.StyleVariant.objects.filter(Style=style).values_list('VariantCode', flat=True))
        return Response(data=variants, status=status.HTTP_200_OK)


class CalculateInventoryRequirement(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'apparelManagement'
    modelName = 'WorkOrder'
    permissionType = 'change'

    def post(self, request: Request):
        styleCode = request.data.get('style', None)
        orderNumber = request.data.get('orderNumber', None)

        if None in [orderNumber, styleCode]:
            response = {'message': 'Incomplete data'}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

        try:
            workOrder = models.WorkOrder.objects.get(OrderNumber=orderNumber)
            styleCard = models.StyleCard.objects.get(StyleCode=styleCode)
        except Exception as e:
            response = {'message': 'Invalid Input'}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

        if workOrder.Merchandiser != request.user:
            response = {'message': 'Access Denied'}
            return Response(data=response, status=status.HTTP_403_FORBIDDEN)

        try:
            work_order_service.CalculateInventoryRequirement(styleCard, workOrder)
            response = {'message': 'Saved Successfully'}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)


class GetReqHistory(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'apparelManagement'
    modelName = 'WorkOrder'
    permissionType = 'view'

    def get(self, request: Request):
        requirementId = request.query_params.get('id', None)
        orderNumber = request.query_params.get('orderNumber', None)

        if not all([requirementId, orderNumber]):
            response = {'message': 'Invalid Input'}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

        try:
            requirement = models.InvRequirement.objects.get(id=requirementId)
            workOrder = models.WorkOrder.objects.get(OrderNumber=orderNumber)
        except models.InvRequirement.DoesNotExist:
            response = {'message': 'Requirement not found'}
            return Response(data=response, status=status.HTTP_404_NOT_FOUND)
        except models.WorkOrder.DoesNotExist:
            response = {'message': 'Invalid Work Order'}
            return Response(data=response, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

        try:
            requirementHistory = work_order_service.GetInventoryRequirementHistory(requirement, workOrder)
            return Response(data=requirementHistory, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)


class DeleteWorkOrderAPI(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'apparelManagement'
    modelName = 'WorkOrder'
    permissionType = 'delete'

    def get(self, request: Request, pk: int):
        try:
            workOrder = models.WorkOrder.objects.get(OrderNumber=pk)
        except:
            response = {'message': 'Resource not found'}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

        if workOrder.Merchandiser != request.user:
            response = {'message': 'Access Denied'}
            return Response(data=response, status=status.HTTP_403_FORBIDDEN)

        try:
            collector = Collector(using='default')
            collector.collect([workOrder])

            if collector.protected:
                raise ProtectedError("Protected objects found", collector.protected)
        except Exception as e:
            conflictingObjects = e.protected_objects
            protectedTypes = {obj._meta.verbose_name.capitalize() for obj in conflictingObjects}
            response = {
                'message': 'Cannot delete this entry due to protected dependencies',
                'protectedResources': list(protectedTypes)
            }
            return Response(data=response, status=status.HTTP_403_FORBIDDEN)

        response = {'message': 'Clear to delete'}
        return Response(data=response, status=status.HTTP_200_OK)

    def delete(self, request: Request, pk: int):
        try:
            workOrder = models.WorkOrder.objects.get(OrderNumber=pk)
        except:
            response = {'message': 'Resource not found'}
            return Response(data=response, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        if workOrder.Merchandiser != request.user:
            response = {'message': 'Access Denied'}
            return Response(data=response, status=status.HTTP_403_FORBIDDEN)

        try:
            workOrder.delete()
            response = {'message': 'Deleted'}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)


class PendingInventoryOrders(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'apparelManagement'
    modelName = 'WorkOrder'
    permissionType = 'view'

    def get(self, request: Request):
        startingOrderNumber = request.query_params.get('StartingOrder', None)
        endOrderNumber = request.query_params.get('EndingOrder', None)
        customers = request.query_params.getlist('Customers', [])

        if None in [startingOrderNumber, endOrderNumber]:
            response = {'message': 'Incomplete data provided'}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

        try:
            startingOrder = models.WorkOrder.objects.get(OrderNumber=startingOrderNumber)
            endingOrder = models.WorkOrder.objects.get(OrderNumber=endOrderNumber)
        except:
            response = {'message': 'Resource not found'}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

        try:
            pending = purchase_order_service.GetPendingOrders(startingOrder, endingOrder, customers)
            return Response(data=pending, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request: Request):
        try:
            poNumber = purchase_order_service.GeneratePOFromPendingPOs(request.data)
            response = {'poNumber': poNumber}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)


class AddSamplingIssuance(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'apparelManagement'
    modelName = 'Issuance'
    permissionType = 'add'

    def get(self, _: Request):
        try:
            formData = issuance_service.GetDataForSamplingIssuance()
            return Response(data=formData, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request: Request):
        try:
            issuanceNumber = issuance_service.AddSamplingIssuance(request.data)
            response = {'issuanceNumber': issuanceNumber}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

class EditIssuanceAPI(APIView):
    def get(self, request: Request, pk: int):
        try:
            data = issuance_service.GetDataForIssuanceUpdate(pk)
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request: Request, pk: int):
        try:
            data = generic_services.refineAPIJson(request)
        except Exception as e:
            print(e)
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        try:
            issuanceId = issuance_service.EditIssuance(pk, data)
            return Response({'issuanceId': issuanceId}, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class IssuanceListAPI(APIView):
    def get(self, request: Request):
        searchTerm = request.GET.get('search', '')
        departmentFilter = request.GET.get('department', None)
        issuanceNumber = request.GET.get('id', None)
        try:
            data = issuance_service.GetIssuanceList(searchTerm, departmentFilter, issuanceNumber)
            return Response(data, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

# API for inventory receipt related to MMC module
class InventoryReceipt(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'apparelManagement'
    modelName = 'InventoryReciept'
    permissionType = 'view'

    def get(self, _: Request):
        try:
            receipts = purchase_receipt_service.GetInventoryReceipts()
            return Response(data=receipts, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class AddInventoryReceiptAPI(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'apparelManagement'
    modelName = 'InventoryReciept'
    permissionType = 'add'

    def get(self, request: Request):
        poNumber = request.query_params.get('po', None)
        if poNumber:
            try:
                inventory = purchase_receipt_service.GetDataForRecAddition(poNumber)
            except Exception as e:
                print(e)
                return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        else:
            inventory = []
        return Response(data=inventory, status=status.HTTP_200_OK)

    def post(self, request: Request):
        try:
            data = generic_services.refineAPIJson(request)
        except Exception as e:
            print(e)
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        try:
            recNumber = purchase_receipt_service.AddPurchaseReceiptAPI(data)
            return Response({'recNumber': recNumber}, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class UpdateInventoryReceiptAPI(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'apparelManagement'
    modelName = 'InventoryReciept'
    permissionType = 'change'

    def get(self, _: Request, pk: int):
        try:
            inventoryReceipt = models.InventoryReciept.objects.get(id=pk)
        except:
            return Response({'message': 'Resource not found'}, status=status.HTTP_404_NOT_FOUND)
        try:
            formData = purchase_receipt_service.GetDataForReceiptUpdate(inventoryReceipt)
            return Response(formData, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request: Request, pk: int):
        try:
            data = generic_services.refineAPIJson(request)
        except Exception as e:
            print(e)
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        try:
            recNumber = purchase_receipt_service.EditPurchaseReceiptAPI(pk, data)
            return Response({'recNumber': recNumber}, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
