from datetime import datetime
import pandas as pd

from Finance import models
from core.services.generic_services import dfToListOfDicts, concatenateValues

def GetPurchaseOrders(startDate: str):
    try:
        datetime.strptime(startDate, '%Y-%m-%d')
    except ValueError:
        raise ValueError('Invalid date format. Use YYYY-MM-DD (e.g. 2026-01-15)')

    fields = ['id', 'OrderDate', 'Supplier']
    orders = models.PurchaseOrder.objects.filter(OrderDate__gte=startDate).values(*fields)
    dfOrders = pd.DataFrame(orders) if orders else pd.DataFrame(columns=fields)
    del orders

    if dfOrders.empty:
        return []

    fields = ['PONumber', 'Inventory__Code', 'Inventory__Name', 'Currency']
    inventories = models.POInventory.objects.filter(PONumber__in=dfOrders['id'].tolist()).values(*fields)
    dfInventories = pd.DataFrame(inventories) if inventories else pd.DataFrame(columns=fields)
    del inventories

    dfOrders.rename(columns={'id': 'PONumber'}, inplace=True)

    dfOrders = pd.merge(dfOrders, dfInventories, on='PONumber', how='left')
    del dfInventories

    dfOrders = dfOrders.groupby('PONumber').agg({
        'OrderDate': 'first',
        'Supplier': 'first',
        'Inventory__Name': concatenateValues,
        'Inventory__Code': concatenateValues,
        'Currency': 'first',
    }).reset_index()

    dfOrders.rename(columns={
        'Inventory__Name': 'InventoryName',
        'Inventory__Code': 'InventoryCode',
    }, inplace=True)

    dfOrders = dfOrders.sort_values(by='PONumber', ascending=False)
    return dfToListOfDicts(dfOrders)

def GetPurchaseOrderDetail(poNumber: int):
    fields = ['id', 'OrderDate', 'Supplier', 'Tax']
    orders = models.PurchaseOrder.objects.filter(id=poNumber).values(*fields)
    dfOrder = pd.DataFrame(orders) if orders else pd.DataFrame(columns=fields)
    del orders

    fields = ['id', 'Inventory', 'Inventory__Name', 'Variant', 'Quantity', 'Price', 'Currency']
    poInventories = models.POInventory.objects.filter(PONumber=poNumber).values(*fields)
    dfPOInventories = pd.DataFrame(poInventories) if poInventories else pd.DataFrame(columns=fields)
    del poInventories

    fields = ['POInvId', 'WorkOrder', 'Quantity', 'WorkOrder__StyleCode__StyleName']
    allocations = models.POAllocation.objects.filter(POInvId__in=dfPOInventories['id'].tolist()).values(*fields)
    dfAllocations = pd.DataFrame(allocations) if allocations else pd.DataFrame(columns=fields)
    del allocations, fields

    if dfOrder.empty:
        return None

    dfPOInventories.rename(columns={'id': 'POInvId'}, inplace=True)
    priceLookup = {row['POInvId']: row['Price'] for _, row in dfPOInventories.iterrows()}

    allocByInv = {}
    for _, row in dfAllocations.iterrows():
        poInvId  = row['POInvId']
        price      = priceLookup.get(poInvId, 0)
        allocAmount = round(row['Quantity'] * price, 2)

        if poInvId not in allocByInv:
            allocByInv[poInvId] = []
        allocByInv[poInvId].append({
            'WorkOrder': int(row['WorkOrder']),
            'Style':     row['WorkOrder__StyleCode__StyleName'] or '',
            'Quantity':  row['Quantity'],
            'Amount':    allocAmount,
        })

    items = []
    for _, row in dfPOInventories.iterrows():
        itemAmount        = round(row['Quantity'] * row['Price'], 2)
        allocations        = allocByInv.get(row['POInvId'], [])
        totalAllocAmount = round(sum(alloc['Amount'] for alloc in allocations), 2)

        items.append({
            'Inventory':        row['Inventory__Name'],
            'Variant':          row['Variant'] or '',
            'Quantity':         row['Quantity'],
            'Price':            row['Price'],
            'Amount':           itemAmount,
            'AmountDifference': round(itemAmount - totalAllocAmount, 2),
            'allocations':      allocations,
        })

    netAmount  = round(sum(item['Amount'] for item in items), 2)
    taxRate    = dfOrder['Tax'].iloc[0] or 0
    taxAmount  = round(netAmount * taxRate / 100, 2)
    grandTotal = round(netAmount + taxAmount, 2)

    return {
        'PONumber':   poNumber,
        'OrderDate':  str(dfOrder['OrderDate'].iloc[0]),
        'Supplier':   dfOrder['Supplier'].iloc[0],
        'Currency':   dfPOInventories['Currency'].iloc[0] if not dfPOInventories.empty else '',
        'Tax':        taxRate,
        'NetAmount':  netAmount,
        'TaxAmount':  taxAmount,
        'GrandTotal': grandTotal,
        'items':      items,
    }