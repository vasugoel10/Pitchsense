import logging
from django.conf import settings

logger = logging.getLogger(__name__)

async def get_competitor_context(pitch_text: str) -> str:
    """
    Fetch market context from Tavily asynchronously for the Competitor persona.
    """
    api_key = getattr(settings, 'TAVILY_API_KEY', None)
    if not api_key:
        logger.warning("TAVILY_API_KEY is not set. Skipping competitor context research.")
        return ""
        
    try:
        from tavily import AsyncTavilyClient
        client = AsyncTavilyClient(api_key=api_key)
        query = f"Market context, existing competitors, and potential flaws for a startup doing: {pitch_text[:500]}"
        response = await client.search(query=query)
        
        results = response.get('results', [])
        if not results:
            return ""
            
        context_parts = []
        for r in results[:3]:
            content = r.get('content', '')
            if content:
                context_parts.append(content)
        
        summary = " ".join(context_parts)[:500]
        return summary
    except Exception as e:
        logger.error(f"Error fetching Tavily context: {e}")
        return ""
