from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import  AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import status

from .services import purchase_order_service

from core.services.auth_service import AppModelPermissions

class FinancePurchaseOrderList(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'apparelManagement'
    modelName = 'PurchaseOrder'
    permissionType = 'view'

    def get(self, request: Request):
        startDate = request.query_params.get('start', None)

        if not startDate:
            return Response({'error': 'start date is required. Use ?start=YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            records = purchase_order_service.GetPurchaseOrders(startDate)
            return Response(records, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({'error': str(e)}, status= status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class FinancePurchaseOrderDetail(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated, AppModelPermissions]

    appName = 'apparelManagement'
    modelName = 'PurchaseOrder'
    permissionType = 'view'

    def get(self, _: Request, pk: int):
        try:
            record = purchase_order_service.GetPurchaseOrderDetail(pk)
            if record is None:
                return Response({'error': 'Purchase order not found'}, status=status.HTTP_404_NOT_FOUND)
            return Response(record, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
