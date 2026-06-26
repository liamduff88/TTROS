import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.jsx'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
)

function installTelegramBridgeStatus() {
  const el = document.createElement('div')
  el.id = 'telegram-bridge-status'
  el.style.cssText = 'position:fixed;right:18px;bottom:18px;z-index:9999;border:1px solid rgba(184,155,99,.45);background:rgba(13,20,24,.96);color:#F7F3EA;border-radius:14px;padding:12px 14px;font:12px Inter,system-ui,sans-serif;box-shadow:0 12px 40px rgba(0,0,0,.35);min-width:230px'
  document.body.appendChild(el)

  async function refreshTelegramBridgeStatus() {
    try {
      const res = await fetch('http://127.0.0.1:8010/api/connectors/telegram/status', { cache: 'no-store' })
      const data = await res.json()
      el.innerHTML = `
        <div style="letter-spacing:.16em;text-transform:uppercase;color:#B89B63;margin-bottom:6px">Telegram Bridge</div>
        <div style="font-size:16px;font-weight:700">${data.running ? 'Running' : 'Stopped'}</div>
        <div style="color:#D8D0C2;margin-top:4px">Pilot: northshore_honda_sales_demo</div>
        <div style="color:#D8D0C2">Reports: ${data.pilot_report_count ?? 0}</div>
      `
    } catch {
      el.innerHTML = `
        <div style="letter-spacing:.16em;text-transform:uppercase;color:#B89B63;margin-bottom:6px">Telegram Bridge</div>
        <div style="font-size:16px;font-weight:700">Status unavailable</div>
      `
    }
  }

  refreshTelegramBridgeStatus()
  setInterval(refreshTelegramBridgeStatus, 10000)
}

installTelegramBridgeStatus()
