from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, password_validation
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.urls import reverse_lazy, reverse
from django.template.loader import get_template
from django.core.mail import send_mail
from django.http import HttpRequest, HttpResponse

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import  AllowAny
from rest_framework.authtoken.models import Token
from rest_framework.request import Request
from rest_framework import status
import rest_framework

from . import serializers

from core.constants.theme import theme
from core.constants.generic import BROWSER_OPTIONS
from core.services.auth_service import authenticateUser, hasPermission
from core.services.generic_services import showMessageResponse

def Login(request: HttpRequest):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            nextUrl = request.GET.get('next')
            if nextUrl:
                return redirect(nextUrl)
            else:
                return redirect('home')
        else:
            error = 'Invalid username or password'
            context = {
                'error': error, 'theme': theme
            }
            return render(request, 'login.html', context)
    else:
        context = {
            'theme': theme
        }

        return render(request, 'login.html', context)

class APILogin(APIView):
    '''
        Log's in a user via API.

        Expected JSON in POST method:
        {
            "username": "jon.doe",
            "password": "1234"
        }
        or
        {
            "token": "token"
        }
    '''
    permission_classes = [AllowAny]
    def post (self, request:Request):
        username = request.data.get('username')
        password = request.data.get('password')
        token = request.data.get('token')

        if token:
            try:
                tokenObj = Token.objects.get(key=token)
            except Token.DoesNotExist:
                response = {'detail': 'Invalid Credentials'}
                return Response(data=response, status=status.HTTP_401_UNAUTHORIZED)
            
            response = {
                'message': 'Login was successful',
                'token': token,
                'fullName': tokenObj.user.get_full_name(),
            }
            
            status = rest_framework.status.HTTP_200_OK
            return Response (data=response, status=status)
        else:
            user = authenticate(username=username, password=password)

            if user is not None:
                token, _ = Token.objects.get_or_create(user=user)

                response = {
                    "message": "Login was successful",
                    "token": token.key,
                    'fullName': user.get_full_name()
                }
                status = rest_framework.status.HTTP_200_OK
            else:
                response = {"message": "Invalid Credentials"}
                status = rest_framework.status.HTTP_401_UNAUTHORIZED
            
            return Response (data=response, status=status)

class APIPasswordResetRequest(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request):
        userEmail = request.data.get('email')

        user = User.objects.filter(email=userEmail).first()

        if user:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)

            response = {
                'token': token,
                'uid': uid,
            }
            status = rest_framework.status.HTTP_200_OK
        else:
            response = {"message": "User does not exist"}
            status = rest_framework.status.HTTP_404_NOT_FOUND

        return Response(data=response, status=status)

class APIPasswordResetConfirm(APIView):
    permission_classes = [AllowAny]

    def getUser(self, uidb64):
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            return User.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, User.DoesNotExist):
            return None

    def post(self, request: Request, uidb64, token):
        user = self.getUser(uidb64)
        if user is None or not default_token_generator.check_token(user, token):
            return Response({"message": "Invalid or expired link"}, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = serializers.APIPasswordResetConfirm(data=request.data)

        if serializer.is_valid():
            newPassword = serializer.validated_data['password1']
            
            try:
                password_validation.validate_password(newPassword, user)
                user.set_password(newPassword)
                user.save()
                return Response({"message": "Password reset successful"}, status=status.HTTP_200_OK)
            except Exception as e:
                return Response({"message": list(e.messages)}, status=status.HTTP_400_BAD_REQUEST)
        
        return Response(data=serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def get(self, request: Request, uidb64, token):
        user = self.getUser(uidb64)
        if user is not None and default_token_generator.check_token(user, token):
            return Response({"message": "Token is valid"}, status=status.HTTP_200_OK)
        
        return Response({"message": "Invalid or expired link"}, status=status.HTTP_400_BAD_REQUEST)

class GetNavBarOptions(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request):
        try:
            user = authenticateUser(request, None, None, None)
        except Exception as e:
            print(e)
            response = {'message': str(e)}
            status = rest_framework.status.HTTP_401_UNAUTHORIZED
            return Response(data=response, status=status)
        
        pageName = request.GET.get('pageName', '')
        options = BROWSER_OPTIONS.get(pageName, [])

        finalOptions = []
        for option in options:
            appName = option.get('appName')   
            modelName = option.get('modelName') 
            
            if hasPermission(user, appName, modelName, type='view'):
                filteredOption = option.copy()
                filteredOption.pop('appName', None)
                filteredOption.pop('modelName', None)
                finalOptions.append(filteredOption)

        return Response(data=finalOptions, status=rest_framework.status.HTTP_200_OK)

def Logout(request: HttpRequest):
    if request.method != 'GET':
        return HttpResponse('Not allowed', status=405)
    
    logout(request)

    return redirect(reverse('login'))

def PasswordResetRequest(request: HttpRequest):
    if request.method == 'POST':
        userEmail = request.POST.get('email')

        try:
            user = User.objects.get(email=userEmail)
        except User.DoesNotExist:
            context = {
                'error': 'Incorrect email address', 'theme': theme
            }
            return render(request, 'reset/request.html', context)
        except Exception as e:
            context = {
                'error': e, 'theme': theme
            }
            return render(request, 'reset/request.html', context)
        
        # Generate token and UID
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        resetLink = request.build_absolute_uri(
                reverse_lazy('passwordResetConfirm', kwargs={'uidb64': uid, 'token': token})
            )
        
        context = {
            'user': user,
            'resetLink': resetLink,
            'siteName': 'Fashion OS',
        }

        template = get_template('reset/email.html').render(context)
        try:
            send_mail(
                subject='Reset Password',
                message=None,
                html_message=template,
                from_email=None,
                recipient_list=[user.email]
            )
            return showMessageResponse(request, 'We have emailed you the instruction on resetting your password.', 200)
        except Exception as e:
            print(e)
            context = {
                'error': e, 'theme': theme
            }
            return render(request, 'reset/request.html', context)
    else:
        context = {
            'theme': theme
        }
        return render(request, 'reset/request.html', context)

def PasswordResetConfirm(request: HttpRequest, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
    except:
        print('UID error')
        return HttpResponse('Not allwed', status=405)
    
    try:
        user = User.objects.get(pk=uid)
    except:
        print('User Error')
        return HttpResponse('Not allowed', status=400)
    
    if request.method == 'POST':
        if default_token_generator.check_token(user, token):
            password1 = request.POST.get('password1')
            password2 = request.POST.get('password2')

            if password1 == password2:  
                try:
                    user.set_password(password1) 
                    user.save()
                    return redirect('login')
                except Exception as e:
                    context = {
                        'error': e,
                        'theme': theme,
                    }
                    return render(request, 'reset/confirm.html', context)
            else:
                context = {
                    'error': 'Your password does not match',
                    'theme': theme,
                }
                return render(request, 'reset/confirm.html', context)
        else:
            return redirect(reverse_lazy('passwordResetRequest'))
    else:        
        if default_token_generator.check_token(user, token):
            context = {
                'theme': theme,
            }
            return render(request, 'reset/confirm.html', context)
        else:
            return redirect(reverse_lazy('passwordResetRequest'))