import pandas as pd
import numpy as np

from django.contrib.auth.models import User
from django.db.models import Sum, Q
from django.http import JsonResponse
from django.forms import model_to_dict

from .. import models
from .generic_services import convertTexttoObject, updateModelWithDF

pd.options.mode.chained_assignment = None

#Get the List of Orders.
def GetOrderList(searchTerm, customer):
    if customer:
        orders = models.WorkOrder.objects.filter(Customer=customer).values()
    else:
        orders = models.WorkOrder.objects.all().values()
    
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

    searchTerm = searchTerm.lower()
    mask = OrderDF.apply(lambda row: any(searchTerm in str(val).lower() for val in row.values)
                        , axis=1)

    OrderDF = OrderDF[mask]

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
    print(dfVariants)

    for _, row in dfVariants.iterrows():
        try:  
            newEntry = models.OrderVariant(**row.to_dict())
            newEntry.save()
        except Exception as e:
            raise ValueError(f"Error Saving Variants: {e}")

    return orderNumber

def UpdateWorkOrder(
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
    
    dfVariants = dfVariants[dfVariants['Name'].str.len()>0]
    dfVariants = dfVariants[dfVariants['Quantity'].str.len()>0]

    #Raise error if no variants are provided
    if not dfVariants['Name'].str.len().sum():
        raise ValueError('No Variant is provided')

    dfOrder['Style'] = convertTexttoObject(models.StyleCard, dfOrder['Style'], 'StyleCode')
    dfOrder['Customer'] = convertTexttoObject(models.Customer, dfOrder['Customer'], 'Name')
    dfOrder['Currency'] = convertTexttoObject(models.Currency, dfOrder['Currency'], 'Code')

    dfOrder['DeliveryDate'] = pd.to_datetime(dfOrder["DeliveryDate"], format="%m/%d/%Y")
    dfOrder['OrderDate'] = pd.to_datetime(dfOrder["OrderDate"], format="%m/%d/%Y")
    
    #Below fields would be kept same as already existing
    dfOrder['Merchandiser'] = currentData.Merchandiser
    dfOrder['Agent'] = currentData.Agent
    dfOrder['Commission'] = currentData.Commission

    dfOrder.rename(inplace=True, columns={'Style':'StyleCode'})
    dfOrder.drop(inplace=True, columns=['Quantity'])

    orderCard = dfOrder.iloc[0].to_dict()
    
    try:
        orderCard = models.WorkOrder(**orderCard)
        #orderCard.save()
    except models.WorkOrder.DoesNotExist:
        raise ValueError(f"Order Number: {orderNumber}, doesn't exist.")
    except Exception as e:
        #Raise any other error, if found to be safe.
        raise LookupError(f"Error saving Order: {e}")
    
    fields = ['id','Name']
    previousVariants = models.OrderVariant.objects.filter(OrderNumber=orderCard).values(*fields)
    if previousVariants:
        dfPreviousVariants = pd.DataFrame(previousVariants)
    else:
        dfPreviousVariants = pd.DataFrame(columns=fields)
    del previousVariants, fields

    fields = ['id','InventoryCode','Variant']
    previousRequirement = models.InvRequirement.objects.filter(OrderNumber=orderCard).values(*fields)
    if previousRequirement:
        dfPreviousRequirement = pd.DataFrame(previousRequirement)
    else:
        dfPreviousRequirement = pd.DataFrame(columns=fields)
    del previousRequirement

    dfVariants['Quantity'] = dfVariants['Quantity'].astype(int)

    dfVariants = pd.merge(left=dfVariants, right=dfPreviousVariants, on='Name', how='left')

    dfVariants['OrderNumber'] = orderCard

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

        dfRequirement.drop(inplace=True, columns=['Ordered','Received','InventoryName',''])
        
        dfRequirement = pd.merge(left=dfRequirement, right=dfPreviousRequirement, on=['InventoryCode','Variant'], how='left')

        dfRequirement['InventoryCode'] = convertTexttoObject(models.Inventory, dfRequirement['InventoryCode'], 'Code')
        dfRequirement['OrderNumber'] = orderCard
        
        dfRequirement['id_x'] = np.where(dfRequirement['id_x'].str.len()==0, np.nan, dfRequirement['id_x'])

        dfRequirement['id'] = np.where(dfRequirement['id_x'].isna(), dfRequirement['id_y'], dfRequirement['id_x'])
        dfRequirement.drop(inplace=True, columns=['id_x','id_y'])
        
        try:
            updateModelWithDF(models.InvRequirement, dfRequirement, dfPreviousRequirement)
        except Exception as e:
            raise ValueError (e)
        del dfRequirement, dfPreviousRequirement

#To process the data of already added order
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
    
    dfReceivedQty = pd.merge(left=dfReceivedQty, right=dfReceivedInvs, left_on='RecInvId', right_on='id', how='left')
    del dfReceivedInvs
    dfReceivedQty.drop(inplace=True, columns=['id','RecInvId'])
    dfReceivedQty.rename(inplace=True, columns={'Quantity':'Received'})

    dfRequirement = pd.merge(left=dfRequirement, right=dfReceivedQty, left_on=['InventoryCode','Variant'],
                             right_on=['InventoryCode','Variant'], how='outer')
    del dfReceivedQty
    dfRequirement['Received'] = np.where(dfRequirement['Received'].isna(), 0, dfRequirement['Received'])
    
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

    #This is in response to a bug, where empty requirement didn't show any table.
    if dfRequirement.empty:
        dfRequirement.loc[0] = {'id':None, 'InventoryName': '', 'Variant': '','Quantity':0, 'Ordered':0, 'Received':0}
    

    cols = [i for i in dfRequirement]
    requirement = [dict(zip(cols, i)) for i in dfRequirement.values]
    
    return order, variants, requirement

#To calculate requirement from stylecard
def CalculateRequirement(styleCode: str, orderNumber: int):
    consumption = models.StyleConsumption.objects.filter(Style=styleCode).values('InventoryCode','FinalCons','HasVariant','SizeDetails')
    if consumption:
        dfConsumption = pd.DataFrame(consumption)
        dfConsumption.rename(columns={'FinalCons':'Consumption'}, inplace=True)
    else:
        dfConsumption = pd.DataFrame(columns=['InventoryCode','Consumption','HasVariant','SizeDetails'])
    del consumption

    variants = models.OrderVariant.objects.filter(OrderNumber=orderNumber).values('Name','Quantity')
    if variants:
        dfVariants = pd.DataFrame(variants)
    else:
        dfVariants = pd.DataFrame(columns=['Name','Quantity'])
    del variants
    dfVariants = dfVariants.loc[(dfVariants['Quantity'] > 0)]

    ordered = models.POAllocation.objects.filter(WorkOrder=orderNumber).values('POInvId','Quantity')
    if ordered:
        dfOrdered = pd.DataFrame(ordered)
    else:
        dfOrdered = pd.DataFrame(columns=['POInvId','Quantity'])
    del ordered

    orderedInv = models.POInventory.objects.filter(id__in=dfOrdered['POInvId'].to_list()).values('id','Inventory','Variant')
    if orderedInv:  
        dfOrderedInvs = pd.DataFrame(orderedInv)
    else:
        dfOrderedInvs = pd.DataFrame(columns=['id','Inventory','Variant'])
    del orderedInv

    received = models.RecAllocation.objects.filter(WorkOrder=orderNumber).values('RecInvId','Quantity')
    if received:
        dfReceived = pd.DataFrame(received)
    else:
        dfReceived = pd.DataFrame(columns=['RecInvId','Quantity'])
    del received

    receivedInv = models.RecInventory.objects.filter(id__in=dfReceived['RecInvId'].to_list())
    receivedInv = receivedInv.values('id','InventoryCode','Variant')
    if receivedInv:
        dfReceivedInvs = pd.DataFrame(receivedInv)
    else:
        dfReceivedInvs = pd.DataFrame(columns=['id','Inventory','Variant'])
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

    excessCut = models.WorkOrder.objects.get(OrderNumber=orderNumber).ExcessCut
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
    del dfOrdered, dfOrderedInvs

    if dfReceived.empty:
        dfRequirement['Received'] = 0.0  
    else:
        dfReceived = pd.merge(left=dfReceived, right=dfReceivedInvs, left_on='RecInvId', right_on='id', how='left')
        dfReceived.drop(inplace=True, columns=['id','RecInvId'])
        dfReceived.rename(inplace=True, columns={'Quantity':'Received'})

        dfRequirement = pd.merge(left=dfRequirement, right=dfReceived, left_on=['InventoryCode','Variant'],
                                 right_on=['InventoryCode','Variant'], how='outer')
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

    dfRequirement['id'] = None
    
    for col in ['Required','Ordered','Received']:
        dfRequirement[col] = np.where(dfRequirement[col].isna(), 0, dfRequirement[col])

    cols = [i for i in dfRequirement]
    requirement = [dict(zip(cols, i)) for i in dfRequirement.values]
    return requirement

def GetRequirementHistory (inventoryCode: str, variant: str, workOrder: int):
    poAllocation = models.POAllocation.objects.filter(WorkOrder=workOrder).values('POInvId','Quantity')
    if poAllocation:
        dfPOAllocation = pd.DataFrame(poAllocation)
    else:
        dfPOAllocation = pd.DataFrame(columns=['POInvId', 'Quantity'])
    del poAllocation

    poInventory = models.POInventory.objects.filter(id__in=dfPOAllocation['POInvId'].to_list())
    poInventory = poInventory.filter(Inventory=inventoryCode).filter(Variant=variant).values('id','PONumber','Quantity')
    if poInventory:
        dfPOInventory = pd.DataFrame(poInventory)
    else:
        dfPOInventory = pd.DataFrame(columns=['id','PONumber','Quantity'])
    del poInventory

    purchaseOrders = models.PurchaseOrder.objects.filter(id__in=dfPOInventory['PONumber'].to_list())
    purchaseOrders = purchaseOrders.values('id','OrderDate','Supplier')
    if purchaseOrders:
        dfPurchaseOrders = pd.DataFrame(purchaseOrders)
    else:
        dfPurchaseOrders = pd.DataFrame(columns=['id','OrderDate','Supplier'])
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
    dfResults['url'] = 'purchaseorder/'+dfResults['ReceiptNo'].astype(str)+'/edit'

    dfReceiptsInterM = pd.merge(left=dfRecInventory, right=dfRecAllocation, left_on='id', right_on='RecInvId', how='left')
    del dfRecAllocation, dfRecInventory
    dfReceiptsInterM.drop(inplace=True, columns=['id','RecInvId'])
    dfReceiptsInterM.rename(inplace=True, columns={'Quantity_x':'TotalQuantity','Quantity_y':'AllocatedQuantity'})

    dfReceiptsInterM = pd.merge(left=dfReceiptsInterM, right=dfPurchaseReceipts, left_on='ReceiptNumber', right_on='id', how='left')
    del dfPurchaseReceipts
    dfReceiptsInterM.drop(inplace=True, columns=['id'])
    dfReceiptsInterM.rename(inplace=True, columns={'ReceiptNumber':'ReceiptNo'})

    dfReceiptsInterM['Type'] = 'Receipt'
    dfReceiptsInterM['url'] = 'purchasereceipt/'+dfReceiptsInterM['ReceiptNo'].astype(str)+'/edit'

    dfResults = pd.concat([dfResults, dfReceiptsInterM])
    del dfReceiptsInterM

    #TODO: Also get the history of Issuances and Free Stock

    cols = [i for i in dfResults]
    data = [dict(zip(cols, i)) for i in dfResults.values]  
    return JsonResponse(data, safe=False)

def PrintWO (order: models.WorkOrder):
    '''
    Get the data to print the WO.
    '''

    variants = models.OrderVariant.objects.filter(OrderNumber=order).values('Name','Quantity')
    if variants:
        dfVariants = pd.DataFrame(variants)
    else:
        dfVariants = pd.DataFrame(columns=['Name','Quantity'])
    del variants

    allocation = models.POAllocation.objects.filter(WorkOrder=order).values('POInvId','Quantity')
    if allocation:
        dfPOAllocation = pd.DataFrame(allocation)
    else:
        dfPOAllocation = pd.DataFrame(columns=['POInvId', 'Quantity'])
    del allocation

    poInventory = models.POInventory.objects.filter(id__in=dfPOAllocation['POInvId'].to_list()).values('id','Inventory','Variant')
    if poInventory:
        dfPOInventory = pd.DataFrame(poInventory)
    else:
        dfPOInventory = pd.DataFrame(columns=['id','Inventory','Variant'])
    del poInventory

    requirement = models.InvRequirement.objects.filter(OrderNumber=order).values('InventoryCode','Variant','Quantity')
    if requirement:
        dfRequirement = pd.DataFrame(requirement)
    else:
        dfRequirement = pd.DataFrame(columns=['InventoryCode','Variant','Quantity'])
    del requirement

    consumption = models.StyleConsumption.objects.filter(Style=order.StyleCode).values('InventoryCode','FinalCons','HasVariant','SizeDetails','Type')
    if consumption:
        dfConsumption = pd.DataFrame(consumption)
    else:
        dfConsumption = pd.DataFrame(columns=['InventoryCode','FinalCons','HasVariant','SizeDetails','Type'])
    
    #TODO: Also get the inventory receipt, issuance and production status

    dfVariants = dfVariants[dfVariants['Quantity']>0]
    
    dfVariants.rename(inplace=True, columns={'Quantity':'POQuantity'})
    dfVariants['CutQuantity'] = dfVariants['POQuantity'] * (1+(order.ExcessCut/100))
    dfVariants['CutQuantity'] = np.ceil(dfVariants['CutQuantity']).astype(int)

    dfVariants[['Variant1', 'Variant2']] = dfVariants['Name'].str.split('-', n=1, expand=True)
    dfVariants.drop(inplace=True, columns=['Name'])

    dfVariants = dfVariants.groupby(by='Variant1')

    dfRequirement = pd.merge(left=dfConsumption, right=dfRequirement, on='InventoryCode', how='outer')
    dfRequirement.rename(inplace=True, columns={'FinalCons':'Consumption','Quantity':'Required'})
    del dfConsumption

    dfRequirement = pd.merge(left=dfRequirement, right=dfPOInventory, left_on=['InventoryCode','Variant'],
                             right_on=['Inventory','Variant'], how='left')
    del dfPOInventory
    dfRequirement.drop(inplace=True, columns=['Inventory'])

    dfRequirement = pd.merge(left=dfRequirement, right=dfPOAllocation, left_on='id', right_on='POInvId', how='left')
    del dfPOAllocation
    dfRequirement.drop(inplace=True, columns=['id','POInvId'])
    dfRequirement.rename(inplace=True, columns={'Quantity':'Ordered'})

    cutting = {}
    for name, group in dfVariants:
        cutting[name] = group.to_dict(orient='records')
    requirement = dfRequirement.to_dict(orient='records')

    return order, cutting, requirement, None