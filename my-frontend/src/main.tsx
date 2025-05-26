import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
// Note: The code above is the entry point for a React application that renders the main App component into the root element of the HTML document. It uses TypeScript and imports global styles from 'index.css'.