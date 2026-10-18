import type { ReactNode } from "react";

// Iconos lineales del menú lateral: trazo principal en cian (.ico-main) y detalle en lima (.ico-acc).
function Icon({ children }: { children: ReactNode }) {
  return (
    <svg className="nav-icon" viewBox="0 0 24 24" width="20" height="20" fill="none" strokeWidth="1.6"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      {children}
    </svg>
  );
}

const ICONS: Record<string, ReactNode> = {
  Gerencia: <>
    <path className="ico-main" d="M4 20h16M7 17v-4M12 17V9M17 17v-6" />
    <path className="ico-acc" d="M5 9.5l5-4 4 3 5-5" />
  </>,
  Compras: <>
    <path className="ico-main" d="M3 4h2l2.2 10.2a1 1 0 0 0 1 .8h8.6a1 1 0 0 0 1-.76L20 8H6.2" />
    <circle className="ico-acc" cx="9" cy="19" r="1.4" />
    <circle className="ico-acc" cx="17" cy="19" r="1.4" />
  </>,
  "Almacén": <>
    <path className="ico-main" d="M12 3l8 4.5v9L12 21l-8-4.5v-9zM4 7.5l8 4.5 8-4.5M12 12v9" />
    <path className="ico-acc" d="M8 5.3l8 4.5" />
  </>,
  Calidad: <>
    <path className="ico-main" d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6z" />
    <path className="ico-acc" d="M9 12l2 2 4-4" />
  </>,
  "Ventas y logística": <>
    <path className="ico-main" d="M3 6h11v10H3zM14 10h4l3 3v3h-7" />
    <circle className="ico-acc" cx="7" cy="18" r="1.6" />
    <circle className="ico-acc" cx="17.5" cy="18" r="1.6" />
  </>,
  Operaciones: <>
    <path className="ico-main" d="M12 2.5v3M12 18.5v3M2.5 12h3M18.5 12h3M5.3 5.3l2.1 2.1M16.6 16.6l2.1 2.1M5.3 18.7l2.1-2.1M16.6 7.4l2.1-2.1" />
    <circle className="ico-main" cx="12" cy="12" r="5.5" />
    <circle className="ico-acc" cx="12" cy="12" r="2.2" />
  </>,
  Contabilidad: <>
    <rect className="ico-main" x="5" y="3" width="14" height="18" rx="2" />
    <path className="ico-main" d="M8 6.5h8v3.5H8z" />
    <path className="ico-acc" strokeWidth="2.2" d="M8.5 14h.01M12 14h.01M15.5 14h.01M8.5 17.5h.01M12 17.5h.01M15.5 17.5h.01" />
  </>,
  "Datos maestros": <>
    <ellipse className="ico-main" cx="12" cy="5.5" rx="7" ry="2.5" />
    <path className="ico-main" d="M5 5.5v13c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-13" />
    <path className="ico-acc" d="M5 12c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5" />
  </>,
  "Administración": <>
    <circle className="ico-main" cx="9" cy="8" r="3.2" />
    <path className="ico-main" d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6" />
    <path className="ico-acc" d="M15.5 4.8a3.2 3.2 0 0 1 0 6.4M18 14.5c1.9.8 3 2.9 3 5.5" />
  </>,
};

export function SectionIcon({ section }: { section: string }) {
  return <Icon>{ICONS[section] ?? <circle className="ico-main" cx="12" cy="12" r="6" />}</Icon>;
}

/** Indicador direccional (lima): gira 90° cuando la sección está desplegada. */
export function Chevron({ className = "" }: { className?: string }) {
  return (
    <svg className={`nav-chevron ${className}`} viewBox="0 0 24 24" width="16" height="16" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d="M9 6l6 6-6 6" />
    </svg>
  );
}
