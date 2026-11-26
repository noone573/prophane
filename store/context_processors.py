from .models import Notification


def navigation(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}
    profile = getattr(user, 'profile', None)
    return {
        'user_role': profile.role if profile else 'customer',
        'user_status': profile.status if profile else 'approved',
        'unread_count': Notification.objects.filter(user=user, is_read=False).count(),
    }
