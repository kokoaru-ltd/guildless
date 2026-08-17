import { StrictMode } from 'react'
import ReactDOM from 'react-dom/client'
import { OutcomeView } from './outcome-view'
import './styles/index.css'

const rootElement = document.getElementById('root')!

ReactDOM.createRoot(rootElement).render(
  <StrictMode>
    <OutcomeView />
  </StrictMode>
)
