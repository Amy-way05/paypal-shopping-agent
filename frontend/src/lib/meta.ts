import type { IconName } from '../components/Icon'

export type Tone = 'blue' | 'green' | 'amber' | 'red' | 'slate'

interface Meta {
  label: string
  icon: IconName
  tone: Tone
}

// Savings recent_actions use `delivery` / `refund`; Guardian alerts use `delivery_delay` / `late_refund`.
// Both map to the same look.
export const ACTION_META: Record<string, Meta> = {
  price_drop: { label: 'Price drop', icon: 'tag', tone: 'blue' },
  overcharge: { label: 'Overcharge', icon: 'shield', tone: 'amber' },
  better_deal: { label: 'Better deal', icon: 'sparkle', tone: 'green' },
  save_for_it: { label: 'Save For It', icon: 'target', tone: 'green' },
  delivery: { label: 'Late delivery', icon: 'truck', tone: 'slate' },
  delivery_delay: { label: 'Late delivery', icon: 'truck', tone: 'slate' },
  refund: { label: 'Overdue refund', icon: 'undo', tone: 'red' },
  late_refund: { label: 'Overdue refund', icon: 'undo', tone: 'red' },
}

export function actionMeta(type: string): Meta {
  return ACTION_META[type] ?? { label: type, icon: 'info', tone: 'slate' }
}

export const TONE_CLASSES: Record<Tone, { chip: string; dot: string; icon: string }> = {
  blue: { chip: 'bg-pay-soft text-pay-dark', dot: 'bg-pay', icon: 'bg-pay-soft text-pay-dark' },
  green: { chip: 'bg-save-soft text-save', dot: 'bg-save', icon: 'bg-save-soft text-save' },
  amber: { chip: 'bg-warn-soft text-warn', dot: 'bg-warn', icon: 'bg-warn-soft text-warn' },
  red: { chip: 'bg-danger-soft text-danger', dot: 'bg-danger', icon: 'bg-danger-soft text-danger' },
  slate: { chip: 'bg-paper text-muted', dot: 'bg-muted', icon: 'bg-paper text-muted' },
}
