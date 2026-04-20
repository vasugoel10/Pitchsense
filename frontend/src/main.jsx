import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.jsx'
import { DebateProvider } from './context/DebateContext.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <DebateProvider>
        <App />
      </DebateProvider>
    </BrowserRouter>
  </StrictMode>,
)
