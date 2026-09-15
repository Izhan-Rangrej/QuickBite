from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    PasswordChangeView,
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import LoginForm, ProfileForm, SignupForm


# ---------- helpers ----------

def _safe_next(request):
    """Validated `?next=` target, else the default redirect."""
    next_url = request.GET.get('next') or request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(
            next_url, allowed_hosts={request.get_host()},
            require_https=request.is_secure()):
        return next_url
    return settings.LOGIN_REDIRECT_URL


# ---------- login rate limiting (Phase 10) ----------

def _client_ip(request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def _login_attempts_key(request):
    return f'quickbite:login_attempts:{_client_ip(request)}'


# ---------- signup / login / logout ----------

def signup(request):
    if request.user.is_authenticated:
        return redirect('core:home')

    form = SignupForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        auth_login(request, user)  # auto-login after signup
        from cart.service import merge_session_cart
        merge_session_cart(user, request.session)  # keep any guest cart
        messages.success(request, f'Welcome to QuickBite, {user.username}! 🎉 Your account is ready.')
        return redirect('core:home')

    return render(request, 'accounts/signup.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:home')

    from django.core.cache import cache

    attempts_key = _login_attempts_key(request)
    limit = getattr(settings, 'LOGIN_ATTEMPT_LIMIT', 5)
    window = getattr(settings, 'LOGIN_ATTEMPT_WINDOW', 600)

    if request.method == 'POST':
        attempts = cache.get(attempts_key, 0)
        if attempts >= limit:
            messages.error(
                request,
                f'Too many failed login attempts. Please wait a few minutes '
                f'({limit} attempts per {window // 60} minutes).')
            return render(request, 'accounts/login.html',
                          {'form': LoginForm(request), 'rate_limited': True})

    form = LoginForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        auth_login(request, user)
        cache.delete(attempts_key)  # successful login resets the counter

        # "Remember me": 2 weeks when checked, browser session otherwise
        if form.cleaned_data.get('remember_me'):
            request.session.set_expiry(60 * 60 * 24 * 14)
        else:
            request.session.set_expiry(0)

        # Fold the guest's session cart into the user's persistent cart
        from cart.service import merge_session_cart
        merge_session_cart(user, request.session)

        messages.success(request, f'Welcome back, {user.username}! 👋')
        return redirect(_safe_next(request))

    if request.method == 'POST' and not form.is_valid():
        attempts = cache.get(attempts_key, 0) + 1
        cache.set(attempts_key, attempts, window)
        remaining = limit - attempts
        if 0 < remaining <= 3:
            messages.error(request, f'{remaining} login attempt{"s" if remaining > 1 else ""} '
                                    f'remaining before a temporary lockout.')

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    """POST-only logout (CSRF-protected)."""
    if request.method == 'POST':
        auth_logout(request)
        messages.info(request, 'You have been logged out. See you soon! 🍔')
    return redirect('core:home')


# ---------- profile ----------

@login_required
def profile(request):
    return render(request, 'accounts/profile.html')


@login_required
def profile_edit(request):
    form = ProfileForm(request.POST or None, request.FILES or None,
                       instance=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Profile updated successfully! ✅')
        return redirect('accounts:profile')

    return render(request, 'accounts/profile_edit.html', {'form': form})


# ---------- password change (built-in view + flash message) ----------

class QuickBitePasswordChangeView(PasswordChangeView):
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('accounts:profile')

    def form_valid(self, form):
        messages.success(self.request, 'Password changed successfully! 🔒')
        return super().form_valid(form)


# ---------- password reset (built-in views + themed templates) ----------

class QuickBitePasswordResetView(PasswordResetView):
    template_name = 'accounts/password_reset_form.html'
    email_template_name = 'accounts/password_reset_email.txt'
    subject_template_name = 'accounts/password_reset_subject.txt'
    success_url = reverse_lazy('accounts:password_reset_done')


class QuickBitePasswordResetDoneView(PasswordResetDoneView):
    template_name = 'accounts/password_reset_done.html'


class QuickBitePasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'accounts/password_reset_confirm.html'
    success_url = reverse_lazy('accounts:password_reset_complete')

    def form_valid(self, form):
        messages.success(self.request, 'Password reset complete — you can log in now! 🎉')
        return super().form_valid(form)


class QuickBitePasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'accounts/password_reset_complete.html'
