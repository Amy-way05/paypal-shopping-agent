import { useEffect, useState } from 'react'

function parse(): string {
  return window.location.hash.replace(/^#\/?/, '') || 'savings'
}

/** Tiny hash router: #/savings, #/better-deal, #/business ... */
export function useRoute(): string {
  const [route, setRoute] = useState(parse)
  useEffect(() => {
    const onChange = () => setRoute(parse())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])
  return route
}

export function navigate(path: string) {
  window.location.hash = `/${path}`
}
