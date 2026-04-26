from django.urls import path
from . import views

app_name = 'Finance'

urlpatterns = [
    path('finance/purchase-order',              views.FinancePurchaseOrderList.as_view(),   name='financePOs'),
    path('finance/purchase-order/<int:po_id>/', views.FinancePurchaseOrderDetail.as_view(), name='financePODetail'),
]

