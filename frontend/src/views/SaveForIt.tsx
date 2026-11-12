import { useState, type FormEvent } from 'react'
import { Line, LineChart, ResponsiveContainer, Tooltip, YAxis } from 'recharts'
import { api } from '../api'
import { errorMessage } from '../api/errors'
import { Icon } from '../components/Icon'
import { usePayPalCheckout } from '../components/PayPalCheckout'
import { useToast } from '../components/Toast'
import { Badge, Button, Card, EmptyState, ErrorNote, Field, ProgressBar, SavedBurst, Skeleton, cx, inputClass } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { CATEGORIES, DEMO_BUYER_ID, EMPTY } from '../lib/constants'
import { money, moneyExact, shortDate, titleCase } from '../lib/format'
import type { Goal, GoalStatus, PaymentOption } from '../types/api'

const STATUS: Record<GoalStatus, { label: string; tone: 'slate' | 'green' | 'blue' }> = {
  saving: { label: 'Saving', tone: 'slate' },
  deal_found: { label: 'Deal found', tone: 'green' },
  ready: { label: 'Ready to buy', tone: 'green' },
  purchased: { label: 'Purchased', tone: 'blue' },
}

export default function SaveForIt() {
  const { data, error, loading, reload, retry } = useAsync(() => api.listGoals(DEMO_BUYER_ID))
  const [adding, setAdding] = useState(false)

  if (loading && !data) {
    return (
      <div className="space-y-4" role="status" aria-label="Loading goals">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-80 w-full" />
      </div>
    )
  }
  if (error && !data) return <ErrorNote error={error} onRetry={retry} />

  const goals = data?.goals ?? []
  const showForm = adding || goals.length === 0

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-bold">Save for it</h1>
          <p className="mt-1 max-w-xl text-sm text-muted">Pick something you want. PayPal saves a little each week, watches the price and coupons, and asks before it buys.</p>
        </div>
        {goals.length > 0 && !adding && (
          <Button variant="secondary" onClick={() => setAdding(true)}>
            <Icon name="plus" className="h-4 w-4" /> Add a goal
          </Button>
        )}
      </div>

      {showForm && (
        <GoalForm
          onCancel={goals.length > 0 ? () => setAdding(false) : undefined}
          onCreated={() => {
            setAdding(false)
            void reload()
          }}
        />
      )}

      {goals.length === 0 && !showForm && (
        <Card>
          <EmptyState icon="target" title="No goals yet" body={data?.message ?? EMPTY.goals} />
        </Card>
      )}

      {goals.map((g) => (
        <GoalCard key={g.goal_id} goal={g} onChanged={() => void reload()} />
      ))}
    </div>
  )
}

function GoalForm({ onCreated, onCancel }: { onCreated: () => void; onCancel?: () => void }) {
  const toast = useToast()
  const [form, setForm] = useState({ product_name: '', category: 'electronics', target_price: '', weekly_amount: '' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    const target = Number(form.target_price)
    const weekly = Number(form.weekly_amount)
    if (!form.product_name.trim() || !(target > 0) || !(weekly > 0)) {
      setError('Add a product, a target price and how much to save each week.')
      return
    }
    setError(null)
    setSaving(true)
    try {
      await api.createGoal({ buyer_id: DEMO_BUYER_ID, product_name: form.product_name.trim(), category: form.category, target_price: target, weekly_amount: weekly })
      toast({ kind: 'success', title: 'Goal created', body: `Saving ${money(weekly)} a week toward ${form.product_name.trim()}.` })
      setForm({ product_name: '', category: 'electronics', target_price: '', weekly_amount: '' })
      onCreated()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Card className="p-5">
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5" noValidate>
        <div className="sm:col-span-2">
          <Field label="What do you want?">
            <input className={inputClass} value={form.product_name} onChange={(e) => setForm({ ...form, product_name: e.target.value })} placeholder="Dell XPS 14 laptop" autoComplete="off" />
          </Field>
        </div>
        <Field label="Category">
          <select className={inputClass} value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {titleCase(c)}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Target price">
          <input className={inputClass} inputMode="decimal" value={form.target_price} onChange={(e) => setForm({ ...form, target_price: e.target.value.replace(/[^0-9.]/g, '') })} placeholder="1200" />
        </Field>
        <Field label="Save each week">
          <input className={inputClass} inputMode="decimal" value={form.weekly_amount} onChange={(e) => setForm({ ...form, weekly_amount: e.target.value.replace(/[^0-9.]/g, '') })} placeholder="50" />
        </Field>
        <div className="flex flex-wrap items-center gap-3 sm:col-span-2 lg:col-span-5">
          <Button type="submit" loading={saving}>
            Start saving
          </Button>
          {onCancel && (
            <Button type="button" variant="ghost" onClick={onCancel}>
              Cancel
            </Button>
          )}
          {error && (
            <p role="alert" className="text-sm font-semibold text-danger">
              {error}
            </p>
          )}
        </div>
      </form>
    </Card>
  )
}

function GoalCard({ goal, onChanged }: { goal: Goal; onChanged: () => void }) {
  const toast = useToast()
  const { checkout, dialog, busy } = usePayPalCheckout()
  const [confirm, setConfirm] = useState<PaymentOption | null>(null)
  const [skipping, setSkipping] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [burst, setBurst] = useState<number | null>(null)

  const st = STATUS[goal.status]
  const purchased = goal.status === 'purchased'
  const ready = goal.status === 'ready'
  const chartData = goal.price_history.map((p) => ({ date: p.date, price: p.price }))
  const atLow = goal.final_price <= goal.all_time_low

  async function skip(weeks: number) {
    setSkipping(true)
    setErr(null)
    try {
      await api.simulateWeek(goal.goal_id, weeks)
      onChanged()
    } catch (e) {
      setErr(errorMessage(e))
    } finally {
      setSkipping(false)
    }
  }

  // Called from a click: checkout() opens the popup before its first await.
  async function buy(option: PaymentOption) {
    setErr(null)
    try {
      const outcome = await checkout(() => api.purchaseGoal(goal.goal_id, { payment_option: option, confirmed: true }))
      setConfirm(null)
      if (outcome.status === 'captured') {
        if (outcome.capture.saved > 0) setBurst(outcome.capture.saved)
        toast({ kind: 'success', title: outcome.capture.message, body: `${goal.product_name} bought for ${moneyExact(outcome.capture.amount)}.` })
        onChanged()
      }
    } catch (e) {
      setErr(errorMessage(e))
    }
  }

  const optionLabel = (o: PaymentOption) => (o === 'pay_now' ? 'in full' : goal.financing_options.find((f) => f.type === o)?.label ?? o)

  return (
    <Card className="overflow-hidden">
      <SavedBurst amount={burst} onDone={() => setBurst(null)} />
      {dialog}

      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-5">
        <div>
          <h2 className="font-display text-xl font-bold">{goal.product_name}</h2>
          <p className="text-sm text-muted">
            {goal.merchant_name ? `${goal.merchant_name}, ` : ''}target {money(goal.target_price)}, {money(goal.weekly_amount)} a week
          </p>
        </div>
        <Badge tone={st.tone}>{st.label}</Badge>
      </div>

      <div className="grid gap-6 p-5 lg:grid-cols-2">
        {/* Progress */}
        <div>
          <div className="flex items-baseline justify-between">
            <p className="font-display text-3xl font-bold">{money(goal.saved_so_far)}</p>
            <p className="text-sm text-muted">of {money(goal.final_price)}</p>
          </div>
          <div className="mt-3">
            <ProgressBar value={goal.progress_pct} label={`${goal.product_name} savings progress`} />
          </div>
          <p className="mt-2 text-sm text-muted">
            {purchased ? 'Bought and counted in your savings.' : goal.weeks_remaining === 0 ? 'You have enough saved.' : `About ${goal.weeks_remaining} more ${goal.weeks_remaining === 1 ? 'week' : 'weeks'} at this pace.`}
          </p>

          <p className="mt-4 flex items-start gap-2 rounded-lg bg-pay-soft p-3 text-sm">
            <Icon name="sparkle" className="mt-0.5 h-4 w-4 shrink-0 text-pay-dark" />
            <span>{goal.agent_message}</span>
          </p>
        </div>

        {/* Price watch */}
        <div>
          <div className="flex items-baseline justify-between">
            <p className="text-sm font-semibold">Price watch</p>
            <p className="text-sm text-muted">
              Lowest seen {money(goal.all_time_low)}
              {atLow && <span className="font-semibold text-save">, now</span>}
            </p>
          </div>
          <div className="mt-1 h-24" role="img" aria-label={`Price history, now ${money(goal.current_price)}`}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData} margin={{ top: 8, right: 8, left: 8, bottom: 4 }}>
                <YAxis hide domain={['dataMin - 15', 'dataMax + 15']} />
                <Tooltip
                  content={({ active, payload }) =>
                    active && payload?.length ? (
                      <div className="rounded-lg border border-line bg-white px-3 py-1.5 text-sm shadow">
                        <p className="font-semibold">{moneyExact(Number(payload[0].value))}</p>
                        <p className="text-xs text-muted">{shortDate(String(payload[0].payload.date))}</p>
                      </div>
                    ) : null
                  }
                />
                <Line type="stepAfter" dataKey="price" stroke="#0070E0" strokeWidth={2.5} dot={false} activeDot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <dl className="mt-2 grid grid-cols-3 gap-2 text-sm">
            <Mini label="Price now" value={money(goal.current_price)} />
            <Mini label={goal.best_coupon ? `Code ${goal.best_coupon.code}` : 'Coupon'} value={goal.best_coupon ? `−${money(goal.best_coupon.discount)}` : 'None yet'} />
            <Mini label="You'd pay" value={money(goal.final_price)} strong />
          </dl>
        </div>
      </div>

      {!purchased && (
        <div className="space-y-4 border-t border-line bg-paper/60 p-5">
          {confirm ? (
            <div className="flex flex-col gap-3 rounded-xl border border-pay/30 bg-pay-soft p-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm font-semibold text-pay-dark">
                Buy now? {goal.product_name} for {moneyExact(goal.final_price)}, {optionLabel(confirm)}.
              </p>
              <div className="flex gap-2">
                <Button variant="save" loading={busy} onClick={() => void buy(confirm)}>
                  Confirm purchase
                </Button>
                <Button variant="secondary" onClick={() => setConfirm(null)}>
                  Not yet
                </Button>
              </div>
            </div>
          ) : (
            ready && (
              <div className="flex flex-col gap-3 rounded-xl bg-save-soft p-4 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm font-semibold text-save">Goal hit. Your savings cover the price.</p>
                <Button variant="save" onClick={() => setConfirm('pay_now')}>
                  Buy now for {money(goal.final_price)}
                </Button>
              </div>
            )
          )}

          <div>
            <p className="text-sm font-semibold">Can't wait?</p>
            <div className="mt-2 grid gap-3 sm:grid-cols-3">
              {goal.financing_options.map((f) => (
                <div key={f.type} className="flex flex-col rounded-xl border border-line bg-white p-4">
                  <p className="text-sm font-semibold">{f.label}</p>
                  <p className="mt-1 font-display text-2xl font-bold">{moneyExact(f.installment_amount)}</p>
                  <p className="text-xs text-muted">
                    {f.installments} payments, {f.frequency}, {f.interest === 0 ? 'no interest' : `${f.interest}% interest`}
                  </p>
                  <Button small variant="secondary" className="mt-3" onClick={() => setConfirm(f.type)}>
                    Buy with {f.label}
                  </Button>
                </div>
              ))}
              {goal.credit_card_offer && (
                <div className="flex flex-col rounded-xl border border-line bg-white p-4">
                  <p className="text-sm font-semibold">{goal.credit_card_offer.label}</p>
                  <p className="mt-1 font-display text-2xl font-bold">{moneyExact(goal.credit_card_offer.estimated_cashback)}</p>
                  <p className="text-xs text-muted">Estimated cashback at {goal.credit_card_offer.cashback_pct}%. {goal.credit_card_offer.note}.</p>
                </div>
              )}
            </div>
            <p className="mt-2 text-xs text-muted">Pay Later and the card are simulated in the PayPal sandbox.</p>
          </div>

          <div className="flex flex-wrap items-center gap-2 border-t border-dashed border-line pt-4 text-sm">
            <span className="mr-1 font-semibold text-muted">Demo tools</span>
            <Button small variant="secondary" loading={skipping} onClick={() => void skip(1)}>
              Skip 1 week
            </Button>
            <Button small variant="secondary" loading={skipping} onClick={() => void skip(4)}>
              Skip 4 weeks
            </Button>
          </div>

          {err && (
            <p role="alert" className="text-sm font-semibold text-danger">
              {err}
            </p>
          )}
        </div>
      )}
    </Card>
  )
}

function Mini({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex flex-col-reverse rounded-lg bg-paper px-3 py-2">
      <dt className="truncate text-xs text-muted">{label}</dt>
      <dd className={cx('font-bold', strong && 'text-save')}>{value}</dd>
    </div>
  )
}
