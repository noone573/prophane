from django.conf import settings


class SecurityHeadersMiddleware:
    """Adds a Content-Security-Policy and Permissions-Policy to every page.

    Django 5.2 has no built-in CSP support. The policy only allows scripts and
    styles from this site and the pinned Leaflet build on unpkg, so injected
    markup can't run inline scripts or load code from elsewhere.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self.csp = '; '.join(f'{name} {" ".join(values)}' for name, values in settings.CONTENT_SECURITY_POLICY.items())
        self.permissions = settings.PERMISSIONS_POLICY
        self.skip_prefixes = tuple(settings.CSP_EXEMPT_PATHS)

    def __call__(self, request):
        response = self.get_response(request)
        if not request.path.startswith(self.skip_prefixes):
            response.headers.setdefault('Content-Security-Policy', self.csp)
        response.headers.setdefault('Permissions-Policy', self.permissions)
        response.headers.setdefault('Cross-Origin-Resource-Policy', 'same-origin')
        return response
