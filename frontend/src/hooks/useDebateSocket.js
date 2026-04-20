import { useState, useEffect, useRef, useCallback } from 'react';

const MAX_RECONNECT_ATTEMPTS = 5;
const BASE_RECONNECT_DELAY_MS = 1000;

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
  const currentAudioElement = useRef(null);
  const [isMuted, setIsMuted] = useState(false);

  // Reconnect state
  const reconnectAttempts = useRef(0);
  const reconnectTimer = useRef(null);
  const lastSessionId = useRef(null);
  const intentionalClose = useRef(false);

  const processAudioQueue = useCallback(() => {
    if (isPlayingAudio.current || audioQueue.current.length === 0 || isMuted) return;

    isPlayingAudio.current = true;
    const currentAudio = audioQueue.current.shift();

    const audio = new Audio(currentAudio.url);
    currentAudioElement.current = audio;
    
    audio.onended = () => {
      isPlayingAudio.current = false;
      currentAudioElement.current = null;
      URL.revokeObjectURL(currentAudio.url);
      processAudioQueue();
    };

    audio.onerror = () => {
      isPlayingAudio.current = false;
      currentAudioElement.current = null;
      URL.revokeObjectURL(currentAudio.url);
      processAudioQueue();
    };

    audio.play().catch((e) => {
      console.warn("Audio playback blocked:", e);
      isPlayingAudio.current = false;
      currentAudioElement.current = null;
      processAudioQueue();
    });
  }, [isMuted]);

  useEffect(() => {
    if (isMuted) {
      audioQueue.current = []; // Clear queue when muted
      if (currentAudioElement.current) {
        currentAudioElement.current.pause();
        currentAudioElement.current.currentTime = 0;
        currentAudioElement.current = null;
        isPlayingAudio.current = false;
      }
    } else {
      processAudioQueue();
    }
  }, [isMuted, processAudioQueue]);

  const connect = useCallback((sessionId = null, isReconnect = false) => {
    let activeSessionId = sessionId;
    if (!activeSessionId) {
      activeSessionId = sessionStorage.getItem('pitchsense_session_id');
      if (!activeSessionId) {
        activeSessionId = crypto.randomUUID();
      }
    }
    sessionStorage.setItem('pitchsense_session_id', activeSessionId);
    lastSessionId.current = activeSessionId;
    intentionalClose.current = false;

    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      intentionalClose.current = true;
      ws.current.close();
    }

    // Clear any pending reconnect timer
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${window.location.host}/ws/debate/${activeSessionId}/`;
    
    // Only reset state on fresh connections, not reconnects
    if (!isReconnect) {
      setCurrentTurn(0);
      setScorecardData(null);
      setPersonas({
        investor: { status: 'waiting', content: '', fullContent: '', chatHistory: [] },
        customer: { status: 'waiting', content: '', fullContent: '', chatHistory: [] },
        competitor: { status: 'waiting', content: '', fullContent: '', chatHistory: [] },
      });
      setIsProcessing(false);
      reconnectAttempts.current = 0;
    }
    
    setConnectionStatus('connecting');
    ws.current = new WebSocket(url);

    ws.current.onopen = () => {
      setConnectionStatus('connected');
      reconnectAttempts.current = 0; // Reset on successful connect
    };

    ws.current.onclose = (event) => {
      setConnectionStatus('disconnected');
      
      // Auto-reconnect if this wasn't an intentional close
      // and we haven't exceeded max attempts
      // Code 4001 = auth failure, 4003 = pitch limit — don't retry those
      if (
        !intentionalClose.current &&
        event.code !== 4001 &&
        event.code !== 4003 &&
        reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS
      ) {
        const delay = BASE_RECONNECT_DELAY_MS * Math.pow(2, reconnectAttempts.current);
        reconnectAttempts.current += 1;
        setConnectionStatus('reconnecting');
        
        reconnectTimer.current = setTimeout(() => {
          console.log(`Reconnect attempt ${reconnectAttempts.current}/${MAX_RECONNECT_ATTEMPTS} (delay: ${delay}ms)`);
          connect(lastSessionId.current, true);
        }, delay);
      }
    };

    ws.current.onerror = () => {
      // onerror is always followed by onclose, so reconnect logic lives there
      setConnectionStatus('error');
    };

    ws.current.onmessage = (e) => {
      const data = JSON.parse(e.data);

      if (data.type === 'connection_established') {
        setCurrentTurn(data.current_turn);
        if (data.scorecard) {
          setScorecardData(data.scorecard);
        }
        if (data.history && data.history.length > 0) {
          // Reconstruct the persona state based on history
          setPersonas(prev => {
            const newPersonas = {
              investor: { ...prev.investor, status: 'done', chatHistory: [] },
              customer: { ...prev.customer, status: 'done', chatHistory: [] },
              competitor: { ...prev.competitor, status: 'done', chatHistory: [] },
            };
            
            data.history.forEach(entry => {
              if (['investor', 'customer', 'competitor'].includes(entry.role)) {
                newPersonas[entry.role].fullContent = entry.content;
                newPersonas[entry.role].content = entry.content;
              }
            });
            return newPersonas;
          });
        }
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
      } else if (data.type === 'persona_error') {
        console.error(`Backend error for ${data.persona}:`, data.error);
        setPersonas(prev => ({
          ...prev,
          [data.persona]: { 
            ...prev[data.persona], 
            status: 'error', 
            content: prev[data.persona].content + "\n[System: An error occurred generating response.]" 
          }
        }));
        setIsProcessing(false);
      } else if (data.type === 'error') {
        console.error("Backend error:", data.message);
        setIsProcessing(false);
      }
    };
  }, [currentMode, activePersona, processAudioQueue]);

  const disconnect = useCallback(() => {
    intentionalClose.current = true;
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
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
        type: 'user_pitch',
        content,
        target,
        mode
      }));
    }
  }, []);

  const generateScorecard = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      setIsProcessing(true);
      ws.current.send(JSON.stringify({
        type: 'generate_scorecard'
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
    generateScorecard,
    isMuted,
    toggleMute
  };
}
