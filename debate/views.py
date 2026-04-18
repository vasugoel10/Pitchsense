"""
Views for the debate app.
Serves test pages and will serve the React frontend in Phase 5.
"""
from django.shortcuts import render
from django.http import HttpResponse
from django.conf import settings
import os

def react_app(request):
    """Serves the built React SPA."""
    try:
        with open(os.path.join(settings.BASE_DIR, 'frontend', 'build', 'index.html')) as f:
            return HttpResponse(f.read())
    except FileNotFoundError:
        return HttpResponse("React build not found. Please run npm run build in frontend directory.", status=404)
