import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Button } from './ui'

interface State {
  failed: boolean
}

export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { failed: false }

  static getDerivedStateFromError(): State {
    return { failed: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Screen crashed', error, info.componentStack)
  }

  render() {
    if (!this.state.failed) return this.props.children
    return (
      <div role="alert" className="mx-auto max-w-md rounded-xl border border-line bg-white p-8 text-center">
        <p className="font-display text-xl font-bold">This screen hit a snag</p>
        <p className="mt-1 text-sm text-muted">Nothing was lost. Reload the screen to try again.</p>
        <Button className="mt-4" onClick={() => this.setState({ failed: false })}>
          Reload screen
        </Button>
      </div>
    )
  }
}
