import { useState, useEffect } from 'react';
import { useDebate } from '../context/DebateContext';

const VERDICT_CONFIG = {
  PROCEED: {
    label: 'PROCEED',
    icon: '🚀',
    color: '#10b981',
    bg: 'rgba(16,185,129,0.12)',
    border: 'rgba(16,185,129,0.3)',
    glow: '0 0 40px rgba(16,185,129,0.3)',
    tagline: "You've got something real. Don't stop now.",
  },
  PIVOT: {
    label: 'PIVOT',
    icon: '🔄',
    color: '#f59e0b',
    bg: 'rgba(245,158,11,0.12)',
    border: 'rgba(245,158,11,0.3)',
    glow: '0 0 40px rgba(245,158,11,0.3)',
    tagline: "The idea has merit — the execution needs rethinking.",
  },
  KILL: {
    label: 'KILL IT',
    icon: '☠️',
    color: '#f43f5e',
    bg: 'rgba(244,63,94,0.12)',
    border: 'rgba(244,63,94,0.3)',
    glow: '0 0 40px rgba(244,63,94,0.3)',
    tagline: "Cut your losses. Find a better problem to solve.",
  },
};

function ScoreBar({ label, score, color, delay = 0 }) {
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const t = setTimeout(() => setWidth(score * 10), delay);
    return () => clearTimeout(t);
  }, [score, delay]);

  const getColor = (s) => {
    if (s >= 7) return '#10b981';
    if (s >= 4) return '#f59e0b';
    return '#f43f5e';
  };

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider">{label}</span>
        <span className="text-sm font-bold tabular-nums" style={{ color: getColor(score) }}>{score}/10</span>
      </div>
      <div className="h-1.5 w-full bg-white/5 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-700 ease-out"
          style={{
            width: `${width}%`,
            background: `linear-gradient(90deg, ${getColor(score)}88, ${getColor(score)})`,
          }}
        />
      </div>
    </div>
  );
}

export default function ScorecardOverlay() {
  const { scorecardData, connect } = useDebate();
  const [isOpen, setIsOpen] = useState(false);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (scorecardData) {
      setIsOpen(true);
      setTimeout(() => setVisible(true), 50);
    }
  }, [scorecardData]);

  if (!scorecardData || !isOpen) return null;

  const verdict = VERDICT_CONFIG[scorecardData.verdict] || VERDICT_CONFIG['PIVOT'];

  const handleNewPitch = () => {
    sessionStorage.removeItem('pitchsense_session_id');
    connect(crypto.randomUUID());
    setIsOpen(false);
    setVisible(false);
  };

  return (
    <div className={`fixed inset-0 z-50 flex items-center justify-center p-4 transition-all duration-500
      ${visible ? 'bg-black/75 backdrop-blur-xl' : 'bg-transparent backdrop-blur-none'}`}>

      <div className={`w-full max-w-lg relative transition-all duration-500 ${visible ? 'opacity-100 scale-100 translate-y-0' : 'opacity-0 scale-95 translate-y-4'}`}>

        {/* Card */}
        <div
          className="rounded-3xl p-8 relative overflow-hidden"
          style={{
            background: 'linear-gradient(135deg, #0e0e1a 0%, #111126 100%)',
            border: `1px solid ${verdict.border}`,
            boxShadow: `${verdict.glow}, 0 25px 50px rgba(0,0,0,0.5)`,
          }}
        >
          {/* Background glow blob */}
          <div
            className="absolute -top-24 -right-24 w-64 h-64 rounded-full blur-3xl pointer-events-none"
            style={{ background: verdict.bg }}
          />
          <div
            className="absolute -bottom-16 -left-16 w-48 h-48 rounded-full blur-3xl pointer-events-none opacity-50"
            style={{ background: verdict.bg }}
          />

          {/* Close button */}
          <button
            onClick={() => { setIsOpen(false); setVisible(false); }}
            className="absolute top-4 right-4 w-8 h-8 flex items-center justify-center rounded-full bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white transition-all z-20 text-lg"
          >
            ×
          </button>

          <div className="relative z-10 flex flex-col gap-6">

            {/* Header */}
            <div className="text-center">
              <p className="text-xs font-bold uppercase tracking-[0.2em] text-[var(--text-muted)] mb-3">Final Verdict</p>
              <div className="flex flex-col items-center gap-3">
                <div className="text-5xl animate-float">{verdict.icon}</div>
                <div
                  className="px-8 py-2.5 rounded-2xl text-2xl font-black tracking-widest"
                  style={{ background: verdict.bg, border: `2px solid ${verdict.border}`, color: verdict.color, boxShadow: verdict.glow }}
                >
                  {verdict.label}
                </div>
                <p className="text-sm text-[var(--text-muted)] italic">{verdict.tagline}</p>
              </div>
            </div>

            {/* Feedback */}
            <div
              className="rounded-xl px-4 py-3.5 text-sm leading-relaxed text-[var(--text-secondary)]"
              style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.06)' }}
            >
              {scorecardData.feedback}
            </div>

            {/* Score grid */}
            <div className="grid grid-cols-2 gap-x-6 gap-y-4">
              <ScoreBar label="Overall" score={scorecardData.overall_score} delay={100} />
              <ScoreBar label="Market" score={scorecardData.market} delay={200} />
              <ScoreBar label="Moat" score={scorecardData.moat} delay={300} />
              <ScoreBar label="Feasibility" score={scorecardData.feasibility} delay={400} />
            </div>

            {/* CTA */}
            <button
              onClick={handleNewPitch}
              className="w-full py-4 rounded-2xl font-bold text-sm tracking-wide transition-all relative overflow-hidden group"
              style={{ background: 'rgba(99,102,241,0.15)', border: '1px solid rgba(99,102,241,0.3)', color: '#a5b4fc' }}
            >
              <div className="absolute inset-0 bg-indigo-500/10 opacity-0 group-hover:opacity-100 transition-opacity" />
              <span className="relative z-10 flex items-center justify-center gap-2">
                🔁 Start a New Pitch
              </span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
