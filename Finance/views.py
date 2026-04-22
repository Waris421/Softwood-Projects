from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

# Create your views here.
def Home(request: HttpRequest):
    return HttpResponse('Home View')
