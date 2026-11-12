import type { AgentPassDecision } from '../types/api'
import { Icon } from './Icon'
import { cx } from './ui'

const COPY = {
  APPROVE: { label: 'Auto-approved', tone: 'bg-save-soft text-save', icon: 'check' as const },
  NEEDS_CONFIRMATION: { label: 'Needs your OK', tone: 'bg-pay-soft text-pay-dark', icon: 'lock' as const },
  BLOCK: { label: 'Blocked by Agent Pass', tone: 'bg-danger-soft text-danger', icon: 'x' as const },
}

/** Shows what Agent Pass decided and why. Used on Better deal, Save For It and the chat. */
export function AgentPassChip({ decision, className }: { decision: AgentPassDecision | null | undefined; className?: string }) {
  if (!decision) return null
  const c = COPY[decision.decision]
  return (
    <div className={cx('flex items-start gap-2.5 rounded-lg px-3 py-2.5 text-sm', c.tone, className)}>
      <Icon name={c.icon} className="mt-0.5 h-4 w-4 shrink-0" />
      <div>
        <p className="font-semibold">{c.label}</p>
        <p className="opacity-90">{decision.reason}</p>
      </div>
    </div>
  )
}
