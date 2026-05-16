import { useState } from 'react';
import { useDebate } from '../context/DebateContext';
import VoiceInput from './VoiceInput';

const MAX_PANEL_TURNS = 2;

export default function ControlBar() {
  const {
    connectionStatus, currentMode, isProcessing, activePersona,
    sendPitch, generateScorecard, isMuted, toggleMute,
    panelTurnCount, deepDiveCounts,
  } = useDebate();
  const [inputValue, setInputValue] = useState('');

  const panelTurnsLeft = MAX_PANEL_TURNS - (panelTurnCount || 0);
  const personaName = activePersona ? activePersona.charAt(0).toUpperCase() + activePersona.slice(1) : '';

  const handleSend = () => {
    if (!inputValue.trim() || isProcessing) return;
    if (currentMode === 'panel') {
      sendPitch(inputValue, 'all', 'panel');
    } else {
      sendPitch(inputValue, activePersona, 'deep_dive');
    }
    setInputValue('');
  };

  const handleVoiceSend = (transcript) => {
    if (isProcessing) return;
    if (currentMode === 'panel') {
      sendPitch(transcript, 'all', 'panel');
    } else {
      sendPitch(transcript, activePersona, 'deep_dive');
    }
  };

  const onKeyDown = (e) => {
    if (e.key === 'Enter') handleSend();
  };

  const getPlaceholder = () => {
    if (currentMode === 'deep_dive') {
      const used = deepDiveCounts?.[activePersona] ?? 0;
      const left = 2 - used;
      return `Ask ${personaName} a follow-up... (${left} question${left !== 1 ? 's' : ''} left)`;
    }
    return panelTurnsLeft > 0
      ? `Pitch to the full panel... (${panelTurnsLeft} pitch${panelTurnsLeft !== 1 ? 'es' : ''} left)`
      : 'No panel pitches left — click a persona card to deep dive';
  };

  const isPanelDisabled = currentMode === 'panel' && panelTurnsLeft <= 0;

  return (
    <div className="bg-[var(--bg-card)] border-t border-[var(--border-default)] p-4 shadow-xl z-10 w-full relative">
      <div className="max-w-6xl mx-auto flex items-center gap-3">
        <button
          onClick={toggleMute}
          className="p-3 rounded-xl bg-black/30 border border-white/5 hover:bg-black/50 transition-colors"
          title="Toggle TTS Audio"
        >
          {isMuted ? '🔇' : '🔊'}
        </button>

        <VoiceInput onSend={handleVoiceSend} activeMicTarget={currentMode} />

        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder={getPlaceholder()}
          className="flex-1 bg-black/40 border border-[var(--border-default)] focus:border-indigo-500 rounded-xl px-4 py-3 text-sm text-gray-200 outline-none transition-colors placeholder:text-gray-600"
          disabled={isProcessing || connectionStatus !== 'connected' || isPanelDisabled}
        />

        {sessionStorage.getItem('pitchsense_user_role') === 'admin' && (
          <button
            onClick={generateScorecard}
            disabled={isProcessing || connectionStatus !== 'connected'}
            className={`px-4 py-3 rounded-xl font-semibold transition-all shadow-lg text-sm
              ${isProcessing || connectionStatus !== 'connected'
                ? 'bg-gray-800 text-gray-500 cursor-not-allowed hidden sm:block'
                : 'bg-red-600/20 text-red-400 border border-red-500/30 hover:bg-red-600/30'
              }`}
            title="Force Scorecard Generation"
          >
            Scorecard
          </button>
        )}

        <button
          onClick={handleSend}
          disabled={isProcessing || !inputValue.trim() || connectionStatus !== 'connected' || isPanelDisabled}
          className={`px-6 py-3 rounded-xl font-semibold transition-all shadow-lg
            ${isProcessing || !inputValue.trim() || connectionStatus !== 'connected' || isPanelDisabled
              ? 'bg-gray-800 text-gray-500 cursor-not-allowed hidden sm:block'
              : currentMode === 'panel'
                ? 'bg-indigo-600 text-white hover:bg-indigo-500 shadow-indigo-500/25'
                : 'bg-purple-600 text-white hover:bg-purple-500 shadow-purple-500/25'
            }`}
        >
          {currentMode === 'panel' ? 'Send Pitch' : 'Ask'}
        </button>
      </div>
    </div>
  );
}
