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
                                   turn_number=None, tavily_context=None, mode='panel'):
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
        mode=mode,
    )

    client = AsyncGroq(api_key=settings.GROQ_API_KEY)

    # Deep dive mode gets more tokens for detailed analysis
    max_tokens = 4096 if mode == 'deep_dive' else 1024

    # Fallback sequence of models
    models_to_try = [
        "llama-3.3-70b-versatile",
        "mixtral-8x7b-32768",
        "llama-3.1-8b-instant"
    ]

    stream = None
    used_model = None

    for model in models_to_try:
        try:
            stream = await client.chat.completions.create(
                messages=messages,
                model=model,
                stream=True,
                temperature=0.8,
                max_tokens=max_tokens,
            )
            used_model = model
            break  # Success, exit the fallback loop
        except Exception as e:
            logger.warning(f"Model {model} failed: {e}. Trying next fallback...")
            continue
            
    if not stream:
        raise RuntimeError("All fallback models failed to generate a response.")

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
    
    models_to_try = [
        "llama-3.3-70b-versatile",
        "mixtral-8x7b-32768",
        "llama-3.1-8b-instant"
    ]
    
    content = ""
    # Layer 1
    for model in models_to_try:
        try:
            response = await client.chat.completions.create(
                messages=messages,
                model=model,
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=500,
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except json.JSONDecodeError:
            break # Not an API failure, JSON format failure. Proceed to layer 2
        except Exception as e:
            logger.warning(f"Layer 1 model {model} failed: {e}. Trying next...")
            continue

    # Layer 2: Retry
    for model in models_to_try:
        try:
            retry_prompt = "Output STRICT JSON ONLY matching the required format."
            # Only append if content exists, else use standard prompt
            current_messages = list(messages)
            if content:
                current_messages.append({"role": "assistant", "content": content})
            current_messages.append({"role": "user", "content": retry_prompt})
            
            response = await client.chat.completions.create(
                messages=current_messages,
                model=model,
                temperature=0.1,
                max_tokens=500,
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.warning(f"Layer 2 model {model} failed: {e}. Trying next...")
            continue

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
