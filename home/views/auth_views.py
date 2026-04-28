from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import logout
from ..forms import UserRegisterForm
from ..forms import UserProfileForm
from ..models import UserProfile
from django.shortcuts import get_object_or_404


# Auth Views
def custom_login(request):
    if request.user.is_authenticated:
        return redirect('home:home')
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.success(request, f'¡Bienvenido {username}!')
                
                # Redirect to next page or home
                next_page = request.GET.get('next', 'home:home')
                return redirect(next_page)
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')
    else:
        form = AuthenticationForm()
    
    return render(request, 'home/login.html', {'form': form})

def custom_logout(request):
    logout(request)
    messages.info(request, 'Has cerrado sesión exitosamente.')
    return redirect('home:home')

def register(request):
    if request.user.is_authenticated:
        return redirect('home:home')
    
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()  # Only save User
            # <-- REMOVE UserProfile.objects.create(...) here
            
            # Optionally, log in the user automatically
            login(request, user)
            messages.success(request, f'¡Cuenta creada para {user.username}!')
            return redirect('home:home')
    else:
        form = UserRegisterForm()
    
    return render(request, 'home/register.html', {'form': form})




@login_required
def profile(request):
    profile = get_object_or_404(UserProfile, user=request.user)
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            
            # Update user info
            request.user.first_name = form.cleaned_data.get('first_name', '')
            request.user.last_name = form.cleaned_data.get('last_name', '')
            request.user.email = form.cleaned_data.get('email', '')
            request.user.save()
            
            messages.success(request, 'Perfil actualizado exitosamente.')
            return redirect('home:profile')
    else:
        form = UserProfileForm(initial={
            'first_name': request.user.first_name,
            'last_name': request.user.last_name,
            'email': request.user.email,
            'role': profile.role,
            'company': profile.company,
            'phone': profile.phone,
        })
    
    return render(request, 'home/profile.html', {'form': form, 'profile': profile})




@login_required
def password_change(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Tu contraseña ha sido actualizada.')
            return redirect('home:profile')
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'home/password_change.html', {'form': form})




    # urls.py — temporary, remove after diagnosis
from django.http import JsonResponse
import sys, locale

def encoding_debug(request):
    return JsonResponse({
        'sys.getdefaultencoding': sys.getdefaultencoding(),
        'sys.stdout.encoding': sys.stdout.encoding,
        'sys.getfilesystemencoding': sys.getfilesystemencoding(),
        'locale.getpreferredencoding': locale.getpreferredencoding(),
    })