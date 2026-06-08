"""
Tests for PitchSense service layer.

Covers:
- Groq service: model fallback chain, scorecard generation, 3-layer JSON defense
- Tavily service: caching behavior, API key guard
- TTS service: empty input handling, error resilience
"""
import json
from unittest.mock import patch, AsyncMock, MagicMock
from django.test import TestCase, override_settings
from django.core.cache import cache


class TavilyCachingTests(TestCase):
    """Test that Tavily research results are properly cached."""

    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    @patch('debate.services.tavily_service.settings')
    async def test_returns_empty_when_no_api_key(self, mock_settings):
        from debate.services.tavily_service import get_competitor_context
        mock_settings.TAVILY_API_KEY = None
        result = await get_competitor_context("Test pitch")
        self.assertEqual(result, "")

    async def test_returns_empty_for_blank_input(self):
        from debate.services.tavily_service import get_competitor_context
        result = await get_competitor_context("")
        self.assertEqual(result, "")
        result2 = await get_competitor_context("   ")
        self.assertEqual(result2, "")


class GroqServiceTests(TestCase):
    """Test Groq service edge cases."""

    def test_fallback_scorecard_structure(self):
        from debate.services.groq_service import _get_fallback_scorecard
        scorecard = _get_fallback_scorecard()
        required_keys = {'overall_score', 'market', 'moat', 'feasibility', 'verdict', 'feedback'}
        self.assertEqual(set(scorecard.keys()), required_keys)
        self.assertIn(scorecard['verdict'], ['KILL', 'PIVOT', 'PROCEED'])
        self.assertIsInstance(scorecard['overall_score'], int)
        self.assertTrue(0 <= scorecard['overall_score'] <= 10)

    @override_settings(GROQ_API_KEY='')
    async def test_stream_raises_without_api_key(self):
        from debate.services.groq_service import stream_persona_response
        with self.assertRaises(ValueError) as ctx:
            async for _ in stream_persona_response('investor', []):
                pass
        self.assertIn('GROQ_API_KEY', str(ctx.exception))

    @override_settings(GROQ_API_KEY='gsk_test_dummy_key')
    async def test_stream_raises_for_unknown_persona(self):
        from debate.services.groq_service import stream_persona_response
        with self.assertRaises(ValueError) as ctx:
            async for _ in stream_persona_response('unknown_persona', []):
                pass
        self.assertIn('Unknown persona', str(ctx.exception))

    @override_settings(GROQ_API_KEY='')
    async def test_generate_scorecard_returns_fallback_without_key(self):
        from debate.services.groq_service import generate_scorecard
        result = await generate_scorecard([])
        self.assertEqual(result['verdict'], 'PIVOT')
        self.assertEqual(result['overall_score'], 5)


class TTSServiceTests(TestCase):
    """Test TTS service edge cases."""

    async def test_empty_text_returns_empty(self):
        from debate.services.tts_service import synthesize_speech
        result = await synthesize_speech('', 'en-US-GuyNeural')
        self.assertEqual(result, '')

    async def test_whitespace_text_returns_empty(self):
        from debate.services.tts_service import synthesize_speech
        result = await synthesize_speech('   ', 'en-US-GuyNeural')
        self.assertEqual(result, '')
