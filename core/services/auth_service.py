from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.apps import apps

from rest_framework.request import Request
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from rest_framework import permissions

from typing import Literal, List, Dict, Optional, Union

from core.constants.generic import NAV_LINKS_CONFIG

def hasPermission (
        user: User,
        appName: str,
        modelName: str,
        type: Literal["view", "add", "change", "delete"]
) -> bool: 
    """
    Checks if user has the given permission to the given django model.

    Parameters
    ----------
    request : HttpRequest
        The http request, containing the user session info.
    appName: str
        The name of the app in which the model lies
    modelName : str
        The name of the django model
    type : str
        The type of permissions to check.  Options are 'view', 'add', 'change', 'delete'.

    Returns
    -------
    bool
        True if user's group has the permission otherwise false.
    """
    
    if not user.is_authenticated:
        return False

    if user.is_staff:
        return True
    
    try:
        model = apps.get_model(app_label=appName, model_name=modelName.split('.')[-1])
    except (LookupError, ValueError):
        return False
    except Exception as e:
        raise Exception(e)
    
    permissionCodename = f"{type}_{model._meta.model_name}"
    contentType = ContentType.objects.get_for_model(model)

    filteredGroups = user.groups.filter(
        permissions__codename=permissionCodename,
        permissions__content_type=contentType
    )
    return filteredGroups.exists()

class AppModelPermissions(permissions.BasePermission):
    """
        Custom permission to check user access based on app name, model name, 
        and permission type defined on the view.
    """
    def has_permission(self, request: Request, view: APIView):
        user = request.user

        appName: Optional[str] = getattr(view, 'appName', None)
        modelName: Optional[str] = getattr(view, 'modelName', None)
        
        #permission_config could be a single string or a mapping of HTTP methods
        permissionConfig: Union[str, Dict[str, str], None] = getattr(view, 'permissionType', None)

        #Deny access if developer forgot configure in view
        if not all([appName, modelName, permissionConfig]):
            return False
        
        #For method specific permissions in a view
        if isinstance(permissionConfig, dict):
            permissionType = permissionConfig.get(request.method)

        #For singular permission in a view
        else:
            permissionType = permissionConfig
        
        #Deny access if developer didn't configure properly
        if not permissionType:
            return False
        
        #Rights validation using a helper function
        return hasPermission(user, appName, modelName, permissionType)

def authenticateUser(
        request: Request,
        appName: str|None,
        modelName: str|None,
        type: Literal["view", "add", "change", "delete"]|None
) -> User:
    '''
        Check if the user is authenticated. Compatible with both browser and api.
    '''
    user = request.user
    
    #This implements when a user is accessing via
    if user.is_anonymous:
        token = request.META.get('HTTP_AUTHORIZATION')

        try:
            user = Token.objects.get(key=token).user
        except Token.DoesNotExist:
            raise PermissionError('Unauthorised')
        except Exception as e:
            raise ValueError(e)

    if all([appName, modelName, type]):
        if not hasPermission(user, appName, modelName, type):
            raise PermissionError('Access Denied')
    
    return user

def canApprovePD (user: User):    
    #Users are maunally allowed to approve PD
    authorizedUsers = ['tanveer.hassan', 'firasat']
    if user.username in authorizedUsers:
        return True
    
    #if user is server admin, they can access PD approval
    if user.is_staff:
        return True

    return False

def getNavLinks(user: User, app: str) -> List[Dict]:
    appNavConfig = NAV_LINKS_CONFIG.get(app, [])
    filteredNavLinks = []

    for groupData in appNavConfig:
        groupAppName = groupData['appName']
        groupModelName = groupData['modelName']
        
        if hasPermission(user, groupAppName, groupModelName, 'view'):
            filteredNavLinks.append(groupData)
        
    return filteredNavLinks

def getAPIUser(request:Request) -> User:
    credentials = request.data.get('token')
    
    try:
        token = Token.objects.get(key=credentials)
        return token.user
    except:
        raise PermissionError('Unauthorised')

def getUserFromEmail(email: str) -> User:
    try:
        return User.objects.get(email=email)
    except Exception as e:
        raise LookupError(e)