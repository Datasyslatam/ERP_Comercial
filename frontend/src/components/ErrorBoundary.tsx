import { Component, ReactNode } from "react";

/** Evita que un fallo de una pantalla deje toda la aplicación en blanco: el menú sigue disponible. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: unknown) {
    console.error(error);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return (
      <div className="alert alert-error" role="alert">
        Esta pantalla encontró un error. Sus datos no se perdieron.{" "}
        <button className="link" onClick={() => window.location.reload()}>Recargar</button>
      </div>
    );
  }
}
