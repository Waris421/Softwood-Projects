from django.http import JsonResponse

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.request import Request
from rest_framework.permissions import  AllowAny
from rest_framework import status as restResponseStatus

import requests
import json

from core.services.auth_service import getUserFromEmail, hasPermission, authenticateUser
from integration.services import apparel_management, human_resource
from . import models

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

class ImportMachineAttendance(APIView):
    '''
        Import attendance from machine.

        Expected POST method parameters in url
        location: {primary key id of location}

        Export JSON in post method
        [
            {
                "EmployeeCode": "number",
                "Date": "(yyyy-mm-dd)",
                "Time": "(hh:mm:ss)",
                "Type": "(in/out)"
            },
            {
                "EmployeeCode": "number",
                "Date": "(yyyy-mm-dd)",
                "Time": "(hh:mm:ss)",
                "Type": "(in/out)"
            }
        ]
    '''
    permission_classes = [AllowAny]

    def post(self, request: Request):
        try:
            authenticateUser(request, 'HumanResource', 'Attendance', 'add')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=restResponseStatus.HTTP_401_UNAUTHORIZED)
        
        try:
            locationId = int(request.query_params.get('location'))
            location = models.Location.objects.get(id=locationId)
        except:
            response = {'Invalid location code'}
            return Response(data=response, status=restResponseStatus.HTTP_400_BAD_REQUEST)

        try:
            human_resource.AddAttendanceFromMachines(location, request.data['attData'])
            response = {'message': 'Added Successfully'}
            return Response(data=response, status=restResponseStatus.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=restResponseStatus.HTTP_400_BAD_REQUEST)