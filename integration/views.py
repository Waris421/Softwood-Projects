from django.http import JsonResponse

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.permissions import  AllowAny
from rest_framework import status as restResponseStatus

import requests
import json

from core.services.auth_service import getUserFromEmail, hasPermission
from integration.services import apparel_management

class ExportPOAllocation(APIView):
    permission_classes = [AllowAny]
    def post (self, request:Request):
        credentials = request.data.get('Credentials')
        type = request.query_params.get('type')

        try:
            user = getUserFromEmail(credentials)
        except Exception as e:
            print(e)
            return Response(status=restResponseStatus.HTTP_401_UNAUTHORIZED)

        if not hasPermission(user, 'apparelManagement', 'PurchaseOrder', 'view'):
            return Response(status=restResponseStatus.HTTP_403_FORBIDDEN)

        allocations = apparel_management.GetPOAllocations(type)

        return JsonResponse(allocations, safe=False)