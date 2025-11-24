from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps

def seller_required(view_func):
    """Decorator to restrict access to approved sellers only"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Please log in to access this page.")
            return redirect('login')
        
        profile = request.user.profile
        if profile.role != 'seller' or profile.status != 'approved':
            messages.error(request, "You must be an approved seller to access this page.")
            return redirect('dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper

def admin_required(view_func):
    """Decorator to restrict access to admins only"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Please log in to access this page.")
            return redirect('login')
        
        profile = request.user.profile
        if profile.role != 'admin':
            messages.error(request, "Admin access required.")
            return redirect('dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper

def customer_only(view_func):
    """Decorator to restrict access to customers only"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, "Please log in to access this page.")
            return redirect('login')
        
        profile = request.user.profile
        if profile.role not in ['customer', 'seller', 'admin']:
            messages.error(request, "Invalid user role.")
            return redirect('dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper