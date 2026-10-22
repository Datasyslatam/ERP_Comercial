# Documentación de la API

- Especificación completa OpenAPI 3: [`openapi.json`](openapi.json) (196 rutas, generada desde el código).
- Interactiva: `http://<host>/api/docs` (Swagger) y `/api/redoc` en entornos distintos de producción.

## Convenciones
- Base: `/api/v1`. JSON UTF-8. Importes y cantidades se envían y reciben como **texto decimal** (`"1285.20"`).
- Autenticación: `POST /auth/login` → `access_token` (15 min) + `refresh_token` (rotativo). Cabecera
  `Authorization: Bearer <token>`. Renovar con `POST /auth/refresh`; cerrar con `POST /auth/logout`.
- Multiempresa: cabecera obligatoria `X-Company-Id` en toda operación de negocio.
- Errores: `{"error": {"code", "message", "details"}, "request_id"}`. Códigos: 401 credenciales, 403
  permiso/segregación, 404 inexistente, 409 conflicto/duplicado/integridad, 422 regla de negocio o
  validación, 429 límite de solicitudes.
- Listados: `limit`/`offset`, respuesta `{"total", "items"}`.
- Idempotencia: pagos con `idempotency_key`; contabilizaciones y emisiones son idempotentes por documento.

## Mapa de recursos

| Área | Rutas principales |
|---|---|
| Precios y promociones | `/sales/price-lists` (+ `/items`, `/customers`), `/sales/promotions`, `/sales/pricing` (consulta) |
| Documentos comerciales | `/documents/{tipo}/{id}/pdf`, `/email`, `/email-defaults`, `/emails` (cotización, pedido, OC, factura, pago: recibo de caja / comprobante de egreso) |
| Trazabilidad | `/trace/{tipo}/{id}` (cadena documental entre módulos), `/trace/search?q=` |
| Autenticación y administración | `/auth/*`, `/admin/users` (ficha, roles, contraseña, desbloqueo, sesiones), `/admin/roles`, `/admin/permissions`, `/admin/access-review`, `/admin/audit` (+ `export.csv`), `/admin/login-attempts` |
| Empresa y parametrización | `/company`, `/company/settings`, `/company/modules/{m}`, `/approval-limits`, `/sites`, `/business-units`, `/cost-centers`, `/exchange-rates`, `/document-sequences`, `/posting-accounts` |
| Maestros | `/parties` (+`/withholdings`), `/items`, `/item-categories`, `/uoms`, `/uom-conversions`, `/taxes`, `/payment-terms`, `/accounts`, `/bank-accounts`, `/warehouses`, `/locations`, `/routes` |
| Compras | `/purchasing/requisitions`, `/rfqs` (+`/quotes`, `/comparison`, `/award`), `/orders` (+`/submit`, `/decision`, `/receipts`, `/cancel`), `/receipts`, `/invoices` (+`/post`), `/price-history/{item}`, `/suppliers/{id}/evaluation`, `/budget-status` |
| Inventario | `/inventory/stock`, `/kardex/{item}`, `/availability/{item}`, `/replenishment`, `/expiring`, `/lots`, `/reservations`, `/consistency`, `/documents` (+`/approve`, `/post`), `/counts` (+`/entries`, `/close`) |
| Calidad | `/quality/plans`, `/inspections` (+`/result`), `/lots/{id}/status`, `/nonconformities` (+`/advance`, `/actions`), `/actions/{id}/status`, `/history` |
| Ventas | `/sales/orders` (+`/confirm`, `/cancel`), `/customers/{id}/credit` |
| Logística | `/logistics/dispatches` (+`/plan`, `/start-picking`, `/picking`, `/pack`, `/ship`, `/deliver`, `/cancel`, `/events`, `/incidents`, `/returns`), `/incidents/{id}/resolve`, `/returns`, `/delivery-plan` |
| Operaciones | `/operations/boms`, `/work-orders` (+`/release`, `/issues`, `/time-logs`, `/output`, `/incidents`, `/complete`, `/close`) |
| Contabilidad | `/accounting/entries` (+`/post`, `/reverse`), `/periods` (+`/close`, `/reopen`, `/open-year`), `/year-close`, `/open-items`, `/aging`, `/payments` (+`/void`, `/withholding-suggestions`), `/bank-statements` (+`/parse` archivo CSV/XLSX/OFX, `/auto-match`, `/reconciliation`), `/bank-statement-lines/{id}/match`, `/reports/{trial-balance, general-ledger, journal, income-statement, balance-sheet, cash-flow}`, `/budgets`, `/goals` |
| Facturación | `/einvoicing/numbering-ranges`, `/invoices` (+`/from-dispatch`, `/issue`, `/resend`, `/cancel`, `/notes`, `/document`), `/reconciliation`, `/correction-codes` |
| Indicadores | `/kpi/definitions`, `/dashboard` (+`.csv`), `/kpis/{code}` (+`/trend`), `/targets`, `/alerts` (+`/ack`, `/evaluate`) |
| Importación | `/imports/entities`, `/templates/{entity}`, `/jobs` (+`/rows`, `/validate`, `/commit`, `/reconciliation`), `/rows/{id}`, `/opening-batches` (+`/approve`, `/post`) |
| Adjuntos y sistema | `/attachments`, `/attachments/{id}/content`, `/health/live`, `/health/ready`, `/metrics` |

## Ejemplo: ciclo de venta

```http
POST /api/v1/sales/orders            {"site_id":1,"customer_id":1,"warehouse_id":1,"order_date":"2026-10-17","currency":"COP","lines":[{"item_id":1,"quantity":"6"}]}
POST /api/v1/sales/orders/1/confirm
POST /api/v1/logistics/dispatches    {"sales_order_id":1}
POST /api/v1/logistics/dispatches/1/start-picking
POST /api/v1/logistics/dispatches/1/picking   {"picks":[{"dispatch_line_id":1,"qty_picked":"6"}]}
POST /api/v1/logistics/dispatches/1/pack      {"packages_count":1}
POST /api/v1/logistics/dispatches/1/ship      {"freight_cost":"50"}
POST /api/v1/einvoicing/invoices/from-dispatch {"dispatch_id":1}
POST /api/v1/einvoicing/invoices/1/issue
```
