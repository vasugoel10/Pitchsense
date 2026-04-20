import { useState, useEffect } from 'react';
import { useDebate } from '../context/DebateContext';

export default function ScorecardOverlay() {
  const { scorecardData, connect } = useDebate();
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    if (scorecardData) {
      setIsOpen(true);
    }
  }, [scorecardData]);

  if (!scorecardData || !isOpen) return null;

  const getVerdictStyle = (v) => {
    switch (v) {
      case 'PROCEED': return 'bg-emerald-500 shadow-[0_0_40px_rgba(16,185,129,0.4)] text-white border-emerald-400';
      case 'PIVOT': return 'bg-amber-500 shadow-[0_0_40px_rgba(245,158,11,0.4)] text-white border-amber-400';
      case 'KILL': return 'bg-red-500 shadow-[0_0_40px_rgba(239,68,68,0.4)] text-white border-red-400';
      default: return 'bg-gray-600 text-white';
    }
  };

  const getVerdictIcon = (v) => {
    switch (v) {
      case 'PROCEED': return '🚀';
      case 'PIVOT': return '🔄';
      case 'KILL': return '☠️';
      default: return '📊';
    }
  };

  const BarInfo = ({ label, score }) => (
    <div className="mb-4">
      <div className="flex justify-between mb-1.5">
        <span className="text-sm font-semibold text-gray-300">{label}</span>
        <span className="text-sm font-bold text-white">{score}/10</span>
      </div>
      <div className="h-2 w-full bg-black/40 rounded-full overflow-hidden">
        <div 
          className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all duration-1000 ease-out" 
          style={{ width: `${score * 10}%` }}
        />
      </div>
    </div>
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 backdrop-blur-xl bg-black/60 animate-in fade-in duration-500">
      <div className="w-full max-w-lg rounded-2xl bg-[#111118] border border-[#2d2d3d] p-8 shadow-2xl relative overflow-hidden flex flex-col gap-6 animate-in zoom-in-95 duration-500">
        
        {/* Background glow top right */}
        <div className="absolute -top-20 -right-20 w-48 h-48 bg-indigo-500/20 blur-3xl rounded-full pointer-events-none" />

        <button 
          onClick={() => setIsOpen(false)}
          className="absolute top-4 right-4 text-gray-400 hover:text-white transition-colors z-20 p-2"
          title="Close scorecard and return to debate"
        >
          ✕
        </button>

        <div className="text-center relative z-10">
          <h2 className="text-3xl font-extrabold text-white mb-2">Final Verdict</h2>
          <p className="text-sm text-gray-400">The panel has reached a consensus.</p>
        </div>

        <div className="flex flex-col items-center gap-3 relative z-10 my-4">
          <div className="text-5xl drop-shadow-xl">{getVerdictIcon(scorecardData.verdict)}</div>
          <div className={`px-6 py-2 rounded-full border-2 text-2xl font-black tracking-widest ${getVerdictStyle(scorecardData.verdict)}`}>
            {scorecardData.verdict}
          </div>
        </div>

        <div className="bg-black/30 p-5 rounded-xl text-sm leading-relaxed text-gray-200 border border-white/5 relative z-10 whitespace-pre-wrap flex-1 overflow-y-auto max-h-40 custom-scrollbar">
          {scorecardData.feedback}
        </div>

        <div className="relative z-10 mt-2">
          <BarInfo label="Overall Score" score={scorecardData.overall_score} />
        </div>

        <button 
          onClick={() => {
            sessionStorage.removeItem('pitchsense_session_id');
            connect(crypto.randomUUID());
            setIsOpen(false);
          }}
          className="w-full py-4 mt-2 bg-[#2d2d3d] hover:bg-[#3d3d4d] text-white rounded-xl font-bold tracking-wide transition-colors relative z-10 shadow-lg"
        >
          Start New Pitch
        </button>
      </div>
    </div>
  );
}
