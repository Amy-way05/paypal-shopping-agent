import { useState, type FormEvent } from 'react'
import { api } from '../api'
import { ApiError, errorMessage } from '../api/errors'
import { AgentPassChip } from '../components/AgentPassChip'
import { Icon } from '../components/Icon'
import { usePayPalCheckout } from '../components/PayPalCheckout'
import { useToast } from '../components/Toast'
import { Button, Card, EmptyState, Field, SavedBurst, Skeleton, cx, inputClass } from '../components/ui'
import { CATEGORIES, DEMO_BUYER_ID, EMPTY } from '../lib/constants'
import { moneyExact, pct, titleCase } from '../lib/format'
import type { AgentPassDecision, Alternative, BetterDealResponse, CaptureResult } from '../types/api'

const OVERPAYING_FROM = 65 // percentile where the contract starts flagging "overpaying"

export default function BetterDeal() {
  const toast = useToast()
  const { checkout, dialog, busy } = usePayPalCheckout()

  const [form, setForm] = useState({ product_name: '', price: '', category: 'sports', merchant_name: '' })
  const [result, setResult] = useState<BetterDealResponse | null>(null)
  const [searchedCategory, setSearchedCategory] = useState('sports')
  const [finding, setFinding] = useState(false)
  const [findError, setFindError] = useState<string | null>(null)

  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [decisions, setDecisions] = useState<Record<string, AgentPassDecision>>({})
  const [confirming, setConfirming] = useState(false)
  const [buyError, setBuyError] = useState<string | null>(null)
  const [done, setDone] = useState<CaptureResult | null>(null)
  const [burst, setBurst] = useState<number | null>(null)

  const selected: Alternative | undefined = result?.alternatives.find((a) => a.product_id === selectedId)
  const decision = selected ? decisions[selected.product_id] : undefined

  function set<K extends keyof typeof form>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }))
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const price = Number(form.price)
    if (!form.product_name.trim() || !(price > 0)) {
      setFindError('Add what you are buying and its price.')
      return
    }
    setFindError(null)
    setFinding(true)
    setResult(null)
    setDone(null)
    setConfirming(false)
    setBuyError(null)
    try {
      const res = await api.findBetterDeal({
        buyer_id: DEMO_BUYER_ID,
        product_name: form.product_name.trim(),
        price,
        category: form.category,
        merchant_name: form.merchant_name.trim() || undefined,
      })
      setResult(res)
      setSearchedCategory(form.category)
      setSelectedId(res.best_option)
      setDecisions(res.best_option && res.agent_pass ? { [res.best_option]: res.agent_pass } : {})
    } catch (err) {
      setFindError(errorMessage(err))
    } finally {
      setFinding(false)
    }
  }

  function choose(alt: Alternative) {
    setSelectedId(alt.product_id)
    setConfirming(false)
    setBuyError(null)
    if (decisions[alt.product_id]) return
    // Only the best option comes with an Agent Pass decision, so ask for the others.
    api
      .checkAgentPass({ buyer_id: DEMO_BUYER_ID, amount: alt.price, category: searchedCategory, merchant_id: alt.merchant_id, action: 'purchase', planned: false })
      .then((r) => setDecisions((d) => ({ ...d, [alt.product_id]: { decision: r.decision, reason: r.reason } })))
      .catch(() => undefined)
  }

  // Called straight from a click: the popup must open before the first await.
  async function buy(confirmed: boolean) {
    if (!result || !selected) return
    setBuyError(null)
    try {
      const outcome = await checkout(() =>
        api.createOrder({
          buyer_id: DEMO_BUYER_ID,
          product_id: selected.product_id,
          product_name: selected.product_name,
          merchant_id: selected.merchant_id,
          category: searchedCategory,
          amount: selected.price,
          original_price: result.your_pick.price,
          payment_option: 'pay_now',
          source: 'better_deal',
          goal_id: null,
          confirmed,
        }),
      )
      setConfirming(false)
      if (outcome.status === 'captured') {
        setDone(outcome.capture)
        if (outcome.capture.saved > 0) setBurst(outcome.capture.saved)
        toast({ kind: 'success', title: outcome.capture.message, body: `Paid ${moneyExact(outcome.capture.amount)} at ${selected.merchant_name}.` })
      }
    } catch (err) {
      if (err instanceof ApiError && err.code === 'NEEDS_CONFIRMATION') {
        setDecisions((d) => ({ ...d, [selected.product_id]: { decision: 'NEEDS_CONFIRMATION', reason: err.detail.reason ?? err.message } }))
        setConfirming(true)
      } else if (err instanceof ApiError && err.code === 'AGENT_PASS_BLOCKED') {
        setDecisions((d) => ({ ...d, [selected.product_id]: { decision: 'BLOCK', reason: err.detail.reason ?? err.message } }))
      } else {
        setBuyError(errorMessage(err))
      }
    }
  }

  function fillExample() {
    setForm({ product_name: 'Running Insoles', price: '24', category: 'sports', merchant_name: 'FootFirst' })
  }

  return (
    <div className="grid gap-6 lg:grid-cols-5">
      <SavedBurst amount={burst} onDone={() => setBurst(null)} />
      {dialog}

      {/* Form */}
      <div className="lg:col-span-2">
        <h1 className="font-display text-2xl font-bold">Before you pay</h1>
        <p className="mt-1 text-sm text-muted">Tell us what's in your cart. We check the price against what others paid and look for the same thing cheaper.</p>
        <Card className="mt-4 p-5">
          <form onSubmit={onSubmit} className="space-y-4" noValidate>
            <Field label="What are you buying?">
              <input className={inputClass} value={form.product_name} onChange={(e) => set('product_name', e.target.value)} placeholder="Running insoles" autoComplete="off" />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Price">
                <div className="relative">
                  <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted">$</span>
                  <input className={cx(inputClass, 'pl-6')} inputMode="decimal" value={form.price} onChange={(e) => set('price', e.target.value.replace(/[^0-9.]/g, ''))} placeholder="24.00" />
                </div>
              </Field>
              <Field label="Category">
                <select className={inputClass} value={form.category} onChange={(e) => set('category', e.target.value)}>
                  {CATEGORIES.map((c) => (
                    <option key={c} value={c}>
                      {titleCase(c)}
                    </option>
                  ))}
                </select>
              </Field>
            </div>
            <Field label="Store (optional)">
              <input className={inputClass} value={form.merchant_name} onChange={(e) => set('merchant_name', e.target.value)} placeholder="FootFirst" autoComplete="off" />
            </Field>
            {findError && (
              <p role="alert" className="text-sm font-semibold text-danger">
                {findError}
              </p>
            )}
            <div className="flex items-center gap-3">
              <Button type="submit" loading={finding} className="flex-1">
                {finding ? 'Looking' : 'Find a better deal'}
              </Button>
              <Button type="button" variant="ghost" onClick={fillExample}>
                Try an example
              </Button>
            </div>
          </form>
        </Card>
      </div>

      {/* Result */}
      <div className="space-y-4 lg:col-span-3">
        {finding && (
          <div className="space-y-4" role="status" aria-label="Looking for a better deal">
            <Skeleton className="h-16" />
            <div className="grid gap-4 sm:grid-cols-2">
              <Skeleton className="h-48" />
              <Skeleton className="h-48" />
            </div>
            <Skeleton className="h-24" />
          </div>
        )}

        {!finding && !result && (
          <Card>
            <EmptyState icon="sparkle" title="Nothing compared yet" body="Add a product and price on the left. We'll show how your price compares and what we'd buy instead." />
          </Card>
        )}

        {!finding && result && (
          <>
            <div className="flex items-start gap-3 rounded-xl bg-pay-soft p-4 text-sm text-ink">
              <Icon name="sparkle" className="mt-0.5 h-5 w-5 shrink-0 text-pay-dark" />
              <p>{result.agent_message}</p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <Card className="p-5">
                <p className="text-sm font-semibold text-muted">Your pick</p>
                <p className="mt-2 font-semibold">{result.your_pick.product_name}</p>
                <p className="text-sm text-muted">{result.your_pick.merchant_name ?? 'Store not given'}</p>
                <p className="mt-4 font-display text-3xl font-bold">{moneyExact(result.your_pick.price)}</p>
              </Card>

              {selected ? (
                <Card className="border-save p-5 ring-1 ring-save/30">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-semibold text-save">Better option</p>
                    <span className="rounded-full bg-save px-2.5 py-0.5 text-xs font-bold text-white">Save {moneyExact(selected.savings)}</span>
                  </div>
                  <p className="mt-2 font-semibold">{selected.product_name}</p>
                  <p className="text-sm text-muted">{selected.merchant_name}</p>
                  <p className="mt-4 font-display text-3xl font-bold text-save">{moneyExact(selected.price)}</p>
                  <p className="mt-2 text-sm text-muted">
                    Rated {selected.rating}/10, {selected.delivery_days}-day delivery, {pct(selected.on_time_rate)} on time, {pct(selected.dispute_rate, 1)} disputes
                  </p>
                </Card>
              ) : (
                <Card className="grid place-items-center p-5 text-center">
                  <div>
                    <p className="font-display text-lg font-bold text-save">You have the best price</p>
                    <p className="mt-1 text-sm text-muted">{result.message ?? EMPTY.alternatives}</p>
                  </div>
                </Card>
              )}
            </div>

            <PriceGauge median={result.network.median_price} percentile={result.network.percentile} price={result.your_pick.price} overpaying={result.network.overpaying} />

            {result.alternatives.length > 1 && (
              <Card className="p-4">
                <p className="mb-2 text-sm font-semibold">Other options</p>
                <div role="radiogroup" aria-label="Choose a store" className="space-y-2">
                  {result.alternatives.map((alt) => (
                    <button
                      key={alt.product_id}
                      role="radio"
                      aria-checked={alt.product_id === selectedId}
                      onClick={() => choose(alt)}
                      className={cx(
                        'flex w-full items-center justify-between gap-3 rounded-lg border px-3 py-2.5 text-left text-sm',
                        alt.product_id === selectedId ? 'border-pay bg-pay-soft' : 'border-line hover:bg-paper',
                      )}
                    >
                      <span>
                        <span className="font-semibold">{alt.merchant_name}</span>
                        <span className="ml-2 text-muted">
                          {alt.rating}/10, {alt.delivery_days}-day delivery
                        </span>
                      </span>
                      <span className="font-bold">{moneyExact(alt.price)}</span>
                    </button>
                  ))}
                </div>
              </Card>
            )}

            {selected && !done && (
              <div className="space-y-3">
                <AgentPassChip decision={decision} />
                {buyError && (
                  <p role="alert" className="text-sm font-semibold text-danger">
                    {buyError}
                  </p>
                )}
                {confirming && decision?.decision === 'NEEDS_CONFIRMATION' ? (
                  <div className="flex flex-col gap-2 sm:flex-row">
                    <Button variant="save" loading={busy} className="flex-1" onClick={() => void buy(true)}>
                      Confirm and pay {moneyExact(selected.price)}
                    </Button>
                    <Button variant="secondary" onClick={() => setConfirming(false)}>
                      Not now
                    </Button>
                  </div>
                ) : (
                  <Button
                    variant="save"
                    className="w-full"
                    loading={busy}
                    disabled={decision?.decision === 'BLOCK'}
                    onClick={() => (decision?.decision === 'NEEDS_CONFIRMATION' ? setConfirming(true) : void buy(false))}
                  >
                    {decision?.decision === 'BLOCK'
                      ? 'Blocked by Agent Pass'
                      : decision?.decision === 'NEEDS_CONFIRMATION'
                        ? `Review and buy from ${selected.merchant_name}`
                        : `Buy from ${selected.merchant_name}`}
                  </Button>
                )}
              </div>
            )}

            {done && selected && (
              <div role="status" className="flex items-center gap-3 rounded-xl bg-save-soft p-4 text-save">
                <Icon name="check" className="h-6 w-6 shrink-0" />
                <div className="text-sm">
                  <p className="font-bold">
                    Paid {moneyExact(done.amount)} at {selected.merchant_name}
                    {done.saved > 0 && `. You saved ${moneyExact(done.saved)}.`}
                  </p>
                  <p>It's counted in your total on the Savings screen.</p>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function PriceGauge({ median, percentile, price, overpaying }: { median: number; percentile: number; price: number; overpaying: boolean }) {
  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-semibold">How your price compares</p>
        <p className="text-sm text-muted">
          Typical price {moneyExact(median)}. You'd pay {moneyExact(price)}.
        </p>
      </div>
      <div className="relative mt-5 h-3 rounded-full bg-save-soft" role="img" aria-label={`Your price is higher than ${percentile}% of what others paid`}>
        <div className="absolute inset-y-0 rounded-r-full bg-warn-soft" style={{ left: `${OVERPAYING_FROM}%`, right: 0 }} />
        <div className="absolute -top-1 h-5 w-0.5 bg-muted/60" style={{ left: `${OVERPAYING_FROM}%` }} />
        <div
          className={cx('absolute top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px] border-white shadow', overpaying ? 'bg-warn' : 'bg-save')}
          style={{ left: `${Math.max(2, Math.min(98, percentile))}%` }}
        />
      </div>
      <div className="relative mt-2 h-4 text-xs text-muted">
        <span className="absolute left-0">Cheaper</span>
        <span className="absolute whitespace-nowrap" style={{ left: `${OVERPAYING_FROM}%`, paddingLeft: 4 }}>
          Overpaying zone
        </span>
      </div>
      <p className={cx('mt-3 text-sm font-semibold', overpaying ? 'text-warn' : 'text-save')}>
        {overpaying ? `Your price is higher than ${percentile}% of what others paid.` : `Your price is in line with what others paid (higher than ${percentile}%).`}
      </p>
    </Card>
  )
}
