import { useDebate } from '../context/DebateContext';
import PersonaCard from './PersonaCard';

const MAX_TOTAL_TURNS = 5;

export default function DebateArena() {
  const { currentMode, currentTurn, setCurrentMode, setActivePersona, isProcessing, panelTurnCount } = useDebate();
  const isDeepDive = currentMode === 'deep_dive';

  const handleBackToPanel = () => {
    if (!isProcessing) {
      setCurrentMode('panel');
      setActivePersona(null);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-4 sm:p-6 w-full custom-scrollbar relative">

      {/* Subtle ambient background blobs */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-indigo-600/4 rounded-full blur-3xl" />
        <div className="absolute bottom-1/4 right-1/4 w-80 h-80 bg-purple-600/4 rounded-full blur-3xl" />
      </div>

      <div className="max-w-6xl mx-auto flex flex-col gap-5 relative z-10">

        {/* Top Info Bar */}
        <div className="flex items-center justify-between">

          {/* Mode badge + back button */}
          <div className="flex items-center gap-3">
            <div className={`px-4 py-1.5 rounded-full text-xs font-bold tracking-widest uppercase flex items-center gap-2 border
              ${isDeepDive
                ? 'bg-purple-950/50 text-purple-300 border-purple-500/30 shadow-[0_0_20px_rgba(168,85,247,0.15)]'
                : 'bg-indigo-950/50 text-indigo-300 border-indigo-500/25'}`}>
              <span>{isDeepDive ? '🔍' : '📋'}</span>
              {isDeepDive ? 'Deep Dive' : 'Panel Mode'}
            </div>

            {isDeepDive && (
              <button
                onClick={handleBackToPanel}
                disabled={isProcessing}
                className="px-3 py-1.5 text-xs font-semibold rounded-full bg-white/5 text-gray-300 hover:bg-white/10 hover:text-white transition-all border border-white/8 disabled:opacity-40"
              >
                ← Back to Panel
              </button>
            )}
          </div>

          {/* Turn tracker */}
          <div className="flex items-center gap-3">
            <span className="text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider">Turn</span>
            <div className="flex items-center gap-1">
              {Array.from({ length: MAX_TOTAL_TURNS }, (_, i) => {
                const turnNum = i + 1;
                const isPast = turnNum < currentTurn;
                const isCurrent = turnNum === currentTurn;
                const isFuture = turnNum > currentTurn;
                return (
                  <div
                    key={i}
                    title={`Turn ${turnNum}`}
                    className={`rounded-full transition-all duration-500 ${
                      isPast ? 'w-2 h-2 bg-indigo-500' :
                      isCurrent ? 'w-5 h-2 bg-indigo-400' :
                      'w-2 h-2 bg-[var(--border-default)]'
                    }`}
                    style={isCurrent ? { boxShadow: '0 0 8px rgba(99,102,241,0.6)' } : {}}
                  />
                );
              })}
            </div>
            <span className="text-xs text-[var(--text-muted)] tabular-nums">
              {currentTurn}/{MAX_TOTAL_TURNS}
            </span>
          </div>
        </div>

        {/* Persona Grid */}
        <div className={`grid gap-5 transition-all duration-500 ease-in-out
          ${isDeepDive ? 'grid-cols-1' : 'grid-cols-1 lg:grid-cols-3'}`}>
          <PersonaCard personaKey="investor" />
          <PersonaCard personaKey="customer" />
          <PersonaCard personaKey="competitor" />
        </div>

        {/* Panel turn exhausted hint */}
        {!isDeepDive && panelTurnCount >= 2 && (
          <div className="text-center py-2 animate-slide-up">
            <p className="text-xs text-[var(--text-muted)]">
              Both panel turns used — click any persona card to go deeper with one-on-one questions
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
