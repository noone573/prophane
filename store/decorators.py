from functools import wraps

from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.shortcuts import redirect


def _role_required(check, denied_message):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            profile = getattr(request.user, 'profile', None)
            if profile is None or not check(profile):
                messages.error(request, denied_message)
                return redirect('dashboard')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


seller_required = _role_required(
    lambda p: p.role == 'seller' and p.status == 'approved',
    'Only approved sellers can open that page.',
)

admin_required = _role_required(
    lambda p: p.role == 'admin',
    'Only administrators can open that page.',
)
