import { useDebate } from '../context/DebateContext';
import PersonaCard from './PersonaCard';

export default function DebateArena() {
  const { currentMode, currentTurn, setCurrentMode, setActivePersona, isProcessing } = useDebate();
  
  const isDeepDive = currentMode === 'deep_dive';

  const handleBackToPanel = () => {
    if (!isProcessing) {
      setCurrentMode('panel');
      setActivePersona(null);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-4 sm:p-8 w-full custom-scrollbar relative">
      <div className="max-w-6xl mx-auto h-full flex flex-col gap-6">
        
        {/* Top Info Bar */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className={`px-4 py-1.5 rounded-full text-xs font-bold tracking-widest uppercase flex items-center gap-2 border
              ${isDeepDive ? 'bg-purple-900/40 text-purple-300 border-purple-500/30 shadow-[0_0_15px_rgba(168,85,247,0.2)]' : 'bg-indigo-900/40 text-indigo-300 border-indigo-500/30'}`}>
              <span className="text-lg">{isDeepDive ? '🔍' : '📋'}</span>
              {isDeepDive ? 'Deep Dive Mode' : 'Panel Mode'}
            </div>
            
            {isDeepDive && (
              <button 
                onClick={handleBackToPanel}
                disabled={isProcessing}
                className="px-4 py-1.5 text-xs font-semibold rounded-full bg-gray-800 text-gray-300 hover:bg-gray-700 hover:text-white transition-colors disabled:opacity-50"
              >
                ← Back to Panel
              </button>
            )}
          </div>

          <div className="flex items-center gap-3">
            <span className="text-sm font-semibold text-gray-400">Turn</span>
            <div className="flex gap-1.5">
              {[1,2,3,4,5].map(t => (
                <div key={t} className={`h-2.5 w-8 rounded-full transition-all duration-300
                  ${t < currentTurn ? 'bg-indigo-500 shadow-[0_0_8px_rgba(99,102,241,0.5)]' : 
                    t === currentTurn ? 'bg-indigo-400 animate-pulse outline outline-1 outline-offset-1 outline-indigo-500 shadow-[0_0_10px_rgba(99,102,241,0.6)]' : 'bg-[#2d2d3d]'}`} />
              ))}
            </div>
          </div>
        </div>

        {/* Persona Grid/Layout */}
        <div className={`grid gap-6 flex-1 transition-all duration-500 ease-in-out
          ${isDeepDive ? 'grid-cols-1 max-w-4xl mx-auto w-full' : 'grid-cols-1 lg:grid-cols-3'}
        `}>
          <PersonaCard personaKey="investor" />
          <PersonaCard personaKey="customer" />
          <PersonaCard personaKey="competitor" />
        </div>
      </div>
    </div>
  );
}
