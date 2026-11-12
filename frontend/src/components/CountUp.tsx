import { useEffect, useRef, useState } from 'react'
import { money } from '../lib/format'

/** Animates between values. Starts from the previous value, so live updates tick up. */
export function CountUp({ value, className, duration = 900 }: { value: number; className?: string; duration?: number }) {
  const [shown, setShown] = useState(0)
  const from = useRef(0)

  useEffect(() => {
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    if (reduce) {
      from.current = value
      setShown(value)
      return
    }
    const start = performance.now()
    const startValue = from.current
    let raf = 0
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration)
      const eased = 1 - Math.pow(1 - t, 3)
      const v = startValue + (value - startValue) * eased
      from.current = v
      setShown(v)
      if (t < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [value, duration])

  const rounded = Math.round(shown * 100) / 100
  return (
    <span className={className} aria-label={money(value)}>
      {money(Number.isInteger(value) ? Math.round(shown) : rounded)}
    </span>
  )
}
