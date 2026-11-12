import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis } from 'recharts'
import { api } from '../api'
import { CountUp } from '../components/CountUp'
import { Icon } from '../components/Icon'
import { Badge, Card, EmptyState, ErrorNote, PageSkeleton, SectionTitle, cx } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { navigate } from '../hooks/useRoute'
import { DEMO_BUYER_ID, EMPTY } from '../lib/constants'
import { money, moneyExact, monthShort, relativeTime, shortDate, titleCase } from '../lib/format'
import { actionMeta, TONE_CLASSES, type Tone } from '../lib/meta'
import type { ActionStatus, SavingsKind } from '../types/api'

const CARD_ORDER: SavingsKind[] = ['price_drop', 'overcharge', 'better_deal', 'save_for_it']

const STATUS_TONE: Record<ActionStatus, { tone: Tone; label: string }> = {
  detected: { tone: 'amber', label: 'Detected' },
  resolved: { tone: 'blue', label: 'Action taken' },
  recovered: { tone: 'green', label: 'Recovered' },
}

export default function SavingsDashboard() {
  const { data, error, loading, retry } = useAsync(() => api.getSavings(DEMO_BUYER_ID))

  if (loading && !data) return <PageSkeleton />
  if (error && !data) return <ErrorNote error={error} onRetry={retry} />
  if (!data) return null

  const trend = data.trend.map((t) => ({ label: monthShort(t.month), amount: t.amount }))
  const a = data.analytics
  const maxSpend = Math.max(1, ...a.spend_by_category.map((c) => c.amount))

  return (
    <div className="space-y-8">
      {/* Hero: the running total is the whole point of the app */}
      <section className="grid overflow-hidden rounded-2xl bg-ink text-white lg:grid-cols-5" aria-label="Total saved">
        <div className="p-6 sm:p-8 lg:col-span-2">
          <p className="text-sm font-semibold text-white/70">Total saved</p>
          <CountUp value={data.total_saved} className="mt-1 block font-display text-6xl font-bold leading-none sm:text-7xl" />
          <p className="mt-5 text-lg font-semibold text-save-bright">+{money(data.this_month)} this month</p>
          <p className="mt-1 text-sm text-white/70">
            {a.savings_rate_pct}% of what you spent this month came back to you.
          </p>
          {data.total_saved === 0 && <p className="mt-4 text-sm text-white/80">{data.message ?? EMPTY.savings}</p>}
        </div>
        <div className="min-h-[190px] border-t border-white/10 px-2 pb-3 pt-4 lg:col-span-3 lg:border-l lg:border-t-0">
          <p className="px-4 text-sm font-semibold text-white/70">Savings by month</p>
          <div className="h-[170px] sm:h-[190px]" role="img" aria-label={`Monthly savings, latest ${money(trend[trend.length - 1]?.amount ?? 0)}`}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trend} margin={{ top: 12, right: 18, left: 18, bottom: 0 }}>
                <defs>
                  <linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#2BD47D" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#2BD47D" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fill: 'rgba(255,255,255,.6)', fontSize: 12 }} />
                <Tooltip
                  cursor={{ stroke: 'rgba(255,255,255,.25)' }}
                  content={({ active, payload, label }) =>
                    active && payload?.length ? (
                      <div className="rounded-lg bg-white px-3 py-2 text-sm text-ink shadow-lg">
                        <p className="font-semibold">{label}</p>
                        <p className="text-save">{moneyExact(Number(payload[0].value))} saved</p>
                      </div>
                    ) : null
                  }
                />
                <Area type="monotone" dataKey="amount" stroke="#2BD47D" strokeWidth={2.5} fill="url(#trendFill)" dot={{ r: 3, fill: '#2BD47D', strokeWidth: 0 }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>

      {/* Where it came from */}
      <div>
        <SectionTitle>Where it came from</SectionTitle>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {CARD_ORDER.map((kind) => {
            const c = data.breakdown[kind]
            const meta = actionMeta(kind)
            const tone = TONE_CLASSES[meta.tone]
            return (
              <Card key={kind} className="flex flex-col p-5">
                <div className="flex items-center gap-3">
                  <span className={cx('grid h-9 w-9 place-items-center rounded-lg', tone.icon)}>
                    <Icon name={meta.icon} className="h-[18px] w-[18px]" />
                  </span>
                  <p className="text-sm font-semibold">{c.label}</p>
                </div>
                <p className="mt-4 font-display text-3xl font-bold">{money(c.total)}</p>
                <p className="text-sm text-muted">
                  {c.count === 0 ? 'Nothing yet' : `${c.count} ${c.count === 1 ? 'time' : 'times'}`}
                </p>
                {c.latest ? (
                  <p className="mt-3 border-t border-line pt-3 text-sm text-muted">
                    <span className="font-semibold text-ink">Latest {money(c.latest.amount)}</span> on {c.latest.item} at{' '}
                    {c.latest.merchant_name}, {shortDate(c.latest.date)}
                  </p>
                ) : (
                  <p className="mt-3 border-t border-line pt-3 text-sm text-muted">Your first one shows up here.</p>
                )}
              </Card>
            )
          })}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        {/* Recent activity */}
        <div className="lg:col-span-3">
          <SectionTitle>Recent activity</SectionTitle>
          <Card>
            {data.recent_actions.length === 0 ? (
              <EmptyState
                icon="bolt"
                title="Nothing yet"
                body={EMPTY.recent}
                action={
                  <button className="text-sm font-semibold text-pay-dark hover:underline" onClick={() => navigate('guardian')}>
                    Scan my purchases
                  </button>
                }
              />
            ) : (
              <ul className="divide-y divide-line">
                {data.recent_actions.map((r) => {
                  const meta = actionMeta(r.type)
                  const st = STATUS_TONE[r.status]
                  return (
                    <li key={r.action_id} className="flex items-center gap-3 p-4">
                      <span className={cx('grid h-9 w-9 shrink-0 place-items-center rounded-lg', TONE_CLASSES[meta.tone].icon)}>
                        <Icon name={meta.icon} className="h-[18px] w-[18px]" />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-semibold">{r.title}</p>
                        <p className="text-xs text-muted">{relativeTime(r.timestamp)}</p>
                      </div>
                      <Badge tone={st.tone} className="hidden sm:inline-flex">
                        {st.label}
                      </Badge>
                      <p className={cx('w-16 text-right text-sm font-bold', r.amount > 0 ? 'text-save' : 'text-muted')}>
                        {r.amount > 0 ? `+${money(r.amount)}` : '—'}
                      </p>
                    </li>
                  )
                })}
              </ul>
            )}
          </Card>
        </div>

        {/* Analytics: the reason to open the app daily */}
        <div className="lg:col-span-2">
          <SectionTitle>Your spending</SectionTitle>
          <Card className="p-5">
            <dl className="grid grid-cols-3 gap-3 text-center">
              <Stat label="Spent this month" value={money(a.spend_this_month)} />
              <Stat label="Purchases watched" value={String(a.purchases_watched)} />
              <Stat label="Open alerts" value={String(a.active_alerts)} />
            </dl>
            {a.top_merchant && (
              <p className="mt-4 rounded-lg bg-paper px-3 py-2 text-sm">
                Most spent at <span className="font-semibold">{a.top_merchant.merchant_name}</span>, {money(a.top_merchant.amount)}.
              </p>
            )}
            <ul className="mt-5 space-y-3">
              {a.spend_by_category.map((c) => (
                <li key={c.category}>
                  <div className="flex items-baseline justify-between text-sm">
                    <span className="font-semibold">{titleCase(c.category)}</span>
                    <span className="text-muted">
                      {money(c.amount)}
                      {c.saved > 0 && <span className="font-semibold text-save">, saved {money(c.saved)}</span>}
                    </span>
                  </div>
                  <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-paper">
                    <div className="h-full rounded-full bg-pay" style={{ width: `${(c.amount / maxSpend) * 100}%` }} />
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col-reverse">
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="font-display text-xl font-bold">{value}</dd>
    </div>
  )
}
