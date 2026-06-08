from django.urls import path

from . import views

app_name = 'HumanResource'

urlpatterns = [
    path('hr/workers', views.EmployeeList.as_view(), name='workerList'),
    path('hr/worker/add', views.AddEmployee.as_view(), name='employeeAdd'),
    path('api/attendance/rfid', views.RFIDAttendanceAPI.as_view(), name='rfidAttendance'),
]