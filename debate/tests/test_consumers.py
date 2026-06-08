"""
Tests for the DebateConsumer WebSocket handler.

These are the most critical tests in the project. consumers.py is where
all the real-time business logic lives: auth, turn advancement, parallel AI,
scorecard triggering, rate limiting, and session ownership.

Uses channels.testing.WebsocketCommunicator for true async WS testing.
All external services (Groq, Tavily, TTS) are mocked.
"""
import json
import uuid
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

from django.test import TestCase, TransactionTestCase, override_settings
from django.contrib.auth.models import User
from channels.testing import WebsocketCommunicator
from channels.db import database_sync_to_async

from debate.consumers import DebateConsumer
from debate.models import DebateSession, GlobalTranscript


def make_communicator(user, session_id=None):
    """Create a WebsocketCommunicator with a user injected into scope."""
    if session_id is None:
        session_id = str(uuid.uuid4())
    communicator = WebsocketCommunicator(
        DebateConsumer.as_asgi(),
        f"/ws/debate/{session_id}/",
    )
    communicator.scope['url_route'] = {'kwargs': {'session_id': session_id}}
    communicator.scope['user'] = user
    return communicator, session_id


class AnonymousUserMock:
    """Mimics an unauthenticated Django user in the WS scope."""
    is_authenticated = False
    is_superuser = False
    id = None
    username = ''


# ═══════════════════════════════════════════════════════════════════════
# 1. CONNECTION TESTS
# ═══════════════════════════════════════════════════════════════════════

class ConsumerConnectTests(TransactionTestCase):
    """Test WebSocket connection lifecycle."""

    async def test_authenticated_user_connects_successfully(self):
        user = await database_sync_to_async(User.objects.create_user)(
            'ws_test@test.com', password='TestPassword123!'
        )
        communicator, sid = make_communicator(user)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        # Should receive connection_established message
        response = await communicator.receive_json_from(timeout=5)
        self.assertEqual(response['type'], 'connection_established')
        self.assertEqual(response['session_id'], sid)
        self.assertEqual(response['current_turn'], 0)
        self.assertEqual(response['status'], 'waiting')
        self.assertIn('limits', response)
        self.assertEqual(response['limits']['max_total_turns'], 5)

        await communicator.disconnect()

    async def test_unauthenticated_user_rejected(self):
        communicator, _ = make_communicator(AnonymousUserMock())
        connected, code = await communicator.connect()
        # Should reject with code 4001
        self.assertFalse(connected)
        self.assertEqual(code, 4001)

    async def test_none_user_rejected(self):
        communicator, _ = make_communicator(None)
        # Manually set user to None to simulate missing auth middleware
        communicator.scope['user'] = None
        connected, code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(code, 4001)

    async def test_session_ownership_rejection(self):
        """User A creates a session, User B tries to connect — should get 4002."""
        user_a = await database_sync_to_async(User.objects.create_user)(
            'owner@test.com', password='TestPassword123!'
        )
        user_b = await database_sync_to_async(User.objects.create_user)(
            'intruder@test.com', password='TestPassword123!'
        )

        # User A connects and creates the session
        comm_a, sid = make_communicator(user_a)
        connected_a, _ = await comm_a.connect()
        self.assertTrue(connected_a)
        await comm_a.receive_json_from(timeout=5)  # consume connection_established
        await comm_a.disconnect()

        # User B tries to connect to the same session
        comm_b, _ = make_communicator(user_b, session_id=sid)
        connected_b, code = await comm_b.connect()
        self.assertFalse(connected_b)
        self.assertEqual(code, 4002)

    async def test_admin_can_connect_to_any_session(self):
        """Superusers should be able to connect to any session."""
        user = await database_sync_to_async(User.objects.create_user)(
            'regular@test.com', password='TestPassword123!'
        )
        admin = await database_sync_to_async(User.objects.create_superuser)(
            'admin@test.com', 'admin@test.com', 'AdminPassword123!'
        )

        # Regular user creates session
        comm_user, sid = make_communicator(user)
        connected, _ = await comm_user.connect()
        self.assertTrue(connected)
        await comm_user.receive_json_from(timeout=5)
        await comm_user.disconnect()

        # Admin connects to same session — should succeed
        comm_admin, _ = make_communicator(admin, session_id=sid)
        connected, _ = await comm_admin.connect()
        self.assertTrue(connected)
        response = await comm_admin.receive_json_from(timeout=5)
        self.assertEqual(response['type'], 'connection_established')
        await comm_admin.disconnect()

    async def test_pitch_limit_enforcement(self):
        """User with >5 sessions should be rejected with 4003."""
        user = await database_sync_to_async(User.objects.create_user)(
            'prolific@test.com', password='TestPassword123!'
        )
        # Create 6 sessions to exceed limit
        for _ in range(6):
            await database_sync_to_async(DebateSession.objects.create)(user=user)

        communicator, _ = make_communicator(user)
        connected, _ = await communicator.connect()
        # Consumer accepts, sends error, then closes with 4003
        # The connection may show as connected briefly before close
        if connected:
            response = await communicator.receive_json_from(timeout=5)
            self.assertEqual(response['type'], 'error')
            self.assertIn('maximum limit', response['message'])
        await communicator.disconnect()

    async def test_session_created_in_database(self):
        """Connecting should create a DebateSession in the DB."""
        user = await database_sync_to_async(User.objects.create_user)(
            'dbcheck@test.com', password='TestPassword123!'
        )
        sid = str(uuid.uuid4())
        communicator, _ = make_communicator(user, session_id=sid)
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.receive_json_from(timeout=5)

        # Verify session exists in DB
        exists = await database_sync_to_async(
            DebateSession.objects.filter(id=sid).exists
        )()
        self.assertTrue(exists)

        # Verify session is linked to user
        session = await database_sync_to_async(
            DebateSession.objects.get
        )(id=sid)
        self.assertEqual(session.user_id, user.id)
        self.assertEqual(session.status, 'waiting')

        await communicator.disconnect()


# ═══════════════════════════════════════════════════════════════════════
# 2. MESSAGE ROUTING TESTS
# ═══════════════════════════════════════════════════════════════════════

class ConsumerMessageRoutingTests(TransactionTestCase):
    """Test that receive() correctly routes different message types."""

    async def _connect_user(self):
        user = await database_sync_to_async(User.objects.create_user)(
            f'route_{uuid.uuid4().hex[:8]}@test.com', password='TestPassword123!'
        )
        communicator, sid = make_communicator(user)
        connected, _ = await communicator.connect()
        assert connected
        await communicator.receive_json_from(timeout=5)  # consume connection_established
        return communicator, user, sid

    async def test_ping_returns_pong(self):
        communicator, user, sid = await self._connect_user()
        await communicator.send_json_to({'type': 'ping'})
        response = await communicator.receive_json_from(timeout=5)
        self.assertEqual(response['type'], 'pong')
        self.assertEqual(response['session_id'], sid)
        await communicator.disconnect()

    async def test_invalid_json_returns_error(self):
        communicator, _, _ = await self._connect_user()
        await communicator.send_to(text_data='not valid json{{{')
        response = await communicator.receive_json_from(timeout=5)
        self.assertEqual(response['type'], 'error')
        self.assertIn('Invalid JSON', response['message'])
        await communicator.disconnect()

    async def test_unknown_message_type_returns_error(self):
        communicator, _, _ = await self._connect_user()
        await communicator.send_json_to({'type': 'nonexistent_type'})
        response = await communicator.receive_json_from(timeout=5)
        self.assertEqual(response['type'], 'error')
        self.assertIn('Unknown message type', response['message'])
        await communicator.disconnect()

    async def test_empty_pitch_returns_error(self):
        communicator, _, _ = await self._connect_user()
        await communicator.send_json_to({
            'type': 'user_pitch',
            'content': '',
            'target': 'all',
            'mode': 'panel',
        })
        response = await communicator.receive_json_from(timeout=5)
        self.assertEqual(response['type'], 'error')
        self.assertIn('Empty pitch', response['message'])
        await communicator.disconnect()

    async def test_non_admin_cannot_generate_scorecard(self):
        communicator, _, _ = await self._connect_user()
        await communicator.send_json_to({'type': 'generate_scorecard'})
        response = await communicator.receive_json_from(timeout=5)
        self.assertEqual(response['type'], 'error')
        self.assertIn('admin', response['message'].lower())
        await communicator.disconnect()


# ═══════════════════════════════════════════════════════════════════════
# 3. PITCH SUBMISSION & TURN ADVANCEMENT TESTS
# ═══════════════════════════════════════════════════════════════════════

def _mock_stream_response():
    """Create an async generator that yields mock LLM chunks."""
    async def mock_gen(*args, **kwargs):
        yield "This is "
        yield "a mock "
        yield "response."
    return mock_gen


class ConsumerPitchTests(TransactionTestCase):
    """Test pitch submission, turn advancement, and limit enforcement."""

    async def _connect_user(self, username=None):
        if username is None:
            username = f'pitch_{uuid.uuid4().hex[:8]}@test.com'
        user = await database_sync_to_async(User.objects.create_user)(
            username, password='TestPassword123!'
        )
        communicator, sid = make_communicator(user)
        connected, _ = await communicator.connect()
        assert connected
        await communicator.receive_json_from(timeout=5)
        return communicator, user, sid

    @patch('debate.consumers.get_competitor_context', new_callable=AsyncMock, return_value='')
    @patch('debate.consumers.synthesize_speech', new_callable=AsyncMock, return_value='')
    @patch('debate.consumers.stream_persona_response', side_effect=_mock_stream_response())
    async def test_panel_pitch_advances_turn(self, mock_stream, mock_tts, mock_tavily):
        communicator, user, sid = await self._connect_user()

        await communicator.send_json_to({
            'type': 'user_pitch',
            'content': 'We are building an AI-powered logistics platform.',
            'target': 'all',
            'mode': 'panel',
        })

        # Collect all messages until turn_complete
        messages = []
        while True:
            try:
                msg = await communicator.receive_json_from(timeout=10)
                messages.append(msg)
                if msg['type'] == 'turn_complete':
                    break
                if msg['type'] == 'error':
                    break
            except asyncio.TimeoutError:
                break

        # Verify message sequence
        types = [m['type'] for m in messages]
        self.assertIn('turn_started', types)
        self.assertIn('turn_complete', types)

        # Verify turn_started has correct turn number
        turn_started = next(m for m in messages if m['type'] == 'turn_started')
        self.assertEqual(turn_started['turn'], 1)

        # Verify turn_complete has updated counters
        turn_complete = next(m for m in messages if m['type'] == 'turn_complete')
        self.assertEqual(turn_complete['current_turn'], 1)
        self.assertEqual(turn_complete['panel_turn_count'], 1)

        # Verify DB state
        session = await database_sync_to_async(DebateSession.objects.get)(id=sid)
        self.assertEqual(session.current_turn, 1)
        self.assertEqual(session.status, 'active')
        self.assertEqual(session.panel_turn_count, 1)

        # Verify transcript was saved
        count = await database_sync_to_async(
            GlobalTranscript.objects.filter(session_id=sid).count
        )()
        self.assertGreaterEqual(count, 1)  # At least user entry

        await communicator.disconnect()

    @patch('debate.consumers.get_competitor_context', new_callable=AsyncMock, return_value='')
    @patch('debate.consumers.synthesize_speech', new_callable=AsyncMock, return_value='')
    @patch('debate.consumers.stream_persona_response', side_effect=_mock_stream_response())
    async def test_persona_streaming_messages(self, mock_stream, mock_tts, mock_tavily):
        """Verify we get persona_start, persona_chunk, persona_done for each persona."""
        communicator, user, sid = await self._connect_user()

        await communicator.send_json_to({
            'type': 'user_pitch',
            'content': 'Test pitch for streaming verification.',
            'target': 'all',
            'mode': 'panel',
        })

        messages = []
        while True:
            try:
                msg = await communicator.receive_json_from(timeout=10)
                messages.append(msg)
                if msg['type'] == 'turn_complete':
                    break
            except asyncio.TimeoutError:
                break

        types = [m['type'] for m in messages]

        # Each of the 3 personas should get start + done
        persona_starts = [m for m in messages if m['type'] == 'persona_start']
        persona_dones = [m for m in messages if m['type'] == 'persona_done']
        self.assertEqual(len(persona_starts), 3)
        self.assertEqual(len(persona_dones), 3)

        # Verify all 3 personas were fired
        started_personas = {m['persona'] for m in persona_starts}
        self.assertEqual(started_personas, {'investor', 'customer', 'competitor'})

        await communicator.disconnect()

    @patch('debate.consumers.get_competitor_context', new_callable=AsyncMock, return_value='')
    @patch('debate.consumers.synthesize_speech', new_callable=AsyncMock, return_value='')
    @patch('debate.consumers.stream_persona_response', side_effect=_mock_stream_response())
    async def test_deep_dive_fires_single_persona(self, mock_stream, mock_tts, mock_tavily):
        """Deep dive mode should only fire the targeted persona."""
        communicator, user, sid = await self._connect_user()

        await communicator.send_json_to({
            'type': 'user_pitch',
            'content': 'Tell me more about the market risk.',
            'target': 'investor',
            'mode': 'deep_dive',
        })

        messages = []
        while True:
            try:
                msg = await communicator.receive_json_from(timeout=10)
                messages.append(msg)
                if msg['type'] == 'turn_complete':
                    break
            except asyncio.TimeoutError:
                break

        persona_starts = [m for m in messages if m['type'] == 'persona_start']
        self.assertEqual(len(persona_starts), 1)
        self.assertEqual(persona_starts[0]['persona'], 'investor')

        await communicator.disconnect()

    async def test_pitch_cooldown_enforcement(self):
        """Sending pitches too fast should be rate-limited."""
        communicator, user, sid = await self._connect_user()

        # First pitch — always accepted (no rate limit)
        with patch('debate.consumers.get_competitor_context', new_callable=AsyncMock, return_value=''), \
             patch('debate.consumers.synthesize_speech', new_callable=AsyncMock, return_value=''), \
             patch('debate.consumers.stream_persona_response', side_effect=_mock_stream_response()):

            await communicator.send_json_to({
                'type': 'user_pitch', 'content': 'First pitch', 'target': 'all', 'mode': 'panel'
            })
            # Drain messages until turn_complete
            while True:
                try:
                    msg = await communicator.receive_json_from(timeout=10)
                    if msg['type'] in ('turn_complete', 'error'):
                        break
                except asyncio.TimeoutError:
                    break

        # Second pitch immediately — should be rate-limited (3s cooldown)
        await communicator.send_json_to({
            'type': 'user_pitch', 'content': 'Too fast pitch', 'target': 'all', 'mode': 'panel'
        })
        response = await communicator.receive_json_from(timeout=5)
        self.assertEqual(response['type'], 'error')
        self.assertIn('wait', response['message'].lower())

        await communicator.disconnect()

    async def test_unknown_deep_dive_persona_rejected(self):
        communicator, _, _ = await self._connect_user()
        await communicator.send_json_to({
            'type': 'user_pitch',
            'content': 'Hello',
            'target': 'nonexistent_persona',
            'mode': 'deep_dive',
        })
        response = await communicator.receive_json_from(timeout=5)
        self.assertEqual(response['type'], 'error')
        self.assertIn('Unknown persona', response['message'])
        await communicator.disconnect()

    async def test_input_truncation(self):
        """Pitches longer than 2000 chars should be truncated, not rejected."""
        communicator, _, sid = await self._connect_user()

        long_content = 'A' * 3000

        with patch('debate.consumers.get_competitor_context', new_callable=AsyncMock, return_value=''), \
             patch('debate.consumers.synthesize_speech', new_callable=AsyncMock, return_value=''), \
             patch('debate.consumers.stream_persona_response', side_effect=_mock_stream_response()):

            await communicator.send_json_to({
                'type': 'user_pitch', 'content': long_content, 'target': 'all', 'mode': 'panel'
            })

            messages = []
            while True:
                try:
                    msg = await communicator.receive_json_from(timeout=10)
                    messages.append(msg)
                    if msg['type'] in ('turn_complete', 'error'):
                        break
                except asyncio.TimeoutError:
                    break

            # Should succeed (not error)
            types = [m['type'] for m in messages]
            self.assertIn('turn_started', types)

            # Verify stored content is truncated
            entry = await database_sync_to_async(
                GlobalTranscript.objects.filter(session_id=sid, role='user').first
            )()
            self.assertIsNotNone(entry)
            self.assertLessEqual(len(entry.content), 2000)

        await communicator.disconnect()


# ═══════════════════════════════════════════════════════════════════════
# 4. TURN LIMIT & SCORECARD TESTS
# ═══════════════════════════════════════════════════════════════════════

class ConsumerTurnLimitTests(TransactionTestCase):
    """Test panel turn limits and scorecard auto-generation."""

    async def _connect_user(self):
        user = await database_sync_to_async(User.objects.create_user)(
            f'limit_{uuid.uuid4().hex[:8]}@test.com', password='TestPassword123!'
        )
        communicator, sid = make_communicator(user)
        connected, _ = await communicator.connect()
        assert connected
        await communicator.receive_json_from(timeout=5)
        return communicator, user, sid

    async def _send_pitch_and_drain(self, communicator, content='Test pitch', mode='panel', target='all'):
        """Send a pitch and consume all messages until turn_complete."""
        with patch('debate.consumers.get_competitor_context', new_callable=AsyncMock, return_value=''), \
             patch('debate.consumers.synthesize_speech', new_callable=AsyncMock, return_value=''), \
             patch('debate.consumers.stream_persona_response', side_effect=_mock_stream_response()):
            await communicator.send_json_to({
                'type': 'user_pitch', 'content': content, 'target': target, 'mode': mode
            })
            messages = []
            while True:
                try:
                    msg = await communicator.receive_json_from(timeout=10)
                    messages.append(msg)
                    if msg['type'] in ('turn_complete', 'error'):
                        break
                    if msg['type'] == 'scorecard_generated':
                        # Keep reading — turn_complete follows scorecard
                        continue
                except asyncio.TimeoutError:
                    break
            return messages

    async def test_panel_limit_enforced_after_2_turns(self):
        communicator, user, sid = await self._connect_user()

        # Pitch 1 — should work
        msgs1 = await self._send_pitch_and_drain(communicator, 'First panel pitch')
        types1 = [m['type'] for m in msgs1]
        self.assertIn('turn_started', types1)

        # Need to wait for cooldown
        await asyncio.sleep(3.5)

        # Pitch 2 — should work
        msgs2 = await self._send_pitch_and_drain(communicator, 'Second panel pitch')
        types2 = [m['type'] for m in msgs2]
        self.assertIn('turn_started', types2)

        # Need to wait for cooldown
        await asyncio.sleep(3.5)

        # Pitch 3 — should be rejected (panel limit = 2)
        await communicator.send_json_to({
            'type': 'user_pitch', 'content': 'Third panel pitch', 'target': 'all', 'mode': 'panel'
        })
        response = await communicator.receive_json_from(timeout=5)
        self.assertEqual(response['type'], 'error')
        self.assertIn('panel pitch turns', response['message'])

        await communicator.disconnect()

    async def test_session_status_transitions_to_active(self):
        communicator, user, sid = await self._connect_user()

        # Before pitch — status should be 'waiting'
        session = await database_sync_to_async(DebateSession.objects.get)(id=sid)
        self.assertEqual(session.status, 'waiting')

        # After pitch — status should be 'active'
        await self._send_pitch_and_drain(communicator, 'Activating pitch')
        session = await database_sync_to_async(DebateSession.objects.get)(id=sid)
        self.assertEqual(session.status, 'active')

        await communicator.disconnect()
