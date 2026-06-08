"""
Views for the debate app.
Phase 7: Hardened with CSRF protection, rate limiting, and server-side auth.
"""
import json
import time
import logging
import functools
import hashlib
from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST, require_GET
from django.core.cache import cache
import os

logger = logging.getLogger(__name__)

from .models import DebateSession, GlobalTranscript


# ── Rate Limiting (cache-backed, per-IP) ─────────────────────────────────
# Uses Django's cache framework (Redis in prod, LocMem in dev).
# Survives process restarts and works across multiple Daphne workers.

def rate_limit(max_requests=5, window_seconds=60):
    """Decorator: limit requests per IP to max_requests within window_seconds.
    
    Uses a sliding window log stored in the cache backend. Each IP gets a
    cache key containing a list of request timestamps. Expired timestamps
    are pruned on each request.

    Fails OPEN on cache failure: if Redis is down, requests pass through
    rather than blocking all users. This trades rate-limit enforcement
    for availability during outages.
    """
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            ip = _get_client_ip(request)
            cache_key = f'rl:{view_func.__name__}:{ip}'
            now = time.time()

            try:
                # Fetch existing timestamps from cache
                timestamps = cache.get(cache_key, [])

                # Prune timestamps outside the current window
                timestamps = [t for t in timestamps if now - t < window_seconds]

                if len(timestamps) >= max_requests:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'Too many requests. Try again in {window_seconds} seconds.'
                    }, status=429)

                timestamps.append(now)
                cache.set(cache_key, timestamps, timeout=window_seconds)
            except Exception:
                # Redis down — fail OPEN (allow request through)
                logger.warning('Rate limiter cache unavailable — failing open for %s', ip)

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

def _get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '0.0.0.0')


# ── SPA Serving ──────────────────────────────────────────────────────────

def react_app(request):
    """Serves the built React SPA."""
    try:
        with open(os.path.join(settings.BASE_DIR, 'frontend', 'build', 'index.html')) as f:
            return HttpResponse(f.read())
    except FileNotFoundError:
        return HttpResponse(
            "React build not found. Please run npm run build in frontend directory.",
            status=404
        )


# ── CSRF Token ───────────────────────────────────────────────────────────

@ensure_csrf_cookie
@require_GET
def csrf_token(request):
    """
    Sets the CSRF cookie on the browser and returns 200.
    The React frontend calls this once on mount so that subsequent
    POST requests can include the X-CSRFToken header.
    """
    return JsonResponse({'status': 'ok'})


# ── Authentication Endpoints ─────────────────────────────────────────────

@require_POST
@rate_limit(max_requests=10, window_seconds=60)
def login_api(request):
    try:
        data = json.loads(request.body)
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return JsonResponse({
                'status': 'error',
                'message': 'Email and password are required.'
            }, status=400)
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return JsonResponse({
                'status': 'success', 
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'is_admin': user.is_superuser
                }
            })
        else:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid credentials'
            }, status=401)
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid request body.'
        }, status=400)
    except Exception as e:
        logger.error(f'Login error: {e}', exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'An unexpected error occurred.'
        }, status=500)


@require_POST
@rate_limit(max_requests=5, window_seconds=60)
def register_api(request):
    try:
        data = json.loads(request.body)
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return JsonResponse({
                'status': 'error',
                'message': 'Email and password are required.'
            }, status=400)
        
        # Use Django's password validators (min 8 chars, not common, not all numeric)
        try:
            validate_password(password)
        except ValidationError as e:
            return JsonResponse({
                'status': 'error',
                'message': ' '.join(e.messages)
            }, status=400)

        if User.objects.filter(username=username).exists():
            return JsonResponse({
                'status': 'error',
                'message': 'An account with this email already exists.'
            }, status=400)
            
        user = User.objects.create_user(username=username, password=password)
            
        login(request, user)
        return JsonResponse({
            'status': 'success', 
            'user': {
                'id': user.id,
                'username': user.username,
                'is_admin': user.is_superuser
            }
        })
    except json.JSONDecodeError:
        return JsonResponse({
            'status': 'error',
            'message': 'Invalid request body.'
        }, status=400)
    except Exception as e:
        logger.error(f'Registration error: {e}', exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': 'An unexpected error occurred.'
        }, status=500)


# ── Server-side Auth State ───────────────────────────────────────────────

@require_GET
def check_auth(request):
    """
    Returns the current user's auth state from the server session.
    The frontend calls this on mount instead of trusting sessionStorage.

    Cached for 30 seconds per user to avoid a DB hit on every poll.
    """
    if request.user.is_authenticated:
        cache_key = f'auth_check:{request.user.id}'
        try:
            cached = cache.get(cache_key)
            if cached:
                return JsonResponse(cached)
        except Exception:
            logger.warning('Auth check cache unavailable — falling back to DB')

        pitch_count = DebateSession.objects.filter(user=request.user).count()
        response_data = {
            'status': 'success',
            'user': {
                'id': request.user.id,
                'username': request.user.username,
                'is_admin': request.user.is_superuser,
                'pitch_count': pitch_count,
            }
        }
        try:
            cache.set(cache_key, response_data, timeout=30)
        except Exception:
            pass  # Cache write failure is non-critical
        return JsonResponse(response_data)
    return JsonResponse({
        'status': 'error',
        'message': 'Not authenticated'
    }, status=401)


@require_POST
def logout_api(request):
    logout(request)
    return JsonResponse({'status': 'success'})


# ── Account Deletion (GDPR/CCPA) ────────────────────────────────────────

@require_POST
def delete_account_api(request):
    """Permanently delete the logged-in user and all associated data."""
    if not request.user.is_authenticated:
        return JsonResponse({
            'status': 'error',
            'message': 'Not authenticated'
        }, status=401)
    
    user = request.user
    # Invalidate auth cache before deletion — non-critical if cache is down
    try:
        cache.delete(f'auth_check:{user.id}')
    except Exception:
        pass
    # Cascade delete will remove DebateSession + GlobalTranscript
    user.delete()
    return JsonResponse({'status': 'success', 'message': 'Account permanently deleted.'})


# ── Admin Endpoints ──────────────────────────────────────────────────────

@require_GET
def admin_sessions_api(request):
    if not request.user.is_authenticated or not request.user.is_superuser:
        return JsonResponse({
            'status': 'error',
            'message': 'Unauthorized'
        }, status=403)
        
    sessions = DebateSession.objects.select_related('user').all().order_by('-current_turn')
    
    session_list = []
    for s in sessions:
        session_list.append({
            'id': str(s.id),
            'username': s.user.username if s.user else 'Anonymous',
            'status': s.status,
            'current_turn': s.current_turn,
            'scorecard': s.scorecard is not None
        })
        
    return JsonResponse({'status': 'success', 'sessions': session_list})
