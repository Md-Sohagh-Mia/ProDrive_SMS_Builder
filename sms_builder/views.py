from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Company

# Create your views here.

def index(request):
    return render(request, 'index.html')


def signup(request):
    if request.method == 'POST':
        company_name = request.POST.get('company_name')
        abn = request.POST.get('abn')
        full_name = request.POST.get('full_name')
        email = request.POST.get('email')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')

        # NULL VALIDATION
        if not company_name or not abn or not full_name or not email or not password:
            messages.error(request, "All required fields must be filled!")
            return redirect('signup')

        # PASSWORD MATCH
        if password != confirm_password:
            messages.error(request, "Passwords do not match!")
            return redirect('signup')

        # PASSWORD LENGTH
        if len(password) < 8:
            messages.error(request, "Password must be at least 8 characters!")
            return redirect('signup')

        # EMAIL EXISTS
        if User.objects.filter(username=email).exists():
            messages.error(request, "Email already exists!")
            return redirect('signup')

        # CREATE USER
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password
        )

        # CREATE COMPANY
        Company.objects.create(
            user=user,
            company_name=company_name,
            abn=abn,
            address=request.POST.get('address'),
            full_name=full_name,
            role=request.POST.get('role'),
            phone=request.POST.get('phone'),
        )

        messages.success(request, "Signup successful!")
        return redirect('signup')

    return render(request, 'signup.html')


def signin(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        # ❌ EMPTY FIELD CHECK
        if not email or not password:
            messages.error(request, "Email and password required!")
            return redirect('signin')

        user = authenticate(request, username=email, password=password)

        # ❌ WRONG LOGIN
        if user is None:
            messages.error(request, "Invalid email or password!")
            return redirect('signin')

        # ✅ SUCCESS LOGIN
        login(request, user)
        messages.success(request, "Login successful!")
        return redirect('signin')

    return render(request, 'signin.html')


# ✅ FIXED: Correct indentation for profile and logout_view
@login_required(login_url='signin')
def profile(request):
    return render(request, 'profile.html')

def logout_view(request):
    logout(request)
    return redirect('signin')