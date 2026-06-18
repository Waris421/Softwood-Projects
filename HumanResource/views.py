from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import  AllowAny
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework import status

from . import models
from .services import attendance_service

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
# Token: 76b7ab94a259af0daf37c5c5b72c13abcb7bda17
class RFIDAttendanceAPI(APIView):
    # Static token auth — ESP sends a fixed token, no user login needed
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request: Request):
        cardUID      = request.data.get('CardUID')
        attendanceType = request.data.get('Type')
        machineMAC   = request.data.get('MachineMAC')

        if not cardUID or not attendanceType:
            return Response({'message': 'CardUID and Type are required'}, status=status.HTTP_400_BAD_REQUEST)

        if not machineMAC:
            return Response({'message': 'MachineMAC is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            attendance_service.AddRFIDAttendance(cardUID, attendanceType, machineMAC)
            return Response({'message': 'Attendance recorded'}, status=status.HTTP_200_OK)
        except PermissionError as e:
            return Response({'message': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except Exception as e:
            print(e)
            return Response({'message': str(e)}, status=status.HTTP_400_BAD_REQUEST)
