from django.urls import path
from core.services.generic_services import showMessageResponse
from . import views

urlpatterns = [
    path('login/', views.Login, name='login'),
    path('logout/', views.Logout, name='logout'),
    path('password-reset', views.PasswordResetRequest, name='passwordResetRequest'),
    path('reset/<uidb64>/<token>/', views.PasswordResetConfirm, name='passwordResetConfirm'),

    path ('api/login', views.APILogin.as_view(), name='apiLogin'),
    path('api/reset-password', views.APIPasswordResetRequest.as_view(), name='apiResetPassword'),
    path('reset-password/<uidb64>/<token>/', views.APIPasswordResetConfirm.as_view(), name='apiPasswordResetConfirm'),

    path('access/denied', showMessageResponse, {'message': "You don't have the privileges to access this page."}, name='accessDenied'),

    path ('api/navbar-options', views.GetNavBarOptions.as_view(), name='apiLogin'),
]