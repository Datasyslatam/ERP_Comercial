# Manual de administración

## Usuarios, roles y permisos
- Permisos con formato `módulo.recurso.acción`; acciones: `read`, `create`, `approve`, `post`, `void`,
  `export`, `admin`. Catálogo completo en `backend/app/core/permissions.py` y en *Administración → Usuarios y roles*.
- Roles del sistema: admin, gerente, auditor (solo lectura), comprador, aprobador_compras, almacenista,
  inspector_calidad, vendedor, despachador, facturador, contador, tesorero, operaciones.
- Un usuario recibe roles **por empresa** y opcionalmente **por sede** (`site_id`). Un administrador no
  puede asignarse roles a sí mismo ni desactivarse.
- Superadministrador: solo para la instalación inicial; cree administradores de empresa y desactive el uso
  cotidiano del superadmin.

## Políticas de control interno (`PATCH /api/v1/company/settings`)
| Parámetro | Por defecto | Efecto |
|---|---|---|
| `sod_requisition_self_approval`, `sod_po_self_approval` | false | Permitir aprobar lo propio |
| `sod_adjustment_self_approval` | false | Ajustes, bajas y conteos |
| `sod_journal_self_post` | false | Contabilizar comprobantes propios |
| `sod_opening_balance_self_approval` | false | Saldos iniciales |
| `receipt_over_tolerance_pct` | 0 | Sobre-recepción permitida (%) |
| `invoice_price_tolerance_pct` | 1 | Diferencia de precio factura vs OC (%) |
| `purchase_budget_control` | warn | `block` impide aprobar OC sobre presupuesto |

Límites de aprobación por rol: `PUT /api/v1/approval-limits` (`purchase_requisition`, `purchase_order`,
`inventory_adjustment`, `payment`). Módulos por empresa: `PUT /api/v1/company/modules/{módulo}`.

## Parametrización fiscal (obligatoria antes de producción)
- **Impuestos**: tarifas, bases mínimas (UVT), cuentas y códigos electrónicos son configurables. Las
  tarifas iniciales (`backend/app/modules/org/jurisdictions.py`) son referencia y **deben validarlas el
  contador o revisor fiscal** (en particular ICA municipal, retenciones por concepto, IGTF y alícuotas).
- **Retenciones por tercero**: `PUT /api/v1/parties/{id}/withholdings`.
- **Cuentas de contabilización**: `PUT /api/v1/posting-accounts` (inventario, CxC, CxP, ingresos, costo,
  variaciones, cuenta puente de saldos iniciales, resultados acumulados…).
- **Numeración autorizada**: Maestros → Numeración (resolución DIAN o asignación de imprenta digital).
- **Tasas de cambio**: `POST /api/v1/exchange-rates` (TRM / BCV) diariamente para operaciones en divisas.

## Respaldos y restauración
- El servicio `backup` ejecuta `database/scripts/backup.sh` al iniciar y cada 24 h: `pg_dump -Fc`, suma
  SHA-256, verificación de legibilidad y retención (`BACKUP_RETENTION_DAYS`).
- **Copie los respaldos fuera del servidor** (otro sitio o bucket con versionado). Respalde también el
  volumen `storage` (adjuntos y documentos fiscales conservados).
- Restauración en base nueva: `TARGET_DATABASE_URL=… database/scripts/restore.sh /backups/erp_X.dump`.
- **Prueba de restauración mensual** obligatoria: `database/scripts/verify_restore.sh` (restaura el último
  respaldo en una base temporal, compara conteos y verifica que la contabilidad cuadre). La prueba
  automatizada `tests/test_backup_restore.py` ejercita el mismo ciclo.

## Monitoreo y alertas
- `GET /health/live` (proceso) y `GET /health/ready` (BD + versión de esquema) para el balanceador.
- `GET /metrics` (Prometheus) solo en red interna; perfil `monitoring` del compose.
- Logs JSON en stdout con `request_id`, usuario e IP (en auditoría). Configure `SENTRY_DSN` para errores.
- Alertas funcionales (*Gerencia → Alertas*): KPIs fuera de umbral, faltantes de stock, vencimientos e
  integraciones fallidas. El worker las evalúa cada hora.
- Vigile: eventos `integration_events` en estado `failed`, documentos electrónicos en `error`, espacio
  en disco del volumen de BD y de respaldos.

## Seguridad operativa
- Secretos solo en `.env` (permisos 600) o gestor de secretos del proveedor; nunca en el repositorio.
  Rote `JWT_SECRET` (cierra todas las sesiones) y la contraseña de BD periódicamente.
- HTTPS obligatorio (Caddy o balanceador); HSTS habilitado en producción.
- Límite de solicitudes por IP en la API; en despliegues con varias réplicas, añada límite en el proxy o WAF.
- SSO corporativo: `AUTH_MODE=oidc` con `OIDC_ISSUER`, `OIDC_AUDIENCE`, `OIDC_JWKS_URL`; los usuarios se
  vinculan por `external_subject`.
- Revisión trimestral de usuarios y roles con el informe de auditoría (*Administración → Auditoría*).

## Conservación y eliminación de datos
- Documentos contables, fiscales y su soporte: conservar mínimo **10 años** (Colombia: art. 28 Ley 962
  de 2005 / art. 632 E.T.; Venezuela: lapso de prescripción del COT — validar con asesoría legal).
- La bitácora de auditoría y los movimientos de inventario son de solo inserción; no se eliminan.
- Datos personales de terceros: atender solicitudes de habeas data (Ley 1581 de 2012) desactivando y
  anonimizando el tercero cuando no existan obligaciones de conservación; no borrar documentos fiscales.
- Intentos de acceso y tokens revocados: depurar con más de 1 año (tarea programada pendiente, ver lista).
