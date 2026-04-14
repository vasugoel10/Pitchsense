"""
Groq LLM streaming service for PitchSense.

Uses AsyncGroq with stream=True to yield response chunks
that the WebSocket consumer sends to the client in real-time.

Architecture: This is an async generator — the consumer iterates over it
and forwards each chunk instantly via WebSocket.
"""
import logging
from groq import AsyncGroq
from django.conf import settings
from debate.personas import PERSONAS, build_messages

logger = logging.getLogger(__name__)

# Model constant — single source of truth
GROQ_MODEL = "llama-3.3-70b-versatile"


async def stream_persona_response(persona_key, transcript_entries,
                                   turn_number=None, tavily_context=None):
    """
    Async generator that streams Groq LLM response chunks for a persona.

    Yields strings (content deltas) as they arrive from the Groq API.
    The consumer accumulates these and sends each to the client via WebSocket.

    Args:
        persona_key: One of 'investor', 'customer', 'competitor'
        transcript_entries: QuerySet or list of GlobalTranscript entries
        turn_number: Current turn number (for turn-aware prompting)
        tavily_context: Optional Tavily research string (for competitor persona)

    Yields:
        str: Content chunks from the LLM response

    Raises:
        ValueError: If GROQ_API_KEY is not configured
        ValueError: If persona_key is invalid
    """
    if not settings.GROQ_API_KEY:
        raise ValueError(
            "GROQ_API_KEY is not set. Add it to your environment variables "
            "or .env file. Get a key at https://console.groq.com/"
        )

    if persona_key not in PERSONAS:
        raise ValueError(f"Unknown persona: {persona_key}. Must be one of {list(PERSONAS.keys())}")

    # Build the message chain for this persona
    messages = build_messages(
        persona_key,
        transcript_entries,
        turn_number=turn_number,
        tavily_context=tavily_context,
    )

    client = AsyncGroq(api_key=settings.GROQ_API_KEY)

    stream = await client.chat.completions.create(
        messages=messages,
        model=GROQ_MODEL,
        stream=True,
        temperature=0.8,
        max_tokens=1024,
    )

    async for chunk in stream:
        content = chunk.choices[0].delta.content
        if content is not None:
            yield content


async def generate_scorecard(transcript_entries):
    """
    Generate Turn 5 structured JSON scorecard.

    Stub — full implementation in Phase 3 with 3-layer JSON defense (ADR-009):
    1. response_format: {"type": "json_object"} if Groq supports it
    2. Simplified retry prompt on failure
    3. Hardcoded fallback so UI never breaks

    Args:
        transcript_entries: Full debate transcript

    Returns:
        dict: Scorecard with overall_score, market, moat, feasibility, verdict
    """
    raise NotImplementedError(
        "Scorecard generation is implemented in Phase 3. "
        "See ADR-009 for the 3-layer JSON defense strategy."
    )
