import { useCallback, useRef, useState, type ReactNode } from 'react'
import { api } from '../api'
import { ApiError } from '../api/errors'
import { USE_MOCKS } from '../lib/config'
import { moneyExact } from '../lib/format'
import type { CaptureResult, OrderCreated } from '../types/api'
import { Button } from './ui'

export type CheckoutOutcome = { status: 'captured'; capture: CaptureResult } | { status: 'cancelled' }

type Phase = 'idle' | 'opening' | 'waiting' | 'blocked' | 'mock' | 'capturing'

const sleep = (ms: number) => new Promise((res) => setTimeout(res, ms))

/** Sleep up to `ms`, waking early when `stop()` turns true. */
async function nap(ms: number, stop: () => boolean) {
  const end = Date.now() + ms
  while (Date.now() < end && !stop()) await sleep(100)
}

/**
 * The PayPal approval flow from API.md:
 *   create order -> open approve_url in a popup -> buyer approves in PayPal -> capture.
 *
 * How it works against the real backend:
 * - The popup is opened synchronously in the click handler (before any await), so browsers
 *   allow it. It is pointed at approve_url once the order exists.
 * - We do NOT poll GET /api/orders/{id}: the backend returns the status it stored at creation
 *   and never refreshes it from PayPal. Instead we retry POST .../capture: PayPal answers
 *   409 NOT_APPROVED until the buyer has approved, then the capture goes through.
 * - After approving, PayPal redirects the popup to <frontend>/checkout/return (or /checkout/cancel).
 *   main.tsx shows a "you can close this" page there and messages this window, which makes us
 *   retry the capture straight away instead of waiting for the next retry.
 * - If the popup is blocked we show an "Open PayPal" link instead.
 * - We don't treat a closed popup as a cancel (PayPal pages can make popup.closed unreliable).
 *   The dialog has a Cancel button, and the wait gives up after 10 minutes.
 * - paypal_mode "simulated" (PayPal switched off in the backend) captures immediately.
 * - In mock mode there is no PayPal: a small fake approval dialog stands in for it.
 *
 * Usage:  const { checkout, dialog } = usePayPalCheckout()
 *         const outcome = await checkout(() => api.createOrder({...}))   // call from onClick
 *         ...render {dialog} somewhere in the screen
 */
export function usePayPalCheckout() {
  const [phase, setPhase] = useState<Phase>('idle')
  const [order, setOrder] = useState<OrderCreated | null>(null)
  const cancelled = useRef(false)
  const popupRef = useRef<Window | null>(null)
  const returned = useRef<'approved' | 'cancel' | null>(null)
  const mockDecision = useRef<((approved: boolean) => void) | null>(null)

  const finish = useCallback(() => {
    setPhase('idle')
    setOrder(null)
  }, [])

  const cancel = useCallback(() => {
    cancelled.current = true
    popupRef.current?.close()
    mockDecision.current?.(false)
    finish()
  }, [finish])

  const checkout = useCallback(
    async (createOrder: () => Promise<OrderCreated>): Promise<CheckoutOutcome> => {
      cancelled.current = false
      returned.current = null

      // Must happen synchronously inside the click handler.
      let popup: Window | null = null
      if (!USE_MOCKS) {
        popup = window.open('', 'paypal-checkout', 'popup=yes,width=480,height=740')
        if (popup) {
          popup.document.title = 'PayPal'
          popup.document.body.style.cssText = 'font-family:system-ui,sans-serif;display:grid;place-items:center;height:100vh;margin:0;color:#0A1F44'
          popup.document.body.textContent = 'Connecting to PayPal…'
        }
      }
      popupRef.current = popup
      setPhase('opening')

      let created: OrderCreated
      try {
        created = await createOrder()
      } catch (e) {
        popup?.close()
        finish()
        throw e
      }
      setOrder(created)

      const onMessage = (e: MessageEvent) => {
        if (e.origin !== window.location.origin) return
        const d = e.data as { type?: string; kind?: 'approved' | 'cancel' } | null
        if (d?.type === 'paypal-return' && d.kind) returned.current = d.kind
      }
      window.addEventListener('message', onMessage)

      let capture: CaptureResult | null = null
      try {
        if (USE_MOCKS) {
          setPhase('mock')
          const approved = await new Promise<boolean>((res) => {
            mockDecision.current = res
          })
          if (approved) {
            const { mockApproveOrder } = await import('../api/mock')
            mockApproveOrder(created.order_id)
            setPhase('capturing')
            capture = await api.captureOrder(created.order_id)
          }
        } else if (created.paypal_mode === 'simulated') {
          // Backend has PayPal switched off: nothing to approve.
          popup?.close()
          setPhase('capturing')
          capture = await api.captureOrder(created.order_id)
        } else {
          if (popup && !popup.closed) {
            popup.location.href = created.approve_url
            setPhase('waiting')
          } else {
            setPhase('blocked')
          }
          capture = await captureWhenApproved(created.order_id, cancelled, returned)
        }
      } finally {
        window.removeEventListener('message', onMessage)
        popup?.close()
        finish()
      }

      return capture && !cancelled.current ? { status: 'captured', capture } : { status: 'cancelled' }
    },
    [finish],
  )

  const dialog: ReactNode =
    phase === 'idle' ? null : (
      <div className="fixed inset-0 z-50 grid place-items-center bg-ink/50 p-4" role="dialog" aria-modal="true" aria-label="PayPal checkout">
        <div className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-2xl">
          {phase === 'opening' && (
            <>
              <p className="font-display text-xl font-bold">Creating your order</p>
              <p className="mt-1 text-sm text-muted">Checking Agent Pass and setting up PayPal.</p>
              <div className="skeleton mt-5 h-2 w-full rounded-full" />
            </>
          )}

          {phase === 'capturing' && (
            <>
              <p className="font-display text-xl font-bold">Finishing your payment</p>
              <p className="mt-1 text-sm text-muted">Approved. Capturing the payment now.</p>
              <div className="skeleton mt-5 h-2 w-full rounded-full" />
            </>
          )}

          {phase === 'waiting' && (
            <>
              <p className="font-display text-xl font-bold">Approve in the PayPal window</p>
              <p className="mt-1 text-sm text-muted">
                Log in with the sandbox buyer account and approve the payment. This screen continues on its own.
              </p>
              <div className="skeleton mt-5 h-2 w-full rounded-full" />
              <p className="mt-3 text-xs text-muted">Closed the PayPal window by mistake? Cancel and try again.</p>
              <Button variant="secondary" className="mt-3 w-full" onClick={cancel}>
                Cancel
              </Button>
            </>
          )}

          {phase === 'blocked' && order && (
            <>
              <p className="font-display text-xl font-bold">Your browser blocked the popup</p>
              <p className="mt-1 text-sm text-muted">Open PayPal in a new tab instead. This screen continues once you approve.</p>
              <a
                href={order.approve_url}
                target="_blank"
                rel="noreferrer"
                onClick={() => setPhase('waiting')}
                className="mt-5 block rounded-lg bg-pay px-4 py-2.5 text-center text-sm font-semibold text-white hover:bg-pay-dark"
              >
                Open PayPal
              </a>
              <Button variant="secondary" className="mt-2 w-full" onClick={cancel}>
                Cancel
              </Button>
            </>
          )}

          {phase === 'mock' && order && (
            <>
              <p className="text-xs font-semibold text-muted">Mock PayPal sandbox</p>
              <p className="mt-1 font-display text-xl font-bold">Pay {moneyExact(order.amount)}?</p>
              <p className="mt-1 text-sm text-muted">
                There is no real PayPal in mock mode. Approving here marks the order approved so the capture step runs.
              </p>
              <Button className="mt-5 w-full" onClick={() => mockDecision.current?.(true)}>
                Approve payment
              </Button>
              <Button variant="secondary" className="mt-2 w-full" onClick={cancel}>
                Cancel
              </Button>
            </>
          )}
        </div>
      </div>
    )

  return { checkout, dialog, busy: phase !== 'idle' }
}

/** Retry capture until PayPal says the buyer approved. Returns null if cancelled or timed out. */
async function captureWhenApproved(
  orderId: string,
  cancelled: { current: boolean },
  returned: { current: 'approved' | 'cancel' | null },
): Promise<CaptureResult | null> {
  const deadline = Date.now() + 10 * 60 * 1000
  const stop = () => cancelled.current || returned.current !== null
  await nap(1500, stop) // give the buyer a moment before the first try
  while (!cancelled.current && Date.now() < deadline) {
    if (returned.current === 'cancel') return null
    try {
      return await api.captureOrder(orderId)
    } catch (e) {
      // 409 NOT_APPROVED just means "not yet". Anything else is a real failure.
      if (!(e instanceof ApiError && e.code === 'NOT_APPROVED')) throw e
    }
    await nap(2000, stop)
    // after the return page reports approval, retry faster
    if (returned.current === 'approved') await sleep(300)
  }
  return null
}
