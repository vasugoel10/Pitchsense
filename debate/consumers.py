"""
WebSocket consumer for PitchSense debate sessions.

Handles:
- Connection lifecycle with DebateSession creation
- Message routing (user pitch input → persona responses)
- Streaming LLM chunks to the client (Phase 2)
"""
import json
import uuid
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import DebateSession, GlobalTranscript


class DebateConsumer(AsyncWebsocketConsumer):
    """
    Async WebSocket consumer for PitchSense debate sessions.

    Protocol:
    - Client connects to ws/debate/<session_id>/
    - Client sends: {"type": "user_pitch", "content": "<transcribed speech>"}
    - Server responds with persona streaming chunks (Phase 2)
    """

    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']

        # Create or get the debate session
        self.debate_session = await self._get_or_create_session()

        await self.accept()
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'session_id': str(self.debate_session.id),
            'status': self.debate_session.status,
            'current_turn': self.debate_session.current_turn,
            'message': 'Connected to PitchSense debate session.',
        }))

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type', 'unknown')

        if message_type == 'user_pitch':
            content = data.get('content', '').strip()
            if not content:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Empty pitch content.',
                }))
                return

            # Advance turn and record user's pitch
            turn = await self._advance_turn()
            await self._append_transcript('user', content, turn)

            await self.send(text_data=json.dumps({
                'type': 'turn_started',
                'turn': turn,
                'user_content': content,
                'message': f'Turn {turn}/5 started. Persona responses coming in Phase 2.',
            }))

        elif message_type == 'ping':
            await self.send(text_data=json.dumps({
                'type': 'pong',
                'session_id': str(self.debate_session.id),
            }))

        else:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Unknown message type: {message_type}',
            }))

    async def disconnect(self, close_code):
        pass

    # ── Database helpers ──────────────────────────────────────────────

    @database_sync_to_async
    def _get_or_create_session(self):
        """Get existing session or create a new one."""
        try:
            session_uuid = uuid.UUID(self.session_id)
            session, created = DebateSession.objects.get_or_create(id=session_uuid)
            return session
        except (ValueError, DebateSession.DoesNotExist):
            return DebateSession.objects.create()

    @database_sync_to_async
    def _advance_turn(self):
        """Increment the turn counter and return the new turn number."""
        from django.db import transaction
        with transaction.atomic():
            session = DebateSession.objects.select_for_update().get(pk=self.debate_session.id)
            session.current_turn += 1
            if session.status == 'waiting':
                session.status = 'active'
            session.save()
            self.debate_session = session
            return session.current_turn

    @database_sync_to_async
    def _append_transcript(self, role, content, turn_number, metadata=None):
        """Append an entry to the shared GlobalTranscript."""
        return GlobalTranscript.append_entry(
            session_id=self.debate_session.id,
            role=role,
            content=content,
            turn_number=turn_number,
            metadata=metadata,
        )
