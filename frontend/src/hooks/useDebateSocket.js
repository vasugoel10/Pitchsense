import { useState, useEffect, useRef, useCallback } from 'react';

export function useDebateSocket() {
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [currentTurn, setCurrentTurn] = useState(0);
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentMode, setCurrentMode] = useState('panel'); // 'panel' or 'deep_dive'
  const [activePersona, setActivePersona] = useState(null); // null or persona key
  const [scorecardData, setScorecardData] = useState(null);

  // Persona states
  const [personas, setPersonas] = useState({
    investor: { status: 'waiting', content: '', fullContent: '', chatHistory: [] },
    customer: { status: 'waiting', content: '', fullContent: '', chatHistory: [] },
    competitor: { status: 'waiting', content: '', fullContent: '', chatHistory: [] },
  });

  const ws = useRef(null);
  const audioQueue = useRef([]);
  const isPlayingAudio = useRef(false);
  const [isMuted, setIsMuted] = useState(false);

  const processAudioQueue = useCallback(() => {
    if (isPlayingAudio.current || audioQueue.current.length === 0 || isMuted) return;

    isPlayingAudio.current = true;
    const currentAudio = audioQueue.current.shift();

    const audio = new Audio(currentAudio.url);
    
    audio.onended = () => {
      isPlayingAudio.current = false;
      URL.revokeObjectURL(currentAudio.url);
      processAudioQueue();
    };

    audio.onerror = () => {
      isPlayingAudio.current = false;
      URL.revokeObjectURL(currentAudio.url);
      processAudioQueue();
    };

    audio.play().catch((e) => {
      console.warn("Audio playback blocked:", e);
      isPlayingAudio.current = false;
      processAudioQueue();
    });
  }, [isMuted]);

  useEffect(() => {
    if (isMuted && isPlayingAudio.current) {
      audioQueue.current = []; // Clear queue when muted
    }
    processAudioQueue();
  }, [isMuted, processAudioQueue]);

  const connect = useCallback((sessionId = crypto.randomUUID()) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.close();
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    // Use window.location.host, but if running with Vite proxy, might need adjustment.
    // For local Django + React built as static, the host is exactly the django server port.
    const url = `${protocol}//${window.location.host}/ws/debate/${sessionId}/`;
    
    ws.current = new WebSocket(url);

    ws.current.onopen = () => setConnectionStatus('connected');
    ws.current.onclose = () => setConnectionStatus('disconnected');
    ws.current.onerror = () => setConnectionStatus('error');

    ws.current.onmessage = (e) => {
      const data = JSON.parse(e.data);

      if (data.type === 'connection_established') {
        setCurrentTurn(data.current_turn);
      } else if (data.type === 'turn_started') {
        setCurrentTurn(data.turn);
        setIsProcessing(true);
        // Clear all cards content
        setPersonas(prev => ({
          investor: { ...prev.investor, content: '', status: 'waiting' },
          customer: { ...prev.customer, content: '', status: 'waiting' },
          competitor: { ...prev.competitor, content: '', status: 'waiting' },
        }));
      } else if (data.type === 'persona_start') {
        setPersonas(prev => ({
          ...prev,
          [data.persona]: { ...prev[data.persona], status: 'streaming' }
        }));
      } else if (data.type === 'persona_chunk') {
        setPersonas(prev => ({
          ...prev,
          [data.persona]: { ...prev[data.persona], content: prev[data.persona].content + data.content }
        }));
      } else if (data.type === 'persona_done') {
        setPersonas(prev => {
          const newChatHistory = [...prev[data.persona].chatHistory];
          // If in deep dive mode, append the AI response
          if (currentMode === 'deep_dive' && activePersona === data.persona) {
            newChatHistory.push({ role: 'ai', content: data.full_content });
          }
          return {
            ...prev,
            [data.persona]: { 
              ...prev[data.persona], 
              status: 'done', 
              fullContent: data.full_content,
              chatHistory: newChatHistory 
            }
          };
        });
      } else if (data.type === 'persona_audio') {
        const binaryString = window.atob(data.audio_base64);
        const len = binaryString.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) bytes[i] = binaryString.charCodeAt(i);
        const blob = new Blob([bytes], { type: 'audio/mpeg' });
        const url = URL.createObjectURL(blob);
        audioQueue.current.push({ persona: data.persona, url });
        processAudioQueue();
      } else if (data.type === 'scorecard_generated') {
        setScorecardData(data.scorecard);
      } else if (data.type === 'turn_complete') {
        setIsProcessing(false);
      } else if (data.type === 'error') {
        console.error("Backend error:", data.message);
        setIsProcessing(false);
      }
    };
  }, [currentMode, activePersona, processAudioQueue]);

  const disconnect = useCallback(() => {
    if (ws.current) {
      ws.current.close();
    }
  }, []);

  const sendPitch = useCallback((content, target = 'all', mode = 'panel') => {
    if (ws.current?.readyState === WebSocket.OPEN && content.trim()) {
      setIsProcessing(true);
      
      if (mode === 'deep_dive') {
        setPersonas(prev => {
          const newChatHistory = [...prev[target].chatHistory];
          // Start a new chat history with context if empty
          if (newChatHistory.length === 0 && prev[target].fullContent) {
            newChatHistory.push({ role: 'ai', content: prev[target].fullContent });
          }
          newChatHistory.push({ role: 'user', content });
          return {
            ...prev,
            [target]: { ...prev[target], chatHistory: newChatHistory, status: 'waiting', content: '' }
          };
        });
      }
      
      ws.current.send(JSON.stringify({
        type: 'user_pitch', // Fixed message type
        content,
        target,
        mode
      }));
    }
  }, []);

  const toggleMute = () => setIsMuted(m => !m);

  return {
    connectionStatus,
    currentTurn,
    isProcessing,
    scorecardData,
    personas,
    currentMode,
    setCurrentMode,
    activePersona,
    setActivePersona,
    connect,
    disconnect,
    sendPitch,
    isMuted,
    toggleMute
  };
}
