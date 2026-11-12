import { API_BASE_URL, USE_MOCKS } from '../lib/config'
import { ApiError } from './errors'
import type { ErrorDetail } from '../types/api'

export type Method = 'GET' | 'POST' | 'PUT' | 'DELETE'

function toDetail(body: unknown, status: number): ErrorDetail {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (detail && typeof detail === 'object' && !Array.isArray(detail)) return detail as ErrorDetail
  if (typeof detail === 'string') return { code: 'ERROR', message: detail }
  // FastAPI validation errors (422) come back as an array
  if (Array.isArray(detail)) return { code: 'BAD_REQUEST', message: 'Some fields are missing or invalid.' }
  return { code: 'ERROR', message: `Request failed (${status})` }
}

export async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  if (USE_MOCKS) {
    const { mockHandle } = await import('./mock')
    return mockHandle<T>(method, path, body)
  }

  let res: Response
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, {
      code: 'NETWORK',
      message: "Can't reach the server. Check that the backend is running and the API URL is right.",
    })
  }

  const text = await res.text()
  let json: unknown = null
  if (text) {
    try {
      json = JSON.parse(text)
    } catch {
      json = null
    }
  }
  if (!res.ok) throw new ApiError(res.status, toDetail(json, res.status))
  return json as T
}
