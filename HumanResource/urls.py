from django.urls import path

from . import views
from core.services import options_service

app_name = 'HumanResource'

urlpatterns = [
    path('hr/workers', views.EmployeeList.as_view(), name='workerList'),
    path('hr/worker/add', views.AddEmployee.as_view(), name='employeeAdd'),
    path('hr/worker/bulk-add', views.AddEmployeeBulk.as_view(), name='employeeBulkAdd'),
    path('hr/worker/<int:pk>/update', views.UpdateEmployee.as_view(), name='employeeUpdate'),
    path('hr/worker/shift-define', views.UpdateEmployeeShift.as_view(), name='employeeShiftUpdate'),

    path('hr/holiday/add', views.DefineHoliday.as_view(), name='holidayAdd'),

    path('hr/worker/set-saturday', views.SetSaturday.as_view(), name='setSaturday'),

    path('hr/offices', views.OfficeList.as_view(), name='officeList'),
    path('hr/office/add', views.AddOffice.as_view(), name='addOffice'),
    path('hr/office/<int:pk>/update', views.UpdateOffice.as_view(), name='officeUpdate'),

    path('hr/worker/office-assign', views.AssignOffice.as_view(), name='officeAssign'),

    path('hr/attendance', views.GetAttendance.as_view(), name='getAttendance'),
    path('hr/attendance/add-initial', views.AddUnverifiedAttendance.as_view(), name='addAttendanceUnverified'),
    path('hr/attendance/add-final', views.AddVerifiedAttendance.as_view(), name='addAttendnceVerified'),

    path('options/workers', options_service.GetWorkers.as_view(), name='workersOptions'),
]