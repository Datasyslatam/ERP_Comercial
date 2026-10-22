# Requisitos pendientes para producción

Estado honesto de lo que **falta** antes de operar con validez fiscal y datos reales. Nada de lo listado se
declara terminado en el código. Última revisión: 21/10/2026 (tras usuarios y roles, trazabilidad entre módulos,
funcionalidad por módulo y documentos comerciales en PDF con envío por correo).

## Bloqueantes (legales / fiscales)

| # | Pendiente | Responsable sugerido | Detalle |
|---|---|---|---|
| 1 | Contratar proveedor tecnológico DIAN (Colombia) | Gerencia + contador | Obtener documentación de su API, credenciales de habilitación y ambiente de pruebas; implementar un adaptador `EInvoiceAdapter` real (envío, consulta de estado, notificación al adquiriente, representación gráfica PDF, QR, eventos RADIAN si aplica). |
| 2 | Firma digital XAdES-EPES | Proveedor tecnológico o TI | El XML generado no incluye firma ni `DianExtensions` completas; si se opera como software propio se requiere certificado digital y el `SoftwareSecurityCode`. |
| 3 | Habilitación DIAN | Contador | Set de pruebas, resolución de numeración real, clave técnica. Registrar en *Numeración autorizada* con ambiente `production`. |
| 4 | Imprenta digital autorizada SENIAT (Venezuela) | Gerencia + contador | Definir proveedor, formato de intercambio y credenciales; implementar adaptador que asigne número de control real. |
| 5 | Validación tributaria de parámetros | Revisor fiscal | Tarifas de IVA/INC/IGTF, retenciones por concepto y bases en UVT, ICA por municipio, alícuotas VE, agentes de retención, calendario de declaraciones. |
| 6 | Revisión del plan de cuentas | Contador | Los planes CO/VE incluidos son base de referencia (PUC comercial simplificado / VEN-NIF genérico). |
| 7 | Reportes fiscales | Contador + TI | Medios magnéticos/exógena (CO), libros de compras y ventas e IVA (VE), certificados de retención: no implementados. |

## Funcionales

| # | Pendiente |
|---|---|
| 8 | Devolución de dinero a clientes cuando la nota crédito supera el saldo de la factura (hoy se bloquea). |
| 9 | Retenciones al pagar (en vez de al facturar) y retenciones de IVA en compras de Venezuela por comprobante. |
| 10 | ~~PDF y envío por correo~~ — **implementado** para cotización, pedido, orden de compra y factura / notas (cola con reintentos y bitácora). Falta: código QR y representación gráfica oficial exigida por el proveedor tecnológico (depende del #1), PDF de comprobantes de egreso y recibos de caja, y adjuntar el XML firmado al correo de la factura. |
| 11 | ~~Cotizaciones, listas de precios por cliente, descuentos por volumen y promociones~~ — **implementados**. Falta: listas por canal de venta o zona, y promociones por monto de compra o tipo "lleve N pague M". |
| 12 | Planeación de producción (MRP) y capacidad por centro de trabajo; hoy la planificación es por orden. |
| 13 | Flujo de efectivo indirecto y clasificación de actividades de inversión/financiación por cuenta. |
| 14 | Diferencia en cambio no realizada (reexpresión de saldos en divisas al cierre). |
| 15 | Extractos bancarios: hoy se cargan pegando los movimientos en pantalla. Falta leer los archivos propios de cada banco (CSV/Excel/OFX) con su formato. |
| 16 | ~~Pantallas para retenciones, notas, listas de materiales, rutas, devoluciones, incidencias, conciliación bancaria y límites de aprobación~~ — **implementadas**. Quedan solo por API: metas por sede y la carga de adjuntos desde las pantallas de documentos. |
| 29 | ~~Anulación de cotizaciones y edición de cotizaciones, pedidos y órdenes de compra en borrador~~ — **implementadas**. |

## Técnicos y de seguridad

| # | Pendiente |
|---|---|
| 17 | ~~Construir las imágenes Docker~~ — el CI las construye en cada cambio. Falta probar el `docker compose up` completo. |
| 30 | Configurar el correo saliente en Railway: `EMAIL_BACKEND=smtp`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM` (dominio con SPF/DKIM para no caer en spam). Sin esto el envío se rechaza fuera de desarrollo. El worker (`RUN_WORKER=1`) debe estar activo para entregar los correos. |
| 18 | Cifrado en reposo de campos sensibles (clave técnica de numeración, credenciales del proveedor) con KMS / gestor de secretos; hoy se apoya en cifrado de disco del proveedor. |
| 19 | Almacenamiento de adjuntos en S3 compatible (necesario en Railway con API y worker separados). |
| 20 | Límite de solicitudes distribuido (Redis o proxy/WAF) cuando haya varias réplicas de la API. |
| 21 | MFA para usuarios locales (o exigir SSO OIDC con MFA del proveedor de identidad). |
| 22 | Tarea programada de depuración de `login_attempts` y `refresh_tokens` antiguos; política de retención automatizada. |
| 23 | Pruebas de carga, pruebas E2E de interfaz automatizadas y pentest externo. |
| 24 | Respaldo PITR (WAL) si se requiere RPO menor a 24 h. |
| 25 | Modo offline por sede: descartado por decisión del usuario; diseño de referencia en `arquitectura.md` §9. |

## Datos

| # | Pendiente |
|---|---|
| 26 | Migración de datos reales con las plantillas: terceros, artículos, plan de cuentas, saldos iniciales de inventario y cartera con fecha de corte, origen y aprobación documentados. |
| 27 | Carga de presupuestos, metas y umbrales de KPI por la gerencia (sin ellos los KPI muestran "Sin meta"). |
| 28 | Tasas de cambio oficiales diarias (TRM / BCV): hoy se registran manualmente o por API. |
