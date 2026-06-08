"""
WebSocket + HTTP Load Test for PitchSense.

Answers the question: "How many concurrent users can one Daphne process handle?"

Usage:
    1. Start the dev server:    python manage.py runserver 8000
    2. Install locust:          pip install locust
    3. Run:                     locust -f scripts/load_test.py --host=http://127.0.0.1:8000
    4. Open browser:            http://localhost:8089
    5. Set users + spawn rate, click Start

What this tests:
    - HTTP: login, auth-check, CSRF token endpoint
    - WebSocket: connect, send pitch, receive streaming responses
    - Concurrent load: how many users before response times degrade

Key metrics to watch:
    - Response time P95 > 1s = degradation starting
    - Response time P99 > 3s = under serious load
    - Failures > 0% = capacity exceeded
    - RPS (requests per second) = throughput ceiling
"""
import json
import time
import uuid
import logging

from locust import HttpUser, task, between, events
from locust.exception import StopUser

logger = logging.getLogger(__name__)


class PitchSenseHTTPUser(HttpUser):
    """Simulates a user interacting with the HTTP API."""
    wait_time = between(1, 3)
    
    def on_start(self):
        """Register a unique user and log in."""
        self.username = f"loadtest_{uuid.uuid4().hex[:12]}@test.com"
        self.password = "LoadTest123!!"
        
        # Get CSRF cookie
        resp = self.client.get("/api/csrf/")
        if resp.status_code != 200:
            raise StopUser()
        
        # Register
        csrf_token = resp.cookies.get('csrftoken', '')
        resp = self.client.post(
            "/api/register/",
            json={"username": self.username, "password": self.password},
            headers={"X-CSRFToken": csrf_token},
        )
        if resp.status_code == 429:
            logger.warning("Rate limited during registration — adjust rate limits for load testing")
            raise StopUser()
        if resp.status_code != 200:
            logger.error(f"Registration failed: {resp.status_code} {resp.text}")
            raise StopUser()

    @task(5)
    def check_auth(self):
        """Most common frontend call — happens on every page mount."""
        self.client.get("/api/auth-check/", name="/api/auth-check/")

    @task(2)
    def get_csrf(self):
        """CSRF token fetch."""
        self.client.get("/api/csrf/", name="/api/csrf/")

    @task(1)
    def login_flow(self):
        """Full login cycle."""
        # Get fresh CSRF
        resp = self.client.get("/api/csrf/")
        csrf = resp.cookies.get('csrftoken', '')
        
        # Logout first
        self.client.post(
            "/api/logout/",
            headers={"X-CSRFToken": csrf},
            name="/api/logout/"
        )
        
        # Login
        self.client.post(
            "/api/login/",
            json={"username": self.username, "password": self.password},
            headers={"X-CSRFToken": csrf},
            name="/api/login/"
        )
