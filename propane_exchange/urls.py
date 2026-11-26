from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path(settings.ADMIN_URL, admin.site.urls),
    # One sign-in and sign-up page for the whole site; allauth still handles Google
    path('accounts/login/', RedirectView.as_view(pattern_name='login', query_string=True)),
    path('accounts/signup/', RedirectView.as_view(pattern_name='signup', query_string=True)),
    path('accounts/', include('allauth.urls')),
    path('', include('store.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
