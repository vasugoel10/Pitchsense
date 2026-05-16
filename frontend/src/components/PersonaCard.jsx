import { useDebate } from '../context/DebateContext';

const PERSONA_INFO = {
  investor: { name: 'Ava Chen, VC Partner', emoji: '🏦' },
  customer: { name: 'Rohan Mehta, Target User', emoji: '👤' },
  competitor: { name: 'Sara Lin, Rival Founder', emoji: '⚔️' }
};

const MAX_DEEP_DIVES = 2;

export default function PersonaCard({ personaKey }) {
  const {
    personas,
    currentMode,
    setCurrentMode,
    setActivePersona,
    activePersona,
    isProcessing,
    deepDiveCounts,
    initDeepDive,
  } = useDebate();

  const personaState = personas[personaKey];
  const info = PERSONA_INFO[personaKey];

  const isDeepDive = currentMode === 'deep_dive';
  const isActive = activePersona === personaKey;
  const diveUsed = deepDiveCounts?.[personaKey] ?? 0;
  const diveLeft = MAX_DEEP_DIVES - diveUsed;
  const hasResponse = !!personaState.fullContent;

  // In deep dive mode, hide all non-active cards
  if (isDeepDive && !isActive) return null;

  const handleDeepDiveClick = () => {
    if (!isDeepDive && !isProcessing && hasResponse) {
      // Pre-populate chat history with the existing response so it's visible immediately
      initDeepDive(personaKey);
      setCurrentMode('deep_dive');
      setActivePersona(personaKey);
    }
  };

  // Render a suggestion line with distinct styling
  const renderContent = (text) => {
    if (!text) return <span className="italic opacity-50">Waiting for pitch...</span>;
    const parts = text.split(/(\*\*Suggestion:\*\*[^\n]*)/);
    return parts.map((part, i) => {
      if (part.startsWith('**Suggestion:**')) {
        return (
          <span key={i} className="block mt-3 text-emerald-400 font-semibold text-xs border-t border-emerald-500/20 pt-2">
            {part.replace('**Suggestion:**', '💡 Suggestion:')}
          </span>
        );
      }
      return <span key={i}>{part}</span>;
    });
  };

  return (
    <div
      className={`relative flex flex-col overflow-hidden rounded-xl border bg-[var(--bg-card)] transition-all duration-300
        ${isDeepDive ? 'col-span-full h-[60vh]' : 'h-96'}
        ${!isDeepDive && hasResponse && !isProcessing ? 'hover:-translate-y-1 hover:shadow-lg hover:shadow-indigo-500/10 cursor-pointer' : ''}
        ${personaState.status === 'streaming' ? 'border-[var(--border-active)] shadow-md shadow-indigo-500/20' : 'border-[var(--border-default)]'}
      `}
      onClick={handleDeepDiveClick}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--border-default)] bg-black/20 p-4">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{info.emoji}</span>
          <span className="font-semibold text-[var(--text-primary)]">{info.name}</span>
        </div>
        <div className="flex items-center gap-2">
          {/* Deep dive usage indicator */}
          {!isDeepDive && hasResponse && (
            <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold
              ${diveLeft > 0 ? 'bg-purple-900/40 text-purple-300 border border-purple-500/20' : 'bg-gray-800 text-gray-500 border border-gray-700'}`}>
              {diveLeft > 0 ? `${diveLeft} dive${diveLeft !== 1 ? 's' : ''} left` : 'dives used'}
            </span>
          )}
          <span className={`text-xs px-2 py-1 rounded-full uppercase tracking-wider font-semibold
            ${personaState.status === 'streaming' ? 'bg-indigo-500/20 text-indigo-400 animate-pulse' :
              personaState.status === 'waiting' ? 'bg-gray-800 text-gray-400' : 'bg-emerald-500/20 text-emerald-400'}`}>
            {personaState.status}
          </span>
        </div>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto p-5 relative custom-scrollbar">
        {!isDeepDive ? (
          <div className="text-[var(--text-secondary)] text-sm leading-relaxed whitespace-pre-wrap">
            {renderContent(personaState.content || personaState.fullContent)}
            {personaState.status === 'streaming' && <span className="inline-block w-1 h-4 ml-1 bg-indigo-400 animate-ping" />}
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {personaState.chatHistory.map((msg, i) => (
              <div key={i} className={`p-3 rounded-lg max-w-[90%] text-sm whitespace-pre-wrap
                ${msg.role === 'user'
                  ? 'bg-indigo-900/40 text-indigo-100 self-end rounded-br-sm'
                  : 'bg-black/40 text-gray-200 self-start rounded-bl-sm border border-white/5'}`}>
                {msg.role === 'ai' ? renderContent(msg.content) : msg.content}
              </div>
            ))}
            {personaState.status === 'streaming' && (
              <div className="p-3 rounded-lg max-w-[90%] text-sm whitespace-pre-wrap bg-black/40 text-gray-200 self-start rounded-bl-sm border border-white/5">
                {renderContent(personaState.content)}
                <span className="inline-block w-1 h-3 ml-1 bg-indigo-400 animate-ping" />
              </div>
            )}
          </div>
        )}
      </div>

      {/* Click hint — only when has response and dives remaining */}
      {!isDeepDive && hasResponse && diveLeft > 0 && (
        <div className="absolute bottom-2 inset-x-0 text-center opacity-0 hover:opacity-100 transition-opacity">
          <span className="text-xs text-purple-400 font-medium">Click to deep dive →</span>
        </div>
      )}
    </div>
  );
}
