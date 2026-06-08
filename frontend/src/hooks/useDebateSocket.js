import { useState, useEffect, useRef, useCallback } from 'react';

const MAX_RECONNECT_ATTEMPTS = 5;
const BASE_RECONNECT_DELAY_MS = 1000;
const HEARTBEAT_INTERVAL_MS = 30000;  // Send ping every 30s to keep connection alive

export function useDebateSocket() {
  const [connectionStatus, setConnectionStatus] = useState('disconnected');
  const [currentTurn, setCurrentTurn] = useState(0);
  const [panelTurnCount, setPanelTurnCount] = useState(0);
  const [deepDiveCounts, setDeepDiveCounts] = useState({});
  const [isProcessing, setIsProcessing] = useState(false);
  const [currentMode, setCurrentMode] = useState('panel');
  const [activePersona, setActivePersona] = useState(null);
  const [scorecardData, setScorecardData] = useState(null);

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

  const reconnectAttempts = useRef(0);
  const reconnectTimer = useRef(null);
  const heartbeatTimer = useRef(null);
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
      audioQueue.current = [];
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

    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${window.location.host}/ws/debate/${activeSessionId}/`;

    if (!isReconnect) {
      setCurrentTurn(0);
      setPanelTurnCount(0);
      setDeepDiveCounts({});
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
      reconnectAttempts.current = 0;

      // Start heartbeat to keep connection alive through proxies/load balancers
      if (heartbeatTimer.current) clearInterval(heartbeatTimer.current);
      heartbeatTimer.current = setInterval(() => {
        if (ws.current?.readyState === WebSocket.OPEN) {
          ws.current.send(JSON.stringify({ type: 'ping' }));
        }
      }, HEARTBEAT_INTERVAL_MS);
    };

    ws.current.onclose = (event) => {
      setConnectionStatus('disconnected');
      if (heartbeatTimer.current) {
        clearInterval(heartbeatTimer.current);
        heartbeatTimer.current = null;
      }
      if (
        !intentionalClose.current &&
        event.code !== 4001 &&  // Not authenticated
        event.code !== 4002 &&  // Session belongs to another user
        event.code !== 4003 &&  // Pitch limit exceeded
        reconnectAttempts.current < MAX_RECONNECT_ATTEMPTS
      ) {
        // Exponential backoff with jitter to prevent thundering herd
        const baseDelay = BASE_RECONNECT_DELAY_MS * Math.pow(2, reconnectAttempts.current);
        const jitter = Math.random() * baseDelay * 0.3;
        const delay = baseDelay + jitter;
        reconnectAttempts.current += 1;
        setConnectionStatus('reconnecting');
        reconnectTimer.current = setTimeout(() => {
          connect(lastSessionId.current, true);
        }, delay);
      }
    };

    ws.current.onerror = () => {
      setConnectionStatus('error');
    };

    ws.current.onmessage = (e) => {
      const data = JSON.parse(e.data);

      if (data.type === 'connection_established') {
        setCurrentTurn(data.current_turn || 0);
        if (data.panel_turn_count !== undefined) setPanelTurnCount(data.panel_turn_count);
        if (data.deep_dive_counts) setDeepDiveCounts(data.deep_dive_counts);
        if (data.scorecard) setScorecardData(data.scorecard);
        if (data.history && data.history.length > 0) {
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
          // In deep dive mode, append streaming content as new AI bubble
          if (prev[data.persona].status === 'streaming' && newChatHistory.length > 0) {
            newChatHistory.push({ role: 'ai', content: data.full_content });
          }
          return {
            ...prev,
            [data.persona]: {
              ...prev[data.persona],
              status: 'done',
              fullContent: data.full_content,
              content: data.full_content,
              chatHistory: newChatHistory,
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
        if (data.current_turn !== undefined) setCurrentTurn(data.current_turn);
        if (data.panel_turn_count !== undefined) setPanelTurnCount(data.panel_turn_count);
        if (data.deep_dive_counts !== undefined) setDeepDiveCounts(data.deep_dive_counts);

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
  }, [processAudioQueue]);

  const disconnect = useCallback(() => {
    intentionalClose.current = true;
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    if (heartbeatTimer.current) {
      clearInterval(heartbeatTimer.current);
      heartbeatTimer.current = null;
    }
    if (ws.current) ws.current.close();
  }, []);

  const sendPitch = useCallback((content, target = 'all', mode = 'panel') => {
    if (ws.current?.readyState === WebSocket.OPEN && content.trim()) {
      setIsProcessing(true);

      if (mode === 'deep_dive') {
        setPersonas(prev => {
          const newChatHistory = [...prev[target].chatHistory];
          newChatHistory.push({ role: 'user', content });
          return {
            ...prev,
            [target]: { ...prev[target], chatHistory: newChatHistory, status: 'waiting', content: '' }
          };
        });
      }

      ws.current.send(JSON.stringify({ type: 'user_pitch', content, target, mode }));
    }
  }, []);

  // Enter deep dive — immediately show the persona's latest response as first chat bubble
  const initDeepDive = useCallback((personaKey) => {
    setPersonas(prev => {
      const persona = prev[personaKey];
      if (persona.fullContent && persona.chatHistory.length === 0) {
        return {
          ...prev,
          [personaKey]: {
            ...persona,
            chatHistory: [{ role: 'ai', content: persona.fullContent }]
          }
        };
      }
      return prev;
    });
  }, []);

  const generateScorecard = useCallback(() => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      setIsProcessing(true);
      ws.current.send(JSON.stringify({ type: 'generate_scorecard' }));
    }
  }, []);

  const toggleMute = () => setIsMuted(m => !m);

  return {
    connectionStatus,
    currentTurn,
    panelTurnCount,
    deepDiveCounts,
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
    initDeepDive,
    generateScorecard,
    isMuted,
    toggleMute,
  };
}
