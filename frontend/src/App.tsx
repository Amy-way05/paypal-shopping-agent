import { useEffect, useState } from 'react'
import { api } from './api'
import { errorMessage } from './api/errors'
import { AgentChat } from './components/AgentChat'
import { ErrorBoundary } from './components/ErrorBoundary'
import { Icon } from './components/Icon'
import { ToastProvider, useToast } from './components/Toast'
import { cx } from './components/ui'
import { useAsync } from './hooks/useAsync'
import { useRoute } from './hooks/useRoute'
import { USE_MOCKS } from './lib/config'
import { APP_NAME } from './lib/constants'
import AgentPassSettings from './views/AgentPassSettings'
import BetterDeal from './views/BetterDeal'
import Guardian from './views/Guardian'
import MerchantDashboard from './views/MerchantDashboard'
import SaveForIt from './views/SaveForIt'
import SavingsDashboard from './views/SavingsDashboard'

const BUYER_SECTIONS = [
  { path: 'savings', label: 'Savings', view: SavingsDashboard },
  { path: 'better-deal', label: 'Better deal', view: BetterDeal },
  { path: 'save-for-it', label: 'Save for it', view: SaveForIt },
  { path: 'guardian', label: 'Guardian', view: Guardian },
  { path: 'agent-pass', label: 'Agent Pass', view: AgentPassSettings },
]

export default function App() {
  return (
    <ToastProvider>
      <Shell />
    </ToastProvider>
  )
}

function Shell() {
  const route = useRoute()
  const toast = useToast()
  const [chatOpen, setChatOpen] = useState(false)
  const [epoch, setEpoch] = useState(0) // bump to remount the current screen after a demo reset
  const business = route === 'business'
  const section = BUYER_SECTIONS.find((s) => s.path === route) ?? BUYER_SECTIONS[0]
  const View = business ? MerchantDashboard : section.view

  async function resetDemo() {
    if (!window.confirm('Reset the demo data back to its starting state?')) return
    try {
      await api.resetDemo()
      setEpoch((e) => e + 1)
      toast({ kind: 'success', title: 'Demo reset', body: 'Savings, goals, scans and Agent Pass are back to the start.' })
    } catch (e) {
      toast({ kind: 'error', title: 'Could not reset', body: errorMessage(e) })
    }
  }

  return (
    <div className="min-h-screen">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-3 focus:top-3 focus:z-[70] focus:rounded-lg focus:bg-white focus:px-3 focus:py-2">
        Skip to content
      </a>

      <header className="sticky top-0 z-30 border-b border-line bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6">
          <a href="#/savings" className="flex items-center gap-2.5" aria-label={`${APP_NAME}, home`}>
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-ink text-save-bright">
              <Icon name="check" className="h-5 w-5" />
            </span>
            <span className="font-display text-lg font-bold">{APP_NAME}</span>
          </a>

          <nav aria-label="Switch between buyer and business" className="order-3 flex w-full rounded-lg bg-paper p-1 sm:order-none sm:ml-2 sm:w-auto">
            <a
              href="#/savings"
              aria-current={!business ? 'page' : undefined}
              className={cx('flex-1 rounded-md px-4 py-1.5 text-center text-sm font-semibold sm:flex-none', !business ? 'bg-white text-ink shadow-sm' : 'text-muted hover:text-ink')}
            >
              For You
            </a>
            <a
              href="#/business"
              aria-current={business ? 'page' : undefined}
              className={cx('flex-1 rounded-md px-4 py-1.5 text-center text-sm font-semibold sm:flex-none', business ? 'bg-white text-ink shadow-sm' : 'text-muted hover:text-ink')}
            >
              For Your Business
            </a>
          </nav>

          <div className="ml-auto">
            <StatusPill />
          </div>
        </div>

        {!business && (
          <nav aria-label="For You sections" className="mx-auto max-w-6xl overflow-x-auto px-4 sm:px-6">
            <ul className="flex gap-1">
              {BUYER_SECTIONS.map((s) => {
                const active = s.path === section.path
                return (
                  <li key={s.path}>
                    <a
                      href={`#/${s.path}`}
                      aria-current={active ? 'page' : undefined}
                      className={cx('block whitespace-nowrap border-b-2 px-3 py-2.5 text-sm font-semibold', active ? 'border-pay text-ink' : 'border-transparent text-muted hover:text-ink')}
                    >
                      {s.label}
                    </a>
                  </li>
                )
              })}
            </ul>
          </nav>
        )}
      </header>

      <main id="main" className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
        <ErrorBoundary key={`${business ? 'business' : section.path}-${epoch}`}>
          <View />
        </ErrorBoundary>
      </main>

      <footer className="mx-auto max-w-6xl px-4 pb-24 pt-4 text-xs text-muted sm:px-6">
        <p>
          PayPal sandbox only. No real money moves.{' '}
          <button className="font-semibold text-pay-dark hover:underline" onClick={() => void resetDemo()}>
            Reset demo data
          </button>
        </p>
      </footer>

      {!business && (
        <>
          <button
            onClick={() => setChatOpen(true)}
            className="fixed bottom-5 right-5 z-30 flex items-center gap-2 rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white shadow-lg hover:bg-navy"
          >
            <Icon name="bolt" className="h-4 w-4 text-save-bright" />
            Ask the agent
          </button>
          <AgentChat open={chatOpen} onClose={() => setChatOpen(false)} />
        </>
      )}
    </div>
  )
}

function StatusPill() {
  const { data, error, loading, reload } = useAsync(() => api.health())

  // Keep checking: every few seconds while the backend is down (so the pill recovers if it starts late), slowly once healthy.
  useEffect(() => {
    if (USE_MOCKS) return
    const t = setInterval(() => void reload(), error || !data ? 4000 : 30000)
    return () => clearInterval(t)
  }, [error, data, reload])

  if (USE_MOCKS) {
    return (
      <span className="rounded-full bg-pay-soft px-3 py-1 text-xs font-semibold text-pay-dark" title="Screens are using built-in sample data. Set VITE_USE_MOCKS=false to use the backend.">
        Sample data
      </span>
    )
  }
  if (loading) return <span className="skeleton block h-6 w-24 rounded-full" aria-hidden="true" />
  if (error || !data) {
    return (
      <span className="rounded-full bg-danger-soft px-3 py-1 text-xs font-semibold text-danger" title={errorMessage(error)}>
        Backend offline
      </span>
    )
  }
  const ready = data.paypal_configured && data.gemini_configured
  return (
    <span className={cx('rounded-full px-3 py-1 text-xs font-semibold', ready ? 'bg-save-soft text-save' : 'bg-warn-soft text-ink')} title={`PayPal ${data.paypal_configured ? 'configured' : 'not configured'}, Gemini ${data.gemini_configured ? 'configured' : 'not configured'}`}>
      {ready ? 'Live sandbox' : 'Backend needs keys'}
    </span>
  )
}
