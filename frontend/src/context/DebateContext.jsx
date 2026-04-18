import { createContext, useContext } from 'react';
import { useDebateSocket } from '../hooks/useDebateSocket';

const DebateContext = createContext();

export function DebateProvider({ children }) {
  const socketData = useDebateSocket();
  
  return (
    <DebateContext.Provider value={socketData}>
      {children}
    </DebateContext.Provider>
  );
}

export function useDebate() {
  return useContext(DebateContext);
}
