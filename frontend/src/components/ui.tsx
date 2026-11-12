import { useEffect, type ButtonHTMLAttributes, type ReactNode } from 'react'
import { Icon, type IconName } from './Icon'
import { TONE_CLASSES, type Tone } from '../lib/meta'
import { errorMessage } from '../api/errors'

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(' ')
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <section className={cx('rounded-xl border border-line bg-white', className)}>{children}</section>
}

type Variant = 'primary' | 'save' | 'secondary' | 'ghost' | 'danger'

const VARIANTS: Record<Variant, string> = {
  primary: 'bg-pay text-white hover:bg-pay-dark disabled:bg-pay/50',
  save: 'bg-save text-white hover:bg-[#0e6b4c] disabled:bg-save/50',
  secondary: 'border border-line bg-white text-ink hover:bg-paper disabled:text-muted/60',
  ghost: 'text-pay-dark hover:bg-pay-soft disabled:text-muted/60',
  danger: 'bg-danger text-white hover:bg-[#962019] disabled:bg-danger/50',
}

export function Button({
  variant = 'primary',
  loading,
  small,
  className,
  children,
  disabled,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; loading?: boolean; small?: boolean }) {
  return (
    <button
      {...rest}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cx(
        'inline-flex items-center justify-center gap-2 rounded-lg font-semibold transition-colors disabled:cursor-not-allowed',
        small ? 'px-3 py-1.5 text-sm' : 'px-4 py-2.5 text-sm',
        VARIANTS[variant],
        className,
      )}
    >
      {children}
    </button>
  )
}

export function Badge({ tone = 'slate', children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span className={cx('inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold', TONE_CLASSES[tone].chip, className)}>
      {children}
    </span>
  )
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cx('skeleton rounded-lg', className)} aria-hidden="true" />
}

export function PageSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-4" role="status" aria-label="Loading">
      <Skeleton className="h-44 w-full rounded-2xl" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-28" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-16 w-full" />
      ))}
    </div>
  )
}

export function EmptyState({ icon = 'info', title, body, action }: { icon?: IconName; title: string; body?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center px-6 py-10 text-center">
      <span className="mb-3 grid h-11 w-11 place-items-center rounded-full bg-paper text-muted">
        <Icon name={icon} />
      </span>
      <p className="font-display text-lg font-bold">{title}</p>
      {body && <p className="mt-1 max-w-sm text-sm text-muted">{body}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function ErrorNote({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-xl border border-danger/30 bg-danger-soft p-4 text-sm text-danger">
      <Icon name="info" className="mt-0.5 h-5 w-5 shrink-0" />
      <div className="flex-1">
        <p className="font-semibold">That didn't work</p>
        <p className="mt-0.5">{errorMessage(error)}</p>
      </div>
      {onRetry && (
        <Button small variant="secondary" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  )
}

export function ProgressBar({ value, tone = 'green', label }: { value: number; tone?: 'green' | 'blue'; label?: string }) {
  const v = Math.max(0, Math.min(100, value))
  return (
    <div
      className="h-2.5 w-full overflow-hidden rounded-full bg-paper"
      role="progressbar"
      aria-valuenow={Math.round(v)}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label}
    >
      <div className={cx('h-full rounded-full transition-[width] duration-700', tone === 'green' ? 'bg-save' : 'bg-pay')} style={{ width: `${v}%` }} />
    </div>
  )
}

export function Toggle({ checked, onChange, label, description }: { checked: boolean; onChange: (v: boolean) => void; label: string; description?: string }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <p className="text-sm font-semibold">{label}</p>
        {description && <p className="mt-0.5 text-sm text-muted">{description}</p>}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={cx('relative mt-0.5 h-6 w-11 shrink-0 rounded-full transition-colors', checked ? 'bg-save' : 'bg-line')}
      >
        <span className={cx('absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-[left]', checked ? 'left-[22px]' : 'left-0.5')} />
      </button>
    </div>
  )
}

export const inputClass =
  'w-full rounded-lg border border-line bg-white px-3 py-2.5 text-sm text-ink placeholder:text-muted/70 focus:border-pay focus:outline-none focus:ring-2 focus:ring-pay/20'

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-semibold">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-muted">{hint}</span>}
    </label>
  )
}

export function SectionTitle({ children, aside }: { children: ReactNode; aside?: ReactNode }) {
  return (
    <div className="mb-3 flex items-end justify-between gap-3">
      <h2 className="font-display text-xl font-bold">{children}</h2>
      {aside}
    </div>
  )
}

/** "+$6 saved!" moment after a purchase. */
export function SavedBurst({ amount, onDone }: { amount: number | null; onDone: () => void }) {
  useEffect(() => {
    if (amount === null) return
    const t = setTimeout(onDone, 2400)
    return () => clearTimeout(t)
  }, [amount, onDone])
  if (amount === null) return null
  return (
    <div className="pointer-events-none fixed inset-0 z-50 grid place-items-center" role="status" aria-live="polite">
      <div className="animate-pop rounded-2xl bg-save px-8 py-5 text-center text-white shadow-2xl">
        <p className="font-display text-5xl font-bold">+${amount % 1 === 0 ? amount : amount.toFixed(2)}</p>
        <p className="mt-1 text-lg font-semibold">saved!</p>
      </div>
    </div>
  )
}
