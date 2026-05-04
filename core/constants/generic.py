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
            {'displayName': 'Reports', 'viewName': 'apparelManagement:inventoryReportsHome'},
        ]},
        {'groupName': 'StyleCard', 'appName': 'apparelManagement', 'modelName': 'StyleCard', 'views': [
            {'displayName': 'View All', 'viewName': 'apparelManagement:Style'},
            {'displayName': 'Add New', 'viewName': 'apparelManagement:addStyle'},
            {'displayName': 'Cons Requests', 'viewName': 'apparelManagement:threadConsRequests'},
        ]},
        {'groupName': 'Work Order', 'appName': 'apparelManagement', 'modelName': 'WorkOrder', 'views': [
            {'displayName': 'View All', 'viewName': 'apparelManagement:WOs'},
            {'displayName': 'Add New', 'viewName': 'apparelManagement:addWO'},
            {'displayName': 'Auto Requirement', 'viewName': 'apparelManagement:autoReq'},
            {'displayName': 'Initial Plan', 'viewName': 'apparelManagement:initialPlan'},
        ]},
        {'groupName': 'Purchase Demand', 'appName': 'apparelManagement', 'modelName': 'PurchaseDemand', 'views': [
            {'displayName': 'View All', 'viewName': 'apparelManagement:purchaseDemand'},
            {'displayName': 'Add New', 'viewName': 'apparelManagement:addPD'},
        ]},
        {'groupName': 'Inventory Order', 'appName': 'apparelManagement', 'modelName': 'PurchaseOrder', 'views': [
            {'displayName': 'View All', 'viewName': 'apparelManagement:POs'},
            {'displayName': 'Add New', 'viewName': 'apparelManagement:addPO'},
        ]},
        {'groupName': 'Inventory Receipt', 'appName': 'apparelManagement', 'modelName': 'InventoryReciept', 'views': [
            {'displayName': 'View All', 'viewName': 'apparelManagement:purchaseRec'},
            {'displayName': 'Add New', 'viewName': 'apparelManagement:addRec'},
        ]},
        {'groupName': 'Issuance', 'appName': 'apparelManagement', 'modelName': 'Requisition', 'views': [
            {'displayName': 'View Requests', 'viewName': 'apparelManagement:requisition'},
            {'displayName': 'Issue For Order', 'viewName': 'apparelManagement:addIssueForOrder'},
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
        ]},
        {'groupName': 'Cutting', 'appName': 'prodManagement', 'modelName': 'Cut', 'views': [
            {'displayName': 'Core Sheet', 'viewName': 'PM:coreSheets'},
        ]},
        {'groupName': 'Stitching', 'appName': 'prodManagement', 'modelName': 'Serial', 'views': [
            {'displayName': 'Scan Report', 'viewName': 'PM:serials'},
        ]},
        {'groupName': 'Outsource', 'appName': 'prodManagement', 'modelName': 'OutSourceJobContract', 'views': [
            {'displayName': 'Contract List', 'viewName': 'PM:outSourceContracts'},
            {'displayName': 'Add Contract', 'viewName': 'PM:addoutsourceContracts'},
            {'displayName': 'Print Contracts', 'viewName': 'PM:outSourceContracts', 'searchParams':'approval=approved'},
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
    'planning': [
        {'groupName':'Dashboard', 'appName':'planning', 'modelName':'Capacity', 'views':[], 'viewName':'planning:planning'},
        {'groupName':'Presets', 'appName':'planning', 'modelName':'Capacity', 'views':[
            {'displayName':'Production Planning', 'viewName':'planning:setSource'},
            {'displayName':'Capacity', 'viewName':'planning:capacity'},
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

BROWSER_OPTIONS: Dict[str, List[Dict[str, Union[str, List[Dict[str, str]]]]]] = {
    'productivity': [
        {'label': 'Dashboard', 'href':'/productivity', 'appName': 'prodManagement', 'modelName': 'Operation'},
        {'label': 'Consumption', 'appName': 'prodManagement', 'modelName': 'Operation', 'children': [
            {'label': 'Pending Consumptions', 'href':'/consumption/request/thread/pending', 'subtext': 'Review and finalize thread consumptions'},
            {'label': 'View All', 'href':'/consumption/request/thread', 'subtext': 'Complete history of thread consumptions'},
        ]},
        {'label': 'Presets', 'appName': 'prodManagement', 'modelName': 'Operation', 'children': [
            {'label':'Style Bulletin', 'href':'/productivity/buletins', 'subtext': 'Manage style bulletins'},
            {'label':'Operation', 'href':'/productivity/operations', 'subtext': 'Define and categorize production operations'},
            {'label':'Machines', 'href':'/productivity/machines', 'subtext': 'Define and categorize production machines'},
            {'label':'Workers', 'href':'/productivity/workers', 'subtext': 'Manage operator profiles and skill matrices'},
        ]},
        {'label': 'Cutting', 'appName': 'prodManagement', 'modelName': 'Cut', 'children': [
            {'label': 'Core Sheet', 'href': '/productivity/core-sheets', 'subtext': 'Track core sheets'},
        ]},
        {'label': 'Stitching', 'appName': 'prodManagement', 'modelName': 'Serial', 'children': [
            {'label': 'Scan Report', 'href': '/productivity/serials', 'subtext': 'Monitor production scanning data'},
        ]},
        {'label': 'Outsource', 'appName': 'prodManagement', 'modelName': 'OutSourceJobContract', 'children': [
            {'label': 'Contract List', 'href': '/productivity/outsource-contracts', 'subtext': 'Manage out-source contracts'},
        ]},
    ],
    'finance': [
        {'label': 'Dashboard', 'href': '/finance', 'appName': 'apparelManagement', 'modelName':'Inventory'},
        {'label': 'Inventory', 'appName': 'apparelManagement', 'modelName': 'Inventory', 'children': [
            {'label': 'Raw Material Stock', 'href': '/finance/inventory/stock-report' , 'subtext': 'Current balance of fabrics, trims, and accessories (limited to 2yrs)'},
            {'label': 'Free Inventory', 'href': '/finance/inventory/free-stock', 'subtext': 'Unallocated materials available for new orders'},
            {'label': 'View PO', 'href': '/finance/purchase-order', 'subtext': 'View all Purchase Orders'},
        ]},
    ],
    'hr': [
        {'label': 'Dashboard', 'href': '/hr', 'appName': 'apparelManagement', 'modelName': 'Inventory'},
        {'label': 'Employees', 'appName': 'HumanResource', 'modelName': 'Employee', 'children': [
            {'label': 'View All', 'href': '/hr/worker', 'subtext': 'Manage Employees'},
            {'label': 'Performance', 'href': '/hr/performance', 'subtext': 'Follow up on employee performance'},
            {'label': 'Training', 'href': '/hr/training', 'subtext': 'Follow up on employee training'},
        ]},
        {'label': 'Attendance', 'appName': 'HumanResource', 'modelName': 'Employee', 'children': [
            {'label': 'View Attendance', 'href': '/hr/attendance', 'subtext': 'View your attendance record or your sub-ordinates'},
            {'label': 'Pending Approvals', 'href': '/hr/attendance/approval/pending', 'subtext': 'Pending approval requests'},
            {'label': 'Leaves record', 'href': '/hr/attendance/leaves', 'subtext': 'View Leaves Record'},
        ]},
    ],
    'mmc': [
        {'label': 'Dashboard', 'href': '/mmc', 'appName': 'apparelManagement', 'modelName': 'Inventory'},
        {'label': 'Inventory', 'appName': 'apparelManagement', 'modelName': 'Inventory', 'children': [
            {'label': 'Raw Material Stock', 'href': '/mmc/inventory/stock-report' , 'subtext': 'Current balance of fabrics, trims, and accessories (limited to 2yrs)'},
            {'label': 'Free Inventory', 'href': '/mmc/inventory/free-stock', 'subtext': 'Unallocated materials available for new orders'},
            {'label': 'Manage Cards', 'href': '/mmc/inventory', 'subtext': 'Manage Inventory Cards in the database'},
        ]},
    ],
    'merchandising': [
        {'label': 'Dashboard', 'href': '/merchandising', 'appName': 'apparelManagement', 'modelName': 'WorkOrder'},
        {'label': 'Presets', 'appName': 'apparelManagement', 'modelName': 'StyleCard', 'children': [
            {'label': 'Style Cards', 'href': '/merchandising/style', 'subtext': 'Manage style Cards in the database'},
            {'label': 'Work Orders', 'href': '/merchandising/work-order', 'subtext': 'Manage work orders in the database'},
        ]}
    ],
}

LOCAL_TIMEZONE = timezone('Asia/Karachi')
GST_RATE = 18.0
GST_RATE_FOR_SERVICES = 16.0
LOCAL_CURRENCY = 'PKR'

NOW = datetime.now()
TODAY = datetime.today()

MIN_WAGE = 32000

EMPLOYEMENT_AGE_IN_YEARS = 18

API_KEY_FOR_AI = os.environ.get("API_KEY_FOR_AI")