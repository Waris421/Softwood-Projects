from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework import status

from .services import purchase_order_service


class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        return


class FinancePurchaseOrderList(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        startDate = request.query_params.get('start', None)
        supplier = request.query_params.get('supplier', None)
        poNumber = request.query_params.get('poNumber', None)
        search   = request.query_params.get('search', None)
        page     = request.query_params.get('page', 1)

        if not startDate:
            return Response({'error': 'start date is required. Use ?start=YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            records = purchase_order_service.GetPurchaseOrders(startDate, supplier, poNumber, search, page)
            return Response(records, status=status.HTTP_200_OK)
        except ValueError as e:
            return Response({'error': str(e)}, status= status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Information on the PO
class FinancePurchaseOrderDetail(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication, TokenAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, po_id):
        try:
            record = purchase_order_service.GetPurchaseOrderDetail(po_id)
            if record is None:
                return Response({'error': 'Purchase order not found'}, status=status.HTTP_404_NOT_FOUND)
            return Response(record, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
