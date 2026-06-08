import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.cache import cache
from unittest.mock import patch

from debate.models import DebateSession


class AuthTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.register_url = reverse('register_api')
        self.login_url = reverse('login_api')
        self.check_auth_url = reverse('check_auth')
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_register_creates_user(self):
        resp = self.client.post(
            self.register_url,
            data=json.dumps({"username": "test@test.com", "password": "TestPassword123!"}),
            content_type="application/json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(User.objects.filter(username="test@test.com").exists())
        self.assertEqual(resp.json()['status'], 'success')

    def test_register_duplicate_email_fails(self):
        User.objects.create_user("test@test.com", password="TestPassword123!")
        resp = self.client.post(
            self.register_url,
            data=json.dumps({"username": "test@test.com", "password": "AnotherPassword1!"}),
            content_type="application/json"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['status'], 'error')
        self.assertIn('already exists', resp.json()['message'])

    def test_register_weak_password_fails(self):
        resp = self.client.post(
            self.register_url,
            data=json.dumps({"username": "weak@test.com", "password": "123"}),
            content_type="application/json"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['status'], 'error')
        self.assertIn('too short', resp.json()['message'].lower())

    def test_login_success(self):
        User.objects.create_user("login@test.com", password="CorrectPassword123!")
        resp = self.client.post(
            self.login_url,
            data=json.dumps({"username": "login@test.com", "password": "CorrectPassword123!"}),
            content_type="application/json"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'success')

    def test_login_wrong_password(self):
        User.objects.create_user("wrong@test.com", password="CorrectPassword123!")
        resp = self.client.post(
            self.login_url,
            data=json.dumps({"username": "wrong@test.com", "password": "WrongPassword1!"}),
            content_type="application/json"
        )
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.json()['status'], 'error')

    def test_auth_check_unauthenticated(self):
        resp = self.client.get(self.check_auth_url)
        self.assertEqual(resp.status_code, 401)

    def test_auth_check_authenticated(self):
        user = User.objects.create_user("check@test.com", password="TestPassword123!")
        self.client.force_login(user)
        resp = self.client.get(self.check_auth_url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['user']['username'], "check@test.com")
        self.assertFalse(resp.json()['user']['is_admin'])

    def test_admin_access_unauthorized(self):
        # Create normal user
        user = User.objects.create_user("normal@test.com", password="TestPassword123!")
        self.client.force_login(user)
        resp = self.client.get(reverse('admin_sessions'))
        self.assertEqual(resp.status_code, 403)

    def test_admin_access_authorized(self):
        # Create superuser
        admin = User.objects.create_superuser("admin@test.com", "admin@test.com", "AdminPassword123!")
        self.client.force_login(admin)
        resp = self.client.get(reverse('admin_sessions'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['status'], 'success')


class RateLimitTests(TestCase):
    """Test the cache-backed rate limiter."""

    def setUp(self):
        self.client = Client()
        self.register_url = reverse('register_api')
        self.login_url = reverse('login_api')
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_login_rate_limit_triggers_after_10_requests(self):
        """Login allows 10 requests per minute, 11th should be blocked."""
        User.objects.create_user("rl@test.com", password="TestPassword123!")
        payload = json.dumps({"username": "rl@test.com", "password": "WrongPassword1!"})

        for i in range(10):
            resp = self.client.post(
                self.login_url, data=payload, content_type="application/json"
            )
            # These may be 401 (wrong password) but should NOT be 429
            self.assertNotEqual(resp.status_code, 429, f"Request {i+1} was rate-limited too early")

        # 11th request should be rate-limited
        resp = self.client.post(
            self.login_url, data=payload, content_type="application/json"
        )
        self.assertEqual(resp.status_code, 429)
        self.assertIn('Too many requests', resp.json()['message'])

    def test_register_rate_limit_triggers_after_5_requests(self):
        """Register allows 5 requests per minute, 6th should be blocked."""
        for i in range(5):
            payload = json.dumps({
                "username": f"user{i}@test.com",
                "password": "TestPassword123!"
            })
            resp = self.client.post(
                self.register_url, data=payload, content_type="application/json"
            )
            self.assertNotEqual(resp.status_code, 429, f"Request {i+1} was rate-limited too early")

        # 6th request should be rate-limited
        resp = self.client.post(
            self.register_url,
            data=json.dumps({"username": "extra@test.com", "password": "TestPassword123!"}),
            content_type="application/json"
        )
        self.assertEqual(resp.status_code, 429)


class AuthCheckCachingTests(TestCase):
    """Test that auth-check responses are cached."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("cached@test.com", password="TestPassword123!")
        self.client.force_login(self.user)
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_auth_check_caches_response(self):
        """Second auth-check call should return cached data without DB hit."""
        resp1 = self.client.get(reverse('check_auth'))
        self.assertEqual(resp1.status_code, 200)

        # The cache should now have the response
        cached = cache.get(f'auth_check:{self.user.id}')
        self.assertIsNotNone(cached)
        self.assertEqual(cached['user']['username'], 'cached@test.com')

    def test_delete_account_invalidates_cache(self):
        """Deleting account should clear the auth cache."""
        # Populate cache
        self.client.get(reverse('check_auth'))
        self.assertIsNotNone(cache.get(f'auth_check:{self.user.id}'))

        # Delete account
        self.client.post(reverse('delete_account'))

        # Cache should be cleared
        self.assertIsNone(cache.get(f'auth_check:{self.user.id}'))

    def test_auth_check_returns_pitch_count(self):
        """Auth check should include the user's pitch count."""
        DebateSession.objects.create(user=self.user)
        DebateSession.objects.create(user=self.user)

        # Clear cache to force fresh DB query
        cache.clear()
        resp = self.client.get(reverse('check_auth'))
        self.assertEqual(resp.json()['user']['pitch_count'], 2)
