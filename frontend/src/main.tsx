import { StrictMode } from 'react'
import ReactDOM from 'react-dom/client'
import { GuildlessApp } from './guildless-app'
import './styles/index.css'

const rootElement = document.getElementById('root')!

ReactDOM.createRoot(rootElement).render(
  <StrictMode>
    <GuildlessApp />
  </StrictMode>
)
