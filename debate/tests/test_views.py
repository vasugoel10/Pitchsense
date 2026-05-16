import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from unittest.mock import patch


class AuthTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.register_url = reverse('register_api')
        self.login_url = reverse('login_api')
        self.check_auth_url = reverse('check_auth')

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
