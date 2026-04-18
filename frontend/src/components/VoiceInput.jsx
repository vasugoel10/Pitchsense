import { useEffect, useState } from 'react';

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

export default function VoiceInput({ activeMicTarget, onSend }) {
  const [isRecording, setIsRecording] = useState(false);
  const [recognition, setRecognition] = useState(null);
  
  useEffect(() => {
    if (SpeechRecognition) {
      const rec = new SpeechRecognition();
      rec.continuous = false;
      rec.interimResults = false;
      rec.lang = 'en-US';
      
      rec.onresult = (event) => {
        let finalTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
          if (event.results[i].isFinal) finalTranscript += event.results[i][0].transcript;
        }
        if (finalTranscript) {
          onSend(finalTranscript);
        }
      };

      rec.onend = () => setIsRecording(false);
      rec.onerror = (e) => {
        console.error('Speech recognition error', e);
        setIsRecording(false);
      };
      
      setRecognition(rec);
    }
  }, [onSend]);

  const toggleMic = () => {
    if (!recognition) return;
    if (isRecording) {
      recognition.stop();
    } else {
      recognition.start();
      setIsRecording(true);
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
