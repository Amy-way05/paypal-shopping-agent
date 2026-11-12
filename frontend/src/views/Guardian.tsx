import { useCallback, useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { errorMessage } from '../api/errors'
import { CountUp } from '../components/CountUp'
import { Icon } from '../components/Icon'
import { useToast } from '../components/Toast'
import { Badge, Button, Card, EmptyState, ErrorNote, Skeleton, cx } from '../components/ui'
import { DEMO_BUYER_ID, EMPTY } from '../lib/constants'
import { money, moneyExact, shortDate } from '../lib/format'
import { actionMeta, TONE_CLASSES } from '../lib/meta'
import type { ActionStatus, AlertType, CheckState, GuardianAlert, ScanResults } from '../types/api'

const POLL_MS = 3000
const EXTRA_POLLS_AFTER_COMPLETE = 5 // statuses can still advance (resolved -> recovered) after the scan ends

const CHECKS: { type: AlertType; label: string }[] = [
  { type: 'price_drop', label: 'Price drops' },
  { type: 'overcharge', label: 'Overcharges' },
  { type: 'delivery_delay', label: 'Late deliveries' },
  { type: 'late_refund', label: 'Overdue refunds' },
]

const STEPS: { status: ActionStatus; label: string }[] = [
  { status: 'detected', label: 'Spotted' },
  { status: 'resolved', label: 'We stepped in' },
  { status: 'recovered', label: 'Money back' },
]

export default function Guardian() {
  const toast = useToast()
  const [results, setResults] = useState<ScanResults | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [starting, setStarting] = useState(false)
  const [claiming, setClaiming] = useState<string | null>(null)

  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const extraPolls = useRef(0)
  const alive = useRef(true)

  const stopPolling = useCallback(() => {
    if (timer.current) clearTimeout(timer.current)
    timer.current = null
  }, [])

  const poll = useCallback(async () => {
    try {
      const r = await api.getScanResults(DEMO_BUYER_ID)
      if (!alive.current) return
      setResults(r)
      setError(null)
      if (r.scan_status === 'running') {
        extraPolls.current = EXTRA_POLLS_AFTER_COMPLETE
      } else if (r.scan_status === 'complete' && extraPolls.current > 0) {
        extraPolls.current -= 1
      } else {
        return // idle, or complete and settled: stop
      }
      timer.current = setTimeout(poll, POLL_MS)
    } catch (e) {
      if (!alive.current) return
      setError(e)
    }
  }, [])

  // Show whatever the last scan found when the screen opens.
  useEffect(() => {
    alive.current = true
    extraPolls.current = 0
    void poll()
    return () => {
      alive.current = false
      stopPolling()
    }
  }, [poll, stopPolling])

  async function scan() {
    setStarting(true)
    setError(null)
    stopPolling()
    try {
      await api.startScan(DEMO_BUYER_ID)
      extraPolls.current = EXTRA_POLLS_AFTER_COMPLETE
      await poll()
    } catch (e) {
      setError(e)
    } finally {
      setStarting(false)
    }
  }

  async function claim(alert: GuardianAlert) {
    setClaiming(alert.alert_id)
    try {
      const res = await api.claimAlert(alert.alert_id)
      toast({ kind: 'success', title: 'Claim filed', body: res.message })
      extraPolls.current = EXTRA_POLLS_AFTER_COMPLETE
      stopPolling()
      await poll()
    } catch (e) {
      toast({ kind: 'error', title: 'Could not file the claim', body: errorMessage(e) })
    } finally {
      setClaiming(null)
    }
  }

  const status = results?.scan_status ?? 'idle'
  const running = status === 'running'
  const alerts = results?.alerts ?? []

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-bold">Guardian</h1>
          <p className="mt-1 max-w-xl text-sm text-muted">After you buy, PayPal keeps watching. It catches the things nobody checks and acts on them for you, within your Agent Pass rules.</p>
        </div>
        <Button onClick={() => void scan()} loading={starting || running}>
          <Icon name="shield" className="h-4 w-4" />
          {running ? 'Scanning' : status === 'idle' ? 'Scan my purchases' : 'Scan again'}
        </Button>
      </div>

      {error != null && <ErrorNote error={error} onRetry={() => void poll()} />}

      {/* Running counter */}
      <section className="grid gap-px overflow-hidden rounded-2xl bg-line sm:grid-cols-2" aria-label="Scan totals">
        <div className="bg-ink p-6 text-white">
          <p className="text-sm font-semibold text-white/70">Back in your pocket</p>
          <CountUp value={results?.total_recovered ?? 0} className="mt-1 block font-display text-5xl font-bold text-save-bright" duration={700} />
        </div>
        <div className="bg-white p-6">
          <p className="text-sm font-semibold text-muted">Found for you to get back</p>
          <CountUp value={results?.total_recoverable ?? 0} className="mt-1 block font-display text-5xl font-bold" duration={700} />
        </div>
      </section>

      {/* The four checks */}
      <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4" aria-label="Checks">
        {CHECKS.map((c) => (
          <CheckTile key={c.type} label={c.label} type={c.type} state={results?.checks[c.type] ?? 'pending'} scanning={running} />
        ))}
      </ul>

      {/* Activity feed */}
      <div>
        <h2 className="mb-3 font-display text-xl font-bold">What we found</h2>
        {status === 'idle' && (
          <Card>
            <EmptyState icon="shield" title="Nothing scanned yet" body={results?.message ?? EMPTY.guardianIdle} />
          </Card>
        )}
        {running && alerts.length === 0 && (
          <div className="space-y-3" role="status" aria-label="Scanning your purchases">
            <Skeleton className="h-28" />
            <Skeleton className="h-28" />
          </div>
        )}
        {status === 'complete' && alerts.length === 0 && (
          <Card>
            <EmptyState icon="check" title="All clear" body={results?.message ?? EMPTY.guardianClean} />
          </Card>
        )}
        <ul className="space-y-3">
          {alerts.map((a) => (
            <AlertCard key={a.alert_id} alert={a} claiming={claiming === a.alert_id} onClaim={() => void claim(a)} />
          ))}
          {running && alerts.length > 0 && alerts.length < CHECKS.length && <Skeleton className="h-28" />}
        </ul>
      </div>
    </div>
  )
}

function CheckTile({ label, type, state, scanning }: { label: string; type: AlertType; state: CheckState; scanning: boolean }) {
  const meta = actionMeta(type)
  const done = state === 'complete'
  const active = scanning && state !== 'complete'
  return (
    <li className={cx('flex items-center gap-3 rounded-xl border p-3.5', done ? 'border-save/40 bg-save-soft' : 'border-line bg-white')}>
      <span className={cx('grid h-9 w-9 shrink-0 place-items-center rounded-lg', done ? 'bg-white text-save' : TONE_CLASSES[meta.tone].icon)}>
        <Icon name={done ? 'check' : meta.icon} className="h-[18px] w-[18px]" />
      </span>
      <div>
        <p className="text-sm font-semibold">{label}</p>
        <p className={cx('text-xs', done ? 'text-save' : 'text-muted', active && 'animate-pulse')}>{done ? 'All checked' : active ? 'Checking now' : 'Up next'}</p>
      </div>
    </li>
  )
}

function AlertCard({ alert, claiming, onClaim }: { alert: GuardianAlert; claiming: boolean; onClaim: () => void }) {
  const meta = actionMeta(alert.type)
  const stepIndex = STEPS.findIndex((s) => s.status === alert.status)
  const money$ = alert.recoverable_amount > 0
  return (
    <li>
      <Card className="animate-rise p-5">
        <div className="flex items-start gap-4">
          <span className={cx('grid h-10 w-10 shrink-0 place-items-center rounded-lg', TONE_CLASSES[meta.tone].icon)}>
            <Icon name={meta.icon} />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="font-semibold">{alert.title}</p>
                <p className="text-xs text-muted">
                  {alert.product_name} at {alert.merchant_name}, bought {shortDate(alert.purchase_date)}
                </p>
              </div>
              {money$ ? (
                <p className={cx('font-display text-2xl font-bold', alert.status === 'recovered' ? 'text-save' : 'text-ink')}>{moneyExact(alert.recoverable_amount)}</p>
              ) : (
                <Badge tone="slate">Nothing to refund</Badge>
              )}
            </div>
            <p className="mt-2 text-sm">{alert.details}</p>

            {/* detected -> resolved -> recovered */}
            <ol className="mt-4 flex items-center gap-2 text-xs font-semibold" aria-label="Progress">
              {STEPS.map((s, i) => {
                const reached = i <= stepIndex
                // Late deliveries have nothing to recover, so the last step doesn't apply.
                if (!money$ && s.status === 'recovered') return null
                return (
                  <li key={s.status} className="flex items-center gap-2">
                    {i > 0 && <span className={cx('h-0.5 w-6 rounded', reached ? 'bg-save' : 'bg-line')} />}
                    <span className={cx('inline-flex items-center gap-1.5 rounded-full px-2.5 py-1', reached ? 'bg-save-soft text-save' : 'bg-paper text-muted')}>
                      {reached && <Icon name="check" className="h-3 w-3" />}
                      {s.label}
                    </span>
                  </li>
                )
              })}
            </ol>

            <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
              {alert.action_taken && <p className="text-sm text-muted">{alert.action_taken}</p>}
              {alert.status !== 'detected' && alert.recovery_method === 'paypal_refund' && <Badge tone="blue">PayPal refund{alert.paypal_reference ? `, ref ${alert.paypal_reference}` : ''}</Badge>}
              {alert.status !== 'detected' && alert.recovery_method === 'simulated' && <Badge tone="slate">Simulated in sandbox</Badge>}
              {alert.status === 'detected' && (
                <Button small variant="save" loading={claiming} onClick={onClaim}>
                  {alert.type === 'delivery_delay' ? 'Contact merchant' : money$ ? `Claim ${money(alert.recoverable_amount)}` : 'Take action'}
                </Button>
              )}
            </div>
          </div>
        </div>
      </Card>
    </li>
  )
}
