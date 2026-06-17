import { useEffect, useState, useRef } from 'react';

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

export default function VoiceInput({ activeMicTarget, onResult }) {
  const [isRecording, setIsRecording] = useState(false);
  const [recognition, setRecognition] = useState(null);
  
  // Use a ref for the callback to prevent useEffect from re-triggering on every text update
  const onResultRef = useRef(onResult);
  useEffect(() => {
    onResultRef.current = onResult;
  }, [onResult]);
  
  useEffect(() => {
    if (SpeechRecognition) {
      const rec = new SpeechRecognition();
      rec.continuous = true;
      rec.interimResults = true;
      rec.lang = 'en-US';
      
      rec.onstart = () => {
        setIsRecording(true);
      };

      rec.onresult = (event) => {
        let newFinalTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) {
            newFinalTranscript += event.results[i][0].transcript + ' ';
          }
        }
        if (newFinalTranscript.trim()) {
          if (onResultRef.current) {
            onResultRef.current(newFinalTranscript.trim());
          }
        }
      };

      rec.onend = () => {
        setIsRecording(false);
      };

      rec.onerror = (e) => {
        console.error('Speech recognition error', e);
        setIsRecording(false);
      };
      
      setRecognition(rec);

      return () => {
        try {
          rec.abort();
        } catch(e) {}
      };
    }
  }, []);

  const toggleMic = () => {
    if (!recognition) return;
    if (isRecording) {
      recognition.stop();
    } else {
      try {
        recognition.start();
      } catch (err) {
        console.error('Failed to start recognition', err);
      }
    }
  };

  if (!SpeechRecognition) {
    return (
      <button disabled className="p-3 rounded-xl bg-gray-800 text-gray-500" title="Voice input not supported">
        🎙️
      </button>
    );
  }

  return (
    <button 
      onClick={toggleMic}
      className={`p-3 rounded-xl transition-all duration-200 shadow-md flex items-center justify-center 
        ${isRecording ? 'bg-red-500 text-white animate-pulse shadow-red-500/40' : 'bg-[#2d2d3d] text-gray-300 hover:bg-[#3d3d4d]'}`}
      title={isRecording ? "Listening..." : "Tap to speak"}
    >
      <span className="text-lg">🎙️</span>
    </button>
  );
}
