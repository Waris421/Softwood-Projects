from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from core.constants.theme import theme

@login_required(login_url='/login')
def home(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not allowed', status=403)
    
    return render(request, 'erp_home.html', context={'theme': theme})

urlpatterns = [
    path('', home),
    path('home', home, name='home'),
    path('admin/', admin.site.urls),
    path('api-auth/', include('rest_framework.urls')),
    path ('', include ('apparelManagement.urls')),
    path ('', include ('qualityControl.urls')),
    path ('', include ('marketing.urls')),
    path ('', include ('prodManagement.urls')),
    path ('', include ('planning.urls')),
    path ('', include ('authentication.urls')),
    path ('', include ('integration.urls')),
    path ('', include ('HumanResource.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)