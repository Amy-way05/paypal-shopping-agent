import { useCallback, useMemo, useRef, useState } from 'react'
import { AgGridReact, type CustomCellRendererProps } from 'ag-grid-react'
import { AllCommunityModule, ModuleRegistry, themeQuartz, type ColDef, type GridApi } from 'ag-grid-community'
import { api } from '../api'
import { errorMessage } from '../api/errors'
import { Icon } from '../components/Icon'
import { useToast } from '../components/Toast'
import { Badge, Button, Card, EmptyState, ErrorNote, PageSkeleton, SectionTitle, cx } from '../components/ui'
import { useAsync } from '../hooks/useAsync'
import { DEMO_MERCHANT_ID, EMPTY } from '../lib/constants'
import { money, moneyExact, pct, titleCase } from '../lib/format'
import type { ChurnRow, CrossSellRow, OfferSent, OfferStatus, RiskTier } from '../types/api'

ModuleRegistry.registerModules([AllCommunityModule])

const gridTheme = themeQuartz.withParams({
  accentColor: '#0070E0',
  foregroundColor: '#0A1F44',
  borderColor: '#DCE2EC',
  headerBackgroundColor: '#F3F5F9',
  headerTextColor: '#0A1F44',
  fontFamily: 'Figtree, ui-sans-serif, system-ui, sans-serif',
  fontSize: 14,
  wrapperBorderRadius: 12,
})

const TIER_RANK: Record<RiskTier, number> = { high: 3, medium: 2, low: 1 }
const TIER_TONE: Record<RiskTier, 'red' | 'amber' | 'green'> = { high: 'red', medium: 'amber', low: 'green' }

interface GridContext {
  busyId: string | null
  onWinBack: (row: ChurnRow) => void
  onSimulate: (row: ChurnRow) => void
}

type Tier = 'all' | RiskTier

// "Let PayPal handle it" sends this many offers at once. More than this makes the demo wait (each offer is written by the LLM).
const MAX_BULK = 5

/** What actually happened to the PayPal invoice. The backend says SIMULATED until Invoicing is enabled on the PayPal app. */
function invoiceNote(offer: OfferSent): string {
  if (offer.invoice_status === 'SENT') return 'PayPal sent the invoice.'
  if (offer.invoice_status === 'SIMULATED') return 'Offer saved. The PayPal invoice is simulated for now.'
  return offer.invoice_error ? `Offer saved, but the invoice failed: ${offer.invoice_error}` : `Offer saved. Invoice status: ${offer.invoice_status}.`
}

function bulkNote(offers: OfferSent[]): string {
  if (offers.every((o) => o.invoice_status === 'SENT')) return 'PayPal wrote each message and sent the invoices.'
  if (offers.every((o) => o.invoice_status === 'SIMULATED')) return 'Offers saved. The PayPal invoices are simulated for now.'
  return 'Some invoices were not sent. Check the latest offer below.'
}

// ---------- custom cell renderers ----------
function ProbabilityCell(p: CustomCellRendererProps<ChurnRow>) {
  const v = Number(p.value ?? 0) / 100
  const color = v >= 0.7 ? 'bg-danger' : v >= 0.4 ? 'bg-amber' : 'bg-save'
  return (
    <div className="flex h-full items-center gap-2" title={`${Math.round(v * 100)}% likely to stop buying`}>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-paper">
        <div className={cx('h-full rounded-full', color)} style={{ width: `${Math.min(100, v * 100)}%` }} />
      </div>
      <span className="w-10 text-right text-sm font-semibold">{Math.round(v * 100)}%</span>
    </div>
  )
}

function TierCell(p: CustomCellRendererProps<ChurnRow>) {
  const tier = p.value as RiskTier | undefined
  if (!tier) return null
  return (
    <div className="flex h-full items-center">
      <Badge tone={TIER_TONE[tier]}>{titleCase(tier)}</Badge>
    </div>
  )
}

function ActionCell(p: CustomCellRendererProps<ChurnRow>) {
  const row = p.data
  if (!row || p.node.rowPinned) return null
  const ctx = p.context as GridContext
  const status: OfferStatus = row.offer_status
  return (
    <div className="flex h-full items-center gap-2">
      {status === null && (
        <Button small variant="secondary" loading={ctx.busyId === row.customer_id} onClick={() => ctx.onWinBack(row)}>
          Win back
        </Button>
      )}
      {status === 'sent' && (
        <>
          <Badge tone="blue">Offer sent</Badge>
          <button className="text-xs font-semibold text-pay-dark hover:underline" onClick={() => ctx.onSimulate(row)} title="Demo: pretend the customer used the offer">
            Simulate reply
          </button>
        </>
      )}
      {status === 'redeemed' && <Badge tone="green">Won back</Badge>}
      {status === 'ignored' && <Badge tone="slate">Ignored</Badge>}
      {status === 'opened' && <Badge tone="blue">Opened</Badge>}
    </div>
  )
}

function RateCell(p: CustomCellRendererProps<CrossSellRow>) {
  const v = Number(p.value ?? 0)
  return (
    <div className="flex h-full items-center gap-2">
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-paper">
        <div className="h-full rounded-full bg-pay" style={{ width: `${Math.min(100, v * 100)}%` }} />
      </div>
      <span className="w-10 text-right text-sm font-semibold">{pct(v)}</span>
    </div>
  )
}

// ---------- page ----------
export default function MerchantDashboard() {
  const toast = useToast()
  const { data, error, loading, reload, retry } = useAsync(() => api.getMerchantDashboard(DEMO_MERCHANT_ID))

  const gridApi = useRef<GridApi<ChurnRow> | null>(null)
  const [overrides, setOverrides] = useState<Record<string, { offer_status: OfferStatus; offer_id: string }>>({})
  const [tier, setTier] = useState<Tier>('all')
  const [selected, setSelected] = useState(0)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [bulkBusy, setBulkBusy] = useState(false)
  const [lastOffer, setLastOffer] = useState<OfferSent | null>(null)

  // Server rows, with any offer we just sent layered on top so the grid updates instantly.
  const allRows = useMemo<ChurnRow[]>(
    () => (data?.churn_risk ?? []).map((r) => (overrides[r.customer_id] ? { ...r, ...overrides[r.customer_id] } : r)),
    [data, overrides],
  )
  const rows = useMemo(() => (tier === 'all' ? allRows : allRows.filter((r) => r.risk_tier === tier)), [allRows, tier])

  const sendOne = useCallback(
    async (row: ChurnRow): Promise<OfferSent | null> => {
      try {
        const offer = await api.sendOffer({ merchant_id: DEMO_MERCHANT_ID, customer_id: row.customer_id })
        setOverrides((o) => ({ ...o, [row.customer_id]: { offer_status: 'sent', offer_id: offer.offer_id } }))
        setLastOffer(offer)
        return offer
      } catch (e) {
        toast({ kind: 'error', title: `Could not send the offer to ${row.customer_name}`, body: errorMessage(e) })
        return null
      }
    },
    [toast],
  )

  const onWinBack = useCallback(
    async (row: ChurnRow) => {
      setBusyId(row.customer_id)
      const offer = await sendOne(row)
      setBusyId(null)
      if (offer) {
        toast({ kind: 'success', title: `Offer sent to ${row.customer_name}`, body: invoiceNote(offer) })
        void reload()
      }
    },
    [sendOne, toast, reload],
  )

  const onSimulate = useCallback(
    async (row: ChurnRow) => {
      const offerId = row.offer_id ?? overrides[row.customer_id]?.offer_id
      if (!offerId) {
        toast({ kind: 'error', title: 'Offer ID missing', body: 'The dashboard needs offer_id on each churn row to log an outcome.' })
        return
      }
      try {
        const orderAmount = Math.round(row.total_spend / Math.max(1, row.order_count))
        const res = await api.logOfferOutcome(offerId, { outcome: 'redeemed', order_amount: orderAmount })
        setOverrides((o) => ({ ...o, [row.customer_id]: { offer_status: 'redeemed', offer_id: offerId } }))
        toast({ kind: 'success', title: `${row.customer_name} came back: ${money(res.revenue_won_back)}`, body: res.message })
        void reload()
      } catch (e) {
        toast({ kind: 'error', title: 'Could not log the outcome', body: errorMessage(e) })
      }
    },
    [overrides, toast, reload],
  )

  const context = useMemo<GridContext>(() => ({ busyId, onWinBack: (r) => void onWinBack(r), onSimulate: (r) => void onSimulate(r) }), [busyId, onWinBack, onSimulate])

  async function letPayPalHandleIt() {
    const picked = (gridApi.current?.getSelectedRows() ?? []).filter((r) => r.offer_status === null)
    const targets = picked.length > 0 ? picked : rows.filter((r) => r.risk_tier === 'high' && r.offer_status === null)
    if (targets.length === 0) {
      toast({ kind: 'info', title: 'Nobody to send to', body: 'Everyone in view already has an offer.' })
      return
    }
    const batch = targets.slice(0, MAX_BULK)
    const waiting = targets.length - batch.length
    setBulkBusy(true)
    const results = await Promise.all(batch.map((row) => sendOne(row)))
    const offers = results.filter((o): o is OfferSent => o !== null)
    const sent = offers.length
    setBulkBusy(false)
    gridApi.current?.deselectAll()
    if (sent > 0) {
      toast({ kind: 'success', title: `Sent ${sent} ${sent === 1 ? 'offer' : 'offers'}`, body: waiting > 0 ? `${bulkNote(offers)} ${waiting} more ${waiting === 1 ? 'is' : 'are'} still waiting. Run it again for the next batch.` : bulkNote(offers) })
      void reload()
    }
  }

  const pinnedBottom = useMemo(() => {
    if (rows.length === 0) return []
    const n = rows.length
    return [
      {
        customer_id: 'summary',
        customer_name: 'Average and total',
        churn_probability: rows.reduce((s, r) => s + r.churn_probability, 0) / n,
        days_since_purchase: Math.round(rows.reduce((s, r) => s + r.days_since_purchase, 0) / n),
        total_spend: rows.reduce((s, r) => s + r.total_spend, 0),
        order_count: rows.reduce((s, r) => s + r.order_count, 0),
      },
    ] as unknown as ChurnRow[]
  }, [rows])

  const churnCols = useMemo<ColDef<ChurnRow>[]>(
    () => [
      { colId: 'customer_name', field: 'customer_name', headerName: 'Customer', minWidth: 170, flex: 1.2, filter: 'agTextColumnFilter', floatingFilter: true },
      {
        colId: 'churn_probability',
        headerName: 'Churn risk',
        valueGetter: (p) => (p.data ? Math.round(p.data.churn_probability * 100) : null),
        cellRenderer: ProbabilityCell,
        minWidth: 190,
        flex: 1.4,
        sort: 'desc',
        filter: 'agNumberColumnFilter',
        floatingFilter: true,
      },
      {
        colId: 'risk_tier',
        field: 'risk_tier',
        headerName: 'Tier',
        cellRenderer: TierCell,
        minWidth: 120,
        comparator: (a: RiskTier, b: RiskTier) => (TIER_RANK[a] ?? 0) - (TIER_RANK[b] ?? 0),
        filter: 'agTextColumnFilter',
        floatingFilter: true,
      },
      { colId: 'days_since_purchase', field: 'days_since_purchase', headerName: 'Days since purchase', type: 'numericColumn', minWidth: 150, filter: 'agNumberColumnFilter', floatingFilter: true },
      { colId: 'total_spend', field: 'total_spend', headerName: 'Total spend', type: 'numericColumn', minWidth: 130, valueFormatter: (p) => (p.value == null ? '' : moneyExact(Number(p.value))), filter: 'agNumberColumnFilter', floatingFilter: true },
      { colId: 'order_count', field: 'order_count', headerName: 'Orders', type: 'numericColumn', minWidth: 100, filter: 'agNumberColumnFilter', floatingFilter: true },
      { colId: 'last_category', field: 'last_category', headerName: 'Last bought', minWidth: 130, valueFormatter: (p) => (p.value ? titleCase(String(p.value)) : ''), filter: 'agTextColumnFilter', floatingFilter: true },
      { colId: 'actions', headerName: '', cellRenderer: ActionCell, sortable: false, filter: false, resizable: false, width: 210, pinned: 'right' },
    ],
    [],
  )

  const crossCols = useMemo<ColDef<CrossSellRow>[]>(
    () => [
      { headerName: 'Bundle', valueGetter: (p) => (p.data ? `${p.data.product_a} + ${p.data.product_b}` : ''), flex: 1.4, minWidth: 200 },
      { field: 'co_purchase_rate', headerName: 'Bought together', cellRenderer: RateCell, flex: 1.2, minWidth: 180, sort: 'desc' },
      { field: 'suggested_bundle_discount_pct', headerName: 'Suggested discount', type: 'numericColumn', minWidth: 160, valueFormatter: (p) => `${p.value}% off` },
    ],
    [],
  )

  if (loading && !data) return <PageSkeleton />
  if (error && !data) return <ErrorNote error={error} onRetry={retry} />
  if (!data) return null

  const s = data.summary
  const mi = data.model_info
  const modelBits = [mi.auc != null && `AUC ${mi.auc.toFixed(2)}`, mi.precision != null && `precision ${mi.precision.toFixed(2)}`, mi.recall != null && `recall ${mi.recall.toFixed(2)}`].filter(Boolean).join(', ')
  const counts: Record<Tier, number> = {
    all: allRows.length,
    high: allRows.filter((r) => r.risk_tier === 'high').length,
    medium: allRows.filter((r) => r.risk_tier === 'medium').length,
    low: allRows.filter((r) => r.risk_tier === 'low').length,
  }
  const bulkTargets = selected > 0 ? selected : rows.filter((r) => r.risk_tier === 'high' && r.offer_status === null).length

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-2xl font-bold">{data.merchant_name}</h1>
        <p className="mt-1 max-w-2xl text-sm text-muted">PayPal sees what your customers do after they leave your store, and what they buy elsewhere. Here is who is about to stop buying, and what to do about it.</p>
      </div>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-label="Summary">
        <Summary label="Customers at risk" value={s.at_risk_customers.toLocaleString('en-US')} note={`${counts.high} high risk in this list`} />
        <Summary label="Revenue at stake" value={money(s.recoverable_revenue)} note="Typical order value of at-risk customers" />
        <Summary label="Offers sent" value={String(s.offers_sent)} note={`${s.offers_redeemed} redeemed`} />
        <Summary label="Win-back rate" value={`${s.win_back_rate_pct}%`} note={`${money(s.revenue_won_back)} won back`} good />
      </section>

      <div>
        <SectionTitle
          aside={
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="secondary" small onClick={() => gridApi.current?.exportDataAsCsv({ fileName: 'at-risk-customers.csv', columnKeys: ['customer_name', 'churn_probability', 'risk_tier', 'days_since_purchase', 'total_spend', 'order_count', 'last_category'] })}>
                <Icon name="download" className="h-4 w-4" /> Export CSV
              </Button>
              <Button small loading={bulkBusy} disabled={bulkTargets === 0} onClick={() => void letPayPalHandleIt()}>
                <Icon name="bolt" className="h-4 w-4" />
                Let PayPal handle it{bulkTargets > 0 ? ` (${Math.min(bulkTargets, MAX_BULK)})` : ''}
              </Button>
            </div>
          }
        >
          Who is about to leave
        </SectionTitle>

        <div className="mb-3 flex flex-wrap gap-2" role="group" aria-label="Filter by risk tier">
          {(['all', 'high', 'medium', 'low'] as Tier[]).map((t) => (
            <button
              key={t}
              onClick={() => setTier(t)}
              aria-pressed={tier === t}
              className={cx('rounded-full border px-3.5 py-1.5 text-sm font-semibold', tier === t ? 'border-ink bg-ink text-white' : 'border-line bg-white hover:bg-paper')}
            >
              {t === 'all' ? 'Everyone' : titleCase(t)} <span className={tier === t ? 'text-white/70' : 'text-muted'}>{counts[t]}</span>
            </button>
          ))}
        </div>

        {allRows.length === 0 ? (
          <Card>
            <EmptyState icon="check" title="Nobody at risk" body={data.message ?? EMPTY.churn} />
          </Card>
        ) : (
          <div style={{ height: 470 }}>
            <AgGridReact<ChurnRow>
              theme={gridTheme}
              rowData={rows}
              columnDefs={churnCols}
              defaultColDef={{ sortable: true, resizable: true, filter: true }}
              pinnedBottomRowData={pinnedBottom}
              getRowId={(p) => p.data.customer_id}
              context={context}
              rowSelection={{ mode: 'multiRow', enableClickSelection: false, isRowSelectable: (n) => n.data?.offer_status === null }}
              onGridReady={(e) => {
                gridApi.current = e.api
              }}
              onSelectionChanged={(e) => setSelected(e.api.getSelectedRows().length)}
              animateRows
            />
          </div>
        )}
        <p className="mt-2 text-xs text-muted">
          Churn model: {titleCase(mi.churn_model)}{modelBits ? `, ${modelBits}` : ''}. {mi.note}. Tick customers to pick who gets an offer, or leave all unticked to message every high-risk customer without one.
        </p>
      </div>

      {lastOffer && (
        <Card className="p-5" aria-live="polite">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-semibold">Latest offer, to {lastOffer.customer_name}</p>
            <div className="flex gap-2">
              <Badge tone="slate">{lastOffer.message_source === 'template' ? 'Template text' : `Written by ${lastOffer.message_source}`}</Badge>
              <Badge tone={lastOffer.invoice_status === 'SENT' ? 'green' : lastOffer.invoice_status === 'SIMULATED' ? 'slate' : 'red'}>Invoice {lastOffer.invoice_status.toLowerCase()}</Badge>
            </div>
          </div>
          <blockquote className="mt-3 border-l-4 border-pay pl-4 text-lg">{lastOffer.message}</blockquote>
          {lastOffer.invoice_id && <p className="mt-2 text-xs text-muted">PayPal invoice {lastOffer.invoice_id}</p>}
          {lastOffer.invoice_error && <p className="mt-2 text-xs text-danger">{lastOffer.invoice_error}</p>}
        </Card>
      )}

      <div>
        <SectionTitle>Bundle ideas</SectionTitle>
        {data.cross_sell.length === 0 ? (
          <Card>
            <EmptyState icon="sparkle" title="No bundles yet" body={EMPTY.crossSell} />
          </Card>
        ) : (
          <AgGridReact<CrossSellRow> theme={gridTheme} rowData={data.cross_sell} columnDefs={crossCols} defaultColDef={{ sortable: true, resizable: true }} domLayout="autoHeight" />
        )}
      </div>
    </div>
  )
}

function Summary({ label, value, note, good }: { label: string; value: string; note: string; good?: boolean }) {
  return (
    <Card className="p-5">
      <p className="text-sm font-semibold text-muted">{label}</p>
      <p className={cx('mt-1 font-display text-3xl font-bold', good && 'text-save')}>{value}</p>
      <p className="mt-1 text-sm text-muted">{note}</p>
    </Card>
  )
}
