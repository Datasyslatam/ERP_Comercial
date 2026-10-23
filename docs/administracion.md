# Manual de administración

## Usuarios, roles y permisos
- Permisos con formato `módulo.recurso.acción`; acciones: `read`, `create`, `approve`, `post`, `void`,
  `export`, `admin`. Catálogo con etiquetas en español en *Administración → Roles y permisos*
  (`GET /api/v1/admin/permissions`).
- **Roles del sistema** (comunes a todas las empresas, no editables): admin, gerente, auditor, comprador,
  aprobador_compras, almacenista, inspector_calidad, vendedor, despachador, facturador, contador, tesorero,
  operaciones. **Roles propios**: cada empresa crea los suyos (en blanco o duplicando uno existente) y ajusta
  su matriz de permisos; solo se eliminan si no tienen usuarios asignados.
- **Asignaciones**: un usuario recibe roles **por empresa**, opcionalmente **por sede** y con **vigencia hasta
  una fecha** (reemplazos por vacaciones, auditores externos). Al vencer, el rol deja de otorgar permisos sin
  intervención; reasignarlo renueva la misma asignación. Cada asignación guarda quién la otorgó, cuándo y una nota.
- **Alta de usuarios** (*Administración → Usuarios → Nuevo usuario*): requiere al menos un rol. Sin contraseña
  ni SSO, el sistema genera una contraseña temporal que se muestra **una sola vez**; toda contraseña asignada por
  un administrador obliga a cambiarla en el primer ingreso (la API responde 403 hasta hacerlo). Si el correo ya
  existe en otra empresa del grupo, el usuario se **vincula** a la empresa activa y conserva su contraseña.
- **Ficha del usuario**: datos, roles, permisos efectivos con el rol que los otorga, sesiones abiertas, intentos
  de acceso, historial de la cuenta y actividad en la empresa. Acciones: editar, restablecer contraseña (cierra
  sesiones y desbloquea), desbloquear, cerrar sesiones, activar/desactivar (desactivar cierra sus sesiones).

### Controles de seguridad
| Regla | Efecto |
|---|---|
| No otorgar lo que no se tiene | Asignar un rol, crear o ampliar un rol propio exige poseer todos sus permisos (403 con la lista faltante) |
| Último administrador | Ninguna revocación, desactivación o edición de rol puede dejar la empresa sin un usuario activo con `admin.users.admin` vigente |
| Autogestión | Nadie se asigna, revoca roles ni se desactiva a sí mismo |
| Cuentas compartidas entre empresas | Correo, contraseña y activación de un usuario que también pertenece a otra empresa solo los cambia el superadministrador; el administrador de empresa le revoca los roles para retirarle el acceso |
| Superadministrador | Solo para la instalación inicial; cree administradores de empresa y no lo use a diario |

### Revisión periódica de accesos
*Usuarios → Revisión de accesos (CSV)* (`GET /api/v1/admin/access-review/export.csv`, requiere
`admin.audit.export`) entrega una fila por usuario, rol y sede, con vigencia, quién lo otorgó y el último acceso.
Revísela al menos cada trimestre con los responsables de cada área y revoque lo que sobre. La bitácora se filtra
por fechas, usuario, acción, entidad y texto, y se exporta desde *Administración → Auditoría*.

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
| `withholding_on_payment` | false | `true` practica las retenciones a proveedores al pagar (no al causar la factura); cada una genera comprobante de retención (`CR` en Colombia; `AAAAMM` + 8 dígitos en Venezuela) |

Límites de aprobación por rol: `PUT /api/v1/approval-limits` (`purchase_requisition`, `purchase_order`,
`inventory_adjustment`, `payment`). Módulos por empresa: `PUT /api/v1/company/modules/{módulo}`.

## Parametrización fiscal (obligatoria antes de producción)
- **Impuestos**: tarifas, bases mínimas (UVT), cuentas y códigos electrónicos son configurables. Las
  tarifas iniciales (`backend/app/modules/org/jurisdictions.py`) son referencia y **deben validarlas el
  contador o revisor fiscal** (en particular ICA municipal, retenciones por concepto, IGTF y alícuotas).
- **Retenciones por tercero**: `PUT /api/v1/parties/{id}/withholdings`.
- **Comprobantes de retención**: la retención de IVA en Venezuela usa su propia secuencia (`AAAAMM` + 8
  dígitos, consecutiva para el TXT del SENIAT); las demás (ISLR, y en Colombia fuente, IVA e ICA) usan el
  consecutivo `CR-000001`. Para los certificados de Colombia registre la **ciudad** de la empresa (ciudad de
  práctica y consignación).
- **Libros y reportes fiscales**: permisos `accounting.tax_reports.read` (consultar y descargar comprobantes
  y certificados) y `accounting.tax_reports.export` (Excel de los libros y TXT del SENIAT). Los tienen el
  contador, la gerencia y el auditor; cada descarga queda en la auditoría.
- **Cuentas de contabilización**: `PUT /api/v1/posting-accounts` (inventario, CxC, CxP, ingresos, costo,
  variaciones, cuenta puente de saldos iniciales, resultados acumulados, anticipos de clientes
  `customer_advances` y a proveedores `supplier_advances`…). Las cuentas que una versión nueva incorpora al
  paquete del país (p. ej. anticipos: Colombia 280505 y 133005; Venezuela 2.1.04.01 y 1.1.05.01) se crean
  solas en las empresas existentes al arrancar (`python -m app.cli init`), sin tocar las que ya existen.
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
- **Correo saliente** (envío de cotizaciones, pedidos, órdenes de compra y facturas en PDF): `EMAIL_BACKEND=smtp`,
  `SMTP_HOST`, `SMTP_PORT` (587 con `SMTP_STARTTLS=true`, o 465 con `SMTP_SSL=true`), `SMTP_USER`,
  `SMTP_PASSWORD`, `MAIL_FROM`. En desarrollo `EMAIL_BACKEND=file` guarda los mensajes `.eml` en
  `STORAGE_PATH/mail` sin enviarlos; en staging/producción ese modo rechaza el envío. Los correos los entrega el
  worker con reintentos (5 intentos con espera creciente); un envío fallido queda con su error en el historial del
  documento y genera una alerta de integración.
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
- Revisión trimestral de usuarios y roles con la revisión de accesos (*Administración → Usuarios*) y la auditoría.

## Conservación y eliminación de datos
- Documentos contables, fiscales y su soporte: conservar mínimo **10 años** (Colombia: art. 28 Ley 962
  de 2005 / art. 632 E.T.; Venezuela: lapso de prescripción del COT — validar con asesoría legal).
- La bitácora de auditoría y los movimientos de inventario son de solo inserción; no se eliminan.
- Datos personales de terceros: atender solicitudes de habeas data (Ley 1581 de 2012) desactivando y
  anonimizando el tercero cuando no existan obligaciones de conservación; no borrar documentos fiscales.
- Intentos de acceso y tokens revocados: depurar con más de 1 año (tarea programada pendiente, ver lista).
