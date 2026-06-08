from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
# pyrefly: ignore [missing-import]
from rest_framework import serializers

class UserSerializer(serializers.ModelSerializer):
    is_admin = serializers.BooleanField(source='is_superuser', read_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'is_admin')

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, validators=[validate_password])
    
    class Meta:
        model = User
        fields = ('username', 'password')

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data['username'],
            password=validated_data['password']
        )
        return user
