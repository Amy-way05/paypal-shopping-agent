import { StrictMode, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './index.css'

type ReturnKind = 'approved' | 'cancel'

// After the buyer approves (or cancels) in PayPal, the backend's return_url / cancel_url send the popup to
// <frontend>/checkout/return or /checkout/cancel (API.md v0.3). This page tells the window that opened the
// popup, so checkout can continue, then closes itself.
function returnKind(): ReturnKind | null {
  const path = window.location.pathname
  if (path.startsWith('/checkout/cancel')) return 'cancel'
  if (path.startsWith('/checkout/return')) return 'approved'
  const legacy = new URLSearchParams(window.location.search).get('paypal')
  if (legacy) return legacy === 'cancel' ? 'cancel' : 'approved'
  return null
}

function PayPalReturn({ kind }: { kind: ReturnKind }) {
  useEffect(() => {
    try {
      window.opener?.postMessage({ type: 'paypal-return', kind }, window.location.origin)
    } catch {
      // opener can be unavailable after a cross-site redirect; the main window still retries the capture on its own
    }
    const t = setTimeout(() => window.close(), 900)
    return () => clearTimeout(t)
  }, [kind])

  return (
    <div className="grid h-screen place-items-center p-6 text-center">
      <div>
        <p className="font-display text-2xl font-bold">{kind === 'cancel' ? 'Payment cancelled' : 'Payment approved'}</p>
        <p className="mt-1 text-muted">You can close this window and go back to the app.</p>
      </div>
    </div>
  )
}

const kind = returnKind()

createRoot(document.getElementById('root')!).render(<StrictMode>{kind ? <PayPalReturn kind={kind} /> : <App />}</StrictMode>)
