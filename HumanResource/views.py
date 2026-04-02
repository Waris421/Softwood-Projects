from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import  AllowAny
from rest_framework.request import Request
from rest_framework import status

from . import models

from .services import employee_service

from core.services.auth_service import authenticateUser

class EmployeeList(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request):
        try:
            authenticateUser(request, 'HumanResource', 'Employee', type='view')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)
    
        response = {'message': 'Under Construction'}
        return Response(data=response, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    
class AddEmployee(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request):
        try:
            authenticateUser(request, 'HumanResource', 'Employee', type='add')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            data = employee_service.GetDataForEmployeeAddition()
            return Response(data=data, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request: Request):
        try:
            authenticateUser(request, 'HumanResource', 'Employee', type='add')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)

        data = request.data
        try:
            employeeCode = employee_service.AddEmployee(data)
            response = {'EmployeeCode': employeeCode}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)