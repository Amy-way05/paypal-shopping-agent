import type { ErrorDetail } from '../types/api'

export class ApiError extends Error {
  status: number
  detail: ErrorDetail

  constructor(status: number, detail: ErrorDetail) {
    super(detail.message ?? detail.reason ?? 'Something went wrong')
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }

  get code(): string {
    return this.detail.code ?? 'UNKNOWN'
  }
}

/** Plain-language message for any thrown value. */
export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.code === 'AGENT_PASS_BLOCKED') return e.detail.reason ?? 'Agent Pass blocked this action.'
    if (e.code === 'PAYPAL_ERROR') return 'PayPal sandbox had a problem. Try again in a moment.'
    return e.message
  }
  if (e instanceof Error) return e.message
  return 'Something went wrong. Try again.'
}
