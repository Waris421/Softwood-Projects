from django.urls import path

from . import views

app_name = 'HumanResource'

urlpatterns = [
    path('hr/workers', views.EmployeeList.as_view(), name='workerList'),
    path('hr/worker/add', views.AddEmployee.as_view(), name='employeeAdd'),
    path('hr/worker/bulk-add', views.AddEmployeeBulk.as_view(), name='employeeBulkAdd'),
    path('hr/worker/<int:pk>/update', views.UpdateEmployee.as_view(), name='employeeUpdate'),
    path('hr/worker/shift-define', views.UpdateEmployeeShift.as_view(), name='employeeShiftUpdate'),
]