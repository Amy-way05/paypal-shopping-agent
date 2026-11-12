// Set in frontend/.env.local (see .env.example). On Render, set these as environment variables on the static site.
export const API_BASE_URL: string = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '')

// true = built-in sample data, no backend needed. Make sure it is false for the real demo and the Devpost screenshots.
export const USE_MOCKS: boolean = import.meta.env.VITE_USE_MOCKS === 'true'
