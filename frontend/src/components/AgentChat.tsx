import { useEffect, useRef, useState, type FormEvent } from 'react'
import { api } from '../api'
import { errorMessage } from '../api/errors'
import { DEMO_BUYER_ID } from '../lib/constants'
import { money, moneyExact } from '../lib/format'
import { navigate } from '../hooks/useRoute'
import type { AgentCard, AgentToolCall, BetterDealResponse, OrderCreated } from '../types/api'
import { AgentPassChip } from './AgentPassChip'
import { Icon } from './Icon'
import { usePayPalCheckout } from './PayPalCheckout'
import { useToast } from './Toast'
import { Badge, Button, SavedBurst, cx, inputClass } from './ui'

interface Msg {
  id: number
  role: 'user' | 'agent'
  text: string
  toolCalls?: AgentToolCall[]
  cards?: AgentCard[]
  pending?: { amount: number; reason: string } | null
  source?: 'gemini' | 'template'
  failed?: boolean
}

const SUGGESTIONS = ["I'm about to buy running insoles for $24 at FootFirst", 'Scan my purchases', 'How much have I saved?']

export function AgentChat({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [messages, setMessages] = useState<Msg[]>([
    {
      id: 0,
      role: 'agent',
      text: "Tell me what you're about to buy and I'll look for it cheaper. I can also scan your past purchases or check what you've saved.",
    },
  ])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const endRef = useRef<HTMLDivElement>(null)
  const nextId = useRef(1)

  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 50)
  }, [open])

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, sending])

  async function send(text: string) {
    const msg = text.trim()
    if (!msg || sending) return
    setInput('')
    setMessages((m) => [...m, { id: nextId.current++, role: 'user', text: msg }])
    setSending(true)
    try {
      const res = await api.agentChat({ buyer_id: DEMO_BUYER_ID, message: msg, session_id: sessionId })
      setSessionId(res.session_id)
      setMessages((m) => [
        ...m,
        { id: nextId.current++, role: 'agent', text: res.reply, toolCalls: res.tool_calls, cards: res.cards, pending: res.pending_confirmation, source: res.reply_source },
      ])
    } catch (e) {
      setMessages((m) => [...m, { id: nextId.current++, role: 'agent', text: errorMessage(e), failed: true }])
    } finally {
      setSending(false)
    }
  }

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    void send(input)
  }

  if (!open) return null
  const lastAgent = [...messages].reverse().find((m) => m.role === 'agent')

  return (
    <div className="fixed inset-0 z-40" role="dialog" aria-modal="true" aria-label="Ask the agent">
      <div className="absolute inset-0 bg-ink/40" onClick={onClose} aria-hidden="true" />
      <aside className="absolute inset-y-0 right-0 flex w-full animate-slidein flex-col bg-white shadow-2xl sm:w-[420px]">
        <header className="flex items-center justify-between border-b border-line px-5 py-4">
          <div>
            <p className="font-display text-lg font-bold">Ask the agent</p>
            <p className="text-xs text-muted">It picks the tools, and Agent Pass checks every spend.</p>
          </div>
          <button onClick={onClose} aria-label="Close chat" className="grid h-9 w-9 place-items-center rounded-lg hover:bg-paper">
            <Icon name="x" />
          </button>
        </header>

        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
          {messages.map((m) => (
            <Bubble key={m.id} msg={m} isLast={m === lastAgent} sending={sending} onYes={() => void send('yes')} onClose={onClose} />
          ))}
          {sending && (
            <div className="flex" role="status" aria-label="Agent is working">
              <div className="skeleton h-10 w-40 rounded-2xl" />
            </div>
          )}
          <div ref={endRef} />
        </div>

        <div className="border-t border-line p-4">
          {messages.length <= 1 && (
            <div className="mb-3 flex flex-wrap gap-2">
              {SUGGESTIONS.map((s) => (
                <button key={s} onClick={() => void send(s)} className="rounded-full border border-line px-3 py-1.5 text-left text-xs font-semibold hover:bg-paper">
                  {s}
                </button>
              ))}
            </div>
          )}
          <form onSubmit={onSubmit} className="flex gap-2">
            <input ref={inputRef} className={inputClass} value={input} onChange={(e) => setInput(e.target.value)} placeholder="What are you about to buy?" aria-label="Message the agent" />
            <Button type="submit" disabled={!input.trim() || sending} aria-label="Send">
              <Icon name="send" className="h-4 w-4" />
            </Button>
          </form>
        </div>
      </aside>
    </div>
  )
}

function Bubble({ msg, isLast, sending, onYes, onClose }: { msg: Msg; isLast: boolean; sending: boolean; onYes: () => void; onClose: () => void }) {
  if (msg.role === 'user') {
    return (
      <div className="flex justify-end">
        <p className="max-w-[85%] rounded-2xl rounded-br-md bg-pay px-4 py-2.5 text-sm text-white">{msg.text}</p>
      </div>
    )
  }
  return (
    <div className="space-y-2">
      <p className={cx('max-w-[92%] rounded-2xl rounded-bl-md px-4 py-2.5 text-sm', msg.failed ? 'bg-danger-soft text-danger' : 'bg-paper')}>{msg.text}</p>

      {msg.toolCalls && msg.toolCalls.length > 0 && (
        <div className="rounded-xl border border-line p-3">
          <p className="mb-1.5 text-xs font-semibold text-muted">What the agent did</p>
          <ol className="space-y-1.5">
            {msg.toolCalls.map((t, i) => (
              <li key={i} className="flex items-start gap-2 text-xs">
                <Icon name="check" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-save" />
                <span>
                  <span className="font-semibold">{t.tool.replace(/_/g, ' ')}</span>
                  <span className="text-muted">: {t.summary}</span>
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}

      {msg.cards?.map((c, i) => <CardView key={i} card={c} onClose={onClose} />)}

      {msg.pending && isLast && (
        <div className="rounded-xl border border-warn/40 bg-warn-soft p-3 text-sm text-warn">
          <p className="font-semibold">Waiting for your OK: {moneyExact(msg.pending.amount)}</p>
          <p>{msg.pending.reason}</p>
          <Button small variant="save" className="mt-2" disabled={sending} onClick={onYes}>
            Yes, go ahead
          </Button>
        </div>
      )}

      {msg.source === 'template' && !msg.failed && <Badge tone="slate">Fallback reply, Gemini was not used</Badge>}
    </div>
  )
}

function CardView({ card, onClose }: { card: AgentCard; onClose: () => void }) {
  if (card.type === 'order') return <OrderCard order={card.data as OrderCreated} />

  if (card.type === 'better_deal') {
    const d = card.data as BetterDealResponse
    const best = d.alternatives.find((a) => a.product_id === d.best_option)
    return (
      <div className="rounded-xl border border-line p-3 text-sm">
        {best ? (
          <>
            <p className="font-semibold">
              {best.product_name} at {best.merchant_name}
            </p>
            <p className="mt-0.5">
              <span className="font-display text-xl font-bold text-save">{moneyExact(best.price)}</span>{' '}
              <span className="text-muted">instead of {moneyExact(d.your_pick.price)}. Saves {moneyExact(best.savings)}.</span>
            </p>
            <AgentPassChip decision={d.agent_pass} className="mt-2" />
          </>
        ) : (
          <p className="text-muted">{d.message ?? 'No cheaper option found.'}</p>
        )}
      </div>
    )
  }

  if (card.type === 'scan') {
    return (
      <Button
        small
        variant="secondary"
        onClick={() => {
          onClose()
          navigate('guardian')
        }}
      >
        Open Guardian
      </Button>
    )
  }

  if (card.type === 'savings') {
    const d = card.data as { total_saved?: number; this_month?: number }
    if (d.total_saved === undefined) return null
    return (
      <div className="rounded-xl border border-line p-3 text-sm">
        <span className="font-display text-xl font-bold text-save">{money(d.total_saved)}</span> saved in total
        {d.this_month !== undefined && <span className="text-muted">, {money(d.this_month)} this month.</span>}
      </div>
    )
  }

  if (card.type === 'agent_pass') {
    const d = card.data as { decision?: 'APPROVE' | 'NEEDS_CONFIRMATION' | 'BLOCK'; reason?: string }
    return d.decision && d.reason ? <AgentPassChip decision={{ decision: d.decision, reason: d.reason }} /> : null
  }

  if (card.type === 'goal') {
    const d = card.data as { product_name?: string; saved_so_far?: number; final_price?: number }
    return (
      <div className="rounded-xl border border-line p-3 text-sm">
        <p className="font-semibold">{d.product_name ?? 'Your goal'}</p>
        {d.saved_so_far !== undefined && d.final_price !== undefined && (
          <p className="text-muted">
            {money(d.saved_so_far)} of {money(d.final_price)} saved
          </p>
        )}
        <button className="mt-1 text-xs font-semibold text-pay-dark hover:underline" onClick={() => { onClose(); navigate('save-for-it') }}>
          Open Save for it
        </button>
      </div>
    )
  }

  return null
}

function OrderCard({ order }: { order: OrderCreated }) {
  const toast = useToast()
  const { checkout, dialog, busy } = usePayPalCheckout()
  const [paid, setPaid] = useState<{ saved: number } | null>(null)
  const [burst, setBurst] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function approve() {
    setError(null)
    try {
      // The agent already created this order, so there is nothing to create here: just approve and capture.
      const outcome = await checkout(async () => order)
      if (outcome.status === 'captured') {
        setPaid({ saved: outcome.capture.saved })
        if (outcome.capture.saved > 0) setBurst(outcome.capture.saved)
        toast({ kind: 'success', title: outcome.capture.message })
      }
    } catch (e) {
      setError(errorMessage(e))
    }
  }

  return (
    <div className="rounded-xl border border-line p-3 text-sm">
      {dialog}
      <SavedBurst amount={burst} onDone={() => setBurst(null)} />
      <p className="font-semibold">Order for {moneyExact(order.amount)} is ready</p>
      {order.installment_plan && (
        <p className="text-muted">
          {order.installment_plan.installments} payments of {moneyExact(order.installment_plan.installment_amount)}
        </p>
      )}
      {paid ? (
        <p className="mt-2 font-semibold text-save">Paid{paid.saved > 0 ? `. You saved ${moneyExact(paid.saved)}.` : '.'}</p>
      ) : (
        <Button small variant="save" className="mt-2" loading={busy} onClick={() => void approve()}>
          Approve in PayPal
        </Button>
      )}
      {error && (
        <p role="alert" className="mt-2 text-xs font-semibold text-danger">
          {error}
        </p>
      )}
    </div>
  )
}
