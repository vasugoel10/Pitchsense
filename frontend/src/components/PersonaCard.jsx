import { useDebate } from '../context/DebateContext';

// Per-persona theme config
const PERSONA_THEME = {
  investor: {
    name: 'Ava Chen',
    role: 'VC Partner',
    emoji: '🏦',
    color: 'var(--investor-color)',
    bg: 'var(--investor-bg)',
    border: 'var(--investor-border)',
    glow: 'var(--investor-glow)',
    streamBorder: '#f59e0b',
    badge: 'bg-amber-500/15 text-amber-300 border border-amber-500/25',
    statusDot: 'bg-amber-400',
  },
  customer: {
    name: 'Rohan Mehta',
    role: 'Target User',
    emoji: '👤',
    color: 'var(--customer-color)',
    bg: 'var(--customer-bg)',
    border: 'var(--customer-border)',
    glow: 'var(--customer-glow)',
    streamBorder: '#22d3ee',
    badge: 'bg-cyan-500/15 text-cyan-300 border border-cyan-500/25',
    statusDot: 'bg-cyan-400',
  },
  competitor: {
    name: 'Sara Lin',
    role: 'Rival Founder',
    emoji: '⚔️',
    color: 'var(--competitor-color)',
    bg: 'var(--competitor-bg)',
    border: 'var(--competitor-border)',
    glow: 'var(--competitor-glow)',
    streamBorder: '#f43f5e',
    badge: 'bg-rose-500/15 text-rose-300 border border-rose-500/25',
    statusDot: 'bg-rose-400',
  },
};

const MAX_DEEP_DIVES = 2;

// Parse and render markdown-like content with Suggestion highlighting
function renderContent(text, streaming = false) {
  if (!text && !streaming) return null;
  if (!text) return null;

  // Split on **Suggestion:** pattern (with or without emoji prefix)
  const suggestionRegex = /(\*\*Suggestion:\*\*|💡 Suggestion:)(.*?)(?=\n|$)/;
  const match = text.match(suggestionRegex);

  if (match) {
    const before = text.slice(0, match.index);
    const suggestionText = match[2]?.trim() || '';
    return (
      <>
        <span className="whitespace-pre-wrap">{before.trim()}</span>
        {suggestionText && (
          <div className="mt-3 flex items-start gap-2 bg-emerald-950/40 border border-emerald-500/25 rounded-lg px-3 py-2.5">
            <span className="text-emerald-400 mt-0.5 shrink-0">💡</span>
            <p className="text-emerald-300 text-xs font-medium leading-relaxed">
              <span className="text-emerald-400 font-bold">Suggestion: </span>
              {suggestionText}
            </p>
          </div>
        )}
      </>
    );
  }

  return <span className="whitespace-pre-wrap">{text}</span>;
}

function TypingIndicator({ color }) {
  return (
    <div className="flex items-center gap-1.5 py-2">
      {[0, 1, 2].map(i => (
        <span
          key={i}
          className="typing-dot"
          style={{ color, animationDelay: `${i * 0.2}s` }}
        />
      ))}
    </div>
  );
}

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
  const theme = PERSONA_THEME[personaKey];

  const isDeepDive = currentMode === 'deep_dive';
  const isActive = activePersona === personaKey;
  const diveUsed = deepDiveCounts?.[personaKey] ?? 0;
  const diveLeft = MAX_DEEP_DIVES - diveUsed;
  const hasResponse = !!personaState.fullContent;
  const isStreaming = personaState.status === 'streaming';
  const isWaiting = personaState.status === 'waiting';

  if (isDeepDive && !isActive) return null;

  const handleDeepDiveClick = () => {
    if (!isDeepDive && !isProcessing && hasResponse && diveLeft > 0) {
      initDeepDive(personaKey);
      setCurrentMode('deep_dive');
      setActivePersona(personaKey);
    }
  };

  const cardStyle = isStreaming
    ? { borderColor: theme.streamBorder, boxShadow: `0 0 20px ${theme.glow}` }
    : hasResponse && !isDeepDive
    ? { borderColor: theme.border }
    : {};

  return (
    <div
      className={`relative flex flex-col overflow-hidden rounded-2xl border transition-all duration-300 group
        ${isDeepDive ? 'col-span-full' : 'h-80'}
        ${!isDeepDive && hasResponse && !isProcessing && diveLeft > 0 ? 'cursor-pointer hover:-translate-y-1' : ''}
        ${isStreaming ? 'border-current' : isWaiting && !hasResponse ? 'border-[var(--border-default)]' : 'border-[var(--border-default)]'}
      `}
      style={{
        background: hasResponse || isStreaming ? theme.bg : 'var(--bg-card)',
        ...cardStyle,
      }}
      onClick={handleDeepDiveClick}
    >
      {/* Accent top bar */}
      <div
        className="absolute top-0 left-0 right-0 h-[2px] rounded-t-2xl transition-all duration-500"
        style={{
          background: isStreaming || hasResponse
            ? `linear-gradient(90deg, transparent, ${theme.color}, transparent)`
            : 'transparent',
          opacity: isStreaming ? 1 : hasResponse ? 0.5 : 0,
        }}
      />

      {/* Header */}
      <div className="flex items-center justify-between px-5 pt-4 pb-3 border-b border-[var(--border-default)]/60">
        <div className="flex items-center gap-3">
          {/* Persona avatar */}
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center text-lg shrink-0 transition-all duration-300"
            style={{
              background: `linear-gradient(135deg, ${theme.glow}, ${theme.bg})`,
              border: `1px solid ${theme.border}`,
              boxShadow: isStreaming ? `0 0 12px ${theme.glow}` : 'none',
            }}
          >
            {theme.emoji}
          </div>
          <div>
            <div className="font-bold text-sm text-white leading-tight">{theme.name}</div>
            <div className="text-[11px] font-medium" style={{ color: theme.color }}>{theme.role}</div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Deep dive counter badge */}
          {!isDeepDive && hasResponse && (
            <span className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${diveLeft > 0 ? theme.badge : 'bg-gray-800/60 text-gray-500 border border-gray-700/50'}`}>
              {diveLeft > 0 ? `${diveLeft} dive${diveLeft !== 1 ? 's' : ''}` : 'done'}
            </span>
          )}
          {/* Status chip */}
          <div className={`flex items-center gap-1.5 text-[10px] px-2.5 py-1 rounded-full font-bold uppercase tracking-wider
            ${isStreaming ? 'bg-indigo-500/15 text-indigo-300 border border-indigo-500/25' :
              isWaiting && !hasResponse ? 'bg-[var(--border-default)]/60 text-[var(--text-muted)]' :
              'bg-emerald-500/12 text-emerald-400 border border-emerald-500/20'}`}>
            {isStreaming && <span className={`w-1.5 h-1.5 rounded-full ${theme.statusDot} animate-pulse`} />}
            {isStreaming ? 'Live' : isWaiting && !hasResponse ? 'Waiting' : 'Done'}
          </div>
        </div>
      </div>

      {/* Content Area */}
      <div className={`flex-1 overflow-y-auto custom-scrollbar ${isDeepDive ? 'p-5' : 'px-5 py-4'}`}
        style={{ minHeight: isDeepDive ? '50vh' : undefined }}>

        {!isDeepDive ? (
          // Panel mode content
          <div className="text-[var(--text-secondary)] text-sm leading-relaxed">
            {isStreaming ? (
              <>
                {renderContent(personaState.content)}
                <TypingIndicator color={theme.color} />
              </>
            ) : hasResponse ? (
              <div className="animate-slide-up">
                {renderContent(personaState.fullContent)}
              </div>
            ) : (
              // Waiting state
              <div className="flex flex-col items-center justify-center h-40 gap-3 animate-breathe">
                <div className="text-3xl opacity-20">{theme.emoji}</div>
                <p className="text-xs text-[var(--text-muted)] font-medium">Listening for your pitch...</p>
              </div>
            )}
          </div>
        ) : (
          // Deep dive chat mode
          <div className="flex flex-col gap-4">
            {personaState.chatHistory.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'} animate-slide-up`}
                style={{ animationDelay: `${i * 0.05}s` }}
              >
                <div className={`max-w-[85%] text-sm leading-relaxed rounded-2xl px-4 py-3
                  ${msg.role === 'user'
                    ? 'bg-indigo-600/25 text-indigo-100 rounded-br-sm border border-indigo-500/20'
                    : 'bg-[var(--border-default)]/60 text-[var(--text-primary)] rounded-bl-sm border border-white/5'
                  }`}>
                  {msg.role === 'ai' ? renderContent(msg.content) : msg.content}
                </div>
              </div>
            ))}
            {isStreaming && (
              <div className="flex justify-start animate-slide-up">
                <div className="max-w-[85%] text-sm leading-relaxed rounded-2xl rounded-bl-sm px-4 py-3 bg-[var(--border-default)]/60 text-[var(--text-primary)] border border-white/5">
                  {personaState.content
                    ? renderContent(personaState.content, true)
                    : <TypingIndicator color={theme.color} />}
                </div>
              </div>
            )}
            {!isProcessing && personaState.chatHistory.length <= 1 && (
              <div className="text-center py-4">
                <p className="text-xs text-[var(--text-muted)]">
                  Ask {theme.name} your hardest question ↑
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Click to deep dive hint */}
      {!isDeepDive && hasResponse && diveLeft > 0 && !isProcessing && (
        <div className="px-5 pb-3 pt-1 border-t border-[var(--border-default)]/40 flex items-center justify-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity duration-200">
          <span className="text-[10px] font-semibold" style={{ color: theme.color }}>
            Click to go deep with {theme.name} →
          </span>
        </div>
      )}
    </div>
  );
}
