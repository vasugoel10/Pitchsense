from django.contrib import admin
from .models import DebateSession, GlobalTranscript


@admin.register(DebateSession)
class DebateSessionAdmin(admin.ModelAdmin):
    list_display = ['id', 'status', 'current_turn', 'pitch_topic', 'created_at']
    list_filter = ['status']
    readonly_fields = ['id', 'created_at', 'updated_at']


@admin.register(GlobalTranscript)
class GlobalTranscriptAdmin(admin.ModelAdmin):
    list_display = ['id', 'session', 'role', 'turn_number', 'created_at']
    list_filter = ['role', 'turn_number']
    readonly_fields = ['id', 'created_at']
