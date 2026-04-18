import { useDebate } from '../context/DebateContext';

const PERSONA_INFO = {
  investor: { name: 'Ava Chen, VC Partner', emoji: '🏦' },
  customer: { name: 'Rohan Mehta, Target User', emoji: '👤' },
  competitor: { name: 'Sara Lin, Rival Founder', emoji: '⚔️' }
};

export default function PersonaCard({ personaKey }) {
  const { 
    personas, 
    currentMode, 
    setCurrentMode, 
    setActivePersona, 
    activePersona,
    isProcessing
  } = useDebate();
  
  const personaState = personas[personaKey];
  const info = PERSONA_INFO[personaKey];

  const isDeepDive = currentMode === 'deep_dive';
  const isActive = activePersona === personaKey;
  
  if (isDeepDive && !isActive) return null;

  const handleDeepDiveClick = () => {
    if (!isDeepDive && !isProcessing) {
      setCurrentMode('deep_dive');
      setActivePersona(personaKey);
    }
  };

  return (
    <div 
      className={`relative flex flex-col overflow-hidden rounded-xl border bg-[var(--bg-card)] transition-all duration-300
        ${isDeepDive ? 'col-span-full h-[60vh]' : 'h-96 hover:-translate-y-1 hover:shadow-lg hover:shadow-indigo-500/10'}
        ${personaState.status === 'streaming' ? 'border-[var(--border-active)] shadow-md shadow-indigo-500/20' : 'border-[var(--border-default)]'}
        ${!isDeepDive && !isProcessing ? 'cursor-pointer' : ''}
      `}
      onClick={handleDeepDiveClick}
    >
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[var(--border-default)] bg-black/20 p-4">
        <div className="flex items-center gap-3">
          <span className="text-2xl">{info.emoji}</span>
          <span className="font-semibold text-[var(--text-primary)]">{info.name}</span>
        </div>
        <span className={`text-xs px-2 py-1 rounded-full uppercase tracking-wider font-semibold
          ${personaState.status === 'streaming' ? 'bg-indigo-500/20 text-indigo-400 animate-pulse' : 
            personaState.status === 'waiting' ? 'bg-gray-800 text-gray-400' : 'bg-emerald-500/20 text-emerald-400'}`}>
          {personaState.status}
        </span>
      </div>

      {/* Content Area */}
      <div className="flex-1 overflow-y-auto p-5 relative custom-scrollbar">
        {!isDeepDive ? (
          <div className="text-[var(--text-secondary)] text-sm leading-relaxed whitespace-pre-wrap">
            {personaState.content || personaState.fullContent || <span className="italic opacity-50">Waiting for pitch...</span>}
            {personaState.status === 'streaming' && <span className="inline-block w-1 h-4 ml-1 bg-indigo-400 animate-ping" />}
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            {personaState.chatHistory.map((msg, i) => (
              <div key={i} className={`p-3 rounded-lg max-w-[90%] text-sm whitespace-pre-wrap
                ${msg.role === 'user' 
                  ? 'bg-indigo-900/40 text-indigo-100 self-end rounded-br-sm' 
                  : 'bg-black/40 text-gray-200 self-start rounded-bl-sm border border-white/5'}`}>
                {msg.content}
              </div>
            ))}
            {personaState.status === 'streaming' && (
              <div className="p-3 rounded-lg max-w-[90%] text-sm whitespace-pre-wrap bg-black/40 text-gray-200 self-start rounded-bl-sm border border-white/5">
                {personaState.content}
                <span className="inline-block w-1 h-3 ml-1 bg-indigo-400 animate-ping" />
              </div>
            )}
          </div>
        )}
      </div>

      {/* Click Hint */}
      {!isDeepDive && (
        <div className="absolute bottom-2 inset-x-0 text-center opacity-0 hover:opacity-100 transition-opacity">
          <span className="text-xs text-indigo-400 font-medium">Click to deep dive →</span>
        </div>
      )}
    </div>
  );
}
