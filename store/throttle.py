"""Small cache-backed limiter for login attempts.

Counts failed logins per (username, client IP) and per IP. Once a limit is
hit, further attempts are refused until the window passes. The default cache
is per-process, which is enough to slow down password guessing on a small
deployment; point CACHES at Redis/Memcached to share counts across workers.
"""
import hashlib

from django.core.cache import cache

WINDOW_SECONDS = 15 * 60
MAX_PER_ACCOUNT = 5
MAX_PER_IP = 20


def client_ip(request):
    # Render's proxy appends the real client address as the last entry;
    # anything before it could have been supplied by the client.
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[-1].strip()
    return request.META.get('REMOTE_ADDR', '')


def _key(*parts):
    digest = hashlib.sha256('|'.join(parts).encode()).hexdigest()[:32]
    return f'login-fail:{digest}'


def _keys(request, username):
    ip = client_ip(request)
    return (
        (_key('acct', (username or '').strip().lower(), ip), MAX_PER_ACCOUNT),
        (_key('ip', ip), MAX_PER_IP),
    )


def is_locked(request, username):
    return any(cache.get(key, 0) >= limit for key, limit in _keys(request, username))


def record_failure(request, username):
    for key, _limit in _keys(request, username):
        if cache.add(key, 1, WINDOW_SECONDS):
            continue
        try:
            cache.incr(key)
        except ValueError:
            cache.set(key, 1, WINDOW_SECONDS)


def reset(request, username):
    cache.delete(_keys(request, username)[0][0])
