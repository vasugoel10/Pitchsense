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
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import DebateSession, GlobalTranscript
from .personas import PERSONAS, PERSONA_ORDER
from .services.groq_service import stream_persona_response
from .services.tavily_service import get_competitor_context
from .services.tts_service import synthesize_speech

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
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4001) # Unauthorized
            return

        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.debate_session = await self._get_or_create_session(user)

        # Prevent session hijacking — reject if session belongs to another user
        if self.debate_session.user and self.debate_session.user.id != user.id and not user.is_superuser:
            await self.close(code=4002)  # Forbidden — not your session
            return

        # Check pitch limits for customers
        if not user.is_superuser:
            pitch_count = await self._get_user_pitch_count(user)
            if pitch_count > 5:
                await self.accept()
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'You have reached the maximum limit of 5 pitches. Upgrade or contact support.'
                }))
                await self.close(code=4003)
                return

        await self.accept()
        transcript = await self._get_transcript()
        history = [
            {'role': entry.role, 'content': entry.content, 'turn': entry.turn_number}
            for entry in transcript
        ]

        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'session_id': str(self.debate_session.id),
            'status': self.debate_session.status,
            'current_turn': self.debate_session.current_turn,
            'history': history,
            'scorecard': self.debate_session.scorecard,
            'is_admin': user.is_superuser,
            'message': 'Connected to PitchSense debate session.',
        }))

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type', 'unknown')

        if message_type == 'user_pitch':
            await self._handle_user_pitch(data)
            
        elif message_type == 'generate_scorecard':
            user = self.scope.get('user')
            if user and user.is_superuser:
                await self._generate_and_send_scorecard()
            else:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Only admins can manually generate scorecards.'
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

    # ── Core debate logic ─────────────────────────────────────────────

    async def _handle_user_pitch(self, data):
        """Handle a user's pitch input and trigger all persona responses."""
        user = self.scope.get('user')
        content = data.get('content', '').strip()
        if not content:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Empty pitch content.',
            }))
            return
        
        # Cap input length to prevent abuse
        if len(content) > 2000:
            content = content[:2000]
            
        # Check Turn Limits for customers
        if not user.is_superuser:
            session = await self._refresh_session()
            if session.current_turn >= 2:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'Customers are limited to 2 turns per pitch. Upgrade for unlimited deep dives.'
                }))
                return

        target_persona = data.get('target', 'all')
        mode = data.get('mode', 'panel')
        
        # Prepend explicit tag and make the targeted persona respond FIRST
        if target_persona in PERSONAS:
            target_name = PERSONAS[target_persona]['name']
            transcript_content = f"[Founder speaking directly to {target_name}]: {content}"
            
            if mode == 'deep_dive':
                # Deep dive: only the targeted persona fires
                personas_to_fire = [target_persona]
            else:
                # Panel: target fires first, then the rest
                personas_to_fire = [target_persona] + [p for p in PERSONA_ORDER if p != target_persona]
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

        # Launch background Tavily search for latency hiding
        tavily_task = asyncio.create_task(get_competitor_context(content))

        # Fire targeted personas
        for persona_key in personas_to_fire:
            tavily_context = None
            if persona_key == 'competitor':
                tavily_context = await tavily_task
            await self._stream_persona(persona_key, turn, tavily_context=tavily_context, mode=mode)

        # For customers, auto-generate scorecard on Turn 2
        is_final = False
        if not user.is_superuser and turn == 2:
            is_final = True
            await self._generate_and_send_scorecard()

        await self.send(text_data=json.dumps({
            'type': 'turn_complete',
            'turn': turn,
            'is_final': is_final,
        }))

    async def _generate_and_send_scorecard(self):
        transcript = await self._get_transcript()
        from .services.groq_service import generate_scorecard
        scorecard_data = await generate_scorecard(transcript)
        await self.send(text_data=json.dumps({
            'type': 'scorecard_generated',
            'scorecard': scorecard_data,
        }))
        await self._complete_session(scorecard_data)

    async def _stream_persona(self, persona_key, turn, tavily_context=None, mode='panel'):
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
                tavily_context=tavily_context,
                mode=mode,
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

            # Synthesize TTS audio asynchronously so it doesn't block turn completion
            if full_text.strip():
                voice = persona.get('voice', 'en-US-GuyNeural')
                asyncio.create_task(self._synthesize_and_send_audio(persona_key, turn, full_text, voice))

        except Exception as e:
            logger.error(f"Persona {persona_key} streaming error: {e}", exc_info=True)
            await self.send(text_data=json.dumps({
                'type': 'persona_error',
                'persona': persona_key,
                'turn': turn,
                'error': str(e),
            }))

    async def _synthesize_and_send_audio(self, persona_key, turn, text, voice):
        try:
            audio_b64 = await synthesize_speech(text, voice)
            if audio_b64:
                # Guard: only send if WebSocket is still open
                try:
                    await self.send(text_data=json.dumps({
                        'type': 'persona_audio',
                        'persona': persona_key,
                        'turn': turn,
                        'audio_base64': audio_b64,
                    }))
                except Exception:
                    pass  # Client disconnected before TTS finished — ignore
        except Exception as e:
            logger.error(f"TTS background task failed for {persona_key}: {e}", exc_info=True)

    # ── Database helpers ──────────────────────────────────────────────

    @database_sync_to_async
    def _get_user_pitch_count(self, user):
        """Get the number of debate sessions owned by this user."""
        return DebateSession.objects.filter(user=user).count()

    @database_sync_to_async
    def _get_or_create_session(self, user):
        """Get existing session or create a new one."""
        try:
            session_uuid = uuid.UUID(self.session_id)
            session, created = DebateSession.objects.get_or_create(id=session_uuid)
            if not session.user:
                session.user = user
                session.save()
            return session
        except (ValueError, DebateSession.DoesNotExist):
            return DebateSession.objects.create(id=self.session_id, user=user)

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
    def _complete_session(self, scorecard_data=None):
        """Mark the debate session as completed and save scorecard."""
        from django.db import transaction
        with transaction.atomic():
            session = DebateSession.objects.select_for_update().get(pk=self.debate_session.id)
            session.status = 'completed'
            if scorecard_data:
                session.scorecard = scorecard_data
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
