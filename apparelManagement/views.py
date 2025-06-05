from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse, HttpRequest

import json

from . import models
from .services import auth_service, generic_services, notifications_service
from .services import inventory_card_service, style_card_service, work_order_service
from .services import purchase_receipt_service, purchase_order_service, purchase_demand_service
from .services import requisition_service, issuance_service
from .theme import theme

@login_required(login_url='/login')
def blank (request: HttpRequest):
    context = {'theme': theme}
    return render (request, 'blank.html', context)

@login_required(login_url='/login')
def home (request: HttpRequest):
    notifications = notifications_service.GetNotifications(request.user)

    context = {
        'data': json.dumps(list(notifications)),
        'theme': theme
    }
    return render(request, 'app_home.html', context)

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
        return HttpResponse('Not allowed', status=405)

    if not auth_service.hasPermission(request, models.Inventory, type='view'):
        return HttpResponse('Access Denied', status=403)
    
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
               'theme': theme}
    return render (request, 'inventory/home.html',context)

@login_required(login_url = '/login')
def AddInv (request: HttpRequest): 
    if not auth_service.hasPermission(request, models.Inventory, type='add'):
        return HttpResponse('Access Denied', status=403)
       
    if request.method == 'POST':
        #Convert the json to a dict
        jsonData = json.loads(request.body.decode('utf-8'))

        dfInventory = generic_services.refineJson(jsonData)
        try:
            inventoryCode = inventory_card_service.AddInventory(dfInventory)
            return HttpResponse(inventoryCode, status=200)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)
    else:
        groups, unitTypes, auditReq, inUse, currencies,  codeP1  = inventory_card_service.getInventoryCardDropDowns()
        context = {
            'groups': groups, 'unitTypes': unitTypes, 'auditReq': auditReq, 'inUse': inUse,'currencies': currencies,
            'codeP1': codeP1,
            'theme': theme
            }
        
        return render (request, 'inventory/add.html', context)

@login_required(login_url='/login')
def GenerateInventoryCode (request: HttpRequest):
    if request.method != 'POST':
        return HttpResponse('Not allowed', status=405)
    
    jsonData = json.loads(request.body.decode('utf-8'))
    
    data = inventory_card_service.GenenrateCode(jsonData)
    return JsonResponse(data, safe=False)

@login_required(login_url='/login')
def CheckInventoryCodeExists(request: HttpRequest, pk: str):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', code=405)
    
    try:
        models.Inventory.objects.get(Code=pk)
        return HttpResponse('Code already exists', status=400)
    except:
        return HttpResponse('OK', status=200)

@login_required(login_url = '/login')
def UpdateInv(request: HttpRequest, pk: str):
    if not auth_service.hasPermission(request, models.Inventory, type='change'):
        return HttpResponse('Access Denied', status=403)
    
    try:
        inv = models.Inventory.objects.get(Code=pk)
    except:
        return HttpResponse('Resource not found', status=400)

    if request.method == 'POST':
        #Convert the json to a dict
        jsonData = json.loads(request.body.decode('utf-8'))

        dfInventory = generic_services.refineJson(jsonData)

        try:
            inventory_card_service.EditInventory(dfInventory, inv)
            return HttpResponse('OK', status=200)
        except Exception as e:
            return HttpResponse(e, status=400)
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
            'theme': theme
        }
        return render (request, 'inventory/edit.html', context)

@login_required(login_url = '/login')
def DeleteInv(request: HttpRequest, pk: int):
    if not auth_service.hasPermission(request, models.Inventory, type='delete'):
        return HttpResponse('Access Denied', status=403)
    
    try:
        inv = models.Inventory.objects.get(Code=pk)
    except:
        return HttpResponse('Resource not found', status=404)

    if request.method == 'POST':
        if 'confirm' in request.POST:
            try:
                inv.delete()
                return redirect('/inv')
            except Exception as e:
                context = {'object': inv, 'confirm': True, 'theme': theme, 'error': e}
                return render(request, 'inventory/delete.html', context)
        else:
            return redirect('/inv')
    else:
        context = {'object':inv, 'confirm':True, 'theme': theme}
        return render(request, 'inventory/delete.html', context)

@login_required(login_url = '/login')
def CopyInv (request: HttpRequest, pk: str): 
    if not auth_service.hasPermission(request, models.Inventory, type='add'):
        return HttpResponse('Access Denied', status=403)   
    
    if request.method == 'POST':
        sourceCode = request.POST.get('source')
        targetCode = request.POST.get('target')

        if not targetCode:
            context = {'message': 'No Code provided','theme': theme, 'code': pk}
            return render(request, 'inventory/copy.html', context)

        try:
            models.Inventory.objects.get(Code=targetCode)
            context = {'message': 'Code Already Exists','theme': theme, 'code': pk}
            return render(request, 'inventory/copy.html', context)
        except:
            Inventory = models.Inventory.objects.get(Code=sourceCode)
            Inventory.Code = targetCode
            Inventory.save()

            return redirect(f'/inv/{targetCode}/edit')
    else:
        context = {'theme': theme, 'code': pk}
        return render(request, 'inventory/copy.html', context)

@login_required(login_url = '/login')
def Style (request: HttpRequest):
    if not auth_service.hasPermission(request, models.StyleCard, type='view'):
        return HttpResponse('Access denied', status=403)
    
    if request.method == 'GET':
        searchTerm = request.GET.get('search_term', '')
        customerFilter = request.GET.get('customerFilter', '')
        pageNumber = request.GET.get('pageNumber',1)

        Style = style_card_service.getStyleCard(searchTerm=searchTerm, customer=customerFilter)

        customers = sorted([customer for customer, in models.StyleCard.objects.values_list('Customer_id').distinct()if customer is not None])

        data = generic_services.paginate(Style, pageNumber)

        context = {'style': data.object_list, 'page_obj': data
                ,'theme': theme
                ,'customers': customers, 'searchTerm': searchTerm, 'selectedCustomer': customerFilter}

        return render(request, 'style/home.html', context)
    else:
        return HttpResponse('Not Allowed', status=403)

@login_required(login_url = '/login')
def AddStyle (request: HttpRequest):
    if not auth_service.hasPermission(request, models.StyleCard, type='add'):
        return HttpResponse('Access Denied', status=403)
    
    if request.method == 'POST':        
        #Convert the json to a dict
        jsonData = json.loads(request.body.decode('utf-8'))

        dfStyle, dfVariants, dfRoute = generic_services.refineJson(jsonData) 
        
        try:
            styleCode = style_card_service.AddStyleCard(dfStyle, dfVariants, dfRoute)       
            return HttpResponse(styleCode, status=200)
        except Exception as e:
            print(e)
            context = {'error': str(e)}
            return HttpResponse(e, status=400)
         
    else:
        context = {
            'theme': theme
        }
        return render (request, 'style/add.html', context)

@login_required(login_url='/login')
def UpdateStyle (request: HttpRequest, pk: str):
    if not auth_service.hasPermission(request, model=models.StyleCard, type='change'):
        return HttpResponse('Access Denied', status=403)

    try:
        style = models.StyleCard.objects.get(StyleCode=pk)
    except:
        return HttpResponse('Style Card not found', status=400)
    if request.method == 'POST':
        #Convert the json to a dict
        data = json.loads(request.body.decode('utf-8'))
        
        dfStyle, dfVariants, dfConsumption, dfRoute = generic_services.refineJson(data)
        del data

        try:
            style_card_service.UpdateStyleCard(dfStyle, dfVariants, dfConsumption, dfRoute)
            selectedTable = dfStyle['SelectedTable'][0]
            return HttpResponse(selectedTable, status=200)
        except Exception as e:
            print(e)
            context = {'error': str(e)}
            return HttpResponse(e, status=400)        
    else:
        style, variants, consumption, route = style_card_service.ProcessStyleData(style)
        context = {'style':style,
                   'var':variants,
                   'cons':consumption, 'consJson': json.dumps(list(consumption)),
                   'route':route, 'routeJson':json.dumps(list(route)),
                   'theme':theme}
        return render(request, 'style/edit.html', context)

@login_required(login_url='/login')
def DeleteStyle(request: HttpRequest, pk: str):
    if not auth_service.hasPermission(request, models.StyleCard, type='delete'):
        return HttpResponse('Access Denied', status=403)
    
    style = models.StyleCard.objects.get(StyleCode=pk)

    if request.method == 'POST':
        if 'confirm' in request.POST:
            try:
                style.delete()
                return redirect('/style')
            except Exception as e:
                context = {'object':style, 'confirm':True, 'theme': theme, 'error': e}
                return render(request, 'style/delete.html', context)
        else:
            return redirect('/style')
    
    else:
        context = {'object':style, 'confirm':True, 'theme': theme}
        return render(request, 'style/delete.html', context)

@login_required(login_url='/login')
def CopyStyle(request: HttpRequest, pk: str):
    if not auth_service.hasPermission(request, models.StyleCard, type='add'):
        return HttpResponse('Access Denied', status=403)

    style = models.StyleCard.objects.get(StyleCode=pk)

    if request.method == 'POST':
        SourceCode = request.POST.get('source')
        TargetCode = request.POST.get('target')

        try:
            models.StyleCard.objects.get(StyleCode=TargetCode)
            context = {'message': 'Code Already Exsits','theme': theme}
            return render (request, 'blank.html',context)
        except models.StyleCard.DoesNotExist:
            styleObj = models.StyleCard.objects.get(StyleCode=SourceCode)
            styleObj.StyleCode = TargetCode
            styleObj.save()

            styleObj = models.StyleCard.objects.get(StyleCode=TargetCode)

            sourceVariants = models.StyleVariant.objects.filter(Style=SourceCode)
            for variant in sourceVariants:
                variant.pk = None
                variant.Style = styleObj
                variant.save()
            
            sourceConsumptions = models.StyleConsumption.objects.filter(Style=SourceCode)
            for consumption in sourceConsumptions:
                consumption.pk = None
                consumption.Style = styleObj
                consumption.save()
            
            sourceRoutes = models.StyleRoute.objects.filter(Style=SourceCode)
            for route in sourceRoutes:
                route.pk = None
                route.Style = styleObj
                route.save()
            
            return redirect(f'/style/{TargetCode}/edit')
        except Exception as e:
            context = {'message': f'Error: {e}', 'theme': theme}
            return render (request, 'blank.html',context)
    else:
        context = {'source':style.StyleCode, 'theme': theme}
        return render(request, 'style/copy.html', context)

@login_required(login_url='/login')
def WorkOrder (request: HttpRequest):
    if not auth_service.hasPermission(request, models.WorkOrder, type='view'):
        return HttpResponse('Access Denied', status=403)

    if request.method != 'GET':
        return HttpResponse('Not allowed', status=405)
    
    searchTerm = request.GET.get('search_term', '')
    customerFilter = request.GET.get('customerFilter', '')
    pageNumber = request.GET.get('pageNumber',1)

    Order = work_order_service.GetOrderList(searchTerm=searchTerm, customer=customerFilter)

    data = generic_services.paginate(Order, pageNumber)

    context = {'order': data.object_list, 'page_obj': data
               ,'theme': theme
               , 'searchTerm': searchTerm, 'selectedCustomer': customerFilter}

    return render(request, 'work_order/home.html', context)

@login_required(login_url='/login')
def AddWorkOrder(request: HttpRequest):
    if not auth_service.hasPermission(request, models.WorkOrder, type='add'):
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
            'theme': theme
        }
        return render(request, 'work_order/add.html', context)

@login_required(login_url='/login')
def UpdateWorkOrder(request: HttpRequest, pk: int):
    if not auth_service.hasPermission(request, models.WorkOrder, type='change'):
        return HttpResponse('Access Denied', status=403)

    try:
        orderObject = models.WorkOrder.objects.get(OrderNumber=pk)
    except:
        return HttpResponse('Resouse not found', status=401)


    if request.method == 'POST':
        #Convert the json to a dict
        jsonData = json.loads(request.body.decode('utf-8'))

        dfOrder, dfVariants, dfRequirement = generic_services.refineJson(jsonData)

        try:
            work_order_service.UpdateWorkOrder(dfOrder, dfVariants, dfRequirement)
            return HttpResponse('OK', status=200)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)
    else:
        order, variants, requirement = work_order_service.ProcessOrderData(orderObject)
        context = {'order':order,
                   'var':variants,
                   'req':requirement, 'reqJson':json.dumps(list(requirement)),
                   'theme':theme}
        
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
    if request.method == 'POST':
        #convert json to a dict.
        data = json.loads(request.body.decode('utf-8'))
        
        styleCode = data['styleCode']
        orderNumber = data['orderNumber']

        requirement = work_order_service.CalculateRequirement(styleCode, orderNumber)

        return JsonResponse(data=requirement, safe=False)
    else:
        return HttpResponse('Not allowed', status=302)

@login_required(login_url='/login')
def GetRequirementHistory (request: HttpRequest):
    data = json.loads(request.body.decode('utf-8'))

    inventoryCode = data['inventory']
    variant = data['variant']
    workOrder = data['workOrder']
    
    try:
        requirement = work_order_service.GetRequirementHistory(inventoryCode, variant, workOrder)
        return requirement
    except Exception as e:
        return HttpResponse(e, status=400)
    
@login_required(login_url='/login')
def GeneratePOFromWO (request: HttpRequest, pk):
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
    try:
        order = models.WorkOrder.objects.get(OrderNumber=pk)
    except:
        return HttpResponse('Resouse not found', status=400)
    
    if not auth_service.hasPermission(request, models.WorkOrder, 'delete'):
        return HttpResponse('Not allowed', status=403)

    if request.method == 'POST':
        if 'confirm' in request.POST:
            try:
                orderNumber = order.OrderNumber
                order.delete()
                notifications_service.DeleteWorkOrder(order, orderNumber)
                return redirect('/workorder')
            except Exception as e:
                context = {'object':order, 'confirm':True, 'theme': theme, 'error': e}
                return render(request, 'work_order/delete.html', context)
        else:
            return redirect('/workorder')
    else:
        context = {'object':order, 'confirm':True, 'theme': theme}
        return render(request, 'work_order/delete.html', context)

@login_required(login_url='/login')
def PrintWorkOrder(request: HttpRequest, pk: str):
    if not auth_service.hasPermission(request, models.WorkOrder, type='view'):
        return HttpResponse('Access Denied', status=403)

    try:
        orderObject = models.WorkOrder.objects.get(OrderNumber=pk)
    except:
        return HttpResponse('Order not found', status=404)
    
    if request.method == 'POST':
        data = json.loads(request.body.decode('utf-8'))
        requiredFormat = data['format']
        
        try:
            order, cutting, material, status = work_order_service.PrintWO(orderObject)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)

        context = {'order':order, 'cut':cutting, 'material': material, 'status': status, 'theme': theme}

        try:
            match requiredFormat:
                case 'CUT':
                    return render(request, 'work_order/print_cut.html', context)
                case 'F&T':
                    print('Need to make farbic and trims status format')
                    return HttpResponse('This page is under construction')
                case 'PST':
                    print('Need to make production status format')
                    return HttpResponse('This page is under construction')
                case _:
                    return HttpResponse('Incorrect format', status=400)
        except Exception as e:
            return HttpResponse(e, status=405)
    else:
        return HttpResponse('Not Allowed', status=403)

@login_required(login_url='/login')
def CopyWorkOrder(request: HttpRequest, pk):
    if not auth_service.hasPermission(request, models.WorkOrder, type='add'):
        return HttpResponse('Access Denied', status=403)

    order = models.WorkOrder.objects.get(OrderNumber=pk)

    if request.method == 'POST':
        SourceNumber = request.POST.get('source')
        TargetNumber = request.POST.get('target')
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
            context = {'message': f'Error: {e}', 'theme': theme}
            return render (request, 'blank.html',context)

    else:
        context = {'source':order.OrderNumber, 'theme': theme}
        return render(request, 'work_order/copy.html', context)

@login_required(login_url='/login')
def AutoInventoryRequirement(request: HttpRequest):
    if not auth_service.hasPermission(request, models.PurchaseOrder, type='add'):
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
        searchTerm = request.GET.get('search','')

        if startingOrder == 'null':
            startingOrder = None
        if endingOrder == 'null':
            endingOrder = None
        
        if not endingOrder:
            endingOrder = startingOrder

        requirement, invs = purchase_order_service.PrepareDataForAutoReq(startingOrder, endingOrder)

        context = {'theme':theme, 'startingOrder':startingOrder, 'endingOrder':endingOrder, 'search':searchTerm,
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
    
    if not auth_service.hasPermission(request, models.PurchaseOrder, type='view'):
        return HttpResponse('Access Denied', status=403)

    searchTerm = request.GET.get('searchTerm', '')
    supplierFilter = request.GET.get('supplierFilter', None)
    poFilter = request.GET.get('poFilter', None)
    pageNumber = request.GET.get('pageNumber',1)
    
    if supplierFilter == 'null':
        supplierFilter = None

    Order = purchase_order_service.GetOrderList(searchTerm=searchTerm, supplier=supplierFilter, poNumber=poFilter)
    data = generic_services.paginate(Order, pageNumber)

    context = {'order': data.object_list, 'page_obj': data
               ,'theme': theme
               , 'searchTerm': searchTerm, 'selectedSupplier': supplierFilter, 'selectedPO':poFilter}
    
    return render(request, 'purchase_order/home.html', context)

@login_required(login_url='/login')
def AddPurchaseOrder(request: HttpRequest):
    if not auth_service.hasPermission(request, models.PurchaseOrder, type='add'):
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
            'theme': theme
        }
        return render(request, 'purchase_order/add.html', context)

@login_required(login_url='/login')
def EditPurchaseOrder(request: HttpRequest, pk):
    if not auth_service.hasPermission(request, models.PurchaseOrder, type='change'):
        return HttpResponse('Access Denied', status=403)

    try:
        orderObject = models.PurchaseOrder.objects.get(id=pk)
    except:
        return HttpResponse('Order not found', status=404)
    
    if request.method == 'POST':
        #convert json data to a dict.
        data = json.loads(request.body.decode('utf-8'))

        dfOrder, dfInventory, dfAllocation = generic_services.refineJson(data)
        try:
            purchase_order_service.EditPurchaseOrder(orderObject, dfOrder, dfInventory, dfAllocation)
            return HttpResponse('Saved Successfuly', status=200)
        except Exception as e:   
            print(e)         
            return HttpResponse(e, status=400)
    else:
        order, inventory=purchase_order_service.ProcessOrderData(orderObject)
        context = {'order':order,
                   'inv':inventory, 'invJson':json.dumps(list(inventory)),
                   'theme':theme}
        
        return render(request, 'purchase_order/edit.html', context)

@login_required(login_url='/login')
def getPOAllocation(request: HttpRequest):
    if request.method == 'POST':
        pk = json.loads(request.body.decode('utf-8'))['id']

        try:
            poInventory = models.POInventory.objects.get(id=pk)
        except:
            return HttpResponse('Resource not found',status=401)

        allocation = purchase_order_service.getPOAllocation(poInventory)

        return JsonResponse(allocation, safe=False)
    else:
        return HttpResponse('Not allowed', status=302)

@login_required(login_url='/login')
def GetWODefaultQtyForPO (request: HttpRequest):
    if request.method != 'POST':
        return HttpResponse('Not Allowed', status=405)
    
    data = json.loads(request.body.decode('utf-8'))

    invVar = data['invVar'].split('_')
    inventory = models.Inventory.objects.get(Code=invVar[0])
    variant = invVar[1]

    workOrder = data['workOrder']
    if workOrder == 'null':
        return JsonResponse(0, safe=False)
    else:
        workOrder = models.WorkOrder.objects.get(OrderNumber=workOrder)

    if 'poNumber' in data:
        currentPO = data['poNumber']
        currentPO = models.PurchaseOrder.objects.get(id=currentPO)
    else:
        currentPO = models.PurchaseOrder()

    quantity = purchase_order_service.GetWorkOrderDefaultQty(workOrder, inventory, variant, currentPO)

    return JsonResponse(quantity, safe=False)

@login_required(login_url='/login')
def getAllocatedQty (request: HttpRequest):
    if request.method == 'POST':
        data = json.loads(request.body.decode('utf-8'))
    
        inventory = models.Inventory.objects.get(Code=data['invCode'])
        variant = data['variant']
        purchaseOrder = models.PurchaseOrder.objects.get(id=data['poNumber'])

        quantity = purchase_order_service.getAllocatedQty(purchaseOrder, inventory, variant)

        return JsonResponse(quantity, safe=False)
    else:
        return HttpResponse('Not Allowed', status=405)

@login_required(login_url='/login')
def PrintPurchaseOrder(request: HttpRequest, pk: str):
    if not auth_service.hasPermission(request, models.PurchaseOrder, type='view'):
        return HttpResponse('Access Denied', status=403)

    try:
        orderObject = models.PurchaseOrder.objects.get(id=pk)
    except:
        return HttpResponse('Order not found', status=404)
    
    if request.method == 'POST':
        data = json.loads(request.body.decode('utf-8'))
        requiredFormat = data['format']

        order, inventory, allocation, summary = purchase_order_service.PrintPO(orderObject)
        
        context = {'order':order, 'inv':inventory, 'alloc': allocation, 'summary': summary, 'theme': theme} 

        if requiredFormat == 'SUP':
            return render(request, 'purchase_order/print_supplier.html', context)
        elif requiredFormat=='ACC':
            return render(request, 'purchase_order/print_accounts.html', context)
        else:
            return HttpResponse('Invalid print format.', status=400)
    else:
        return HttpResponse('Not Allowed', status=405)

@login_required(login_url='/login')
def CopyPurchaseOrder (request: HttpRequest, pk):
    if not auth_service.hasPermission(request, models.PurchaseOrder, type='add'):
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
        context = {'source':po, 'theme': theme}
        return render(request, 'purchase_order/copy.html', context)

@login_required(login_url='/login')
def DeletePurchaseOrder(request: HttpRequest, pk: int):
    try:
        order = models.PurchaseOrder.objects.get(id=pk)
    except:
        return HttpResponse('Resource not found', status=400)
    
    if not auth_service.hasPermission(request, models.PurchaseOrder, type='delete'):
        return HttpResponse('Access Denied', status=403)
    
    if request.method == 'POST':
        if 'confirm' in request.POST:
            try:
                order.delete()
                return redirect('/purchaseorder')
            except Exception as e:
                context = {'object':order, 'confirm':True, 'theme': theme, 'error':e}
                return render(request, 'purchase_order/delete.html', context)
        else:
            return redirect('/purchaseorder')
    else:
        context = {'object':order, 'confirm':True, 'theme': theme}
        return render(request, 'purchase_order/delete.html', context)

@login_required(login_url='/login')
def PurchaseReceipt(request: HttpRequest):
    if not auth_service.hasPermission(request, models.InventoryReciept, type='view'):
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
    
    receipt = purchase_receipt_service.GetReceiptList(searchTerm, supplierFilter, recFilter)

    data = generic_services.paginate(receipt, pageNumber)
    
    context = {
        'receipt': data.object_list, 'receiptObj': data,
        'theme':theme,
        'searchTerm': searchTerm, 'selectedSupplier': supplierFilter, 'selectedRec':recFilter}
    return render(request, 'purchase_receipt/home.html', context)

@login_required(login_url='/login')
def AddPurchaseReceipt(request: HttpRequest):
    if not auth_service.hasPermission(request, models.InventoryReciept, type='add'):
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
            purchaseOrder = models.PurchaseOrder()
        
        inventory = purchase_receipt_service.GetPOData(purchaseOrder)

        context = {
            'inventory': inventory,'poNumber': poNumber,
            'theme': theme
        }
        return render(request, 'purchase_receipt/add.html', context)

@login_required(login_url='/login')
def EditPurchaseReceipt(request: HttpRequest, pk:str):
    if not auth_service.hasPermission(request, models.InventoryReciept, type='change'):
        return HttpResponse('Access Denied', status=403)

    try:
        receiptObject = models.InventoryReciept.objects.get(id=pk)
    except:
        return HttpResponse('Resource not found', status=404)
    
    if request.method == 'POST':
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
        receipt, inventory = purchase_receipt_service.ProcessReceiptData(receiptObject)

        context = {'receipt':receipt,
                   'inv':inventory, 'invJson':json.dumps(list(inventory)),
                   'theme':theme}
        
        return render(request, 'purchase_receipt/edit.html', context)

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
def CopyPurchaseReceipt (request: HttpRequest, pk: int):
    if not auth_service.hasPermission(request, models.InventoryReciept, type='add'):
        return HttpResponse('Access Denied', status=403)

    receipt = models.InventoryReciept.objects.get(id=pk)

    if request.method == 'POST':
        SourceNumber = request.POST.get('source')
        receipt = models.InventoryReciept.objects.get(id=SourceNumber)

        receipt.id = None
        receipt.save()

        recInventories = models.RecInventory.objects.filter(ReceiptNumber=SourceNumber)

        for inventory in recInventories:
            oldId = inventory.id
            inventory.id = None
            inventory.ReceiptNumber = receipt
            inventory.save()
            
            invAllocations = models.RecAllocation.objects.filter(RecInvId=oldId)
            for allocation in invAllocations:
                allocation.id = None
                allocation.RecInvId = inventory
                allocation.save()
        return redirect(f'/purchasereceipt/{receipt.id}/edit')
    else:
       context = {'source':receipt, 'theme': theme}
       return render(request, 'purchase_receipt/copy.html', context)

@login_required(login_url='/login')
def DeletePurchaseReceipt (request: HttpRequest, pk: int):
    try:
        receipt = models.InventoryReciept.objects.get(id=pk)
    except:
        return HttpResponse('Resource not found', status=400)

    if not auth_service.hasPermission(request, models.InventoryReciept, type='delete'):
        return HttpResponse('Access Denied', status=403)


    if request.method == 'POST':
        if 'confirm' in request.POST:
            try:
                receipt.delete()
                return redirect('/purchasereceipt')
            except Exception as e:
                context = {'object':receipt, 'confirm':True, 'theme': theme, 'error':e}
                return render(request, 'purchase_receipt/delete.html', context)
        else:
            return redirect('/purchasereceipt')
    else:
        context = {'object':receipt, 'confirm':True, 'theme': theme}
        return render(request, 'purchase_receipt/delete.html', context)

@login_required(login_url='/login')
def PurchaseDemand (request: HttpRequest):
    if not auth_service.hasPermission(request, models.PurchaseDemand, type='view'):
        return HttpResponse('Access Denied', status=403)

    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=405)
    
    searchTerm = request.GET.get('searchTerm', '')
    departmentFilter = request.GET.get('departmentFilter', None)
    statusFilter = request.GET.get('statusFilter', 'OnApp')
    pdNumber = request.GET.get('demandFilter', None)
    pageNumber = request.GET.get('pageNumber',1)

    if (departmentFilter == 'None') or (departmentFilter == 'null'):
        departmentFilter = None

    demand = purchase_demand_service.GetPurchaseDemandList(searchTerm, departmentFilter, pdNumber, statusFilter)
    
    data = generic_services.paginate(demand, pageNumber)
    
    context = {
        'demand': data.object_list, 'demandObj': data,
        'theme':theme,
        'selectedDepartment': departmentFilter, 'searchTerm': searchTerm, 'selectedStatus': statusFilter,
        'selectedDemand': pdNumber
        }

    return render(request, 'purchase_demand/home.html', context)

@login_required(login_url='/login')
def AddPurchaseDemand (request: HttpRequest):
    if not auth_service.hasPermission(request, models.PurchaseDemand, type='add'):
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
            'theme': theme
        }
        return render(request, 'purchase_demand/add.html', context)

@login_required(login_url='/login')
def EditPurchaseDemand (request: HttpRequest, pk: int):
    if not auth_service.hasPermission(request, models.PurchaseDemand, type='change'):
        return HttpResponse('Access Denied', status=403)

    try:
        demand = models.PurchaseDemand.objects.get(id=pk)
    except:
        return HttpResponse('Demand not found', status=400)
    
    if demand.Approval != None:
        return HttpResponse('This demand is closed.', status=405)
    
    if request.method == 'POST':
        #convert json data to a dict.
        data = json.loads(request.body.decode('utf-8'))

        dfDemand, dfInventory = generic_services.refineJson(data)

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
                   'theme':theme}
        
        return render(request, 'purchase_demand/edit.html', context)

@login_required(login_url='/login')
def CopyPurchaseDemand (request: HttpRequest, pk:int):
    if not auth_service.hasPermission(request, models.PurchaseDemand, type='add'):
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
       context = {'source':demand, 'theme': theme}
       return render(request, 'purchase_demand/copy.html', context)

@login_required(login_url='/login')
def DeletePurchaseDemand (request: HttpRequest, pk: int):
    if not auth_service.hasPermission(request, models.PurchaseDemand, type='delete'):
        return HttpResponse('Access Denied', status=403)

    try:
        demand = models.PurchaseDemand.objects.get(id=pk)
    except:
        return HttpResponse('Demand not found', status=400)
    
    if demand.Approval != None:
        return HttpResponse('This demand is closed.', status=405)
    
    if request.method == 'POST':
        if ('confirm' in request.POST):
            try:
                demand.delete()
                return redirect('/purchasedemand')
            except Exception as e:
                context = {'object':demand, 'confirm':True, 'theme': theme, 'error': e}
                return render(request, 'purchase_demand/delete.html', context)
        else:
            return redirect('/purchasedemand')
    else:
        context = {'object':demand, 'confirm':True, 'theme': theme}
        return render(request, 'purchase_demand/delete.html', context)

@login_required(login_url='/login')
def ApprovePurchaseDemand (request: HttpRequest, pk: int):
    try:
        demand = models.PurchaseDemand.objects.get(id=pk)
    except:
        return HttpResponse('Demand not found', status=400)
    
    if not auth_service.canApprovePD(request):
        return HttpResponse('You do not have access to this file', status=405)

    if request.method == 'POST':
        approval = request.POST.get('Approval')

        try:
            purchase_demand_service.ApprovePD(request, demand, approval)
            return redirect('/purchasedemand')
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)
    else:
        try:
            demand, context = purchase_demand_service.GetDataForPDApproval(demand)
            
            context = {'demand': demand, 'context': context, 'theme': theme}
            
            return render(request, 'purchase_demand/approve.html', context)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)

@login_required(login_url='/login')
def ConvertPDtoPO (request: HttpRequest):
    if not auth_service.hasPermission(request, models.PurchaseDemand, type='add'):
        return HttpResponse('Access Denied', status=403)

    if request.method != 'POST':
        return HttpResponse('Not Allowed', status=405)
    
    data = json.loads(request.body.decode('utf-8'))
    try:
        demand = models.PurchaseDemand.objects.get(id=data['pdNumber'])
    except:
        return HttpResponse('Demand not found', status=400)

    try:
        poNumber = purchase_demand_service.ConvertPDtoPO(demand, data['supplier'])
        return HttpResponse(poNumber, status=200)
    except Exception as e:
        print(e)
        return HttpResponse(e, status=400)

@login_required(login_url='/login')
def Requisition (request: HttpRequest):
    if not auth_service.hasPermission(request, models.Requisition, type='view'):
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

    requisition = requisition_service.GetRequisitionList(searchTerm, departmentFilter, statusFilter, requisitionNumber)
    
    data = generic_services.paginate(requisition, pageNumber)

    context = {
    'req': data.object_list, 'demandObj': data,
    'theme':theme,
    'selectedDepartment': departmentFilter, 'searchTerm': searchTerm, 'selectedStatus': statusFilter,
    'selectedRequisition': requisitionNumber
    }

    return render(request, 'requisition/home.html', context)

@login_required(login_url='/login')
def AddRequisitionForOrder (request: HttpRequest):
    if not auth_service.hasPermission(request, models.Requisition, type='add'):
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
                'theme': theme
            }
        
        if order:
            data, invs = requisition_service.PrepareDataForOrderRequitionAdd(order)
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
def AddRequisitionForInv (request: HttpRequest):
    if not auth_service.hasPermission(request, models.Requisition, type='add'):
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
            'theme': theme
        }

        return render(request, 'requisition/add_inv.html', context)

@login_required(login_url='/login')
def EditRequisition (request: HttpRequest, pk: int):
    if not auth_service.hasPermission(request, models.Requisition, type='change'):
        return HttpResponse('Access Denied', status=403)

    try:
        requisition = models.Requisition.objects.get(id=pk)
    except:
        return HttpResponse('Requisition Not Found', status=400)
    
    if request.method == 'POST':
        #convert json data to a dict.
        data = json.loads(request.body.decode('utf-8'))

        dfRequisition, dfInventory, dfAllocation = generic_services.refineJson(data)
        try:
            requisition_service.EditRequisition(requisition, dfRequisition, dfInventory, dfAllocation)
            return HttpResponse('This option is under construction', status=503)
        except Exception as e: 
            print(e)           
            return HttpResponse(e, status=400)
    else:
        try:
            requisition, inventories = requisition_service.ProcessRequsitionData(requisition)

            context = {
                'req':requisition,'inv':inventories,
                'theme':theme
            }
            return render(request, 'requisition/edit.html', context)
        except Exception as e:
            print(e)
            return HttpResponse(e, status=400)

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
    if not auth_service.hasPermission(request, models.Issuance, type='view'):
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
        'theme':theme,
        'selectedDepartment': departmentFilter, 'searchTerm': searchTerm,
        'selectedIssuance': issuanceNumber
        }

    return render(request, 'issuance/home.html', context)
    
@login_required(login_url='/login')
def AddIssuance (request: HttpRequest):
    if not auth_service.hasPermission(request, models.Issuance, type='add'):
        return HttpResponse('Access Denied', status=403)

    if request.method != 'GET':
        return HttpResponse('Not allowed', status=405)
    
    requisition = request.GET.get('req',None)
    try:
        requisition = models.Requisition.objects.get(id=requisition)
    except:
        return HttpResponse('Requisition Not Found', status=400)
    
    if requisition.Confirmation:
        return HttpResponse ('This requisition is closed.', status=405)
    
    try:
        issueNumber = issuance_service.AddIssuance(requisition)
        return redirect('editIssue', pk=issueNumber, permanent=True)
    except Exception as e:
        print(e)
        return HttpResponse(e, status=400)

@login_required(login_url='/login')
def EditIssuance (request: HttpRequest, pk: int):
    if not auth_service.hasPermission(request, models.Issuance, type='change'):
        return HttpResponse('Access Denied', status=403)

    try:
        issuance = models.Issuance.objects.get(id=pk)
    except:
        return HttpResponse('Issuance Not Found', status=400)
    
    if request.method == 'POST':
        pass
    else:      
        print(issuance)
        return HttpResponse('Under construction')
