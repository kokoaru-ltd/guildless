import { StrictMode } from 'react'
import ReactDOM from 'react-dom/client'
import { App } from './app'
import './styles/index.css'

const rootElement = document.getElementById('root')!

ReactDOM.createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>
)
