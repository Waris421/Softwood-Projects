from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('login/', views.Login, name='login'),
    path('logout/', views.Logout, name='logout'),
    path('password-reset', views.PasswordResetRequest, name='passwordResetRequest'),
    path('reset/<uidb64>/<token>/', views.PasswordResetConfirm, name='passwordResetConfirm'),
]