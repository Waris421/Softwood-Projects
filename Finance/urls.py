from django.urls import path

from . import views

app_name = 'Finance'

urlpatterns = [
    path('finance/purchase-order', views.FinancePurchaseOrderList.as_view(), name='financePOs'),
    path('finance/purchase-order/<int:pk>/', views.FinancePurchaseOrderDetail.as_view()),
]