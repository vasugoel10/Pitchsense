import { useState, useRef } from 'react';
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
  const inputRef = useRef(null);

  const panelTurnsLeft = MAX_PANEL_TURNS - (panelTurnCount || 0);
  const isPanel = currentMode === 'panel';
  const isPanelDisabled = isPanel && panelTurnsLeft <= 0;
  const diveUsed = activePersona ? (deepDiveCounts?.[activePersona] ?? 0) : 0;
  const diveLeft = 2 - diveUsed;

  const getPlaceholder = () => {
    if (!isPanel) {
      const name = activePersona ? activePersona.charAt(0).toUpperCase() + activePersona.slice(1) : '';
      return diveLeft > 0
        ? `Ask ${name} your hardest question... (${diveLeft} left)`
        : `No more questions with this persona`;
    }
    if (panelTurnsLeft <= 0) return 'Panel turns used — click a card to deep dive';
    return panelTurnsLeft === 1
      ? 'Your final pitch to the full panel...'
      : 'Pitch to the full panel — all 3 will respond...';
  };

  const handleSend = () => {
    if (!inputValue.trim() || isProcessing || isPanelDisabled) return;
    if (isPanel) sendPitch(inputValue, 'all', 'panel');
    else sendPitch(inputValue, activePersona, 'deep_dive');
    setInputValue('');
    inputRef.current?.focus();
  };

  const handleVoiceSend = (transcript) => {
    if (isProcessing) return;
    if (isPanel) sendPitch(transcript, 'all', 'panel');
    else sendPitch(transcript, activePersona, 'deep_dive');
  };

  const canSend = inputValue.trim() && !isProcessing && connectionStatus === 'connected' && !isPanelDisabled;

  return (
    <div className="border-t flex-none w-full" style={{ background: 'rgba(7,7,15,0.95)', borderColor: 'var(--border-default)', backdropFilter: 'blur(20px)' }}>
      <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-2.5">

        {/* Mute button */}
        <button
          onClick={toggleMute}
          className="w-10 h-10 shrink-0 flex items-center justify-center rounded-xl transition-all border text-base"
          style={{
            background: 'rgba(255,255,255,0.04)',
            borderColor: 'var(--border-default)',
          }}
          title="Toggle audio"
        >
          {isMuted ? '🔇' : '🔊'}
        </button>

        {/* Voice input */}
        <VoiceInput onResult={(text) => setInputValue(prev => prev ? prev + ' ' + text : text)} activeMicTarget={currentMode} />

        {/* Text input */}
        <div className="flex-1 relative">
          <input
            ref={inputRef}
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSend()}
            placeholder={getPlaceholder()}
            disabled={isProcessing || connectionStatus !== 'connected' || isPanelDisabled}
            className="w-full rounded-xl px-4 py-3 text-sm outline-none transition-all"
            style={{
              background: 'rgba(255,255,255,0.04)',
              border: `1px solid ${isProcessing ? 'var(--border-default)' : isPanel ? 'rgba(99,102,241,0.25)' : 'rgba(168,85,247,0.25)'}`,
              color: 'var(--text-primary)',
              caretColor: isPanel ? '#818cf8' : '#c084fc',
            }}
          />
          {inputValue.length > 2000 && (
            <div className="absolute right-3 bottom-full mb-1.5 text-[10px] text-amber-400 font-semibold bg-[#1a1307] px-2 py-1 rounded-lg border border-amber-500/20 shadow-lg backdrop-blur-sm animate-pulse">
              ⚠️ Input is {inputValue.length} chars. AI will condense it to under 2,000 characters.
            </div>
          )}
          {isProcessing && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1.5">
              {[0, 1, 2].map(i => (
                <span
                  key={i}
                  className="w-1.5 h-1.5 rounded-full bg-indigo-400 typing-dot"
                  style={{ animationDelay: `${i * 0.2}s` }}
                />
              ))}
            </div>
          )}
        </div>

        {/* Admin scorecard button */}
        {sessionStorage.getItem('pitchsense_user_role') === 'admin' && (
          <button
            onClick={generateScorecard}
            disabled={isProcessing || connectionStatus !== 'connected'}
            className="shrink-0 px-4 py-3 rounded-xl text-sm font-bold transition-all border"
            style={{
              background: 'rgba(244,63,94,0.08)',
              borderColor: 'rgba(244,63,94,0.2)',
              color: '#f87171',
              opacity: isProcessing ? 0.5 : 1,
            }}
            title="Force generate scorecard"
          >
            Verdict
          </button>
        )}

        {/* Send button */}
        <button
          onClick={handleSend}
          disabled={!canSend}
          className="shrink-0 px-6 py-3 rounded-xl font-bold text-sm transition-all relative overflow-hidden group"
          style={{
            background: canSend
              ? isPanel
                ? 'linear-gradient(135deg, #6366f1, #7c3aed)'
                : 'linear-gradient(135deg, #7c3aed, #a21caf)'
              : 'rgba(255,255,255,0.05)',
            color: canSend ? 'white' : 'var(--text-muted)',
            boxShadow: canSend
              ? isPanel ? '0 0 20px rgba(99,102,241,0.3)' : '0 0 20px rgba(168,85,247,0.3)'
              : 'none',
            border: canSend ? 'none' : '1px solid var(--border-default)',
          }}
        >
          {isProcessing ? (
            <div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
          ) : (
            <span>{isPanel ? 'Pitch →' : 'Ask →'}</span>
          )}
        </button>
      </div>
    </div>
  );
}
