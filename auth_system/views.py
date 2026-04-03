from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import never_cache
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import LoginForm, SignupForm

User = get_user_model()

MAX_FAILED_ATTEMPTS = 5


def _safe_next_url(request):
    """Return the ``next`` URL only if it is safe to redirect to."""
    next_url = request.POST.get('next') or request.GET.get('next', '')
    url_is_safe = url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    )
    return next_url if url_is_safe else ''


@never_cache
@require_http_methods(['GET', 'POST'])
def login_view(request):
    """Customer login view.

    Accepts email or username + password, creates a Django session on success,
    and redirects to the dashboard (or the ``next`` query parameter URL).
    """
    if request.user.is_authenticated:
        return redirect('auth_system:dashboard')

    form = LoginForm()

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            identifier = form.cleaned_data['identifier']
            password = form.cleaned_data['password']
            remember_me = form.cleaned_data.get('remember_me', False)

            # Check for account lock-out before attempting authentication
            try:
                if '@' in identifier:
                    candidate = User.objects.get(email=identifier)
                else:
                    candidate = User.objects.get(username=identifier)

                if candidate.failed_login_attempts >= MAX_FAILED_ATTEMPTS:
                    messages.error(
                        request,
                        'Your account has been temporarily locked due to too many failed '
                        'login attempts. Please contact support.',
                    )
                    return render(request, 'auth_system/login.html', {'form': form})
            except User.DoesNotExist:
                pass  # Let authenticate() handle the "user not found" case

            user = authenticate(request, username=identifier, password=password)

            if user is not None:
                login(request, user)
                if not remember_me:
                    # Session expires when the browser closes
                    request.session.set_expiry(0)
                messages.success(request, f'Welcome back, {user.get_short_name()}!')
                safe_next = _safe_next_url(request)
                if safe_next:
                    return redirect(safe_next)
                return redirect('auth_system:dashboard')
            else:
                messages.error(request, 'Invalid email/username or password. Please try again.')

    return render(request, 'auth_system/login.html', {'form': form})


@require_http_methods(['GET', 'POST'])
def logout_view(request):
    """Customer logout view.

    GET  → confirmation page
    POST → destroys session and redirects to login
    """
    if request.method == 'POST':
        logout(request)
        messages.success(request, 'You have been signed out successfully.')
        return redirect('auth_system:login')

    return render(request, 'auth_system/logout_confirm.html')


@never_cache
@require_http_methods(['GET', 'POST'])
def signup_view(request):
    """Customer registration view."""
    if request.user.is_authenticated:
        return redirect('auth_system:dashboard')

    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend='auth_system.backends.EmailOrUsernameBackend')
            messages.success(
                request,
                f'Account created! Welcome to PRODRIVE, {user.get_short_name()}.',
            )
            return redirect('auth_system:dashboard')
    else:
        form = SignupForm()

    return render(request, 'auth_system/signup.html', {'form': form})


@never_cache
@login_required
def dashboard_view(request):
    """Customer dashboard – requires authentication."""
    return render(request, 'auth_system/dashboard.html', {'customer': request.user})
