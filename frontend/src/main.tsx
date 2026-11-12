import { StrictMode, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './index.css'

// If the backend sets PayPal's return_url / cancel_url to "<frontend>/?paypal=return" (or "cancel"),
// the popup lands here. The opener is already polling the order, so this page only tells the
// buyer they're done and closes itself.
function PayPalReturn({ kind }: { kind: string }) {
  useEffect(() => {
    const t = setTimeout(() => window.close(), 800)
    return () => clearTimeout(t)
  }, [])
  return (
    <div className="grid h-screen place-items-center p-6 text-center">
      <div>
        <p className="font-display text-2xl font-bold">{kind === 'cancel' ? 'Payment cancelled' : 'Payment approved'}</p>
        <p className="mt-1 text-muted">You can close this window and go back to the app.</p>
      </div>
    </div>
  )
}

const paypal = new URLSearchParams(window.location.search).get('paypal')

createRoot(document.getElementById('root')!).render(<StrictMode>{paypal ? <PayPalReturn kind={paypal} /> : <App />}</StrictMode>)
