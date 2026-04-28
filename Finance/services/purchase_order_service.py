from Finance import models
from core.services.generic_services import dfToListOfDicts, concatenateValues

# For the validating the date format
from datetime import datetime
import pandas as pd


def GetPurchaseOrders(startDate: str):
    # Step 1: Validate the date format before hitting the database
    try:
        datetime.strptime(startDate, '%Y-%m-%d')
    except ValueError:
        raise ValueError('Invalid date format. Use YYYY-MM-DD (e.g. 2026-01-15)')

    # Step 2: Fetch POs on or after the start date. Get the accompanying info needed along with the start date
    fields = ['id', 'OrderDate', 'Supplier']
    orders = models.PurchaseOrder.objects.filter(
        OrderDate__gte=startDate
    ).values(*fields)
    dfOrders = pd.DataFrame(list(orders)) if orders.exists() else pd.DataFrame(columns=fields)
    del orders

    if dfOrders.empty:
        return []

    # Step 3: Fetch inventory lines + name for those POs only
    fields = ['PONumber', 'Inventory__Code', 'Inventory__Name', 'Currency']
    inventories = models.POInventory.objects.filter(
        PONumber__in=dfOrders['id'].tolist()
    ).values(*fields)
    dfInventories = pd.DataFrame(list(inventories)) if inventories.exists() else pd.DataFrame(columns=fields)
    del inventories

    # Step 4: Rename id column before merging
    dfOrders.rename(columns={'id': 'PONumber'}, inplace=True)

    # Step 5: Merge DataFrames into one
    dfOrders = pd.merge(dfOrders, dfInventories, on='PONumber', how='left')
    del dfInventories

    # Step 6: Group by PONumber so each PO is one row, combining inventory lines
    dfOrders = dfOrders.groupby('PONumber').agg({
        'OrderDate': 'first',
        'Supplier': 'first',
        'Inventory__Name': concatenateValues,
        'Inventory__Code': concatenateValues,
        'Currency': 'first',
    }).reset_index()

    # Step 7: Rename columns to clean names for the frontend
    dfOrders.rename(columns={
        'Inventory__Name': 'ItemName',
        'Inventory__Code': 'ItemCode',
    }, inplace=True)

    # Step 8: Sort by PONumber descending and return as list of dicts
    dfOrders = dfOrders.sort_values(by='PONumber', ascending=False)
    return dfToListOfDicts(dfOrders)

# For the PO orders page
def GetPurchaseOrderDetail(po_id: int):
    # Step 1: Fetch the single PO by its id — including Tax for the totals
    fields = ['id', 'OrderDate', 'Supplier', 'Tax']
    orders = models.PurchaseOrder.objects.filter(id=po_id).values(*fields)
    dfOrder = pd.DataFrame(list(orders)) if orders.exists() else pd.DataFrame(columns=fields)

    if dfOrder.empty:
        return None

    # Step 2: Fetch PO inventory lines — ordered items with quantity, price and currency
    fields = ['id', 'Inventory', 'Inventory__Name', 'Variant', 'Quantity', 'Price', 'Currency']
    poInventories = models.POInventory.objects.filter(PONumber=po_id).values(*fields)
    dfPOInventories = pd.DataFrame(list(poInventories)) if poInventories.exists() else pd.DataFrame(columns=fields)

    # Step 3: Fetch work order allocations for those PO inventory lines
    fields = ['POInvId', 'WorkOrder', 'Quantity', 'WorkOrder__StyleCode__StyleName']
    allocations = models.POAllocation.objects.filter(
        POInvId__in=dfPOInventories['id'].tolist()
    ).values(*fields)
    dfAllocations = pd.DataFrame(list(allocations)) if allocations.exists() else pd.DataFrame(columns=fields)

    # Step 4: Rename id to POInvId
    dfPOInventories.rename(columns={'id': 'POInvId'}, inplace=True)
    price_lookup = {row['POInvId']: row['Price'] for _, row in dfPOInventories.iterrows()}

    # Step 5: Group allocations by POInvId — one list per item containing its work order splits
    alloc_by_inv = {}
    for _, row in dfAllocations.iterrows():
        po_inv_id  = row['POInvId']
        price      = price_lookup.get(po_inv_id, 0)
        alloc_amount = round(row['Quantity'] * price, 2)

        if po_inv_id not in alloc_by_inv:
            alloc_by_inv[po_inv_id] = []
        alloc_by_inv[po_inv_id].append({
            'WorkOrder': int(row['WorkOrder']),
            'Style':     row['WorkOrder__StyleCode__StyleName'] or '',
            'Quantity':  row['Quantity'],
            'Amount':    alloc_amount,
        })


    # Step 6: Build items list from POInventory rows with nested allocations
    items = []
    for _, row in dfPOInventories.iterrows():
        item_amount        = round(row['Quantity'] * row['Price'], 2)
        allocations        = alloc_by_inv.get(row['POInvId'], [])
        total_alloc_amount = round(sum(alloc['Amount'] for alloc in allocations), 2)

        items.append({
            'Inventory':        row['Inventory__Name'],
            'Variant':          row['Variant'] or '',
            'Quantity':         row['Quantity'],
            'Price':            row['Price'],
            'Amount':           item_amount,
            'AmountDifference': round(item_amount - total_alloc_amount, 2),
            'allocations':      allocations,
        })

    # Step 7: Calculate totals — NetAmount sums item Amounts
    net_amount  = round(sum(item['Amount'] for item in items), 2)
    tax_rate    = dfOrder['Tax'].iloc[0] or 0
    tax_amount  = round(net_amount * tax_rate / 100, 2)
    grand_total = round(net_amount + tax_amount, 2)

    # Step 8: Return a single dict for this PO
    return {
        'PONumber':   po_id,
        'OrderDate':  str(dfOrder['OrderDate'].iloc[0]),
        'Supplier':   dfOrder['Supplier'].iloc[0],
        'Currency':   dfPOInventories['Currency'].iloc[0] if not dfPOInventories.empty else '',
        'Tax':        tax_rate,
        'NetAmount':  net_amount,
        'TaxAmount':  tax_amount,
        'GrandTotal': grand_total,
        'items':      items,
    }
