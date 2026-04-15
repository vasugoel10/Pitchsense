"""
Groq LLM streaming service for PitchSense.

Uses AsyncGroq with stream=True to yield response chunks
that the WebSocket consumer sends to the client in real-time.

Architecture: This is an async generator — the consumer iterates over it
and forwards each chunk instantly via WebSocket.
"""
import logging
import json
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
    Generate Turn 5 structured JSON scorecard using 3-layer JSON defense (ADR-009).
    """
    if not settings.GROQ_API_KEY:
        return _get_fallback_scorecard()

    client = AsyncGroq(api_key=settings.GROQ_API_KEY)
    
    system_prompt = """You are an impartial judge. Review the startup pitch debate transcript and return a final scorecard in STRICT JSON format.
The JSON must contain EXACTLY these keys:
{
  "overall_score": <int 0-10>,
  "market": <int 0-10>,
  "moat": <int 0-10>,
  "feasibility": <int 0-10>,
  "verdict": "<KILL | PIVOT | PROCEED>",
  "feedback": "<1-2 sentence summary>"
}
Output nothing else."""

    debate_text = ""
    for entry in transcript_entries:
        debate_text += f"[{entry.role}] {entry.content}\n"
        
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": debate_text}
    ]
    
    content = ""
    # Layer 1
    try:
        response = await client.chat.completions.create(
            messages=messages,
            model=GROQ_MODEL,
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=500,
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    except Exception as e:
        logger.error(f"Layer 1 JSON parsing failed: {e}")

    # Layer 2: Retry
    try:
        retry_prompt = "Output STRICT JSON ONLY matching the required format."
        messages.append({"role": "assistant", "content": content})
        messages.append({"role": "user", "content": retry_prompt})
        response = await client.chat.completions.create(
            messages=messages,
            model=GROQ_MODEL,
            temperature=0.1,
            max_tokens=500,
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.error(f"Layer 2 JSON parsing failed: {e}")

    # Layer 3: Hardcoded fallback
    return _get_fallback_scorecard()

def _get_fallback_scorecard():
    return {
        "overall_score": 5,
        "market": 5,
        "moat": 5,
        "feasibility": 5,
        "verdict": "PIVOT",
        "feedback": "The debate concluded with mixed signals. Reassess your core hypotheses."
    }
