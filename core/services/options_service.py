from django.http import JsonResponse, HttpResponse, HttpRequest
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Exists, OuterRef, Q, Count

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import  AllowAny
from rest_framework.authtoken.models import Token
from rest_framework.request import Request
import rest_framework

from django_countries import countries

import pandas as pd

from apparelManagement import models as appModels
from marketing import models as marketingModels
from prodManagement import models as prodModels

from core.constants.prod import operationSections, operationCategories, machineTypes, machineManufacturers
from core.constants.generic import APP_OPTIONS
from core.services.auth_service import hasPermission

from .generic_services import dfToListOfDicts

@login_required(login_url='/login')
def yesOrNo(request):
    if request.method == 'GET':
        data = {
            "value": [True, False],
            "text": ["Yes", "No"]
        }

        dfData = pd.DataFrame(data)

        cols = [i for i in dfData]
        data = [dict(zip(cols, i)) for i in dfData.values]
        return JsonResponse(data, safe=False)

@login_required(login_url='/login')
def getCustomersList(request):
    if request.method == 'GET':
        objects = appModels.Customer.objects.all()     
        dfData = pd.DataFrame(index=range(objects.count()))
        
        dfData['text'] = pd.DataFrame(objects.values('Name'))
        dfData['value'] = pd.DataFrame(objects.values('Name'))

        dfData = pd.concat([pd.Series({'value':None, 'text':'-----------'}).to_frame().T, dfData], ignore_index=True)

        cols = [i for i in dfData]
        data = [dict(zip(cols, i)) for i in dfData.values]
        return JsonResponse(data, safe=False)

@login_required(login_url='/login')
def getSuppliersList(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=405)

    search = request.GET.get('search','')

    searchFilter = Q()
    if search:
        searchFilter &= (
            Q(Name__icontains=search) |
            Q(TradeName__icontains=search) |
            Q(Address__icontains=search)
        )
    
    fields = ['Name','TradeName']
    suppliers = appModels.Supplier.objects.filter(searchFilter)[:15].values(*fields)

    if suppliers:
        dfSupplier = pd.DataFrame(suppliers)
        dfSupplier['text'] = dfSupplier['Name'].astype(str)+' - '+dfSupplier['TradeName'].astype(str)
        dfSupplier.drop(inplace=True, columns=['TradeName'])
        dfSupplier.rename(inplace=True, columns={'Name':'value'})
        
        suppliers = dfSupplier.to_dict(orient='records')  
    else:
        suppliers = []

    return JsonResponse(suppliers, safe=False)

@login_required(login_url='/login')
def getDepartmentsList (request: HttpRequest):
    if request.method == 'GET':
        objects = appModels.Department.objects.all()
        dfData = pd.DataFrame(index=range(objects.count()))

        dfData['text'] = pd.DataFrame(objects.values('FullName'))
        dfData['value'] = pd.DataFrame(objects.values('Name'))

        dfData = pd.concat([pd.Series({'value':None, 'text':'-----------'}).to_frame().T, dfData], ignore_index=True)

        cols = [i for i in dfData]
        data = [dict(zip(cols, i)) for i in dfData.values]
        return JsonResponse(data, safe=False)

@login_required(login_url='/login')
def getCategories(request):
    if request.method == 'GET':
        options = appModels.Categories
        dfData = pd.DataFrame(options)

        dfData.columns = ['value', 'text']

        cols = [i for i in dfData]
        data = [dict(zip(cols, i)) for i in dfData.values]
        return JsonResponse(data, safe=False)

@login_required(login_url='/login')
def getInventories(request: HttpRequest):
    if request.method == 'GET':
        invGroup = request.GET.get('group',None)
        search = request.GET.get('search', '')
        searches = request.GET.getlist('searches', [])
        newFormat = request.GET.get('newFormat', None)

        if invGroup == 'Direct':
            groups = ['Fabric','Trim']
            objects = appModels.Inventory.objects.filter(InUse=True).filter(Group__in=groups)
        elif invGroup == 'Indirect':
            groups = ['Electrical','Mechanical','Other','Medicine','Stationery','Housekeeping','Electronics','Fixed Assets']
            objects = appModels.Inventory.objects.filter(InUse=True).filter(Group__in=groups)
        elif invGroup:
            objects = appModels.Inventory.objects.filter(InUse=True).filter(Group=invGroup)
        else:
            objects = appModels.Inventory.objects.filter(InUse=True)
        
        if search:
            objects = objects.filter(Q(Name__icontains=search) | Q(Code__icontains=search))
        
        if searches:
            for search in searches:
                if search:
                    objects = objects.filter(Q(Name__icontains=search) | Q(Code__icontains=search))

        if objects.count() < 1:
            return JsonResponse([], safe=False)

        if newFormat != 'No':
            objects = objects[:15]
        data = objects.values('Code','Name')
        dfData = pd.DataFrame(data)
        
        dfData['text'] = dfData['Name']+' - '+dfData['Code']
        dfData.drop(inplace=True, columns=['Name'])
        dfData.rename(inplace=True, columns={'Code': 'value'})
        dfData['value'] = dfData['value'].astype(str)
        
        dfData = pd.concat([pd.Series({'value':None, 'text':'-----------'}).to_frame().T, dfData], ignore_index=True)

        cols = [i for i in dfData]
        data = [dict(zip(cols, i)) for i in dfData.values]  
        return JsonResponse(data, safe=False)
    else:
        return HttpResponse ('No allowed', status=405)

@login_required(login_url='/login')
def getInvGroups (request: HttpRequest):
    if request.method == 'GET':
        options = appModels.InvGroups
        dfData = pd.DataFrame(options, columns=['value','text'])

        cols = [i for i in dfData]
        data = [dict(zip(cols, i)) for i in dfData.values] 
        return JsonResponse(data, safe=False)
    else:
        return HttpResponse('Not allowed', status=405)

@login_required(login_url='/login')
def getUnits(request):
    if request.method == 'GET':
        objects = appModels.Unit.objects.all()
        dfData = pd.DataFrame(index=range(objects.count()))

        dfData['text'] = pd.DataFrame(objects.values('Name'))
        dfData['value'] = pd.DataFrame(objects.values('Name'))

        dfData = pd.concat([pd.Series({'value':None, 'text':'-----------'}).to_frame().T, dfData], ignore_index=True)

        cols = [i for i in dfData]
        data = [dict(zip(cols, i)) for i in dfData.values]  
        return JsonResponse(data, safe=False)

@login_required(login_url='/login')
def getConsTypes(request):
    if request.method == 'GET':
        options = appModels.ConsTypes
        dfData = pd.DataFrame(options)

        dfData.columns = ['value', 'text']

        cols = [i for i in dfData]
        data = [dict(zip(cols, i)) for i in dfData.values] 
        return JsonResponse(data, safe=False)

@login_required(login_url='/login')
def getProductionStages(request):
    if request.method == 'GET':
        options = appModels.Routes
        dfData = pd.DataFrame(options)

        dfData.columns = ['value', 'text']

        cols = [i for i in dfData]
        data = [dict(zip(cols, i)) for i in dfData.values] 
        return JsonResponse(data, safe=False)
    
@login_required(login_url='/login')
def getStyles(request):
    if request.method == 'GET':
        data = appModels.StyleCard.objects.all().values('StyleCode','Customer')
        dfData = pd.DataFrame(data)
        del data

        dfData['text'] = dfData['Customer']+' - '+dfData['StyleCode']
        dfData.rename(inplace=True, columns={'StyleCode':'value'})
        dfData.drop(inplace=True, columns=['Customer'])

        dfData = pd.concat([pd.Series({'value':None, 'text':'-----------'}).to_frame().T, dfData], ignore_index=True)

        cols = [i for i in dfData]
        data = [dict(zip(cols, i)) for i in dfData.values] 
        return JsonResponse(data, safe=False)

@login_required(login_url='/login')
def getOrderTypes(request):
    if request.method == 'GET':
        options = appModels.OrderTypes
        dfData = pd.DataFrame(options)

        dfData.columns = ['value', 'text']

        cols = [i for i in dfData]
        data = [dict(zip(cols, i)) for i in dfData.values]
        return JsonResponse(data, safe=False)
    
@login_required(login_url='/login')
def getCurrencies(request):
    if request.method == 'GET':
        objects = appModels.Currency.objects.all()
        dfData = pd.DataFrame(index=range(objects.count()))

        dfData['text'] = pd.DataFrame(objects.values('Name'))

        dfData['value'] = pd.DataFrame(objects.values('Code'))
        dfData['value'] = dfData['value'].astype(str)

        cols = [i for i in dfData]
        data = [dict(zip(cols, i)) for i in dfData.values] 
        return JsonResponse(data, safe=False)

@login_required(login_url='/login')
def getMerchandisers(request):
    if request.method == 'GET':
        objects = User.objects.all()
        dfData = pd.DataFrame(index=range(objects.count()))

        dfData = pd.DataFrame(objects.values('first_name','last_name','id'))

        dfData['text'] = dfData['first_name']+' '+dfData['last_name']
        dfData.rename(columns={'id':'value'}, inplace=True)
        dfData.drop(columns=['first_name','last_name'], inplace=True)
        dfData.sort_values(by='text',ascending=True, inplace=True)
        
        cols = [i for i in dfData]
        data = [dict(zip(cols, i)) for i in dfData.values] 
        return JsonResponse(data, safe=False)

@login_required(login_url='/login')
def getWorkOrders(request: HttpRequest):
    if request.method == 'GET':
        status = request.GET.get('status', None)
        
        objects = appModels.WorkOrder.objects.all()
        if objects.count() < 1:
            return JsonResponse([], safe=False)

        data = objects.values('OrderNumber','StyleCode','Customer')
        dfData = pd.DataFrame(data)

        dfData.rename(inplace=True, columns={'OrderNumber':'value'})
        dfData['text'] = dfData['value'].astype(str)+' - '+dfData['StyleCode']+' - '+dfData['Customer']
        dfData.drop(inplace=True, columns=['Customer','StyleCode'])

        dfData = pd.concat([pd.Series({'value':None, 'text':'-----------'}).to_frame().T, dfData], ignore_index=True)

        cols = [i for i in dfData]
        data = [dict(zip(cols, i)) for i in dfData.values] 
        return JsonResponse(data, safe=False)
    else:
        return HttpResponse ('No allowed', status=405)

@login_required(login_url='/login')
def getOpenPOs(request:HttpRequest):
    if request.method != 'GET':
        return HttpResponse ('No allowed', status=405)

    #Create a query that checks if a PO number exists in the recept table
    exists = Exists(appModels.InventoryReciept.objects.filter(PONumber=OuterRef('id')))
    
    #get the po's whose po number doesn't exist in reciept table
    data = appModels.PurchaseOrder.objects.annotate(received=exists).filter(received=False).values('id', 'Supplier')

    #Generate a dataframe, if there is data, otherwise return empty list
    if data.exists():
        dfData = pd.DataFrame(data)
    else:
        return JsonResponse([{'value': None, 'text': '-----------'}], safe=False)
    
    del data

    #make po number the value of the dropdown
    dfData.rename(inplace=True, columns={'id':'value'})
    
    #Display concatenation of po number and supplier in the dropdown to user
    dfData['text'] = dfData['value'].astype(str)+' - '+dfData['Supplier']
    dfData.drop(inplace=True, columns=['Supplier'])

    #Sort in ascending order w.r.t. po number
    dfData.sort_values(inplace=True, by='value', ascending=True)

    #Append empty row at the start.
    dfData = pd.concat([pd.Series({'value':None, 'text':'-----------'}).to_frame().T, dfData], ignore_index=True)

    cols = [i for i in dfData]
    data = [dict(zip(cols, i)) for i in dfData.values] 
    return JsonResponse(data, safe=False)

@login_required(login_url='/login')
def getUnitsForGroup(request: HttpRequest, group: str):
    if request.method == 'GET':
        objects = appModels.Unit.objects.filter(Group=group)

        dfData = pd.DataFrame(index=range(objects.count()))

        dfData = pd.DataFrame(objects.values('Name'))

        dfData['text'] = dfData['Name']
        dfData.rename(columns={'Name':'value'}, inplace=True)
        dfData.sort_values(by='text',ascending=True, inplace=True)
        
        cols = [i for i in dfData]
        data = [dict(zip(cols, i)) for i in dfData.values] 
        return JsonResponse(data, safe=False)
    else:
        return HttpResponse('Not allowed', status=405)

@login_required(login_url='/login')
def GetUsers(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=405)
    
    search = request.GET.get('search', '')

    if search:
        try:
            search = int(search)
            searchFilter = Q(id=search)
        except:
            searchFilter = Q(username__icontains=search)
            searchFilter = searchFilter | Q(first_name__icontains=search)
            searchFilter = searchFilter | Q(last_name__icontains=search)
            searchFilter = searchFilter | Q(email__icontains=search)

        users = User.objects.filter(searchFilter)
    else:
        users = User.objects.all()
    
    users = users[:15]

    fields = ['id', 'first_name', 'last_name']
    users = users.values(*fields)

    if users:
        dfUsers = pd.DataFrame(users)
    else:
        dfUsers = pd.DataFrame(columns=fields)
    del users, fields

    dfUsers['text'] = dfUsers['first_name'].astype(str)+' '+dfUsers['last_name'].astype(str)
    dfUsers.rename(inplace=True, columns={'id': 'value'})
    dfUsers.drop(inplace=True, columns=['first_name', 'last_name'])
    
    if dfUsers.empty:
        return JsonResponse([], safe=False)
    else:
        users = dfUsers.to_dict(orient='records')
        return JsonResponse(users, safe=False)

@login_required(login_url='/login')
def GetCountries(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=405)
    
    listOfCountries = []
    for code, name in list(countries):
        listOfCountries.append({'CountryCode': code, 'CountryName': name})
    
    dfCountries = pd.DataFrame(listOfCountries)
    del listOfCountries
    
    countriesCount = marketingModels.Customer.objects.values('Country').annotate(Count=Count('Country'))
    dfCountriesCount = pd.DataFrame(countriesCount)

    dfCountries = pd.merge(left=dfCountries, right=dfCountriesCount, left_on='CountryCode', right_on='Country', how='left')

    dfCountries = dfCountries.sort_values(by='Count', ascending=False)
    dfCountries.drop(inplace=True, columns=['Country', 'Count'])

    dfCountries.rename(inplace=True, columns={'CountryCode':'value', 'CountryName': 'text'})

    cols = [i for i in dfCountries]
    data = [dict(zip(cols, i)) for i in dfCountries.values]

    return JsonResponse(data, safe=False)

@login_required(login_url='/login')
def GetOperationSections(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=401)
    return JsonResponse(operationSections, safe=False)

@login_required(login_url='/login')
def GetOperationCategories (request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=401)
    
    return JsonResponse(operationCategories, safe=False)

@login_required(login_url='/login')
def GetMachineTypes(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=401)
    
    return JsonResponse(machineTypes, safe=False)

@login_required(login_url='/login')
def GetMachineManufacturers(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=401)
    
    return JsonResponse(machineManufacturers, safe=False)

@login_required(login_url='/login')
def GetOperations(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=401)
    
    search = request.GET.get('search', '')
    code = request.GET.get('code', None)

    search = None if search == 'null' else search
    code = None if code == 'null' else code
    
    if search:
        operations =prodModels.Operation.objects.filter(Q(Name__icontains=search) | Q(id__icontains=search))[:15]
    else:
        operations =prodModels.Operation.objects.all()
    
    
    if code:
        try:
            operations = operations.filter(id = code)
        except:
            return JsonResponse([], safe=False)

    operations = operations[:15]

    fields = ['id', 'Name']
    operations = operations.values(*fields)

    if operations:
        dfOperations = pd.DataFrame(operations)
    else:
        dfOperations = pd.DataFrame(columns=fields)
    del operations, fields

    dfOperations['Name'] = dfOperations['id'].astype(str)+ ' - '+dfOperations['Name'].astype(str)
    dfOperations.rename(inplace=True, columns={'id': 'value', 'Name':'text'})

    operations = dfToListOfDicts(dfOperations)
    return JsonResponse(operations, safe=False)

@login_required(login_url='/login')
def GetStylesWithoutBulletins (request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=405)

    search = request.GET.get('search', '')
    
    addedStyles =prodModels.StyleBulletin.objects.values_list('StyleCard', flat=True)

    pendingStyles = prodModels.StyleCard.objects.exclude(StyleCode__in=addedStyles)
    if search:
        pendingStyles = pendingStyles.filter(StyleCode__icontains=search)
    
    pendingStyles = pendingStyles[:15]

    fields = ['StyleCode']
    pendingStyles = pendingStyles.values(*fields)
    
    if pendingStyles:
        dfPendingStyles = pd.DataFrame(pendingStyles)
    else:
        dfPendingStyles = pd.DataFrame(columns=fields)
    del pendingStyles, fields
    
    dfPendingStyles['text'] = dfPendingStyles['StyleCode']
    dfPendingStyles.rename(inplace=True, columns={'StyleCode':'value'})
    
    pendingStyles = dfToListOfDicts(dfPendingStyles)
    return JsonResponse(pendingStyles, safe=False)

@login_required(login_url='/login')
def getOperationSection(request, pk):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=405)
    
    section = prodModels.Operation.objects.get(id=pk).Section
    return JsonResponse(section, safe=False)

@login_required(login_url='/login')
def GetOrdersWithMissingCS (request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=405)
    
    search = request.GET.get('search', '')

    addedOrders = prodModels.Cut.objects.values_list('WorkOrder', flat=True)

    pendingOrders = prodModels.WorkOrder.objects.exclude(OrderNumber__in=addedOrders)
    del addedOrders
    if search:
        searchFilter = Q(OrderNumber__icontains=search)
        searchFilter = searchFilter | Q(StyleCode__StyleCode__icontains=search)
        searchFilter = searchFilter | Q(Customer__Name__icontains=search)
        pendingOrders = pendingOrders.filter(searchFilter)
    del search
    
    pendingOrders = pendingOrders[:15]
    
    fields = ['OrderNumber', 'StyleCode', 'Customer']
    pendingOrders = pendingOrders.values(*fields)

    if pendingOrders:
        dfPendingOrders = pd.DataFrame(pendingOrders)
    else:
        dfPendingOrders = pd.DataFrame(columns=fields)
    del pendingOrders, fields

    dfPendingOrders['text'] = dfPendingOrders['OrderNumber'].astype(str) + ' - ' + dfPendingOrders['StyleCode'].astype(str) +' - '+ dfPendingOrders['Customer'].astype(str)
    dfPendingOrders.rename(inplace=True, columns={'OrderNumber': 'value'})
    dfPendingOrders.drop(inplace=True, columns=['StyleCode', 'Customer'])

    pendingOrders = dfToListOfDicts(dfPendingOrders)
    return JsonResponse(pendingOrders, safe=False)

@login_required(login_url='/login')
def GetCutsForOrder(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=405)
    
    orderNumber = request.GET.get('orderNumber')
    
    try:
        workOrder = prodModels.WorkOrder.objects.get(OrderNumber=orderNumber)
    except:
        return HttpResponse('Resource Not Found', status=403)
    del orderNumber
    
    fields = ['id','CutNumber','NoOfPlies']
    cuts = prodModels.Cut.objects.filter(WorkOrder=workOrder).values(*fields)[:15]
    del workOrder

    if cuts:
        dfCuts = pd.DataFrame(cuts)
    else:
        dfCuts = pd.DataFrame(columns=fields)
    del fields, cuts

    dfCuts.sort_values(by='CutNumber', inplace=True)
    dfCuts['text'] = dfCuts['CutNumber'].astype(str)+' - Qty:'+dfCuts['NoOfPlies'].astype(str)
    dfCuts.drop(inplace=True, columns=['CutNumber','NoOfPlies'])
    dfCuts.rename(inplace=True, columns={'id':'value'})

    emptyRow = {'value': None, 'text': '-------------'}
    dfCuts = pd.concat([pd.DataFrame([emptyRow]), dfCuts]).reset_index(drop=True)

    return JsonResponse(dfToListOfDicts(dfCuts), safe=False)

@login_required(login_url='/login')
def GetBundlesForCut(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=405)

    cutId = request.GET.get('cutId')
    try:
        cut = prodModels.Cut.objects.get(id=cutId)
    except:
        return HttpResponse('Resource Not Found', status=403)
    del cutId

    fields = ['id','Size','Bundle']
    bundles = prodModels.Bundle.objects.filter(Cut=cut).values(*fields)

    if bundles:
        dfBundles = pd.DataFrame(bundles)
    else:
        dfBundles = pd.DataFrame(columns=fields)
    del bundles, fields

    dfBundles.sort_values(by='Bundle', inplace=True)
    dfBundles['text'] = dfBundles['Bundle'].astype(str)+' - Size:'+dfBundles['Size'].astype(str)
    dfBundles.drop(inplace=True, columns=['Bundle','Size'])
    dfBundles.rename(inplace=True, columns={'id':'value'})

    emptyRow = {'value': None, 'text': '-------------'}
    dfBundles = pd.concat([pd.DataFrame([emptyRow]), dfBundles]).reset_index(drop=True)

    return JsonResponse(dfToListOfDicts(dfBundles), safe=False)

@login_required(login_url='/login')
def GetAvailableCardGroups(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=405)
    
    cards = prodModels.RFIDCard.objects.filter(GroupStatus='Complete').exclude(GroupNumber=None).values('GroupNumber').annotate(CardQty=Count('CardId')).order_by('GroupNumber')
    if cards:
        dfCards = pd.DataFrame(cards)
    else:
        dfCards = pd.DataFrame(columns=['GroupNumber','CardQty'])
    del cards
    
    dfCards.sort_values(by='GroupNumber', inplace=True)
    dfCards['text'] = 'Group: '+dfCards['GroupNumber'].astype(str)+' - Qty:'+dfCards['CardQty'].astype(str)
    dfCards.drop(inplace=True, columns=['CardQty'])
    dfCards.rename(inplace=True, columns={'GroupNumber':'value'})

    emptyRow = {'value': None, 'text': '-------------'}
    dfCards = pd.concat([pd.DataFrame([emptyRow]), dfCards]).reset_index(drop=True)

    return JsonResponse(dfToListOfDicts(dfCards), safe=False)

@login_required(login_url='/login')
def GetWorkers(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not Allowed', status=405)

    search = request.GET.get('search', '')
    code = request.GET.get('code', None)

    try:
        code = int(code)
    except:
        code = None

    filters = Q()

    if search:
        filters |= (Q(WorkerCode__icontains=search) | Q(WorkerName__icontains=search))
    
    if code:
        filters &= Q(WorkerCode=code)
    
    workers = prodModels.Worker.objects.filter(filters)[:15]

    fields = ['WorkerCode', 'WorkerName','Department','SubDepartment']
    workers = workers.values(*fields)
    if workers:
        dfWorkers = pd.DataFrame(workers)
    else:
        dfWorkers = pd.DataFrame(columns=fields)
    del workers

    dfSubDepartments = pd.DataFrame(operationSections)
    
    dfWorkers = pd.merge(left=dfWorkers, right=dfSubDepartments, left_on='SubDepartment', right_on='value', how='left')
    del dfSubDepartments
    dfWorkers.drop(inplace=True, columns=['SubDepartment','value'])
    dfWorkers.rename(inplace=True, columns={'text':'Section'})

    dfWorkers['text'] = dfWorkers['WorkerCode'].astype(str)+' - '+dfWorkers['WorkerName'].astype(str)
    dfWorkers['text'] = dfWorkers['text']+' - '+dfWorkers['Department']+' - '+dfWorkers['Section']
    dfWorkers.drop(inplace=True, columns=['WorkerName','Department','Section'])
    dfWorkers.rename(inplace=True, columns={'WorkerCode':'value'})

    emptyRow = {'value': None, 'text': '-------------'}
    dfWorkers = pd.concat([pd.DataFrame([emptyRow]), dfWorkers]).reset_index(drop=True)

    return JsonResponse(dfToListOfDicts(dfWorkers), safe=False)

class AppOptons(APIView):
    permission_classes = [AllowAny]

    def post (self, request:Request):
        token = request.data.get('token')
        deviceType = request.data.get('deviceType')

        if token:
            try:
                user = Token.objects.get(key=token).user
            except:
                response = {'message': 'Invalid Credentials'}
                status = rest_framework.status.HTTP_404_NOT_FOUND
                return Response (data=response, status=status)
            
            finalOptions = []
            for group in APP_OPTIONS:
                groupName = group['groupname']
                
                filteredGroupOptions = [
                    {'value': option['value'], 'name': option['name']} for option in group['options']
                    if hasPermission(user, groupName, option['modelName'], 'view') and \
                        option.get('deviceType') == deviceType
                ]
                
                if filteredGroupOptions:
                    finalOptions.append({
                        'groupname': groupName,
                        'options': filteredGroupOptions
                    })

            response = {'availableOptions': finalOptions}
            status = rest_framework.status.HTTP_200_OK
            return Response (data=response, status=status)
        else:
            response = {'message': 'Invalid Credentials'}
            status = rest_framework.status.HTTP_404_NOT_FOUND
            return Response (data=response, status=status)