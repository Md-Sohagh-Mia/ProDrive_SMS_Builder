from django.contrib import auth, messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import LoginForm, SignupForm


def login_view(request):
    """Display and process the customer login form."""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    form = LoginForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email']
        password = form.cleaned_data['password']
        remember_me = form.cleaned_data.get('remember_me', False)

        user = auth.authenticate(request, username=email, password=password)
        if user is not None:
            auth.login(request, user)
            if not remember_me:
                # Session expires when the browser is closed
                request.session.set_expiry(0)
            messages.success(request, f'Welcome back, {user.get_short_name()}!')
            next_url = request.GET.get('next') or request.POST.get('next', '')
            # Validate the redirect target to prevent open-redirect attacks.
            if next_url and url_has_allowed_host_and_scheme(
                url=next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            return redirect('accounts:dashboard')
        else:
            messages.error(request, 'Invalid email address or password. Please try again.')

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    """Log the customer out and redirect to the login page."""
    if request.method == 'POST':
        auth.logout(request)
        messages.success(request, 'You have been signed out successfully.')
        return redirect('accounts:login')
    # GET request: show confirmation page
    return render(request, 'accounts/logout_confirm.html')


def signup_view(request):
    """Display and process the customer registration form."""
    if request.user.is_authenticated:
        return redirect('accounts:dashboard')

    form = SignupForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        customer = form.save()
        # Log the new customer in immediately
        auth.login(request, customer, backend='accounts.backends.EmailBackend')
        messages.success(request, 'Your account has been created. Welcome to PRODRIVE!')
        return redirect('accounts:dashboard')

    return render(request, 'accounts/signup.html', {'form': form})


@login_required
def dashboard_view(request):
    """Customer dashboard – requires authentication."""
    return render(request, 'accounts/dashboard.html', {'customer': request.user})
