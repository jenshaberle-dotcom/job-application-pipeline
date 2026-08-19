import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode };
type State = { error: string | null };

export default class RuntimeErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: unknown): State {
    return { error: error instanceof Error ? error.message : String(error) };
  }

  componentDidCatch(error: unknown, info: ErrorInfo): void {
    console.error("Control Center render failed", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <main className="fatal">
          <div className="fatal-card">
            <span className="eyebrow">Fail closed · frontend runtime</span>
            <h1>Control Center render failed</h1>
            <p>The API may still be healthy. This screen preserves the browser-side error instead of rendering a blank page.</p>
            <pre>{this.state.error}</pre>
            <button className="secondary-action" type="button" onClick={() => window.location.reload()}>
              Reload current truth
            </button>
          </div>
        </main>
      );
    }
    return this.props.children;
  }
}
