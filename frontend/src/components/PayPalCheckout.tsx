import { useCallback, useRef, useState, type ReactNode } from 'react'
import { api } from '../api'
import { USE_MOCKS } from '../lib/config'
import { moneyExact } from '../lib/format'
import type { CaptureResult, OrderCreated } from '../types/api'
import { Button } from './ui'

export type CheckoutOutcome = { status: 'captured'; capture: CaptureResult } | { status: 'cancelled' }

type Phase = 'idle' | 'opening' | 'waiting' | 'blocked' | 'mock' | 'capturing'

const sleep = (ms: number) => new Promise((res) => setTimeout(res, ms))

/**
 * The PayPal approval flow from API.md:
 *   create order -> open approve_url in a popup -> buyer approves -> capture.
 *
 * How it works:
 * - The popup is opened synchronously in the click handler (before any await), so
 *   browsers don't treat it as an unwanted popup. It's pointed at approve_url once the
 *   order exists.
 * - We then poll GET /api/orders/{id} until it says APPROVED, close the popup and
 *   capture. This needs no return_url, so it works even if the backend doesn't set one.
 * - If the popup is blocked we show an "Open PayPal" link instead.
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

      let approved = false
      try {
        if (USE_MOCKS) {
          setPhase('mock')
          approved = await new Promise<boolean>((res) => {
            mockDecision.current = res
          })
          if (approved) {
            const { mockApproveOrder } = await import('../api/mock')
            mockApproveOrder(created.order_id)
          }
        } else {
          if (popup && !popup.closed) {
            popup.location.href = created.approve_url
            setPhase('waiting')
          } else {
            setPhase('blocked')
          }
          approved = await waitForApproval(created.order_id, popup, cancelled)
        }
      } finally {
        popup?.close()
      }

      if (!approved || cancelled.current) {
        finish()
        return { status: 'cancelled' }
      }

      setPhase('capturing')
      try {
        const capture = await api.captureOrder(created.order_id)
        return { status: 'captured', capture }
      } finally {
        finish()
      }
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
              <Button variant="secondary" className="mt-5 w-full" onClick={cancel}>
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

async function waitForApproval(orderId: string, popup: Window | null, cancelled: { current: boolean }): Promise<boolean> {
  const deadline = Date.now() + 10 * 60 * 1000
  while (!cancelled.current && Date.now() < deadline) {
    const popupClosed = popup ? popup.closed : false
    const status = await api
      .getOrder(orderId)
      .then((o) => o.status)
      .catch(() => null)
    if (status === 'APPROVED' || status === 'COMPLETED') return true
    // Popup closed without approval: that was one last check, so the buyer backed out.
    if (popupClosed) return false
    await sleep(2000)
  }
  return false
}
