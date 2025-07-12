from pytz import timezone
from datetime import datetime
from typing import Dict, List, Union
import os

#The navigation options to show to user for each app
NAV_LINKS_CONFIG: Dict[str, List[Dict[str, Union[str, List[Dict[str, str]]]]]]= {
    'apparelManagement': [
        {'groupName': 'Dashboard', 'appName': 'apparelManagement', 'modelName': 'Inventory', 'views': [], 'viewName': 'apparelManagement:apparel'},
        {'groupName': 'Inventory', 'appName': 'apparelManagement', 'modelName': 'Inventory', 'views': [
            {'displayName': 'View All', 'viewName': 'apparelManagement:Inv'},
            {'displayName': 'Add New', 'viewName': 'apparelManagement:addInv'},
        ]},
        {'groupName': 'StyleCard', 'appName': 'apparelManagement', 'modelName': 'StyleCard', 'views': [
            {'displayName': 'View All', 'viewName': 'apparelManagement:Style'},
            {'displayName': 'Add New', 'viewName': 'apparelManagement:addStyle'},
        ]},
        {'groupName': 'Work Order', 'appName': 'apparelManagement', 'modelName': 'WorkOrder', 'views': [
            {'displayName': 'View All', 'viewName': 'apparelManagement:WOs'},
            {'displayName': 'Add New', 'viewName': 'apparelManagement:addWO'},
            {'displayName': 'Auto Requirement', 'viewName': 'apparelManagement:autoReq'},
        ]},
        {'groupName': 'Purchase Demand', 'appName': 'apparelManagement', 'modelName': 'PurchaseDemand', 'views': [
            {'displayName': 'View All', 'viewName': 'apparelManagement:purchaseDemand'},
            {'displayName': 'Add New', 'viewName': 'apparelManagement:addPD'},
        ]},
        {'groupName': 'Inventory Order', 'appName': 'apparelManagement', 'modelName': 'PurchaseOrder', 'views': [
            {'displayName': 'View All', 'viewName': 'apparelManagement:POs'},
            {'displayName': 'Add New', 'viewName': 'apparelManagement:addPO'},
        ]},
        {'groupName': 'Inventory Receipt', 'appName': 'apparelManagement', 'modelName': 'PurchaseReceipt', 'views': [
            {'displayName': 'View All', 'viewName': 'apparelManagement:purchaseRec'},
            {'displayName': 'Add New', 'viewName': 'apparelManagement:addRec'},
        ]},
        {'groupName': 'Issuance', 'appName': 'apparelManagement', 'modelName': 'Requisition', 'views': [
            {'displayName': 'View Requests', 'viewName': 'apparelManagement:requisition'},
            {'displayName': 'Request For Order', 'viewName': 'apparelManagement:addRequisitionForOrder'},
            {'displayName': 'Request For Item', 'viewName': 'apparelManagement:addRequisitionForInv'},
            {'displayName': 'View Issuances', 'viewName': 'apparelManagement:issue'},
        ]},
    ],
    'marketing': [
        {'groupName': 'Dashboard', 'appName': 'marketing', 'modelName': 'Customer', 'views': [], 'viewName': 'marketing:marketing'},
        {'groupName': 'Customers', 'appName': 'marketing', 'modelName': 'Customer', 'views': [
            {'displayName': 'Database', 'viewName': 'marketing:customerData'},
            {'displayName': 'Master List', 'viewName': 'marketing:exportData'},
        ]},
        {'groupName': 'Correspondance', 'appName': 'marketing', 'modelName': 'Correspondance', 'views': [
            {'displayName': 'Pending', 'viewName': 'marketing:pendingCorresponance'},
            {'displayName': 'Calls', 'viewName': 'marketing:corresponanceHistory'},
            {'displayName': 'Emails', 'viewName': 'marketing:pendingCorresponance'},
            {'displayName': 'Meetings', 'viewName': 'marketing:pendingCorresponance'},
        ]},
        {'groupName': 'Inquiries', 'appName': 'marketing', 'modelName': 'Correspondance', 'views': [
            {'displayName': 'In Process', 'viewName': 'marketing:pendingCorresponance'},
        ]},
        {'groupName': 'Insights', 'appName': 'marketing', 'modelName': 'Correspondance', 'views': [
            {'displayName': 'In Process', 'viewName': 'marketing:pendingCorresponance'},
        ]},
    ],
    'PM': [
        {'groupName': 'Dashboard', 'appName': 'prodManagement', 'modelName': 'Operation', 'views': [], 'viewName': 'PM:productivity'},
        {'groupName': 'Presets', 'appName': 'prodManagement', 'modelName': 'Operation', 'views': [
            {'displayName': 'Style Bulletin', 'viewName': 'PM:styleBulletins'},
            {'displayName': 'Operations', 'viewName': 'PM:operations'},
            {'displayName': 'Machines', 'viewName': 'PM:machines'},
            {'displayName': 'Workers', 'viewName': 'PM:workers'},
        ]},
        {'groupName': 'Cutting', 'appName': 'prodManagement', 'modelName': 'Cut', 'views': [
            {'displayName': 'Core Sheet', 'viewName': 'PM:coreSheets'},
            {'displayName': 'Card Assignment', 'viewName': 'PM:assignBundleCards'},
        ]},
        {'groupName': 'Stitching', 'appName': 'prodManagement', 'modelName': 'Serial', 'views': [
            {'displayName': 'Scan Report', 'viewName': 'PM:serials'},
        ]},
    ],
    'QC': [
        {'groupName': 'Dashboard', 'appName': 'qualityControl', 'modelName': 'TrimAudit',  'views': [], 'viewName': 'QC:quality'},
        {'groupName': 'Fabric','appName': 'qualityControl', 'modelName': 'TrimAudit',   'views': [
            {'displayName': 'Under Process', 'viewName': 'QC:pendingTrimAudit'},
        ]},
        {'groupName': 'Trims','appName': 'qualityControl', 'modelName': 'TrimAudit',   'views': [
            {'displayName': 'Pending Audits', 'viewName': 'QC:pendingTrimAudit'},
            {'displayName': 'Audit History', 'viewName': 'QC:trimAudit'},
        ]},
        {'groupName': 'Production','appName': 'qualityControl', 'modelName': 'TrimAudit',   'views': [
            {'displayName': 'Under Process', 'viewName': 'QC:pendingTrimAudit'},
        ]},
    ],
}

APP_OPTIONS = [
    {'groupValue':'PM', 'groupName':'Production', 'options':[
        {'route':'/mark-group-complete/', 'name':'Mark Group Completion', 'modelName':'BundleCardAssignment', 'deviceType':'Tablet'},
        {'route':'/rfid-worker-assign/', 'name':'Assign Worker Card', 'modelName':'Worker', 'deviceType':'Tablet'},
        {'route':'/esp-op-w-assign/', 'name':'Box Management', 'modelName':'Operation', 'deviceType':'Tablet'},
    ]},
    {'groupValue':'QC', 'groupName':'Quality Control','options':[]},
]

LOCAL_TIMEZONE = timezone('Asia/Karachi')
GST_RATE = 18.0
LOCAL_CURRENCY = 'PKR'

NOW = datetime.now()
TODAY = datetime.today()

MIN_WAGE = 32000

API_KEY_FOR_AI = os.environ.get("API_KEY_FOR_AI")