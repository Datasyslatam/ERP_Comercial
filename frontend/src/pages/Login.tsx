import { FormEvent, useEffect, useState } from "react";
import { ArrowRightIcon, BrandMark, EyeIcon, LockIcon, MailIcon, SectionIcon } from "../components/NavIcons";
import { Alert } from "../components/ui";
import { serverStatus } from "../lib/api";
import { useSession } from "../lib/session";
import novixLogo from "../assets/novix-logo.png";

const ENVIRONMENT: Record<string, string> = {
  development: "Desarrollo", test: "Pruebas", staging: "Preproducción", production: "Producción",
};

const FEATURES: [string, string][] = [
  ["Ventas y logística", "Ventas, despachos y rutas de entrega"],
  ["Almacén", "Inventario por bodega, lotes y conteos"],
  ["Contabilidad", "Contabilidad, cartera y pagos multisede"],
  ["Calidad", "Facturación electrónica DIAN · SENIAT"],
];

/** Indicador de conexión con la API: evita que un servidor caído se confunda con credenciales erróneas. */
function ServerStatus({ check }: { check: number }) {
  const [state, setState] = useState<{ online: boolean; environment?: string } | null>(null);
  useEffect(() => {
    let alive = true;
    serverStatus().then((s) => alive && setState(s));
    return () => { alive = false; };
  }, [check]);
  if (!state) return <p className="server-status checking" role="status">Verificando servidor…</p>;
  return (
    <p className={`server-status ${state.online ? "online" : "offline"}`} role="status">
      {state.online
        ? <>Servidor en línea{state.environment && ` · ${ENVIRONMENT[state.environment] ?? state.environment}`}</>
        : "Servidor sin conexión"}
    </p>
  );
}

export function Login() {
  const { login } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [attempt, setAttempt] = useState(0);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
    } catch (err) {
      setError((err as Error).message);
      setAttempt((n) => n + 1); // vuelve a verificar el servidor tras cada intento fallido
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <aside className="login-brand">
        <img className="login-wordmark" src={novixLogo} alt="Novix ERP" width={300} height={77} />
        <div className="login-pitch">
          <h2>ERP <span className="brand-gradient-text">Comercial</span></h2>
          <p>Compras, inventario, ventas, logística, facturación electrónica y contabilidad en una sola plataforma.</p>
          <ul className="login-features">
            {FEATURES.map(([icon, text]) => <li key={text}><SectionIcon section={icon} />{text}</li>)}
          </ul>
        </div>
        <footer>© {new Date().getFullYear()} Novix ERP · Datasys Latam Group</footer>
      </aside>

      <main className="login-main">
        <form onSubmit={submit} className="login-card" aria-labelledby="login-title">
          <div className="login-card-logo"><BrandMark size={40} /><div className="brand-text"><strong>NOVIX</strong><span>ERP</span></div></div>
          <h1 id="login-title">Iniciar sesión</h1>
          <p className="muted">Ingrese con su usuario corporativo</p>

          <div className="field">
            <label htmlFor="login-email">Correo</label>
            <div className="input-icon">
              <MailIcon />
              <input id="login-email" type="email" autoComplete="username" required placeholder="usuario@empresa.com"
                value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
          </div>
          <div className="field">
            <label htmlFor="login-password">Contraseña</label>
            <div className="input-icon">
              <LockIcon />
              <input id="login-password" type={show ? "text" : "password"} autoComplete="current-password" required
                value={password} onChange={(e) => setPassword(e.target.value)} />
              <button type="button" className="reveal" aria-label={show ? "Ocultar contraseña" : "Mostrar contraseña"}
                aria-pressed={show} onClick={() => setShow(!show)}>
                <EyeIcon off={show} />
              </button>
            </div>
          </div>

          <Alert>{error}</Alert>
          <button type="submit" className="btn-block" disabled={busy}>
            {busy ? "Ingresando…" : <>Ingresar <ArrowRightIcon /></>}
          </button>
          <p className="login-help muted">Tras 5 intentos fallidos el usuario se bloquea 15 minutos.</p>
          <ServerStatus check={attempt} />
        </form>
      </main>
    </div>
  );
}
