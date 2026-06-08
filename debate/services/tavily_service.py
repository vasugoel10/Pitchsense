"""
Tavily web search service for PitchSense Competitor persona.

Fetches live market context so the Competitor persona can cite real companies
and funding rounds instead of hallucinating.

Caching: Results are cached by content hash (first 300 chars of pitch) for 1 hour
via Django's cache framework (Redis in prod, LocMem in dev). This eliminates
redundant API calls when the same pitch is submitted multiple times within a session.
"""
import hashlib
import logging
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

# Cache TTL: 1 hour — market context doesn't change that fast
TAVILY_CACHE_TTL = 3600


async def get_competitor_context(pitch_text: str) -> str:
    """
    Fetch market context from Tavily asynchronously for the Competitor persona.

    Checks the cache first (keyed by content hash). On cache miss, fetches from
    Tavily and stores the result for subsequent turns in the same session.

    Args:
        pitch_text: The founder's pitch text (first 300 chars used as query).

    Returns:
        A summary string of market context (max 500 chars), or '' on failure.
    """
    if not pitch_text or not pitch_text.strip():
        return ""

    # ── Cache check ──────────────────────────────────────────────────────
    pitch_hash = hashlib.sha256(pitch_text[:300].encode()).hexdigest()[:16]
    cache_key = f"tavily:{pitch_hash}"

    try:
        cached = await sync_to_async(cache.get)(cache_key)
        if cached is not None:
            logger.info("Tavily cache HIT for key=%s", cache_key)
            return cached
    except Exception:
        logger.warning("Tavily cache unavailable — skipping cache lookup")

    # ── API key check ────────────────────────────────────────────────────
    api_key = getattr(settings, 'TAVILY_API_KEY', None)
    if not api_key:
        logger.warning("TAVILY_API_KEY is not set. Skipping competitor context research.")
        return ""

    # ── Fetch from Tavily ────────────────────────────────────────────────
    try:
        from tavily import AsyncTavilyClient
        client = AsyncTavilyClient(api_key=api_key)
        query = f"Market context, existing competitors, and potential flaws for a startup doing: {pitch_text[:300]}"
        response = await client.search(query=query)

        results = response.get('results', [])
        if not results:
            # Cache empty result too — avoid hammering Tavily for bad queries
            try:
                await sync_to_async(cache.set)(cache_key, "", timeout=300)
            except Exception:
                pass
            return ""

        context_parts = []
        for r in results[:3]:
            content = r.get('content', '')
            if content:
                context_parts.append(content)

        summary = " ".join(context_parts)[:500]

        # ── Cache result ─────────────────────────────────────────────────
        try:
            await sync_to_async(cache.set)(cache_key, summary, timeout=TAVILY_CACHE_TTL)
            logger.info("Tavily cache SET for key=%s (%d chars)", cache_key, len(summary))
        except Exception:
            logger.warning("Tavily cache write failed — result not cached")

        return summary

    except Exception as e:
        logger.error("Error fetching Tavily context: %s", e, exc_info=True)
        return ""
