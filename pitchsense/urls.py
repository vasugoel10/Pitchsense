"""
URL configuration for pitchsense project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, re_path
from debate import views

urlpatterns = [
    # Obscured admin URL — bots scan /admin/ by default
    path('mgmt-console-7x9k/', admin.site.urls),
    path('api/csrf/', views.csrf_token, name='csrf_token'),
    path('api/login/', views.login_api, name='login_api'),
    path('api/register/', views.register_api, name='register_api'),
    path('api/auth-check/', views.check_auth, name='check_auth'),
    path('api/logout/', views.logout_api, name='logout_api'),
    path('api/delete-account/', views.delete_account_api, name='delete_account'),
    path('api/admin/sessions/', views.admin_sessions_api, name='admin_sessions'),
    re_path(r'^.*$', views.react_app, name='react-app'),
]
