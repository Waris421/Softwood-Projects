from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import  AllowAny
from rest_framework.request import Request
from rest_framework import status

from .services import employee_service, shift_service, holiday_service, location_service
from core.services.auth_service import authenticateUser
from . import models

class EmployeeList(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request):
        try:
            authenticateUser(request, 'HumanResource', 'Employee', type='view')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)
    
        try:
            employees = employee_service.GetEmployeeList()
            return Response(data=employees, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)
    
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

class AddEmployeeBulk(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request):
        #Check user authentication
        try:
            authenticateUser(request, 'HumanResource', 'Employee', type='add')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)
        
        dryRunFlag = request.query_params.get('dry_run')

        #Convert true/false dryRunFlag from str to bool
        mapping = {"true": True, "false": False}
        dryRunFlag = mapping.get(str(dryRunFlag).lower())

        #Return error if not flag is provided
        if dryRunFlag is None:
            response = {'message': 'Invalid run flag'}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

        if dryRunFlag:
            try:
                file = request.FILES.get('file')
                rows, token = employee_service.PreviewUploader(file)
                responseData = {
                    'rows': rows,
                    'token': token,
                }
                return Response(data=responseData, status=status.HTTP_200_OK)
            except Exception as e:
                print(e)
                response = {'message': str(e)}
                return Response(data=response, status=status.HTTP_400_BAD_REQUEST)
        else:
            try:
                token = request.data.get('token')
                numberOfAddedEmployees = employee_service.AddEmployeeBulk(token)
            except Exception as e:
                print(e)
                response = {'message': str(e)}
                return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

        response = {'numberOfAddedEmployees': numberOfAddedEmployees}
        return Response(data=response, status=status.HTTP_200_OK)

class UpdateEmployee(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request, pk: int):
        try:
            authenticateUser(request, 'HumanResource', 'Employee', type='change')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            employee = models.Employee.objects.get(id=pk)
        except:
            response = {'message': 'Resource not found'}
            return Response(data=response, status=status.HTTP_404_NOT_FOUND)
        
        try:
            data = employee_service.GetDataForEmployeeUpdate(employee)
            return Response(data=data, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)
    
    def post(self, request: Request, pk: int):
        try:
            authenticateUser(request, 'HumanResource', 'Employee', type='change')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            employee = models.Employee.objects.get(id=pk)
        except:
            response = {'message': 'Resource not found'}
            return Response(data=response, status=status.HTTP_404_NOT_FOUND)
        
        try:
            employee_service.UpdateEmployee(employee, request.data)
            response = {'message': 'Saved Successfully'}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

class UpdateEmployeeShift(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request):
        try:
            authenticateUser(request, 'HumanResource', 'WorkingShift', type='add')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)
        
        department = request.query_params.get('department')

        try:
            responseData = shift_service.GetDataForShiftUpdate(department)
            return Response(data=responseData, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)
    
    def post(self, request: Request):
        try:
            authenticateUser(request, 'HumanResource', 'WorkingShift', type='add')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            shift_service.UpdateShift(request.data)
            response = {'message': 'Saved Successfully'}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

class DefineHoliday(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request):
        try:
            authenticateUser(request, 'HumanResource', 'Holiday', type='add')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            responseData = holiday_service.GetDataForHolidayDefine()
            return Response(data=responseData, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request: Request):
        try:
            authenticateUser(request, 'HumanResource', 'Holiday', type='add')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            holiday_service.AddHoliday(request.data)
            response = {'message': 'Saved Successfully'}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

class SetSaturday(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request):
        try:
            authenticateUser(request, 'HumanResource', 'OffSaturday', type='add')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)
        
        employeeCode = request.query_params.get('employee')
        
        try:
            responseData = holiday_service.GetDataForOffSaturday(employeeCode)
            return Response(data=responseData, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)
    
    def post(self, request: Request):
        try:
            authenticateUser(request, 'HumanResource', 'OffSaturday', type='add')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            holiday_service.DefineOffSaturday(request.data)
            response = {'message': 'Saved Successfully'}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

class AddOffice(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request):
        try:
            authenticateUser(request, 'HumanResource', 'OffSaturday', type='add')
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)
        
        try:
            location_service.AddOffice(request.data)
            response = {'message': 'Saved Successfully'}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)