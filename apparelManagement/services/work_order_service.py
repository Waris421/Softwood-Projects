import pandas as pd
import numpy as np

from django.contrib.auth.models import User
from django.db.models import Sum, Q
from django.forms import model_to_dict

from .. import models
from core.services.generic_services import convertTexttoObject, updateModelWithDF, convertStrToDateTime, dfToListOfDicts, roundFloatCols
from core.constants.theme import theme

def applyColors(dfRequirement: pd.DataFrame):
    if 'Quantity' in dfRequirement.columns:
        dfRequirement.rename(inplace=True, columns={'Quantity':'Required'})
    
    dfRequirement['Color'] = theme['redText']

    dfRequirement['Color'] = np.where(dfRequirement['Required']<=dfRequirement['Ordered'], theme['blueText'], dfRequirement['Color'])

    dfRequirement['Color'] = np.where(dfRequirement['Required']<=dfRequirement['Received'], theme['grayText'], dfRequirement['Color'])

    dfRequirement['Color'] = dfRequirement['Color']+' text-center'

    return dfRequirement['Color']

def getWorkOrders(startDate, endDate):
    fields = ['OrderNumber','StyleCode','Customer','DeliveryDate','ExcessCut']
    workOrders = models.WorkOrder.objects.filter(DeliveryDate__gte=startDate, DeliveryDate__lte=endDate).values(*fields)
    dfWorkOrders = pd.DataFrame(workOrders) if workOrders else pd.DataFrame(columns=fields)
    del workOrders

    fields = ['OrderNumber','POQuantity']
    variants = models.OrderVariant.objects.filter(OrderNumber__in=dfWorkOrders['OrderNumber'].to_list()).values(
        'OrderNumber'
    ).annotate(POQuantity=Sum('Quantity')).order_by('OrderNumber')
    dfVariants = pd.DataFrame(variants) if variants else pd.DataFrame(columns=fields)
    del variants

    dfWorkOrders = pd.merge(left=dfWorkOrders, right=dfVariants, left_on='OrderNumber', right_on='OrderNumber', how='left')
    del dfVariants
    
    return dfWorkOrders

#Get the List of Orders.
def GetOrderList(customer: str, startDateStr: str, endDateStr: str):
    filters = Q()
    if customer:
        filters &= Q(Customer=customer)
    
    if startDateStr:
        startDate = convertStrToDateTime(startDateStr, '%Y-%m-%d').date()
        filters &= Q(DeliveryDate__gte= startDate)
    
    if endDateStr:
        endDate = convertStrToDateTime(endDateStr, '%Y-%m-%d').date()
        filters &= Q(DeliveryDate__lte= endDate)
    
    orders = models.WorkOrder.objects.filter(filters).values()
    del filters
    
    OrderDF = pd.DataFrame(orders)    
    if OrderDF.empty:
        return pd.DataFrame()

    userObjs = User.objects.all().values('id','first_name')
    UserDF = pd.DataFrame(userObjs)
    del userObjs

    OrderDF = pd.merge(left=OrderDF, right=UserDF, left_on='Merchandiser_id', right_on='id', how='left')

    OrderDF.drop(columns = ['Merchandiser_id','id'], inplace=True)
    OrderDF.rename(columns={'first_name':'Merchandiser'}, inplace=True)

    orders = orders.values('OrderNumber')
    ordersFilter = Q(OrderNumber__in=[order['OrderNumber'] for order in orders])
    variants = models.OrderVariant.objects.filter(ordersFilter).values('OrderNumber','Quantity')
    VariantsDF = pd.DataFrame(variants)

    def calculateQty (Orders, Variants):
        if not Variants.empty:
            merged = pd.merge(Orders, Variants, on='OrderNumber')
            merged = pd.pivot_table(data=merged, values='Quantity', index='OrderNumber', aggfunc='sum', fill_value=0).reset_index()
            return merged
        else:
            return pd.DataFrame(columns=['OrderNumber'])

    OrderQty = calculateQty(pd.DataFrame(OrderDF['OrderNumber']), VariantsDF)
    OrderDF = pd.merge(left=OrderDF, right=OrderQty, left_on='OrderNumber', right_on='OrderNumber', how='left')
    del orders, ordersFilter, variants, VariantsDF, OrderQty

    if not OrderDF.empty:
        OrderDF = OrderDF.sort_values (by='OrderNumber')
        OrderDF = OrderDF.sort_values (by='Customer_id')
    
    cols = [i for i in OrderDF]
    OrderDF = [dict(zip(cols, i)) for i in OrderDF.values]
    return OrderDF

#Function to save new Order
def AddWorkOrder(
        dfOrder: pd.DataFrame,
        dfVariants: pd.DataFrame,
        user: User) -> int:
    
    #Get the order number
    orderNumber = dfOrder['OrderNumber'][0]
    #Return error is order number is blank
    if orderNumber == '':
        raise ValueError ('No Order Number is provided')
    
    dfVariants = dfVariants[dfVariants['VariantCode'].str.len()>0]
    dfVariants = dfVariants[dfVariants['Quantity'].str.len()>0]

    #Raise error if no variants are provided
    if not dfVariants['VariantCode'].str.len().sum():
        raise ValueError('No Variant is provided')
    
    dfOrder['Style'] = convertTexttoObject(models.StyleCard, dfOrder['Style'], 'StyleCode')
    dfOrder['Customer'] = convertTexttoObject(models.Customer, dfOrder['Customer'], 'Name')
    dfOrder['Currency'] = convertTexttoObject(models.Currency, dfOrder['Currency'], 'Code')
    dfOrder['DeliveryDate'] = pd.to_datetime(dfOrder["DeliveryDate"], format="%Y-%m-%d")
    
    UserObjs = User.objects.get(username=user)
    dfOrder['Merchandiser'] = UserObjs
    
    dfOrder['DeliveryDate'] = pd.to_datetime(dfOrder["DeliveryDate"], format="%m/%d/%Y")

    dfOrder.rename(inplace=True, columns={'Style':'StyleCode'})
    orderCard = dfOrder.iloc[0].to_dict()

    try:
        #Try to fetch order and if found, raise error
        models.WorkOrder.objects.get(OrderNumber=orderNumber)
        raise ValueError(f"Order Number: {orderCard['OrderNumber']}, already exists.")
    except models.WorkOrder.DoesNotExist:
        orderCard = models.WorkOrder(**orderCard)
        orderCard.save()
    except Exception as e:
        #Raise any other error, if found to be safe.
        raise LookupError(f"Error saving Order: {e}") 
    
    dfVariants = dfVariants[dfVariants['Quantity'].str.len() > 0]
    dfVariants['Quantity'] = dfVariants['Quantity'].astype(int)

    dfVariants['OrderNumber'] = orderCard

    dfVariants.rename(inplace=True, columns={'VariantCode':'Name'})
   
    for _, row in dfVariants.iterrows():
        try:  
            newEntry = models.OrderVariant(**row.to_dict())
            newEntry.save()
        except Exception as e:
            raise ValueError(f"Error Saving Variants: {e}")
        
    return orderNumber

def UpdateWorkOrder(
        workOrder: models.WorkOrder,
        dfOrder: pd.DataFrame,
        dfVariants: pd.DataFrame,
        dfRequirement: pd.DataFrame,
        ) -> None:
    #Get the order number
    orderNumber = dfOrder['OrderNumber'][0]
    #Raise error is order number is blank
    if orderNumber == '':
        raise ValueError ('No Order Number is provided')
    
    try:
        #Try to fetch order and proceed only if it is found
        currentData = models.WorkOrder.objects.get(OrderNumber=orderNumber)
    except:
        raise LookupError('Work Order not found.')
    
    dfVariants = dfVariants[dfVariants['VariantCode'].str.len()>0]
    dfVariants = dfVariants[dfVariants['Quantity'].str.len()>0]

    #Raise error if no variants are provided
    if not dfVariants['VariantCode'].str.len().sum():
        raise ValueError('No Variant is provided')

    dfOrder['Style'] = convertTexttoObject(models.StyleCard, dfOrder['Style'], 'StyleCode')
    dfOrder['Customer'] = convertTexttoObject(models.Customer, dfOrder['Customer'], 'Name')
    dfOrder['Currency'] = convertTexttoObject(models.Currency, dfOrder['Currency'], 'Code')
    dfOrder['DeliveryDate'] = pd.to_datetime(dfOrder["DeliveryDate"], format="%Y-%m-%d")
    
    #Below fields would be kept same as already existing
    dfOrder['Merchandiser'] = currentData.Merchandiser
    dfOrder['Agent'] = currentData.Agent
    dfOrder['Commission'] = currentData.Commission

    dfOrder.rename(inplace=True, columns={'Style':'StyleCode'})
    dfOrder.drop(inplace=True, columns=['Quantity'])

    orderCard = dfOrder.iloc[0].to_dict()
    del dfOrder
    
    for key, value in orderCard.items():
        setattr(workOrder, key, value)
    
    workOrder.save()
    
    fields = ['id','Name']
    previousVariants = models.OrderVariant.objects.filter(OrderNumber=workOrder).values(*fields)
    if previousVariants:
        dfPreviousVariants = pd.DataFrame(previousVariants)
    else:
        dfPreviousVariants = pd.DataFrame(columns=fields)
    del previousVariants, fields

    fields = ['id','InventoryCode','Variant']
    previousRequirement = models.InvRequirement.objects.filter(OrderNumber=workOrder).values(*fields)
    
    if previousRequirement:
        dfPreviousRequirement = pd.DataFrame(previousRequirement)
    else:
        dfPreviousRequirement = pd.DataFrame(columns=fields)
    del previousRequirement

    dfVariants['Quantity'] = dfVariants['Quantity'].astype(int)
    dfVariants.rename(inplace=True, columns={'VariantCode':'Name'})

    dfVariants = pd.merge(left=dfVariants, right=dfPreviousVariants, on='Name', how='left')

    dfVariants['OrderNumber'] = workOrder

    try:
        updateModelWithDF(models.OrderVariant, dfVariants, dfPreviousVariants)
    except Exception as e:
        raise ValueError (e)
    del dfVariants, dfPreviousVariants
    
    dfRequirement = dfRequirement[dfRequirement['InventoryCode'].str.len() > 0]
    if not dfRequirement.empty:
        dfRequirement = dfRequirement[dfRequirement['Quantity'].str.len() > 0]
        dfRequirement['Quantity'] = dfRequirement['Quantity'].astype(float)
        dfRequirement = dfRequirement[dfRequirement['Quantity']>0]

        dfRequirement.drop(inplace=True, columns=['Ordered','InventoryName'])

        dfRequirement['InventoryCode'] = convertTexttoObject(models.Inventory, dfRequirement['InventoryCode'], 'Code')
        dfRequirement['OrderNumber'] = workOrder

        dfRequirement['id'] = np.where(dfRequirement['id'].str.len()==0, None, dfRequirement['id'])
        
        try:
            updateModelWithDF(models.InvRequirement, dfRequirement, dfPreviousRequirement)
        except Exception as e:
            raise ValueError (e)
        del dfRequirement, dfPreviousRequirement

def ProcessOrderData(workOrder: models.WorkOrder):
    order = model_to_dict(workOrder)

    variants = models.OrderVariant.objects.filter(OrderNumber=workOrder).values('Name','Description','Quantity')
    if not variants:
        variants = [model_to_dict(models.OrderVariant())]
        order['Quantity'] = 0
    else:
        order['Quantity'] = variants.aggregate(Sum('Quantity'))['Quantity__sum']
    order['OrderDate'] = workOrder.OrderDate

    fields = ['id', 'InventoryCode','Variant','Quantity']
    requirement = models.InvRequirement.objects.filter(OrderNumber=workOrder).values(*fields)
    if requirement:
        dfRequirement = pd.DataFrame(requirement)
    else:
        dfRequirement = pd.DataFrame(columns=fields)
    del requirement
    
    fields = ['POInvId','Quantity']
    orderedQty = models.POAllocation.objects.filter(WorkOrder=workOrder).values(*fields)
    if orderedQty:
        dfOrderedQty = pd.DataFrame(orderedQty)
    else:
        dfOrderedQty = pd.DataFrame(columns=fields)
    del orderedQty

    fields = ['id','Inventory','Variant']
    orderedInvs = models.POInventory.objects.filter(id__in=dfOrderedQty['POInvId'].to_list()).values(*fields)
    if orderedInvs:
        dfOrderedInvs = pd.DataFrame(orderedInvs)
    else:
        dfOrderedInvs = pd.DataFrame(columns=fields)
    del orderedInvs

    receivedQty = models.RecAllocation.objects.filter(WorkOrder=workOrder).values('RecInvId','Quantity')
    if receivedQty:
        dfReceivedQty = pd.DataFrame(receivedQty)
    else:
        dfReceivedQty = pd.DataFrame(columns=['RecInvId','Quantity'])
    del receivedQty
    
    fields = ['id','InventoryCode','Variant']
    receivedInvs = models.RecInventory.objects.filter(id__in=dfReceivedQty['RecInvId'].to_list()).values(*fields)
    if receivedInvs:
        dfReceivedInvs = pd.DataFrame(receivedInvs)
    else:
        dfReceivedInvs = pd.DataFrame(columns=fields)
    del receivedInvs, fields

    dfOrderedQty = pd.merge(left=dfOrderedQty, right=dfOrderedInvs, left_on='POInvId', right_on='id', how='left')
    del dfOrderedInvs
    dfOrderedQty.drop(inplace=True, columns=['id','POInvId'])
    dfOrderedQty.rename(inplace=True, columns={'Quantity':'Ordered'})

    dfRequirement = pd.merge(left=dfRequirement, right=dfOrderedQty, left_on=['InventoryCode','Variant'],
                             right_on=['Inventory','Variant'], how='outer')
    del dfOrderedQty
    dfRequirement.drop(inplace=True, columns=['Inventory'])
    dfRequirement['Ordered'] = np.where(dfRequirement['Ordered'].isna(), 0, dfRequirement['Ordered'])
    
    dfRequirement = dfRequirement.groupby(['id', 'InventoryCode', 'Variant']).agg(
        Quantity=('Quantity', 'mean'),
        Ordered=('Ordered', 'sum'),
    ).reset_index()
    
    dfReceivedQty = pd.merge(left=dfReceivedQty, right=dfReceivedInvs, left_on='RecInvId', right_on='id', how='left')
    del dfReceivedInvs
    dfReceivedQty.drop(inplace=True, columns=['id','RecInvId'])
    dfReceivedQty.rename(inplace=True, columns={'Quantity':'Received'})

    dfRequirement = pd.merge(left=dfRequirement, right=dfReceivedQty, left_on=['InventoryCode','Variant'],
                             right_on=['InventoryCode','Variant'], how='outer')
    del dfReceivedQty
    dfRequirement['Received'] = np.where(dfRequirement['Received'].isna(), 0, dfRequirement['Received'])

    dfRequirement = dfRequirement.groupby(['id', 'InventoryCode', 'Variant']).agg(
        Quantity=('Quantity', 'mean'),
        Ordered=('Ordered', 'mean'),
        Received=('Received', 'sum'),
    ).reset_index()
    
    #Convert Inventory names to inventory code and names
    fields = ['Code','Name']
    inventories = models.Inventory.objects.filter(Code__in=dfRequirement['InventoryCode'].to_list()).values(*fields)
    if inventories:
        dfInventories = pd.DataFrame(inventories)
    else:
        dfInventories = pd.DataFrame(columns=fields)
    del inventories, fields
    
    dfRequirement = pd.merge(left=dfRequirement, right=dfInventories, left_on='InventoryCode', right_on='Code', how='left')
    del dfInventories
    dfRequirement.drop(inplace=True, columns=['Code'])
    dfRequirement.rename(inplace=True, columns={'Name':'InventoryName'})

    dfRequirement['Color'] = applyColors(dfRequirement[['Quantity','Ordered','Received']])
    
    if dfRequirement.empty:
        blankRow = pd.DataFrame([[''] * len(dfRequirement.columns)], columns=dfRequirement.columns)
        dfRequirement = pd.concat([dfRequirement, blankRow], ignore_index=True)
        del blankRow
    
    dfRequirement.sort_values(inplace=True, by='InventoryName')
    return order, variants, dfToListOfDicts(dfRequirement)

#To calculate requirement from stylecard
def CalculateRequirement(styleCard: models.StyleCard, workOrder: models.WorkOrder):
    fields = ['id','InventoryCode','Variant']
    currentRequirement = models.InvRequirement.objects.filter(OrderNumber=workOrder).values(*fields)
    dfCurrentRequirement = pd.DataFrame(currentRequirement) if currentRequirement else pd.DataFrame(columns=fields)
    del currentRequirement

    fields = ['InventoryCode','FinalCons','HasVariant','SizeDetails']
    consumption = models.StyleConsumption.objects.filter(Style=styleCard).values(*fields)
    dfConsumption = pd.DataFrame(consumption) if consumption else pd.DataFrame(columns=fields)
    dfConsumption.rename(columns={'FinalCons':'Consumption'}, inplace=True)
    del consumption

    fields = ['Name','Quantity']
    variants = models.OrderVariant.objects.filter(OrderNumber=workOrder).values(*fields)
    dfVariants = pd.DataFrame(variants) if variants else pd.DataFrame(columns=fields)
    del variants
    dfVariants = dfVariants.loc[(dfVariants['Quantity'] > 0)]

    fields = ['POInvId','Quantity']
    ordered = models.POAllocation.objects.filter(WorkOrder=workOrder).values(*fields)
    dfOrdered = pd.DataFrame(ordered) if ordered else pd.DataFrame(columns=fields)
    del ordered

    fields = ['id','Inventory','Variant']
    orderedInv = models.POInventory.objects.filter(id__in=dfOrdered['POInvId'].to_list()).values(*fields)
    dfOrderedInvs = pd.DataFrame(orderedInv) if orderedInv else pd.DataFrame(columns=fields)
    del orderedInv

    fields = ['RecInvId','Quantity']
    received = models.RecAllocation.objects.filter(WorkOrder=workOrder).values(*fields)
    dfReceived = pd.DataFrame(received) if received else pd.DataFrame(columns=fields)
    del received

    fields = ['id','InventoryCode','Variant']
    receivedInv = models.RecInventory.objects.filter(id__in=dfReceived['RecInvId'].to_list()).values(*fields)
    dfReceivedInvs = pd.DataFrame(receivedInv) if receivedInv else pd.DataFrame(columns=fields)
    del receivedInv

    dfSimpleConsumption = dfConsumption[(dfConsumption['HasVariant'] == False) & (dfConsumption['SizeDetails'] == '')][['InventoryCode', 'Consumption']]
    dfVariantConsumption = dfConsumption[(dfConsumption['HasVariant'] == True) & (dfConsumption['SizeDetails'] == '')][['InventoryCode', 'Consumption']]
    dfSizeOnlyConsumption = dfConsumption[(dfConsumption['HasVariant'] == False) & (dfConsumption['SizeDetails'] != '')][['InventoryCode', 'Consumption', 'SizeDetails']]
    dfSizeAndVariantConsumption = dfConsumption[(dfConsumption['HasVariant'] == True) & (dfConsumption['SizeDetails'] != '')][['InventoryCode', 'Consumption', 'SizeDetails']]
    del dfConsumption

    if not dfSimpleConsumption.empty:
        quantity = dfVariants['Quantity'].sum()
        dfSimpleRequirement = pd.DataFrame(dfSimpleConsumption['InventoryCode'])
        dfSimpleRequirement['Required'] = dfSimpleConsumption['Consumption']*quantity
        dfSimpleRequirement['Variant'] = ''
        del dfSimpleConsumption, quantity
        dfRequirement = dfSimpleRequirement
        del dfSimpleRequirement
    else:
        dfRequirement = pd.DataFrame(columns=['InventoryCode','Required','Variant'])
    
    if not dfVariantConsumption.empty:
        dfVariantRequirement = pd.merge(left=dfVariantConsumption, right=dfVariants, how='cross')
        dfVariantRequirement['Required'] = dfVariantRequirement['Consumption'] * dfVariantRequirement['Quantity']
        dfVariantRequirement.rename(columns={'Name':'Variant'}, inplace=True)
        dfVariantRequirement.drop(columns=['Consumption','Quantity'], inplace=True)
        del dfVariantConsumption
        
        dfRequirement = pd.concat([dfRequirement, dfVariantRequirement])
        del dfVariantRequirement 

    if not dfSizeOnlyConsumption.empty:
        dfModifiedVariants = pd.DataFrame(dfVariants)
        dfModifiedVariants['VariantName'] = dfModifiedVariants['Name'].str.split('-')
        dfModifiedVariants = dfModifiedVariants.explode('VariantName')
        dfModifiedVariants.drop(columns=['Name'], inplace=True)
        dfModifiedVariants = dfModifiedVariants.pivot_table(index='VariantName', values='Quantity', aggfunc='sum').reset_index()
        dfModifiedVariants['VariantName'] = dfModifiedVariants['VariantName'].astype(str)

        dfSizeOnlyConsumption['SizeDetails'] = dfSizeOnlyConsumption['SizeDetails'].str.split(',')
        dfSizeOnlyConsumption = dfSizeOnlyConsumption.explode('SizeDetails')
        dfSizeOnlyConsumption['SizeDetails'] = dfSizeOnlyConsumption['SizeDetails'].str.strip()

        dfSizeOnlyRequirement=pd.merge(left=dfSizeOnlyConsumption, right=dfModifiedVariants, left_on='SizeDetails', right_on='VariantName', how='left') 
        del dfSizeOnlyConsumption, dfModifiedVariants

        dfSizeOnlyRequirement['Required'] = dfSizeOnlyRequirement['Consumption'] * dfSizeOnlyRequirement['Quantity']
        
        dfSizeOnlyRequirement.drop(columns=['SizeDetails','Consumption','Quantity','VariantName'], inplace=True)
        dfSizeOnlyRequirement = dfSizeOnlyRequirement.pivot_table(index='InventoryCode', values='Required', aggfunc='sum').reset_index()
        dfSizeOnlyRequirement['Variant'] = ''

        dfRequirement = pd.concat([dfRequirement, dfSizeOnlyRequirement])
    
    if not dfSizeAndVariantConsumption.empty:
        dfSizeAndVariantConsumption['SizeDetails'] = dfSizeAndVariantConsumption['SizeDetails'].str.split(',')
        dfSizeAndVariantConsumption = dfSizeAndVariantConsumption.explode('SizeDetails')
        dfSizeAndVariantConsumption['SizeDetails'] = dfSizeAndVariantConsumption['SizeDetails'].str.strip()

        dfSizeAndVariantRequirement=pd.merge(left=dfSizeAndVariantConsumption, right=dfVariants, how='cross')
        del dfSizeAndVariantConsumption, dfVariants

        def partialMatch(value1, value2):
            return value1.lower() in value2.lower()
        dfSizeAndVariantRequirement = dfSizeAndVariantRequirement[dfSizeAndVariantRequirement.apply(lambda row: partialMatch(row['SizeDetails'], row['Name']), axis=1)]
        
        dfSizeAndVariantRequirement['Required'] = dfSizeAndVariantRequirement['Consumption'] * dfSizeAndVariantRequirement['Quantity']
        
        dfSizeAndVariantRequirement.rename(columns={'Name':'Variant'}, inplace=True)
        dfSizeAndVariantRequirement.drop(columns=['SizeDetails','Consumption','Quantity'], inplace=True)

        dfRequirement = pd.concat([dfRequirement, dfSizeAndVariantRequirement])

    excessCut = workOrder.ExcessCut
    dfRequirement['Required'] = dfRequirement['Required'] * (1+(excessCut/100)) * 1.02
    dfRequirement['Required'] = dfRequirement['Required'].apply(lambda x: round(x, 2))

    if dfOrdered.empty:
        dfRequirement['Ordered'] = 0.0
    else:
        dfOrdered = pd.merge(left=dfOrdered, right=dfOrderedInvs, left_on='POInvId', right_on='id', how='left')
        dfOrdered.drop(inplace=True, columns=['id','POInvId'])
        dfOrdered.rename(inplace=True, columns={'Quantity':'Ordered'})

        dfRequirement = pd.merge(left=dfRequirement, right=dfOrdered, left_on=['InventoryCode','Variant'],
                                right_on=['Inventory','Variant'], how='outer')
        dfRequirement.drop(inplace=True, columns=['Inventory'])
        
        dfRequirement = dfRequirement.groupby(['InventoryCode', 'Variant']).agg(
            Required=('Required', 'mean'),
            Ordered=('Ordered', 'sum'),
        ).reset_index()
    del dfOrdered, dfOrderedInvs

    if dfReceived.empty:
        dfRequirement['Received'] = 0.0  
    else:
        dfReceived = pd.merge(left=dfReceived, right=dfReceivedInvs, left_on='RecInvId', right_on='id', how='left')
        dfReceived.drop(inplace=True, columns=['id','RecInvId'])
        dfReceived.rename(inplace=True, columns={'Quantity':'Received'})

        dfRequirement = pd.merge(left=dfRequirement, right=dfReceived, left_on=['InventoryCode','Variant'],
                                 right_on=['InventoryCode','Variant'], how='outer')
        
        dfRequirement = dfRequirement.groupby(['InventoryCode', 'Variant']).agg(
            Required=('Required', 'mean'),
            Ordered=('Ordered', 'mean'),
            Received=('Received', 'sum'),
        ).reset_index()
    
    del dfReceived, dfReceivedInvs

    fields = ['Code','Name']
    inventories = models.Inventory.objects.filter(Code__in=dfRequirement['InventoryCode'].to_list()).values(*fields)
    if inventories:
        dfInventories = pd.DataFrame(inventories)
    else:
        dfInventories = pd.DataFrame(columns=fields)
    del inventories, fields
    
    dfRequirement = pd.merge(left=dfRequirement, right=dfInventories, left_on='InventoryCode', right_on='Code', how='left')
    del dfInventories
    dfRequirement.drop(inplace=True, columns=['Code'])
    dfRequirement.rename(inplace=True, columns={'Name':'InventoryName'})
    
    for col in ['Required','Ordered','Received']:
        dfRequirement[col] = np.where(dfRequirement[col].isna(), 0, dfRequirement[col])
    
    dfRequirement = pd.merge(left=dfRequirement, right=dfCurrentRequirement, left_on=['InventoryCode','Variant'], right_on=['InventoryCode','Variant'], how='left')
    del dfCurrentRequirement
    dfRequirement['id'] = np.where(dfRequirement['id'].isna(), None, dfRequirement['id'])

    dfRequirement['Color'] = applyColors(dfRequirement[['Required','Ordered','Received']])
    
    dfRequirement.sort_values(inplace=True, by='InventoryName')

    return dfToListOfDicts(dfRequirement)

def GetRequirementHistory (invRequirement: models.InvRequirement, workOrder: models.WorkOrder):
    inventoryCode = invRequirement.InventoryCode
    variant = invRequirement.Variant

    fields = ['POInvId','Quantity']
    poAllocation = models.POAllocation.objects.filter(WorkOrder=workOrder).values(*fields)
    if poAllocation:
        dfPOAllocation = pd.DataFrame(poAllocation)
    else:
        dfPOAllocation = pd.DataFrame(columns=fields)
    del poAllocation

    fields = ['id','PONumber','Quantity']
    poInventory = models.POInventory.objects.filter(id__in=dfPOAllocation['POInvId'].to_list())
    poInventory = poInventory.filter(Inventory=inventoryCode).filter(Variant=variant).values(*fields)
    if poInventory:
        dfPOInventory = pd.DataFrame(poInventory)
    else:
        dfPOInventory = pd.DataFrame(columns=fields)
    del poInventory

    fields = ['id','OrderDate','Supplier']
    purchaseOrders = models.PurchaseOrder.objects.filter(id__in=dfPOInventory['PONumber'].to_list()).values(*fields)
    if purchaseOrders:
        dfPurchaseOrders = pd.DataFrame(purchaseOrders)
    else:
        dfPurchaseOrders = pd.DataFrame(columns=fields)
    del purchaseOrders

    recAllocation = models.RecAllocation.objects.filter(WorkOrder=workOrder).values('RecInvId','Quantity')
    if recAllocation:
        dfRecAllocation = pd.DataFrame(recAllocation)
    else:
        dfRecAllocation = pd.DataFrame(columns=['RecInvId','Quantity'])
    del recAllocation

    recInventory = models.RecInventory.objects.filter(id__in=dfRecAllocation['RecInvId'].to_list())
    recInventory = recInventory.filter(InventoryCode=inventoryCode).filter(Variant=variant).values('id','ReceiptNumber','Quantity')
    if recInventory:
        dfRecInventory = pd.DataFrame(recInventory)
    else:
        dfRecInventory = pd.DataFrame(columns=['id','ReceiptNumber','Quantity'])
    del recInventory

    purchaseReceipts = models.InventoryReciept.objects.filter(id__in=dfRecInventory['ReceiptNumber'].to_list())
    purchaseReceipts = purchaseReceipts.values('id','ReceiptDate','Supplier')
    if purchaseReceipts:
        dfPurchaseReceipts = pd.DataFrame(purchaseReceipts)
    else:
        dfPurchaseReceipts = pd.DataFrame(columns=['id','ReceiptDate','Supplier'])
    del purchaseReceipts

    dfResults = pd.merge(left=dfPOInventory, right=dfPOAllocation, left_on='id', right_on='POInvId', how='left')
    del dfPOAllocation, dfPOInventory
    dfResults.drop(inplace=True, columns=['id','POInvId'])
    dfResults.rename(inplace=True, columns={'Quantity_x':'TotalQuantity', 'Quantity_y':'AllocatedQuantity'})

    dfResults = pd.merge(left=dfResults, right=dfPurchaseOrders, left_on='PONumber', right_on='id', how='left')
    del dfPurchaseOrders
    dfResults.drop(inplace=True, columns=['id'])
    dfResults.rename(inplace=True, columns={'PONumber':'ReceiptNo', 'OrderDate':'ReceiptDate'})
    
    dfResults['Type'] = 'Order'
    dfResults['url'] = '/purchaseorder/'+dfResults['ReceiptNo'].astype(str)+'/edit'

    dfReceiptsInterM = pd.merge(left=dfRecInventory, right=dfRecAllocation, left_on='id', right_on='RecInvId', how='left')
    del dfRecAllocation, dfRecInventory
    dfReceiptsInterM.drop(inplace=True, columns=['id','RecInvId'])
    dfReceiptsInterM.rename(inplace=True, columns={'Quantity_x':'TotalQuantity','Quantity_y':'AllocatedQuantity'})

    dfReceiptsInterM = pd.merge(left=dfReceiptsInterM, right=dfPurchaseReceipts, left_on='ReceiptNumber', right_on='id', how='left')
    del dfPurchaseReceipts
    dfReceiptsInterM.drop(inplace=True, columns=['id'])
    dfReceiptsInterM.rename(inplace=True, columns={'ReceiptNumber':'ReceiptNo'})

    dfReceiptsInterM['Type'] = 'Receipt'
    dfReceiptsInterM['url'] = '/purchasereceipt/'+dfReceiptsInterM['ReceiptNo'].astype(str)+'/edit'

    dfResults = pd.concat([dfResults, dfReceiptsInterM])
    del dfReceiptsInterM

    #TODO: Also get the history of Issuances and Free Stock

    return dfToListOfDicts(dfResults)

def GetInitialPlanning(
        typeFilter: str,
        customerFilter: str|None,
        startDateStr: str|None,
        endDateStr: str|None,
):
    filters = Q()
    if typeFilter == 'unplanned':
        filters &= Q(workorderinitialplan__isnull=True)
    if customerFilter:
        filters &= Q(Customer=customerFilter)
    if startDateStr:
        startDate = convertStrToDateTime(startDateStr, '%Y-%m-%d').date()
        filters &= Q(DeliveryDate__gte=startDate)
    if endDateStr:
        endDate = convertStrToDateTime(endDateStr, '%Y-%m-%d').date()
        filters &= Q(DeliveryDate__lte=endDate)
    
    fields = ['OrderNumber','StyleCode','Customer','DeliveryDate']
    workOrders = models.WorkOrder.objects.filter(filters).values(*fields)
    dfWorkOrders = pd.DataFrame(workOrders) if workOrders else pd.DataFrame(columns=fields)
    del workOrders

    fields = ['OrderNumber','Quantity']
    variants = models.OrderVariant.objects.filter(OrderNumber__in=dfWorkOrders['OrderNumber'].to_list()).values(*fields)
    dfVariants = pd.DataFrame(variants) if variants else pd.DataFrame(columns=fields)
    del variants

    fields = ['id','WorkOrder','FabricETA','BWTrimETA','AWTrimETA', 'PullBack']
    addedPlans = models.WorkOrderInitialPlan.objects.filter(WorkOrder__in=dfWorkOrders['OrderNumber'].to_list()).values(*fields)
    dfAddedPlans = pd.DataFrame(addedPlans) if addedPlans else pd.DataFrame(columns=fields)
    del addedPlans

    dfVariants = dfVariants.groupby('OrderNumber')['Quantity'].sum().reset_index()
    
    dfWorkOrders = pd.merge(left=dfWorkOrders, right=dfVariants, on='OrderNumber', how='left')
    del dfVariants
    dfWorkOrders.rename(inplace=True, columns={'OrderNumber':'WorkOrder'})
    
    dfWorkOrders = pd.merge(left=dfWorkOrders, right=dfAddedPlans, on='WorkOrder', how='left')

    return dfToListOfDicts(dfWorkOrders)

def UpdateInitialPlanning(dfInitialPlan: pd.DataFrame):
    #Remove unwanted columns
    dfInitialPlan.drop(inplace=True, columns=['StyleCode','Customer','DeliveryDate','Quantity'])
    
    #Remvoe rows with empty dates
    condition = dfInitialPlan['FabricETA'].str.len()>0
    condition |= dfInitialPlan['BWTrim'].str.len()>0
    condition |= dfInitialPlan['AWTrim'].str.len()>0
    dfInitialPlan = dfInitialPlan[condition]

    #Raise erros if any of the required fields are empty
    if (dfInitialPlan[['FabricETA','BWTrim','AWTrim']]=='').any().any():
        raise ValueError('Required Data is missing')
    
    fields = ['id']
    idsToSearch = dfInitialPlan[dfInitialPlan['id'].str.len()>0]['id'].to_list()
    previousPlans = models.WorkOrderInitialPlan.objects.filter(id__in=idsToSearch)
    dfPreviousPlans = pd.DataFrame(previousPlans.values(*fields)) if previousPlans else pd.DataFrame(columns=fields)
    del previousPlans, fields

    cols = ['FabricETA', 'BWTrim', 'AWTrim']
    for col in cols:
        dfInitialPlan[col] = pd.to_datetime(dfInitialPlan[col], errors='coerce')

    dfInitialPlan.rename(inplace=True, columns={'OrderNumber':'WorkOrder', 'BWTrim': 'BWTrimETA', 'AWTrim': 'AWTrimETA'})

    dfInitialPlan['WorkOrder'] = convertTexttoObject(models.WorkOrder, dfInitialPlan['WorkOrder'], 'OrderNumber')
    
    dfInitialPlan['PullBack'] = pd.to_numeric(dfInitialPlan['PullBack'], errors='coerce').fillna(0).astype(int)
    
    try:
        updateModelWithDF(models.WorkOrderInitialPlan, dfInitialPlan, dfPreviousPlans)
    except Exception as e:
        raise ValueError(e)

def PrintWO (order: models.WorkOrder):
    '''
    Get the data to print the WO.
    '''

    fields = ['Name','Quantity']
    variants = models.OrderVariant.objects.filter(OrderNumber=order).values(*fields)
    dfVariants = pd.DataFrame(variants) if variants else pd.DataFrame(columns=fields)
    del variants

    fields = ['POInvId','Quantity']
    allocation = models.POAllocation.objects.filter(WorkOrder=order).values(*fields)
    dfPOAllocation = pd.DataFrame(allocation) if allocation else pd.DataFrame(columns=fields)

    fields = ['RecInvId','Quantity']
    allocation = models.RecAllocation.objects.filter(WorkOrder=order).values(*fields)
    dfRecAllocation = pd.DataFrame(allocation) if allocation else pd.DataFrame(columns=fields)

    fields = ['IssueInventory','Quantity']
    allocation = models.IssueAllocation.objects.filter(WorkOrder=order).values(*fields)
    dfIssueAllocation = pd.DataFrame(allocation) if allocation else pd.DataFrame(columns=fields)
    del allocation

    fields = ['id','Inventory','Variant']
    poInventory = models.POInventory.objects.filter(id__in=dfPOAllocation['POInvId'].to_list()).values(*fields)
    dfPOInventory = pd.DataFrame(poInventory) if poInventory else pd.DataFrame(columns=fields)
    del poInventory

    fields = ['id','InventoryCode', 'Variant']
    recInventory = models.RecInventory.objects.filter(id__in=dfRecAllocation['RecInvId'].to_list()).values(*fields)
    dfRecInventory = pd.DataFrame(recInventory) if recInventory else pd.DataFrame(columns=fields)
    del recInventory
    
    fields = ['id', 'Inventory','Variant']
    issueInventory = models.IssueInventory.objects.filter(id__in=dfIssueAllocation['IssueInventory'].to_list()).values(*fields)
    dfIssueInventory = pd.DataFrame(issueInventory) if issueInventory else pd.DataFrame(columns=fields)
    del issueInventory

    fields = ['InventoryCode','Variant','Quantity']
    requirement = models.InvRequirement.objects.filter(OrderNumber=order).values(*fields)
    dfRequirement = pd.DataFrame(requirement) if requirement else pd.DataFrame(columns=fields)
    del requirement

    fields = ['Code','Name']
    reqInventories = models.Inventory.objects.filter(Code__in=dfRequirement['InventoryCode'].to_list()).values(*fields)
    dfReqinventories = pd.DataFrame(reqInventories) if reqInventories else pd.DataFrame(columns=fields)
    del reqInventories

    fields = ['InventoryCode','FinalCons','HasVariant','SizeDetails','Type']
    consumption = models.StyleConsumption.objects.filter(Style=order.StyleCode).values(*fields)
    dfConsumption = pd.DataFrame(consumption) if consumption else pd.DataFrame(columns=fields)
    del consumption, fields

    dfVariants = dfVariants[dfVariants['Quantity']>0]
    
    dfVariants.rename(inplace=True, columns={'Quantity':'POQuantity'})
    cuttingSummary = {}
    cuttingSummary['poQty'] = dfVariants['POQuantity'].sum()

    dfVariants['CutQuantity'] = dfVariants['POQuantity'] * (1+(order.ExcessCut/100))
    dfVariants['CutQuantity'] = np.ceil(dfVariants['CutQuantity']).astype(int)
    cuttingSummary['willCutQty'] = dfVariants['CutQuantity'].sum()
    #TODO: Get the actual cut qty form core sheet.
    cuttingSummary['actualCut'] = '-'
    dfVariants['ActualCut'] = '-'

    dfVariants[['Variant1', 'Variant2']] = dfVariants['Name'].str.split('-', n=1, expand=True)
    dfVariants.drop(inplace=True, columns=['Name'])

    dfVariants = dfVariants.groupby(by='Variant1')

    dfConsumption = dfConsumption.groupby('InventoryCode').agg(
        FinalCons = ('FinalCons', 'sum'),
        HasVariant = ('HasVariant','first'),
        SizeDetails = ('SizeDetails','first'),
        Type = ('Type','first'),
    )
    
    dfRecInventory = pd.merge(left=dfRecInventory, right=dfRecAllocation, left_on='id', right_on='RecInvId', how='left')
    del dfRecAllocation
    dfRecInventory.drop(inplace=True, columns=['id','RecInvId'])    
    #sum up qties for one inv and variant.
    dfRecInventory = dfRecInventory.groupby(by=['InventoryCode','Variant']).sum().reset_index()

    dfIssueInventory = pd.merge(left=dfIssueInventory, right=dfIssueAllocation, left_on='id', right_on='IssueInventory', how='left')
    del dfIssueAllocation
    dfIssueInventory.drop(inplace=True, columns=['id', 'IssueInventory'])
    #sum up qties for one inv and variant.
    dfIssueInventory = dfIssueInventory.groupby(by=['Inventory','Variant']).sum().reset_index()

    dfRequirement = pd.merge(left=dfConsumption, right=dfRequirement, on='InventoryCode', how='outer')
    dfRequirement.rename(inplace=True, columns={'FinalCons':'Consumption','Quantity':'Required'})
    del dfConsumption

    usageMap = {
        'BW': 'Before Wash',
        'AW': 'After Wash',
        'Fab': 'Fabric'
    }
    dfRequirement['Type'] = dfRequirement['Type'].map(usageMap)

    dfRequirement = pd.merge(left=dfRequirement, right=dfPOInventory, left_on=['InventoryCode','Variant'],
                             right_on=['Inventory','Variant'], how='left')
    del dfPOInventory
    dfRequirement.drop(inplace=True, columns=['Inventory'])

    dfRequirement = pd.merge(left=dfRequirement, right=dfPOAllocation, left_on='id', right_on='POInvId', how='left')
    del dfPOAllocation
    dfRequirement.drop(inplace=True, columns=['id','POInvId'])
    dfRequirement.rename(inplace=True, columns={'Quantity':'Ordered'})
    dfRequirement['Ordered'] = dfRequirement['Ordered'].fillna(0).infer_objects(copy=False)
    
    dfRequirement = dfRequirement.groupby(['InventoryCode', 'Variant']).agg(
        Required=('Required', 'first'),
        Ordered=('Ordered', 'sum'),
        Type=('Type', 'first'),
        Consumption=('Consumption', 'first'),
        SizeDetails = ('SizeDetails', 'first'),
    ).reset_index()

    dfRequirement = pd.merge(left=dfRequirement, right = dfRecInventory, on=['InventoryCode','Variant'], how='left')
    del dfRecInventory
    dfRequirement.rename(inplace=True, columns={'Quantity':'Received'})
    dfRequirement['Received'] = dfRequirement['Received'].fillna(0).infer_objects(copy=False)
    
    dfRequirement = pd.merge(left=dfRequirement, right=dfIssueInventory, left_on=['InventoryCode', 'Variant'],
                             right_on=['Inventory', 'Variant'], how='left')
    del dfIssueInventory
    dfRequirement.drop(inplace=True, columns=['Inventory'])
    dfRequirement.rename(inplace=True, columns={'Quantity':'Issued'})
    dfRequirement['Issued'] = dfRequirement['Issued'].fillna(0).infer_objects(copy=False)

    dfRequirement = pd.merge(left=dfRequirement, right=dfReqinventories, left_on='InventoryCode', right_on='Code', how='left')
    del dfReqinventories
    dfRequirement.drop(inplace=True, columns=['Code','InventoryCode'])

    customOrder = ['Fabric', 'Before Wash', 'After Wash']
    dfRequirement['Type'] = pd.Categorical(dfRequirement['Type'], categories=customOrder, ordered=True)
    dfRequirement = dfRequirement.sort_values(by=['Type', 'Name'])

    dfRequirement = roundFloatCols(dfRequirement)

    cutting = {}
    for name, group in dfVariants:
        cutting[name] = group.to_dict(orient='records')

    return order, cutting, cuttingSummary, dfToListOfDicts(dfRequirement), None