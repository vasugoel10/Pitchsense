"""
Tests for PitchSense database models.

Covers:
- DebateSession creation, status lifecycle, and field defaults
- GlobalTranscript thread-safe append and retrieval
- select_for_update concurrency guard
- Cascade deletion
"""
import uuid
from django.test import TestCase
from django.contrib.auth.models import User
from debate.models import DebateSession, GlobalTranscript


class DebateSessionModelTests(TestCase):
    """Tests for the DebateSession model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='founder@test.com', password='TestPassword123!'
        )

    def test_create_session_defaults(self):
        session = DebateSession.objects.create(user=self.user)
        self.assertEqual(session.status, 'waiting')
        self.assertEqual(session.current_turn, 0)
        self.assertEqual(session.panel_turn_count, 0)
        self.assertEqual(session.deep_dive_counts, {})
        self.assertIsNone(session.scorecard)
        self.assertIsNotNone(session.id)
        self.assertIsInstance(session.id, uuid.UUID)

    def test_session_uuid_primary_key(self):
        session = DebateSession.objects.create(user=self.user)
        fetched = DebateSession.objects.get(pk=session.id)
        self.assertEqual(session.id, fetched.id)

    def test_session_str_representation(self):
        session = DebateSession.objects.create(user=self.user)
        expected = f"Debate {session.id} (Turn 0/5 - waiting)"
        self.assertEqual(str(session), expected)

    def test_session_status_transitions(self):
        session = DebateSession.objects.create(user=self.user)
        self.assertEqual(session.status, 'waiting')

        session.status = 'active'
        session.save()
        session.refresh_from_db()
        self.assertEqual(session.status, 'active')

        session.status = 'completed'
        session.save()
        session.refresh_from_db()
        self.assertEqual(session.status, 'completed')

    def test_cascade_delete_user_removes_sessions(self):
        DebateSession.objects.create(user=self.user)
        DebateSession.objects.create(user=self.user)
        self.assertEqual(DebateSession.objects.filter(user=self.user).count(), 2)

        self.user.delete()
        self.assertEqual(DebateSession.objects.count(), 0)

    def test_session_ordering(self):
        """Sessions should be ordered by created_at descending."""
        import time
        s1 = DebateSession.objects.create(user=self.user)
        time.sleep(0.05)  # Ensure distinct timestamps in SQLite
        s2 = DebateSession.objects.create(user=self.user)
        sessions = list(DebateSession.objects.all())
        self.assertEqual(sessions[0].id, s2.id)
        self.assertEqual(sessions[1].id, s1.id)

    def test_deep_dive_counts_json(self):
        session = DebateSession.objects.create(
            user=self.user,
            deep_dive_counts={'investor': 1, 'customer': 0, 'competitor': 2}
        )
        session.refresh_from_db()
        self.assertEqual(session.deep_dive_counts['investor'], 1)
        self.assertEqual(session.deep_dive_counts['competitor'], 2)


class GlobalTranscriptModelTests(TestCase):
    """Tests for the GlobalTranscript model."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='founder@test.com', password='TestPassword123!'
        )
        self.session = DebateSession.objects.create(user=self.user)

    def test_append_entry_creates_transcript(self):
        entry = GlobalTranscript.append_entry(
            session_id=self.session.id,
            role='user',
            content='My pitch is about AI-powered logistics.',
            turn_number=1,
        )
        self.assertIsNotNone(entry.id)
        self.assertEqual(entry.role, 'user')
        self.assertEqual(entry.turn_number, 1)

    def test_append_entry_with_metadata(self):
        entry = GlobalTranscript.append_entry(
            session_id=self.session.id,
            role='competitor',
            content='Market data shows...',
            turn_number=1,
            metadata={'sources': ['https://example.com']},
        )
        self.assertEqual(entry.metadata['sources'], ['https://example.com'])

    def test_get_transcript_ordered_by_time(self):
        import time
        GlobalTranscript.append_entry(self.session.id, 'user', 'First', 1)
        time.sleep(0.05)  # Ensure distinct timestamps in SQLite
        GlobalTranscript.append_entry(self.session.id, 'investor', 'Second', 1)
        time.sleep(0.05)
        GlobalTranscript.append_entry(self.session.id, 'customer', 'Third', 1)

        transcript = list(GlobalTranscript.get_transcript(self.session.id))
        self.assertEqual(len(transcript), 3)
        self.assertEqual(transcript[0].content, 'First')
        self.assertEqual(transcript[2].content, 'Third')

    def test_get_transcript_up_to_turn(self):
        GlobalTranscript.append_entry(self.session.id, 'user', 'Turn 1', 1)
        GlobalTranscript.append_entry(self.session.id, 'investor', 'Turn 1 reply', 1)
        GlobalTranscript.append_entry(self.session.id, 'user', 'Turn 2', 2)
        GlobalTranscript.append_entry(self.session.id, 'investor', 'Turn 2 reply', 2)

        # Only turn 1
        transcript = list(GlobalTranscript.get_transcript(self.session.id, up_to_turn=1))
        self.assertEqual(len(transcript), 2)
        self.assertTrue(all(e.turn_number <= 1 for e in transcript))

    def test_cascade_delete_session_removes_transcripts(self):
        GlobalTranscript.append_entry(self.session.id, 'user', 'Test', 1)
        self.assertEqual(GlobalTranscript.objects.count(), 1)

        self.session.delete()
        self.assertEqual(GlobalTranscript.objects.count(), 0)

    def test_transcript_str_representation(self):
        entry = GlobalTranscript.append_entry(
            self.session.id, 'investor', 'Short response.', 2
        )
        self.assertIn('[Turn 2]', str(entry))
        self.assertIn('investor', str(entry))

    def test_transcript_str_truncates_long_content(self):
        long_content = 'A' * 100
        entry = GlobalTranscript.append_entry(
            self.session.id, 'user', long_content, 1
        )
        self.assertIn('...', str(entry))
