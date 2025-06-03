from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.urls import reverse_lazy, reverse
from django.template.loader import get_template
from django.core.mail import send_mail
from django.http import HttpRequest, HttpResponse

from .theme import theme

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
            return HttpResponse('We have emailed you the instruction on resetting your password.')
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