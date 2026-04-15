"""
WebSocket consumer for PitchSense debate sessions.

Handles:
- Connection lifecycle with DebateSession creation
- User pitch input → 3 AI persona responses (streamed via Groq)
- Real-time chunk-by-chunk streaming to the client
- Turn management (5 turns per debate)
"""
import json
import uuid
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import DebateSession, GlobalTranscript
from .personas import PERSONAS, PERSONA_ORDER
from .services.groq_service import stream_persona_response

logger = logging.getLogger(__name__)


class DebateConsumer(AsyncWebsocketConsumer):
    """
    Async WebSocket consumer for PitchSense debate sessions.

    Protocol (client ↔ server):
    ─────────────────────────────────────────────────────────────
    Client sends:
      {"type": "user_pitch", "content": "<transcribed speech>"}

    Server responds (per persona, in sequence):
      {"type": "persona_start", "persona": "investor", "turn": 1, "name": "Ava Chen", "emoji": "🏦"}
      {"type": "persona_chunk", "persona": "investor", "content": "chunk...", "turn": 1}
      {"type": "persona_chunk", "persona": "investor", "content": "more...", "turn": 1}
      {"type": "persona_done", "persona": "investor", "turn": 1, "full_content": "..."}
      ... (repeat for customer, competitor)
      {"type": "turn_complete", "turn": 1, "is_final": false}
    ─────────────────────────────────────────────────────────────
    """

    async def connect(self):
        self.session_id = self.scope['url_route']['kwargs']['session_id']
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
            await self._handle_user_pitch(data)

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

    # ── Core debate logic ─────────────────────────────────────────────

    async def _handle_user_pitch(self, data):
        """Handle a user's pitch input and trigger all persona responses."""
        content = data.get('content', '').strip()
        if not content:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Empty pitch content.',
            }))
            return

        # Check if debate is already completed
        session = await self._refresh_session()
        if session.status == 'completed':
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'This debate session is already completed (5 turns).',
            }))
            return

        target_persona = data.get('target', 'all')
        
        # Prepend [Directed at Name] so the other personas reading the global 
        # transcript know exactly who this pitch was targeting.
        if target_persona in PERSONAS:
            target_name = PERSONAS[target_persona]['name']
            transcript_content = f"[Directed at {target_name}]: {content}"
            personas_to_fire = [target_persona]
        else:
            transcript_content = content
            personas_to_fire = PERSONA_ORDER

        # Advance turn and record user's pitch
        turn = await self._advance_turn()
        await self._append_transcript('user', transcript_content, turn)

        await self.send(text_data=json.dumps({
            'type': 'turn_started',
            'turn': turn,
            'user_content': transcript_content,
        }))

        # Fire targeted personas
        for persona_key in personas_to_fire:
            await self._stream_persona(persona_key, turn)

        # Check if this was the final turn
        is_final = turn >= 5
        if is_final:
            await self._complete_session()

        await self.send(text_data=json.dumps({
            'type': 'turn_complete',
            'turn': turn,
            'is_final': is_final,
        }))

    async def _stream_persona(self, persona_key, turn):
        """
        Stream a single persona's response from Groq LLM to the client.

        Flow:
        1. Send persona_start
        2. Fetch transcript, call Groq streaming
        3. Forward each chunk to client
        4. Save full response to GlobalTranscript
        5. Send persona_done
        """
        persona = PERSONAS[persona_key]

        # Signal that this persona is starting
        await self.send(text_data=json.dumps({
            'type': 'persona_start',
            'persona': persona_key,
            'turn': turn,
            'name': persona['name'],
            'emoji': persona['emoji'],
        }))

        try:
            # Get the full transcript so far (shared memory — all personas read this)
            transcript_entries = await self._get_transcript()

            # Stream response from Groq
            full_response = []
            async for chunk in stream_persona_response(
                persona_key,
                transcript_entries,
                turn_number=turn,
            ):
                full_response.append(chunk)
                await self.send(text_data=json.dumps({
                    'type': 'persona_chunk',
                    'persona': persona_key,
                    'content': chunk,
                    'turn': turn,
                }))

            # Assemble full response and save to shared transcript
            full_text = ''.join(full_response)

            if full_text.strip():
                await self._append_transcript(persona_key, full_text, turn)

            await self.send(text_data=json.dumps({
                'type': 'persona_done',
                'persona': persona_key,
                'turn': turn,
                'full_content': full_text,
            }))

        except Exception as e:
            logger.error(f"Persona {persona_key} streaming error: {e}", exc_info=True)
            await self.send(text_data=json.dumps({
                'type': 'persona_error',
                'persona': persona_key,
                'turn': turn,
                'error': str(e),
            }))

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
    def _refresh_session(self):
        """Refresh session state from database."""
        self.debate_session = DebateSession.objects.get(pk=self.debate_session.id)
        return self.debate_session

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
    def _complete_session(self):
        """Mark the debate session as completed."""
        from django.db import transaction
        with transaction.atomic():
            session = DebateSession.objects.select_for_update().get(pk=self.debate_session.id)
            session.status = 'completed'
            session.save()
            self.debate_session = session

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

    @database_sync_to_async
    def _get_transcript(self):
        """Fetch the full transcript as a list (evaluated queryset)."""
        return list(GlobalTranscript.get_transcript(self.debate_session.id))
