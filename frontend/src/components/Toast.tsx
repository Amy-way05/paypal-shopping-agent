import { createContext, useCallback, useContext, useState, type ReactNode } from 'react'
import { Icon } from './Icon'
import { cx } from './ui'

type ToastKind = 'success' | 'error' | 'info'
interface ToastItem {
  id: number
  kind: ToastKind
  title: string
  body?: string
}

const ToastContext = createContext<(t: Omit<ToastItem, 'id'>) => void>(() => {})

export const useToast = () => useContext(ToastContext)

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([])

  const push = useCallback((t: Omit<ToastItem, 'id'>) => {
    const id = Date.now() + Math.random()
    setItems((prev) => [...prev, { ...t, id }].slice(-3))
    setTimeout(() => setItems((prev) => prev.filter((x) => x.id !== id)), t.kind === 'error' ? 7000 : 4500)
  }, [])

  return (
    <ToastContext.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[60] flex flex-col items-center gap-2 px-4" aria-live="polite">
        {items.map((t) => (
          <div
            key={t.id}
            role={t.kind === 'error' ? 'alert' : 'status'}
            className={cx(
              'pointer-events-auto flex w-full max-w-md animate-rise items-start gap-3 rounded-xl border bg-white p-3.5 shadow-lg',
              t.kind === 'error' ? 'border-danger/40' : t.kind === 'success' ? 'border-save/40' : 'border-line',
            )}
          >
            <span className={cx('mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-full', t.kind === 'error' ? 'bg-danger-soft text-danger' : t.kind === 'success' ? 'bg-save-soft text-save' : 'bg-pay-soft text-pay-dark')}>
              <Icon name={t.kind === 'error' ? 'info' : 'check'} className="h-4 w-4" />
            </span>
            <div className="min-w-0 flex-1 text-sm">
              <p className="font-semibold">{t.title}</p>
              {t.body && <p className="mt-0.5 text-muted">{t.body}</p>}
            </div>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
