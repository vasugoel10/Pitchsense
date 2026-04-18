import { useEffect } from 'react';
import { useDebate } from './context/DebateContext';
import DebateArena from './components/DebateArena';
import ControlBar from './components/ControlBar';
import ScorecardOverlay from './components/ScorecardOverlay';

function AppContent() {
  const { connect, connectionStatus } = useDebate();

  useEffect(() => {
    connect();
  }, [connect]);

  return (
    <div className="h-screen w-full flex flex-col bg-[var(--bg-primary)] overflow-hidden font-sans text-[var(--text-primary)]">
      {/* Header */}
      <header className="flex-none h-16 border-b border-[var(--border-default)] bg-[#0a0a0f]/80 backdrop-blur-md flex items-center px-6 sticky top-0 z-20">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-[0_0_15px_rgba(99,102,241,0.4)]">
            <span className="text-white text-lg font-black leading-none pb-0.5">P</span>
          </div>
          <h1 className="text-xl font-bold tracking-tight">Pitch<span className="text-indigo-400 font-extrabold">Sense</span></h1>
        </div>
        <div className="ml-auto">
          <span className={`text-xs font-semibold px-2 py-1 rounded-full flex items-center gap-1.5
            ${connectionStatus === 'connected' ? 'text-emerald-400 bg-emerald-400/10' : 
              connectionStatus === 'error' ? 'text-red-400 bg-red-400/10' : 'text-amber-400 bg-amber-400/10'}`}>
            <span className={`w-2 h-2 rounded-full ${connectionStatus === 'connected' ? 'bg-emerald-400' : connectionStatus === 'error' ? 'bg-red-400' : 'bg-amber-400'} animate-pulse`}></span>
            {connectionStatus.toUpperCase()}
          </span>
        </div>
      </header>

      {/* Main Arena */}
      <DebateArena />

      {/* Bottom Controls */}
      <ControlBar />

      {/* Final Scorecard */}
      <ScorecardOverlay />
    </div>
  );
}

function App() {
  return <AppContent />;
}

export default App;
