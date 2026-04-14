"""
Views for the debate app.
Serves test pages and will serve the React frontend in Phase 5.
"""
from django.shortcuts import render


def ws_test(request):
    """WebSocket test page for verifying the connection handshake."""
    return render(request, 'ws_test.html')
