"""
Database models for PitchSense debate sessions.

Core models:
- DebateSession: Represents a single debate (5 turns) between a founder and 3 AI personas.
- GlobalTranscript: Shared memory — all personas read from and write to this single transcript.
  Uses select_for_update() to prevent race conditions during concurrent async writes.
"""
import uuid
from django.db import models, transaction
from django.utils import timezone


class DebateSession(models.Model):
    """
    A single debate session between a founder's pitch and 3 AI personas.
    Each session consists of up to 5 turns.
    """
    STATUS_CHOICES = [
        ('waiting', 'Waiting for pitch'),
        ('active', 'Active debate'),
        ('completed', 'Debate completed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='waiting')
    current_turn = models.IntegerField(default=0)
    pitch_topic = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Stores the final scorecard JSON from Turn 5
    scorecard = models.JSONField(null=True, blank=True)

    # Cache for Tavily research results (pre-fetched for Competitor persona)
    tavily_cache = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Debate {self.id} (Turn {self.current_turn}/5 - {self.status})"


class GlobalTranscript(models.Model):
    """
    Shared transcript that all 3 AI personas read from.

    Architecture Mandate: All personas read the SAME transcript.
    Uses select_for_update() for safe concurrent appends.
    """
    ROLE_CHOICES = [
        ('user', 'User (Founder)'),
        ('investor', 'Investor Persona'),
        ('customer', 'Customer Persona'),
        ('competitor', 'Competitor Persona'),
        ('system', 'System Message'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        DebateSession,
        on_delete=models.CASCADE,
        related_name='transcript_entries',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    turn_number = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    # Optional metadata (e.g., Tavily sources, confidence scores)
    metadata = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['session', 'turn_number']),
            models.Index(fields=['session', 'role']),
        ]

    def __str__(self):
        preview = self.content[:60] + '...' if len(self.content) > 60 else self.content
        return f"[Turn {self.turn_number}] {self.role}: {preview}"

    @classmethod
    def append_entry(cls, session_id, role, content, turn_number, metadata=None):
        """
        Thread-safe append to the global transcript.

        Uses select_for_update() on the session to serialize writes,
        preventing race conditions when multiple personas write concurrently.

        Args:
            session_id: UUID of the debate session
            role: One of 'user', 'investor', 'customer', 'competitor', 'system'
            content: The text content to append
            turn_number: Current turn number (1-5)
            metadata: Optional JSON metadata (e.g., Tavily sources)

        Returns:
            The created GlobalTranscript entry
        """
        with transaction.atomic():
            # Lock the session row to serialize concurrent transcript writes
            session = DebateSession.objects.select_for_update().get(pk=session_id)

            entry = cls.objects.create(
                session=session,
                role=role,
                content=content,
                turn_number=turn_number,
                metadata=metadata,
            )

            return entry

    @classmethod
    def get_transcript(cls, session_id, up_to_turn=None):
        """
        Retrieve the full transcript for a session, optionally up to a specific turn.

        This is what all personas read before generating their response.

        Args:
            session_id: UUID of the debate session
            up_to_turn: If set, only return entries up to this turn number

        Returns:
            QuerySet of GlobalTranscript entries, ordered by creation time
        """
        qs = cls.objects.filter(session_id=session_id)
        if up_to_turn is not None:
            qs = qs.filter(turn_number__lte=up_to_turn)
        return qs.order_by('created_at')
