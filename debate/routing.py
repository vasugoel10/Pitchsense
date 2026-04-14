"""
WebSocket URL routing for the debate app.
"""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/debate/(?P<session_id>[0-9a-f-]+)/$', consumers.DebateConsumer.as_asgi()),
]
