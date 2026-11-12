import { useEffect, useState } from 'react'
import { api } from '../api'
import { errorMessage } from '../api/errors'
import { AgentPassChip } from '../components/AgentPassChip'
import { Icon } from '../components/Icon'
import { useToast } from '../components/Toast'
import { Badge, Button, Card, EmptyState, ErrorNote, Field, ProgressBar, Skeleton, Toggle, cx, inputClass } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { CATEGORIES, DEMO_BUYER_ID, EMPTY } from '../lib/constants'
import { money, moneyExact, relativeTime, titleCase } from '../lib/format'
import type { AgentPassCheckResult, AgentPassRules, AgentPassUpdate, Decision } from '../types/api'

type Draft = Required<AgentPassUpdate>

function toDraft(r: AgentPassRules): Draft {
  return {
    autonomous_enabled: r.autonomous_enabled,
    autonomous_claims: r.autonomous_claims,
    auto_approve_limit: r.auto_approve_limit,
    max_unplanned_purchase: r.max_unplanned_purchase,
    max_daily_spend: r.max_daily_spend,
    monthly_limit: r.monthly_limit,
    blocked_categories: r.blocked_categories,
    approved_merchants: r.approved_merchants,
  }
}

const DECISION_TONE: Record<Decision, 'green' | 'blue' | 'red'> = { APPROVE: 'green', NEEDS_CONFIRMATION: 'blue', BLOCK: 'red' }
const DECISION_LABEL: Record<Decision, string> = { APPROVE: 'Approved', NEEDS_CONFIRMATION: 'Asked you', BLOCK: 'Blocked' }

export default function AgentPassSettings() {
  const toast = useToast()
  const rules = useAsync(() => api.getAgentPass(DEMO_BUYER_ID))
  const log = useAsync(() => api.getAgentPassActions(DEMO_BUYER_ID))

  const [draft, setDraft] = useState<Draft | null>(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (rules.data) setDraft(toDraft(rules.data))
  }, [rules.data])

  if ((rules.loading && !rules.data) || !draft) {
    if (rules.error && !rules.data) return <ErrorNote error={rules.error} onRetry={rules.retry} />
    return (
      <div className="space-y-4" role="status" aria-label="Loading Agent Pass">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-96 w-full" />
      </div>
    )
  }

  const saved = rules.data as AgentPassRules
  const dirty = JSON.stringify(draft) !== JSON.stringify(toDraft(saved))
  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => setDraft((d) => (d ? { ...d, [key]: value } : d))
  const num = (v: string) => Math.max(0, Number(v.replace(/[^0-9.]/g, '')) || 0)

  async function save() {
    if (!draft) return
    setSaving(true)
    try {
      const updated = await api.updateAgentPass(DEMO_BUYER_ID, draft)
      rules.setData(updated)
      toast({ kind: 'success', title: 'Agent Pass saved', body: 'The agent will follow these rules from now on.' })
    } catch (e) {
      toast({ kind: 'error', title: 'Could not save', body: errorMessage(e) })
    } finally {
      setSaving(false)
    }
  }

  const available = CATEGORIES.filter((c) => !draft.blocked_categories.includes(c))

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl font-bold">Agent Pass</h1>
        <p className="mt-1 max-w-xl text-sm text-muted">Your rules for what the agent can do without asking. Everything it wants to buy or claim is checked here first.</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <Card className="space-y-6 p-5 lg:col-span-3">
          <div>
            <div className="flex items-baseline justify-between">
              <label htmlFor="auto-limit" className="text-sm font-semibold">
                Buy without asking up to
              </label>
              <span className="font-display text-2xl font-bold">{money(draft.auto_approve_limit)}</span>
            </div>
            <input
              id="auto-limit"
              type="range"
              min={0}
              max={200}
              step={5}
              value={draft.auto_approve_limit}
              onChange={(e) => set('auto_approve_limit', Number(e.target.value))}
              className="mt-3 w-full accent-pay"
            />
            <div className="flex justify-between text-xs text-muted">
              <span>$0, always ask</span>
              <span>$200</span>
            </div>
          </div>

          <Toggle
            checked={draft.autonomous_enabled}
            onChange={(v) => set('autonomous_enabled', v)}
            label="Let the agent buy for me"
            description="When off, the agent asks before every purchase, whatever the amount."
          />
          <Toggle
            checked={draft.autonomous_claims}
            onChange={(v) => set('autonomous_claims', v)}
            label="Let the agent file claims for me"
            description="Price matches, disputes and refund escalations. When off, you tap Claim yourself."
          />

          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Biggest unplanned purchase" hint="Over this, the agent says no.">
              <MoneyInput value={draft.max_unplanned_purchase} onChange={(v) => set('max_unplanned_purchase', num(v))} />
            </Field>
            <Field label="Daily spending limit">
              <MoneyInput value={draft.max_daily_spend} onChange={(v) => set('max_daily_spend', num(v))} />
            </Field>
            <Field label="Monthly spending limit">
              <MoneyInput value={draft.monthly_limit} onChange={(v) => set('monthly_limit', num(v))} />
            </Field>
          </div>

          <div>
            <p className="text-sm font-semibold">Never buy from these categories</p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {draft.blocked_categories.length === 0 && <span className="text-sm text-muted">None blocked.</span>}
              {draft.blocked_categories.map((c) => (
                <span key={c} className="inline-flex items-center gap-1.5 rounded-full bg-danger-soft py-1 pl-3 pr-1.5 text-sm font-semibold text-danger">
                  {titleCase(c)}
                  <button
                    type="button"
                    aria-label={`Unblock ${c}`}
                    onClick={() => set('blocked_categories', draft.blocked_categories.filter((x) => x !== c))}
                    className="grid h-5 w-5 place-items-center rounded-full hover:bg-danger/15"
                  >
                    <Icon name="x" className="h-3 w-3" />
                  </button>
                </span>
              ))}
              {available.length > 0 && (
                <select
                  aria-label="Block a category"
                  className="rounded-full border border-line bg-white px-3 py-1 text-sm"
                  value=""
                  onChange={(e) => e.target.value && set('blocked_categories', [...draft.blocked_categories, e.target.value])}
                >
                  <option value="">Block a category…</option>
                  {available.map((c) => (
                    <option key={c} value={c}>
                      {titleCase(c)}
                    </option>
                  ))}
                </select>
              )}
            </div>
          </div>

          <p className="text-sm text-muted">
            Stores: {saved.approved_merchants.length === 0 ? 'any store with a low dispute rate.' : `${saved.approved_merchants.length} approved.`}
          </p>

          <div className="flex items-center gap-3 border-t border-line pt-4">
            <Button loading={saving} disabled={!dirty} onClick={() => void save()}>
              Save changes
            </Button>
            <Button variant="ghost" disabled={!dirty || saving} onClick={() => setDraft(toDraft(saved))}>
              Discard
            </Button>
            {dirty && <span className="text-sm text-muted">Unsaved changes</span>}
          </div>
        </Card>

        <div className="space-y-6 lg:col-span-2">
          <Card className="space-y-4 p-5">
            <p className="font-semibold">Spent so far</p>
            <Usage label="Today" spent={saved.spent_today} limit={saved.max_daily_spend} />
            <Usage label="This month" spent={saved.spent_this_month} limit={saved.monthly_limit} />
          </Card>
          <RuleTester onChecked={() => void log.reload()} />
        </div>
      </div>

      <div>
        <h2 className="mb-3 font-display text-xl font-bold">Recent agent decisions</h2>
        <Card>
          {log.loading && !log.data ? (
            <Skeleton className="m-4 h-16" />
          ) : log.error && !log.data ? (
            <div className="p-4">
              <ErrorNote error={log.error} onRetry={log.retry} />
            </div>
          ) : (log.data?.actions.length ?? 0) === 0 ? (
            <EmptyState icon="lock" title="No decisions yet" body={log.data?.message ?? EMPTY.agentLog} />
          ) : (
            <ul className="divide-y divide-line">
              {log.data!.actions.map((a) => (
                <li key={a.action_id} className="flex flex-wrap items-center gap-x-4 gap-y-1 p-4">
                  <Badge tone={DECISION_TONE[a.decision]}>{DECISION_LABEL[a.decision]}</Badge>
                  <p className="min-w-0 flex-1 text-sm">
                    <span className="font-semibold">
                      {a.action === 'claim' ? 'Claim' : 'Purchase'} {moneyExact(a.amount)}
                    </span>{' '}
                    <span className="text-muted">
                      at {a.merchant_name}, {a.reason}
                    </span>
                  </p>
                  <p className="text-xs text-muted">{relativeTime(a.timestamp)}</p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </div>
  )
}

function MoneyInput({ value, onChange }: { value: number; onChange: (v: string) => void }) {
  return (
    <div className="relative">
      <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-muted">$</span>
      <input className={cx(inputClass, 'pl-6')} inputMode="decimal" value={String(value)} onChange={(e) => onChange(e.target.value)} />
    </div>
  )
}

function Usage({ label, spent, limit }: { label: string; spent: number; limit: number }) {
  const share = limit > 0 ? (spent / limit) * 100 : 0
  return (
    <div>
      <div className="flex items-baseline justify-between text-sm">
        <span className="font-semibold">{label}</span>
        <span className="text-muted">
          {money(spent)} of {money(limit)}
        </span>
      </div>
      <div className="mt-1.5">
        <ProgressBar value={share} tone={share > 85 ? 'blue' : 'green'} label={`${label} spending`} />
      </div>
    </div>
  )
}

const PRESETS = [
  { label: '$18 insoles', amount: '18', category: 'sporting_goods', planned: false },
  { label: '$1,050 laptop, saved for', amount: '1050', category: 'electronics', planned: true },
  { label: '$200 random buy', amount: '200', category: 'electronics', planned: false },
]

function RuleTester({ onChecked }: { onChecked: () => void }) {
  const [amount, setAmount] = useState('18')
  const [category, setCategory] = useState('sporting_goods')
  const [planned, setPlanned] = useState(false)
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<AgentPassCheckResult | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function run(a = amount, c = category, p = planned) {
    const n = Number(a)
    if (!(n > 0)) {
      setError('Enter an amount above $0.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      setResult(await api.checkAgentPass({ buyer_id: DEMO_BUYER_ID, amount: n, category: c, action: 'purchase', planned: p }))
      onChecked()
    } catch (e) {
      setError(errorMessage(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card className="space-y-4 p-5">
      <div>
        <p className="font-semibold">Test your rules</p>
        <p className="text-sm text-muted">See what the agent would do with a purchase. Nothing is bought.</p>
      </div>
      <div className="flex flex-wrap gap-2">
        {PRESETS.map((p) => (
          <button
            key={p.label}
            type="button"
            className="rounded-full border border-line px-3 py-1 text-xs font-semibold hover:bg-paper"
            onClick={() => {
              setAmount(p.amount)
              setCategory(p.category)
              setPlanned(p.planned)
              void run(p.amount, p.category, p.planned)
            }}
          >
            {p.label}
          </button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Amount">
          <MoneyInput value={Number(amount) || 0} onChange={(v) => setAmount(v.replace(/[^0-9.]/g, ''))} />
        </Field>
        <Field label="Category">
          <select className={inputClass} value={category} onChange={(e) => setCategory(e.target.value)}>
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {titleCase(c)}
              </option>
            ))}
          </select>
        </Field>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={planned} onChange={(e) => setPlanned(e.target.checked)} className="h-4 w-4 accent-pay" />
        It's something I saved for
      </label>
      <Button variant="secondary" loading={busy} onClick={() => void run()} className="w-full">
        Check
      </Button>
      {error && (
        <p role="alert" className="text-sm font-semibold text-danger">
          {error}
        </p>
      )}
      {result && (
        <div className="space-y-2">
          <AgentPassChip decision={result} />
          <p className="text-xs text-muted">
            Room left: {money(result.remaining_today)} today, {money(result.remaining_this_month)} this month.
          </p>
        </div>
      )}
    </Card>
  )
}
