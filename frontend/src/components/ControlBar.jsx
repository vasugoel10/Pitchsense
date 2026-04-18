import { useState } from 'react';
import { useDebate } from '../context/DebateContext';
import VoiceInput from './VoiceInput';

export default function ControlBar() {
  const { connectionStatus, currentMode, isProcessing, activePersona, sendPitch, isMuted, toggleMute } = useDebate();
  const [inputValue, setInputValue] = useState('');

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
    setInputValue((prev) => prev + (prev ? ' ' : '') + transcript);
    // Auto-send after a voice transcript completes
    setTimeout(() => {
      if (currentMode === 'panel') sendPitch(transcript, 'all', 'panel');
      else sendPitch(transcript, activePersona, 'deep_dive');
      setInputValue('');
    }, 500);
  };

  const onKeyDown = (e) => {
    if (e.key === 'Enter') handleSend();
  };

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
          placeholder={currentMode === 'panel' ? "Speak your pitch to the panel..." : `Ask ${activePersona} a follow-up test...`}
          className="flex-1 bg-black/40 border border-[var(--border-default)] focus:border-indigo-500 rounded-xl px-4 py-3 text-sm text-gray-200 outline-none transition-colors placeholder:text-gray-600"
          disabled={isProcessing || connectionStatus !== 'connected'}
        />

        <button 
          onClick={handleSend}
          disabled={isProcessing || !inputValue.trim() || connectionStatus !== 'connected'}
          className={`px-6 py-3 rounded-xl font-semibold transition-all shadow-lg
            ${isProcessing || !inputValue.trim() || connectionStatus !== 'connected'
              ? 'bg-gray-800 text-gray-500 cursor-not-allowed hidden sm:block'
              : currentMode === 'panel' 
                ? 'bg-indigo-600 text-white hover:bg-indigo-500 shadow-indigo-500/25' 
                : 'bg-purple-600 text-white hover:bg-purple-500 shadow-purple-500/25'
            }`}
        >
          {currentMode === 'panel' ? 'Send Pitch' : 'Send'}
        </button>
      </div>
    </div>
  );
}
