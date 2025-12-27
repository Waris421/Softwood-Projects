from django.urls import path
from . import views
from core.services import options_service

app_name = 'apparelManagement'

urlpatterns = [
    path('apparel', views.home, name = 'apparel'),

    path('notification/<int:pk>/view', views.GetNotificationDetails, name='notifDetails'),
    path('notification/<int:pk>/read', views.ReadNotification, name='notifRead'),

    path ('inv',views.Inventory, name='Inv'),   
    path ('inv/add', views.AddInv, name='addInv'),
    path('inv/<str:pk>/edit/', views.UpdateInv, name='editInv'),
    path('inv/<str:pk>/delete/', views.DeleteInv, name='deleteInv'),
    path('inv/<str:pk>/copy/', views.CopyInv, name='copyInv'),
    path('inv/<str:pk>/check/', views.CheckInventoryCodeExists, name='checkInvcode'),
    path('inv/code/gen/', views.GenerateInventoryCode, name='genInvCode'),
    path('inv/reports', views.InventoryReports, name='inventoryReportsHome'),
    
    path('inv/reports/free-stock', views.InventoryFreeStockReport, name='inventoryReportFreeStock'),
    path('inv/reports/un-ordered', views.UnOrderedInventory, name='inventoryReportUnOrdered'),
    path('inv/free-stock/history', views.InventoryFreeStockHistory, name='inventoryFreeStockHistory'),

    path ('style',views.Style, name='Style'),
    path ('style/add',views.AddStyle, name='addStyle'),
    path('style/<str:pk>/edit/', views.UpdateStyle, name='editStyle'),
    path('style/<str:pk>/delete/', views.DeleteStyle, name='deleteStyle'),
    path('style/<str:pk>/copy/', views.CopyStyle, name='copyStyle'),
    path('style/route-preset/details', views.StyleRoutePrssetDetails, name='getRoutepresetDetails'),
    
    path('consumption/thread/requests', views.ThreadConsumptionRequests, name='threadConsRequests'),
    path('consumption/thread/request/add', views.AddThreadConsumptionRequest, name='addThreadConsRequest'),
    path('consumption/thread/request/<int:pk>/edit', views.EditThreadConsumptionRequest, name='editThreadConsRequest'),
    path('consumption/thread/requests/pending', views.GetPendingThreadConsRequest.as_view(), name='pendingThreadConsRequests'),
    path('consumption/thread/request/<int:pk>/update', views.UpdateThreadConsumption.as_view(), name='updateThreadConst'),

    path('workorder', views.WorkOrder, name='WOs'),
    path('workorder/add', views.AddWorkOrder, name='addWO'),
    path('workorder/<int:pk>/edit', views.UpdateWorkOrder, name='editWO'),
    path('workorder/<int:pk>/delete', views.DeleteWorkOrder, name='deleteWO'),
    path('workorder/<int:pk>/copy', views.CopyWorkOrder, name='copyWO'),
    path('workorder/<int:pk>/print', views.PrintWorkOrder, name='printWO'),
    path('workorder/variants/calculate', views.CalculateVariants, name='calculateVariants'),
    path('workorder/requirement/calculate', views.CalculateRequirement, name='calculateRequirement'),
    path('workorder/requirement/get', views.GetRequirementHistory, name='getRequirementHistory'),
    path('workorder/initial-plan', views.WorkOrderInitialPlan, name='initialPlan'),
    path('purchaseorder/add/fromworkorder/<int:pk>', views.GeneratePOFromWO, name='poFromWO'),

    path('purchaseorder/autogen', views.AutoInventoryRequirement, name='autoReq'),
    path('purchaseorder', views.PurchaseOrder, name='POs'),
    path('purchaseorder/add', views.AddPurchaseOrder, name='addPO'),
    path('purchaseorder/alloc/get', views.getPOAllocation, name='getPOAllocation'),
    path('purchaseorder/<int:pk>/edit', views.EditPurchaseOrder, name='editPO'),
    path('purchaseorder/<int:pk>/copy', views.CopyPurchaseOrder, name='copyPO'),
    path('purchaseorder/<int:pk>/delete', views.DeletePurchaseOrder, name='deletePO'),
    path('purchaseorder/<int:pk>/print', views.PrintPurchaseOrder, name='printPO'),
    path('purchaseorder/defaultqty/get', views.GetWODefaultQtyForPO, name='poDefaultQty'),
    path('purchaseorder/allocatedqty/get', views.getAllocatedQty, name='poAllocatedQty'),

    path('purchasereceipt', views.PurchaseReceipt, name='purchaseRec'),
    path('purchasereceipt/add', views.AddPurchaseReceipt, name='addRec'),
    path('purchasereceipt/<int:pk>/edit', views.EditPurchaseReceipt, name='editRec'),
    path('purchasereceipt/alloc/get', views.GetReceiptAllocation, name='getRecAllocation'),
    path('purchasereceipt/context', views.GetContextForPurchaseReceipt, name='getRecContext'),
    path('purchasereceipt/<int:pk>/re-allocate', views.ReAllocateReceiptInventory, name='reAllocate'),
    path('purchasereceipt/<int:pk>/print', views.PrintPurchaseReceipt, name='printRec'),

    path('purchasedemand', views.PurchaseDemand, name='purchaseDemand'),
    path('purchasedemand/add', views.AddPurchaseDemand, name='addPD'),
    path('purchasedemand/<int:pk>/edit', views.EditPurchaseDemand, name='editPD'),
    path('purchasedemand/<int:pk>/copy', views.CopyPurchaseDemand, name='copyPD'),
    path('purchasedemand/<int:pk>/delete', views.DeletePurchaseDemand, name='deletePD'),
    path('purchasedemand/<int:pk>/approve', views.ApprovePurchaseDemand, name='approvePD'),
    path('purchasedemand/<int:pk>/makepo', views.ConvertPDtoPO, name='PDtoPO'),

    path('requisition', views.Requisition, name='requisition'),
    path('requisition/add/order', views.AddRequisitionForOrder, name='addRequisitionForOrder'),
    path('requisition/add/inv', views.AddRequisitionForInv, name='addRequisitionForInv'),
    path('requisition/alloc/get', views.GetRequisitionAllocation, name='getReqAllocation'),

    path('issuance', views.Issuance, name='issue'),
    path('issuance/add', views.AddIssuance, name='addIssue'),
    path('issuance/add/order', views.AddIssuanceForOrder, name='addIssueForOrder'),

    path('options/yesorno', options_service.yesOrNo, name='YesOrNo' ),
    path('options/customers', options_service.getCustomersList, name='CustomerList'),
    path('options/suppliers', options_service.getSuppliersList, name='SupplierList'),
    path('options/departments', options_service.getDepartmentsList, name='DepartmentList'),
    path('options/categories', options_service.getCategories, name='GenderCategories'),
    path('options/inventories', options_service.getInventories, name='InventoryList'),
    path('options/groups/inventory', options_service.getInvGroups, name='invGroups'),
    path('options/units', options_service.getUnits, name='UnitList'),
    path('options/constypes', options_service.getConsTypes, name='ConsTypes'),
    path('options/prodstages', options_service.getProductionStages, name='ProdTypes'),
    path('options/styles', options_service.getStyles, name='StyleList'),
    path('options/ordertypes', options_service.getOrderTypes, name='OrderTypes'),
    path('options/currencies', options_service.getCurrencies, name='CurrencyList'),
    path('options/merchants', options_service.getMerchandisers, name='merchantList'),
    path('options/users', options_service.GetUsers, name='userList'),
    path('options/unit/<str:group>', options_service.getUnitsForGroup, name='unitsForGroup'),
    path('options/workorders', options_service.getWorkOrders, name='workOrders'),
    path('options/purchaseorders/open', options_service.getOpenPOs, name='openPOs'),
    path('options/preset-routes', options_service.GetPresetRoutes, name='presetRoutes'),

    path('api/inventories', options_service.GetInventories.as_view(), name='apiInventoryList'),
]