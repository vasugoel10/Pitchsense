"""
WebSocket consumer for PitchSense debate sessions.

Turn rules:
- Panel pitches (all 3 respond): max 2 per session
- Deep dive (1 persona, private): max 2 per persona per session
- Total turn counter: max 5 before scorecard generates

Production hardening:
- Per-connection rate limiting (1 pitch per 3 seconds)
- Parallel persona streaming via asyncio.gather
- Input validation and sanitization
- Structured error logging
"""
import json
import time
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

MAX_PANEL_TURNS = 2     # how many times user can pitch to the full panel
MAX_DEEP_DIVES = 2      # how many follow-up questions per persona in deep dive
MAX_TOTAL_TURNS = 5     # scorecard fires after this many total turns

# Rate limiting
PITCH_COOLDOWN_SECONDS = 3      # min gap between pitches per connection
MAX_MESSAGES_PER_MINUTE = 20    # max WebSocket messages per connection per minute


class DebateConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        user = self.scope.get('user')
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.session_id = self.scope['url_route']['kwargs']['session_id']

        # Initialize rate limiting state
        self._last_pitch_time = 0
        self._message_timestamps = []

        self.debate_session = await self._get_or_create_session(user)

        if self.debate_session.user and self.debate_session.user.id != user.id and not user.is_superuser:
            await self.close(code=4002)
            return

        if not user.is_superuser:
            pitch_count = await self._get_user_pitch_count(user)
            if pitch_count > 5:
                await self.accept()
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': 'You have reached the maximum limit of 5 pitches.'
                }))
                await self.close(code=4003)
                return

        await self.accept()
        transcript = await self._get_transcript()
        history = [
            {'role': entry.role, 'content': entry.content, 'turn': entry.turn_number}
            for entry in transcript
        ]

        session = await self._refresh_session()
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'session_id': str(self.debate_session.id),
            'status': session.status,
            'current_turn': session.current_turn,
            'panel_turn_count': session.panel_turn_count,
            'deep_dive_counts': session.deep_dive_counts or {},
            'history': history,
            'scorecard': session.scorecard,
            'is_admin': user.is_superuser,
            'message': 'Connected to PitchSense debate session.',
            'limits': {
                'max_panel_turns': MAX_PANEL_TURNS,
                'max_deep_dives': MAX_DEEP_DIVES,
                'max_total_turns': MAX_TOTAL_TURNS,
            }
        }))

    async def receive(self, text_data):
        # ── Global message rate limit ─────────────────────────────────
        now = time.time()
        self._message_timestamps = [
            t for t in self._message_timestamps if now - t < 60
        ]
        if len(self._message_timestamps) >= MAX_MESSAGES_PER_MINUTE:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Too many messages. Please slow down.',
            }))
            return
        self._message_timestamps.append(now)

        # ── Parse ─────────────────────────────────────────────────────
        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON payload.',
            }))
            return

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
        user = self.scope.get('user')
        content = data.get('content', '').strip()

        if not content:
            await self.send(text_data=json.dumps({'type': 'error', 'message': 'Empty pitch content.'}))
            return

        # Input sanitization
        if len(content) > 2000:
            content = content[:2000]

        # ── Per-pitch rate limit ──────────────────────────────────────
        now = time.time()
        elapsed = now - self._last_pitch_time
        if elapsed < PITCH_COOLDOWN_SECONDS:
            wait = round(PITCH_COOLDOWN_SECONDS - elapsed, 1)
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Please wait {wait}s between pitches.',
            }))
            return
        self._last_pitch_time = now

        target_persona = data.get('target', 'all')
        mode = data.get('mode', 'panel')

        # Validate target_persona is a known persona key
        if mode == 'deep_dive' and target_persona not in PERSONAS:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': f'Unknown persona: {target_persona}',
            }))
            return

        session = await self._refresh_session()
        deep_dive_counts = session.deep_dive_counts or {}

        # ── Validate limits ───────────────────────────────────────────
        is_admin = user.is_superuser

        if mode == 'deep_dive' and target_persona in PERSONAS:
            # Deep dive: max 2 questions per persona
            if not is_admin and deep_dive_counts.get(target_persona, 0) >= MAX_DEEP_DIVES:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'You\'ve used your {MAX_DEEP_DIVES} deep dive questions with this persona.',
                    'limit_type': 'deep_dive',
                    'persona': target_persona,
                }))
                return
            target_name = PERSONAS[target_persona]['name']
            transcript_content = f"[Founder speaking directly to {target_name}]: {content}"
            personas_to_fire = [target_persona]

        else:
            # Panel mode: all 3 respond, max 2 panel pitches
            mode = 'panel'
            if not is_admin and session.panel_turn_count >= MAX_PANEL_TURNS:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'message': f'You\'ve used both your panel pitch turns.',
                    'limit_type': 'panel',
                }))
                return
            transcript_content = content
            personas_to_fire = PERSONA_ORDER
            target_persona = 'all'

        # ── Check overall 5-turn cap ──────────────────────────────────
        # Admin gets higher limit but not unlimited
        turn_limit = MAX_TOTAL_TURNS * 4 if is_admin else MAX_TOTAL_TURNS
        if session.current_turn >= turn_limit:
            if session.status != 'completed':
                await self._generate_and_send_scorecard()
            return

        # ── Advance turn ──────────────────────────────────────────────
        turn = await self._advance_turn(
            mode=mode,
            target_persona=target_persona if mode == 'deep_dive' else None
        )
        await self._append_transcript('user', transcript_content, turn)

        await self.send(text_data=json.dumps({
            'type': 'turn_started',
            'turn': turn,
            'user_content': transcript_content,
        }))

        # ── Fire personas in parallel ─────────────────────────────────
        tavily_context = await get_competitor_context(content)

        async def fire_persona(pk):
            ctx = tavily_context if pk == 'competitor' else None
            await self._stream_persona(pk, turn, tavily_context=ctx, mode=mode)

        await asyncio.gather(
            *[fire_persona(pk) for pk in personas_to_fire],
            return_exceptions=True,
        )

        # ── Check if we've hit the total turn cap ─────────────────────
        session = await self._refresh_session()
        is_final = False
        if not is_admin and session.current_turn >= MAX_TOTAL_TURNS:
            is_final = True
            await self._generate_and_send_scorecard()

        await self.send(text_data=json.dumps({
            'type': 'turn_complete',
            'turn': turn,
            'is_final': is_final,
            'current_turn': session.current_turn,
            'panel_turn_count': session.panel_turn_count,
            'deep_dive_counts': session.deep_dive_counts or {},
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
        persona = PERSONAS[persona_key]

        await self.send(text_data=json.dumps({
            'type': 'persona_start',
            'persona': persona_key,
            'turn': turn,
            'name': persona['name'],
            'emoji': persona['emoji'],
        }))

        try:
            transcript_entries = await self._get_transcript()
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

            full_text = ''.join(full_response)

            if full_text.strip():
                await self._append_transcript(persona_key, full_text, turn)

            await self.send(text_data=json.dumps({
                'type': 'persona_done',
                'persona': persona_key,
                'turn': turn,
                'full_content': full_text,
            }))

            if full_text.strip():
                voice = persona.get('voice', 'en-US-GuyNeural')
                asyncio.create_task(self._synthesize_and_send_audio(persona_key, turn, full_text, voice))

        except Exception as e:
            logger.error(f"Persona {persona_key} streaming error: {e}", exc_info=True)
            await self.send(text_data=json.dumps({
                'type': 'persona_error',
                'persona': persona_key,
                'turn': turn,
                'error': 'An error occurred while generating the response.',
            }))

    async def _synthesize_and_send_audio(self, persona_key, turn, text, voice):
        try:
            audio_b64 = await synthesize_speech(text, voice)
            if audio_b64:
                try:
                    await self.send(text_data=json.dumps({
                        'type': 'persona_audio',
                        'persona': persona_key,
                        'turn': turn,
                        'audio_base64': audio_b64,
                    }))
                except Exception:
                    pass
        except Exception as e:
            logger.error(f"TTS background task failed for {persona_key}: {e}", exc_info=True)

    # ── Database helpers ──────────────────────────────────────────────

    @database_sync_to_async
    def _get_user_pitch_count(self, user):
        return DebateSession.objects.filter(user=user).count()

    @database_sync_to_async
    def _get_or_create_session(self, user):
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
        self.debate_session = DebateSession.objects.get(pk=self.debate_session.id)
        return self.debate_session

    @database_sync_to_async
    def _advance_turn(self, mode='panel', target_persona=None):
        from django.db import transaction
        with transaction.atomic():
            session = DebateSession.objects.select_for_update().get(pk=self.debate_session.id)
            session.current_turn += 1
            if session.status == 'waiting':
                session.status = 'active'

            if mode == 'deep_dive' and target_persona:
                counts = session.deep_dive_counts or {}
                counts[target_persona] = counts.get(target_persona, 0) + 1
                session.deep_dive_counts = counts
            else:
                session.panel_turn_count += 1

            session.save()
            self.debate_session = session
            return session.current_turn

    @database_sync_to_async
    def _complete_session(self, scorecard_data=None):
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
        return GlobalTranscript.append_entry(
            session_id=self.debate_session.id,
            role=role,
            content=content,
            turn_number=turn_number,
            metadata=metadata,
        )

    @database_sync_to_async
    def _get_transcript(self):
        return list(GlobalTranscript.get_transcript(self.debate_session.id))
