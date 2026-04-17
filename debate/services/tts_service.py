"""
Text-to-Speech service using edge-tts.

Converts persona text responses to base64-encoded MP3 audio.
The consumer sends this audio to the frontend via WebSocket for playback.

Architecture: Called AFTER text streaming completes (never blocks text chunks).
Returns base64 string; frontend decodes and plays as Audio blob.
"""
import base64
import io
import logging

import edge_tts

logger = logging.getLogger(__name__)


async def synthesize_speech(text: str, voice: str) -> str:
    """
    Convert text to speech using edge-tts and return base64-encoded MP3.

    Args:
        text:  The text to synthesize.
        voice: The edge-tts voice name (e.g., 'en-US-GuyNeural').

    Returns:
        Base64-encoded MP3 audio string. Empty string on failure.
    """
    if not text or not text.strip():
        return ''

    try:
        communicate = edge_tts.Communicate(text, voice)
        audio_buffer = io.BytesIO()

        async for chunk in communicate.stream():
            if chunk['type'] == 'audio':
                audio_buffer.write(chunk['data'])

        audio_bytes = audio_buffer.getvalue()
        if not audio_bytes:
            logger.warning("edge-tts returned empty audio for voice=%s", voice)
            return ''

        return base64.b64encode(audio_bytes).decode('utf-8')

    except Exception as e:
        logger.error("TTS synthesis failed (voice=%s): %s", voice, e, exc_info=True)
        return ''
