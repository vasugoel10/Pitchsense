import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { DebateProvider } from './context/DebateContext.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <DebateProvider>
      <App />
    </DebateProvider>
  </StrictMode>,
)
