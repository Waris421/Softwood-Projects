from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication, SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.authtoken.models import Token
from rest_framework.request import Request
from rest_framework import status

from .services import employee_service, shift_service, holiday_service, location_service
from .services import attendance_service, correction_service
from core.services.auth_service import AppModelPermissions, authenticateUser
from . import models

class EmployeeList(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'HumanResource'
    modelName = 'Employee'
    permissionType = 'view'

    def get(self, _: Request):    
        try:
            employees = employee_service.GetEmployeeList()
            return Response(data=employees, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)
    
class AddEmployee(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'HumanResource'
    modelName = 'Employee'
    permissionType = 'add'

    def get(self, _: Request):
        try:
            data = employee_service.GetDataForEmployeeAddition()
            return Response(data=data, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request: Request):
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
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'HumanResource'
    modelName = 'Employee'
    permissionType = 'add'

    def post(self, request: Request):        
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
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'HumanResource'
    modelName = 'Employee'
    permissionType = 'change'

    def get(self, _: Request, pk: int):        
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
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'HumanResource'
    modelName = 'WorkingShift'
    permissionType = 'add'

    def get(self, request: Request):        
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
            shift_service.UpdateShift(request.data)
            response = {'message': 'Saved Successfully'}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

class DefineHoliday(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'HumanResource'
    modelName = 'Holiday'
    permissionType = 'add'

    def get(self, _: Request):        
        try:
            responseData = holiday_service.GetDataForHolidayDefine()
            return Response(data=responseData, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

    def post(self, request: Request):        
        try:
            holiday_service.AddHoliday(request.data)
            response = {'message': 'Saved Successfully'}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

class SetSaturday(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'HumanResource'
    modelName = 'OffSaturday'
    permissionType = 'add'

    def get(self, request: Request):        
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
            holiday_service.DefineOffSaturday(request.data)
            response = {'message': 'Saved Successfully'}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

class OfficeList(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'HumanResource'
    modelName = 'Location'
    permissionType = 'view'

    def get(self, _: Request):
        try:
            offices = location_service.GetOffices()
            return Response(data=offices, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

class AddOffice(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'HumanResource'
    modelName = 'Location'
    permissionType = 'add'

    def post(self, request: Request):        
        try:
            location_service.AddOffice(request.data)
            response = {'message': 'Saved Successfully'}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

class UpdateOffice(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'HumanResource'
    modelName = 'Location'
    permissionType = 'change'

    def get(self, _: Request, pk: int):        
        try:
            office = models.Location.objects.get(id=pk)
        except:
            response = {'message': 'Resource not found'}
            return Response(data=response, status=status.HTTP_404_NOT_FOUND)
        
        try:
            responseData = location_service.GetDataForOfficeUpdate(office)
            return Response(data=responseData, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)
    
    def post(self, request: Request, pk: int):        
        try:
            office = models.Location.objects.get(id=pk)
        except:
            response = {'message': 'Resource not found'}
            return Response(data=response, status=status.HTTP_404_NOT_FOUND)
        
        try:
            location_service.updateOffice(office, request.data)
            response = {'message': 'Saved Successfully'}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

class AssignOffice(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'HumanResource'
    modelName = 'OffSaturday'
    permissionType = 'add'

    def get(self, request: Request):
        manager = request.user
        
        employeeCode = request.query_params.get('employee')

        try:
            responseData = location_service.GetDataForOfficeAssign(manager, employeeCode)
            return Response(data=responseData, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)
    
    def post(self, request: Request):
        manager = request.user
        
        try:
            location_service.AssignOffices(manager, request.data)
            response = {'message': 'Saved Successfully'}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)
    
class GetAttendance(APIView):
    '''
        Get a user's attendance within the specified date range.

        Expected GET method parameters
        from: yyyy-mm-dd
        to: yyyy-mm-dd
        employeeCode: (optional)
    '''
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'HumanResource'
    modelName = 'Attendance'
    permissionType = 'view'

    def get(self, request: Request):
        user = request.user

        employeeCode = request.query_params.get('employeeCode')
        try:
            if employeeCode:
                employee = models.Employee.objects.get(id=employeeCode)
            else:
                employee = models.Employee.objects.get(User=user)
        except models.Employee.DoesNotExist:
            return Response(
                data={'message': 'Invalid Employee Code or User'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        startDate = request.query_params.get('from')
        endDate = request.query_params.get('to')

        if (not startDate) or (not endDate):
            response = {'message': 'Invalid Date Range'}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            attendance = attendance_service.GetAttendance(employee, startDate, endDate)
            response = {'data': attendance}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

class AddUnverifiedAttendance(APIView):
    '''
        Get initial data from user for checking if they can add attendance.

        Expected JSON in POST method:
        {
            "Latitude": "float (required)",
            "Longitude": "float (required)",
            "Type": "in/out (required)"
        }
    '''
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'HumanResource'
    modelName = 'Attendance'
    permissionType = 'add'

    def post(self, request: Request):
        user = request.user

        try:
            employee = models.Employee.objects.get(User=user)
        except:
            response = {'message': 'User settings issue. Check wth HR'}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

        try:
            responseData = attendance_service.VerifyAttendance(employee, request.data)
            return Response(data=responseData, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

class AddVerifiedAttendance(APIView):
    '''
        Add user's attendance.

        Expected JSON in POST method:
        {
            "Latitude": "float (required)",
            "Longitude": "float (required)",
            "Type": "in/out (required)"
            "Details": "(required, but can be empty)"
        }
    '''
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'HumanResource'
    modelName = 'Attendance'
    permissionType = 'add'

    def post(self, request: Request):
        user = request.user
        
        try:
            employee = models.Employee.objects.get(User=user)
        except:
            response = {'message': 'User settings issue. Check wth HR'}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            attendance_service.AddAttendance(employee, request.data)
            response = {'message': 'Saved Successfully'}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)
        
class AddCorrection(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'HumanResource'
    modelName = 'Adjustment'
    permissionType = 'add'

    def get(self, request: Request):
        user = request.user

        params = request.query_params.dict()

        try:
            formData = correction_service.GetDataForCorrection(user, params)
            return Response(data=formData, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)
    
    def post(self, request: Request):
        user = request.user

        try:
            correction_service.AddCorrection(user, request.data)
            response = {'message': 'Saved Successfully'}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

class UpdateAdjustment(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'HumanResource'
    modelName = 'Adjustment'
    permissionType = 'change'

    def get(self, request: Request, pk: int):
        user = request.user
        
        try:
            adjustment = models.AttendanceAdjustmentHeader.objects.get(Header__id=pk)
        except Exception as e:
            print(e)
            response = {'message': 'Resource not found'}
            return Response(data=response, status=status.HTTP_404_NOT_FOUND)
        
        try:
            formData = correction_service.GetDataForAdjustmentUpdate(user, adjustment)
            return Response(data=formData, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)
    
    def post(self, request: Request, pk: int):
        user = request.user
        
        try:
            adjustment = models.AttendanceAdjustmentHeader.objects.get(Header__id=pk)
        except Exception as e:
            print(e)
            response = {'message': 'Resource not found'}
            return Response(data=response, status=status.HTTP_404_NOT_FOUND)
        
        try:
            correction_service.UpdateAdjustment(user, adjustment, request.data)
            response = {'message': 'Saved Successfully'}
            return Response(data=response, status=status.HTTP_200_OK)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            return Response(data=response, status=status.HTTP_400_BAD_REQUEST)

class UpdateLeave(APIView):
    authentication_classes = [TokenAuthentication, SessionAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'HumanResource'
    modelName = 'Adjustment'
    permissionType = 'change'

    def get(self, request: Request, pk: int):
        user = request.user

        try:
            adjustment = models.LeaveAdjustmentHeader.objects.get(Header__id=pk)
        except Exception as e:
            print(e)
            response = {'message': 'Resource not found'}
            return Response(data=response, status=status.HTTP_404_NOT_FOUND)

        print(adjustment)

        response = {'message': 'Under Construction'}
        return Response(data=response, status=status.HTTP_503_SERVICE_UNAVAILABLE)