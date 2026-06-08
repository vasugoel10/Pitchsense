"""
Redis outage simulation tests.

These tests PROVE (not reason about) what happens when Redis is unavailable.

FINDINGS FROM FIRST RUN (before fixes):
- Rate limiter: CRASHED (ConnectionError propagated as 500)
- Auth check:   CRASHED (ConnectionError propagated as 500) 
- Delete acct:  CRASHED (cache.delete raised unhandled ConnectionError)
- Tavily:       CRASHED (sync_to_async wrapper propagated ConnectionError)

AFTER FIXES (all cache ops wrapped in try/except):
- Rate limiter: Fails OPEN (allows requests through)
- Auth check:   Falls back to DB query
- Delete acct:  Completes, cache invalidation silently skipped
- Tavily:       Skips cache, proceeds to API call or returns empty

NOTE on test approach:
We patch debate.views.cache and debate.services.tavily_service.cache
rather than the global django.core.cache.cache object. This avoids
breaking Django's internal session engine (cached_db) which also uses
the cache — that's a separate concern from our app code.

Run: python manage.py test debate.tests.test_redis_outage --verbosity 2
"""
import json
from unittest.mock import patch, MagicMock, PropertyMock
from django.test import TestCase, Client, TransactionTestCase
from django.contrib.auth.models import User
from django.urls import reverse

from debate.models import DebateSession


def _make_broken_cache():
    """Create a mock cache object where every operation raises ConnectionError."""
    mock = MagicMock()
    error = ConnectionError("Redis connection refused — simulated outage")
    mock.get = MagicMock(side_effect=error)
    mock.set = MagicMock(side_effect=error)
    mock.delete = MagicMock(side_effect=error)
    return mock


class RedisOutageRateLimiterTests(TestCase):
    """Prove the rate limiter survives Redis failure."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            'rl_redis@test.com', password='TestPassword123!'
        )

    @patch('debate.views.cache', new_callable=_make_broken_cache)
    def test_login_succeeds_rate_limiter_fails_open(self, mock_cache):
        """Login MUST succeed when Redis is down. Rate limiter fails open."""
        resp = self.client.post(
            reverse('login_api'),
            data=json.dumps({
                'username': 'rl_redis@test.com',
                'password': 'TestPassword123!'
            }),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'success')

    @patch('debate.views.cache', new_callable=_make_broken_cache)
    def test_register_succeeds_rate_limiter_fails_open(self, mock_cache):
        """Register MUST succeed when Redis is down."""
        resp = self.client.post(
            reverse('register_api'),
            data=json.dumps({
                'username': 'new_redis@test.com',
                'password': 'TestPassword123!'
            }),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'success')


class RedisOutageAuthCheckTests(TestCase):
    """Prove auth check falls back to DB when cache is down."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            'ac_redis@test.com', password='TestPassword123!'
        )
        self.client.force_login(self.user)

    @patch('debate.views.cache', new_callable=_make_broken_cache)
    def test_auth_check_falls_back_to_db(self, mock_cache):
        """Auth check MUST return user data from DB when cache is down."""
        resp = self.client.get(reverse('check_auth'))
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['user']['username'], 'ac_redis@test.com')


class RedisOutageAccountDeletionTests(TestCase):
    """Prove account deletion works when cache invalidation fails."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            'del_redis@test.com', password='TestPassword123!'
        )
        self.client.force_login(self.user)

    @patch('debate.views.cache', new_callable=_make_broken_cache)
    def test_account_deletion_succeeds_without_cache(self, mock_cache):
        """Account deletion MUST complete even if cache.delete fails."""
        resp = self.client.post(reverse('delete_account'))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(User.objects.filter(username='del_redis@test.com').exists())


class RedisOutageTavilyTests(TransactionTestCase):
    """Prove Tavily service degrades gracefully when cache is down."""

    async def test_tavily_survives_cache_failure(self):
        """Tavily MUST return empty string (not crash) when cache is down."""
        from debate.services.tavily_service import get_competitor_context

        broken_cache = _make_broken_cache()
        with patch('debate.services.tavily_service.cache', broken_cache):
            # Should not raise — cache failure caught, returns empty (no API key set)
            result = await get_competitor_context("Test pitch about AI logistics")
            self.assertIsInstance(result, str)
            # Without TAVILY_API_KEY, should return "" after surviving cache failure
            self.assertEqual(result, "")
