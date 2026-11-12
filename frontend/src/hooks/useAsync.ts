import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Load data on mount (and whenever `deps` change). `reload()` refetches without
 * flashing the skeleton, so numbers can update in place.
 */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [loading, setLoading] = useState(true)
  const latest = useRef(0)
  const fnRef = useRef(fn)
  fnRef.current = fn

  const run = useCallback(async (silent: boolean) => {
    const id = ++latest.current
    if (!silent) setLoading(true)
    try {
      const result = await fnRef.current()
      if (id !== latest.current) return
      setData(result)
      setError(null)
    } catch (e) {
      if (id !== latest.current) return
      setError(e)
    } finally {
      if (id === latest.current) setLoading(false)
    }
  }, [])

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    void run(false)
  }, deps)

  const reload = useCallback(() => run(true), [run])
  const retry = useCallback(() => run(false), [run])
  return { data, error, loading, reload, retry, setData }
}
