"""
REST Framework API views for PitchSense.

STATUS: DEPRECATED — These endpoints are NOT wired into urls.py.
Authentication is handled by the session-based views in views.py.

This file is retained for reference only. If you need DRF/JWT endpoints
in the future, wire these into pitchsense/urls.py and re-add
'rest_framework_simplejwt' to INSTALLED_APPS.

To remove this dead code entirely, delete this file and serializers.py,
then remove 'rest_framework' from INSTALLED_APPS if no longer needed.
"""
# pyrefly: ignore [missing-import]
from rest_framework import generics, status
# pyrefly: ignore [missing-import]
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from django.contrib.auth.models import User
from .serializers import UserSerializer, RegisterSerializer
from .models import DebateSession


class RegisterView(generics.CreateAPIView):
    """DRF registration endpoint — NOT ACTIVE. See views.register_api() instead."""
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                'status': 'success',
                'user': UserSerializer(user).data,
            }, status=status.HTTP_201_CREATED)
        
        # Flatten DRF errors into a simple message for the frontend
        error_messages = []
        for field, errors in serializer.errors.items():
            for error in errors:
                error_messages.append(f"{field}: {error}" if field != "non_field_errors" else error)
        
        return Response({
            'status': 'error',
            'message': ' '.join(error_messages)
        }, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user(request):
    """DRF current user endpoint — NOT ACTIVE. See views.check_auth() instead."""
    user = request.user
    pitch_count = DebateSession.objects.filter(user=user).count()
    user_data = UserSerializer(user).data
    user_data['pitch_count'] = pitch_count
    return Response({
        'status': 'success',
        'user': user_data
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def delete_account(request):
    """DRF account deletion — NOT ACTIVE. See views.delete_account_api() instead."""
    user = request.user
    user.delete()
    return Response({'status': 'success', 'message': 'Account permanently deleted.'})
