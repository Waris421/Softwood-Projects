from django.http import HttpRequest
from django.db.models import Model
from django.contrib.auth.models import User
from typing import Literal
from django.contrib.contenttypes.models import ContentType

def hasPermission (
        request: HttpRequest,
        model: Model,
        type: Literal["view", "add", "change", "delete"]
) -> bool: 
    """
    Checks if user has the given permission to the given django model.

    Parameters
    ----------
    request : HttpRequest
        The http request, containing the user session info.
    model : The django model for which to check the permission
    type : str
        The type of permissions to check.  Options are 'view', 'add', 'change', 'delete'.

    Returns
    -------
    bool
        True if user's group has the permission otherwise false.
    """
    
    user = request.user    
    groups = user.groups.all()

    if user.is_staff:
        return True

    if not groups:
        return False
    
    permissionCodename = f"{type}_{model._meta.model_name}"
    contentType = ContentType.objects.get_for_model(model)

    for group in groups:
        permissions = group.permissions.filter(codename=permissionCodename, content_type=contentType)
        if permissions.exists():
            return True
    
    return False

def canApprovePD (request: HttpRequest):
    user = request.user
    
    #Users are maunally allowed to approve PD
    authorizedUsers = ['tanveer', 'firasat']
    if user.username in authorizedUsers:
        return True
    
    #if user is server admin, they can access PD approval
    if user.is_staff:
        return True

    return False

def getNavLinks(user: User, app: str):
    if app == 'apparelManagement':
        navLinks = [
            {'groupName': 'Dashboard', 'views': [], 'viewName': 'apparelManagement:apparel'},
            {'groupName': 'Inventory', 'views': [
                {'displayName': 'View All', 'viewName': 'apparelManagement:Inv'},
                {'displayName': 'Add New', 'viewName': 'apparelManagement:addInv'},
            ]},
            {'groupName': 'StyleCard', 'views': [
                {'displayName': 'View All', 'viewName': 'apparelManagement:Style'},
                {'displayName': 'Add New', 'viewName': 'apparelManagement:addStyle'},
            ]},
            {'groupName': 'Work Order', 'views': [
                {'displayName': 'View All', 'viewName': 'apparelManagement:WOs'},
                {'displayName': 'Add New', 'viewName': 'apparelManagement:addWO'},
                {'displayName': 'Auto Requirement', 'viewName': 'apparelManagement:autoReq'},
            ]},
            {'groupName': 'Purchase Demand', 'views': [
                {'displayName': 'View All', 'viewName': 'apparelManagement:purchaseDemand'},
                {'displayName': 'Add New', 'viewName': 'apparelManagement:addPD'},
            ]},
            {'groupName': 'Inventory Order', 'views': [
                {'displayName': 'View All', 'viewName': 'apparelManagement:POs'},
                {'displayName': 'Add New', 'viewName': 'apparelManagement:addPO'},
            ]},
            {'groupName': 'Inventory Receipt', 'views': [
                {'displayName': 'View All', 'viewName': 'apparelManagement:purchaseRec'},
                {'displayName': 'Add New', 'viewName': 'apparelManagement:addRec'},
            ]},
            {'groupName': 'Issuance', 'views': [
                {'displayName': 'View Requests', 'viewName': 'apparelManagement:requisition'},
                {'displayName': 'Request For Order', 'viewName': 'apparelManagement:addRequisitionForOrder'},
                {'displayName': 'Request For Item', 'viewName': 'apparelManagement:addRequisitionForInv'},
                {'displayName': 'View Issuances', 'viewName': 'apparelManagement:issue'},
            ]},
        ]
    elif app == 'Mark':
        navLinks = [
            {'groupName': 'Dashboard', 'views': [], 'viewName': 'marketing'},
            {'groupName': 'Customers', 'views': [
                {'displayName': 'Database', 'viewName': 'customerData'},
            ]},
            {'groupName': 'Correspondance', 'views': [
                {'displayName': 'Pending', 'viewName': 'pendingCalls'},
                {'displayName': 'Calls', 'viewName': 'callHistory'},
                {'displayName': 'Emails', 'viewName': 'pendingCalls'},
                {'displayName': 'Meetings', 'viewName': 'pendingCalls'},
            ]},
            {'groupName': 'Inquiries', 'views': [
                {'displayName': 'Meetings', 'viewName': 'pendingCalls'},
            ]},
            {'groupName': 'Insights', 'views': [
                {'displayName': 'Meetings', 'viewName': 'pendingCalls'},
            ]},
        ]
    elif app == 'PM':
        navLinks = [
            {'groupName': 'Dashboard', 'views': [], 'viewName': 'productivity'},
            {'groupName': 'Presets', 'views': [
                {'displayName': 'Style Bulletin', 'viewName': 'styleBulletins'},
                {'displayName': 'Operations', 'viewName': 'operations'},
                {'displayName': 'Machines', 'viewName': 'machines'},
                {'displayName': 'Workers', 'viewName': 'workers'},
            ]},
            {'groupName': 'Cutting', 'views': [
                {'displayName': 'Core Sheet', 'viewName': 'coreSheets'},
            ]},
            {'groupName': 'Stitching', 'views': [
                {'displayName': 'Scan Report', 'viewName': 'serials'},
            ]},
        ]
    elif app == 'QC':
        navLinks = [
            {'groupName': 'Dashboard', 'views': [], 'viewName': 'quality'},
            {'groupName': 'Fabric', 'views': [
                {'displayName': 'Under Process', 'viewName': 'pendingTrimAudit'},
            ]},
            {'groupName': 'Trims', 'views': [
                {'displayName': 'Pending Audits', 'viewName': 'pendingTrimAudit'},
                {'displayName': 'Audit History', 'viewName': 'trimAudit'},
            ]},
            {'groupName': 'Production', 'views': [
                {'displayName': 'Under Process', 'viewName': 'pendingTrimAudit'},
            ]},
        ]
    else:
        navLinks = []

    return navLinks