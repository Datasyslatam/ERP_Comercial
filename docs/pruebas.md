# Resultados de pruebas

Ejecución real del 2026-10-17 sobre **PostgreSQL 16.2** (clúster local exclusivo de pruebas), Python 3.13,
Node 24. Comando: `pytest -v --cov=app --cov=integrations` y `npm test` / `npm run build` en `frontend`.

## Resumen

| Conjunto | Aprobadas | Fallidas | Omitidas | Observación |
|---|---|---|---|---|
| Backend (integración + unitarias) | **64** | 0 | 0 | Cobertura de líneas **84 %** (app + integrations) |
| Frontend (Vitest + Testing Library) | **9** | 0 | 0 | Formato, tabla, formulario; recaudo con retenciones; notas crédito/débito |
| Compilación frontend (`tsc -b` + `vite build`) | OK | — | — | |
| Migraciones (`alembic upgrade/downgrade/upgrade`, `alembic check`) | OK | — | — | Modelo y migraciones sincronizados |
| Lint (`ruff check backend integrations tests`) | OK | — | — | |
| `docker compose config` | OK | — | — | Sintaxis válida |

## Pruebas NO ejecutadas (pendientes)

| Prueba | Motivo |
|---|---|
| Construcción de imágenes Docker y arranque con `docker compose up` | Docker Desktop no inició en la máquina de desarrollo (distro WSL detenida). Queda cubierta por el job `images` del CI (`.github/workflows/ci.yml`). |
| Despliegue en Railway | Requiere cuenta y proyecto del cliente. |
| Envío real a DIAN/SENIAT | Proveedor tecnológico no definido; solo adaptadores sandbox. |
| Pruebas de carga / rendimiento | No incluidas en esta fase. |
| Pruebas end-to-end automatizadas de la interfaz (navegador) | Se verificó manualmente el ingreso, el dashboard, maestros y reportes contra la API real; no hay suite E2E automatizada. |

## Defectos encontrados por las pruebas y corregidos

1. **Numeración concurrente**: la primera creación de una secuencia podía colisionar entre transacciones
   (violación de unicidad). Corregido con `INSERT … ON CONFLICT DO NOTHING` + bloqueo de fila.
2. **Sesión en el navegador**: dos renovaciones simultáneas del refresh token eran detectadas como robo y
   revocaban la sesión. Corregido serializando la renovación en el cliente.
3. **Contexto de auditoría**: el usuario no quedaba registrado en cambios hechos desde dependencias síncronas
   (copia de `ContextVar` por hilo). Corregido mutando el contexto por petición.
4. **Retenciones en facturas de proveedor**: el impuesto de la línea de OC no se heredaba al cruzar la
   recepción. Corregido.
5. **Importes en JSON**: se serializaban como float; ahora como texto decimal sin pérdida de precisión.

## Detalle (pytest -v)

- test_accounting.py::test_unbalanced_entry_rejected_by_api_and_database — aprobada
- test_accounting.py::test_posted_entries_are_immutable_and_reversed — aprobada
- test_accounting.py::test_closed_period_blocks_postings — aprobada
- test_accounting.py::test_financial_statements_tie_out — aprobada
- test_accounting.py::test_year_close — aprobada
- test_accounting.py::test_bank_reconciliation — aprobada
- test_backup_restore.py::test_backup_and_restore_roundtrip — aprobada
- test_concurrency.py::test_concurrent_reservations_never_oversell — aprobada
- test_concurrency.py::test_concurrent_document_numbers_are_unique — aprobada
- test_concurrency.py::test_concurrent_payment_retries_are_idempotent — aprobada
- test_einvoicing_unit.py::test_check_digits — aprobada
- test_einvoicing_unit.py::test_cufe_follows_annex_formula — aprobada
- test_einvoicing_unit.py::test_sandbox_dian_accepts_only_as_sandbox_and_builds_ubl — aprobada
- test_einvoicing_unit.py::test_sandbox_dian_rejects_invalid_documents — aprobada
- test_einvoicing_unit.py::test_sandbox_seniat_amounts_in_bolivares — aprobada
- test_einvoicing_unit.py::test_transient_errors_retry_then_fail_with_alert — aprobada
- test_imports.py::test_template_download — aprobada
- test_imports.py::test_parties_import_with_errors_fix_and_retry — aprobada
- test_imports.py::test_opening_stock_requires_documented_approved_batch — aprobada
- test_imports.py::test_opening_receivables — aprobada
- test_inventory.py::test_negative_stock_is_impossible — aprobada
- test_inventory.py::test_stock_moves_are_append_only — aprobada
- test_inventory.py::test_adjustment_requires_approval_by_another_user — aprobada
- test_inventory.py::test_transfer_and_weighted_average_cost — aprobada
- test_inventory.py::test_blind_physical_count_with_differences — aprobada
- test_inventory.py::test_lot_and_expiry_required — aprobada
- test_kpi.py::test_empty_company_shows_no_data_not_zeros — aprobada
- test_kpi.py::test_kpis_computed_from_transactions — aprobada
- test_kpi.py::test_targets_status_and_alerts — aprobada
- test_kpi.py::test_dashboard_respects_permissions — aprobada
- test_kpi.py::test_trend — aprobada
- test_operations.py::test_module_disabled_for_commercial_company — aprobada
- test_operations.py::test_production_order_costing — aprobada
- test_operations.py::test_service_work_order — aprobada
- test_order_to_cash.py::test_full_order_to_cash — aprobada
- test_order_to_cash.py::test_reservation_prevents_overselling — aprobada
- test_order_to_cash.py::test_dispatch_cannot_exceed_reserved — aprobada
- test_order_to_cash.py::test_fefo_reservation_by_expiry — aprobada
- test_order_to_cash.py::test_credit_note_and_customer_return — aprobada
- test_order_to_cash.py::test_einvoice_rejected_then_resent — aprobada
- test_order_to_cash.py::test_credit_limit_blocks_confirmation — aprobada
- test_order_to_cash.py::test_dispatch_planning_and_delivery_plan — aprobada
- test_procure_to_pay.py::test_full_procure_to_pay_flow — aprobada
- test_procure_to_pay.py::test_price_tolerance_and_supplier_evaluation — aprobada
- test_procure_to_pay.py::test_cannot_receive_unapproved_order — aprobada
- test_procure_to_pay.py::test_budget_block_policy — aprobada
- test_quality.py::test_receipt_goes_to_quarantine_and_is_not_reservable — aprobada
- test_quality.py::test_partial_acceptance_releases_and_returns — aprobada
- test_quality.py::test_full_rejection_blocks_lot — aprobada
- test_security.py::test_login_and_me — aprobada
- test_security.py::test_bad_password_is_recorded_and_locks_account — aprobada
- test_security.py::test_unknown_user_same_error — aprobada
- test_security.py::test_refresh_rotation_and_reuse_detection — aprobada
- test_security.py::test_requires_token_and_company — aprobada
- test_security.py::test_permission_denied — aprobada
- test_security.py::test_company_isolation — aprobada
- test_security.py::test_segregation_of_duties_self_approval — aprobada
- test_security.py::test_approval_limit — aprobada
- test_security.py::test_password_policy — aprobada
- test_security.py::test_security_headers_and_request_id — aprobada
- test_security.py::test_rate_limit — aprobada
- test_security.py::test_audit_trail_records_changes_and_actions — aprobada
- test_security.py::test_audit_log_is_append_only — aprobada
- test_venezuela.py::test_ve_sale_in_usd_with_igtf — aprobada

## Qué valida cada archivo

| Archivo | Cobertura funcional |
|---|---|
| `test_security.py` | login, bloqueo por intentos, rotación y reutilización de refresh token, 401/403, aislamiento multiempresa (incluidas FK cruzadas), segregación de funciones, límites de aprobación, política de contraseñas, cabeceras, rate limit, auditoría y su inmutabilidad |
| `test_procure_to_pay.py` | solicitud → cotizaciones → comparativo → OC → recepción parcial → sobre-recepción rechazada → factura con cruce a tres vías y retención → duplicado rechazado → contabilización idempotente → pago idempotente → trazabilidad; tolerancia de precio; presupuesto bloqueante |
| `test_order_to_cash.py` | planificación de despachos (ruta, transportista, fecha) y plan de entregas; pedido con descuento → reserva → picking limitado a lo reservado → envío y costo de ventas → factura electrónica sandbox (CUFE, XML) → cartera → recaudo con retención → conciliación; sobreventa imposible; FEFO; nota crédito y devolución; rechazo y reenvío; cupo de crédito |
| `test_quality.py` | cuarentena no reservable ni facturable, aceptación parcial con devolución y NC automática, característica crítica, flujo CAPA, bloqueo de lote |
| `test_inventory.py` | no negativos (servicio y BD), libro inmutable, ajustes con aprobación de otro usuario, promedio ponderado, transferencias, kardex, conteo ciego, lote/vencimiento obligatorios |
| `test_accounting.py` | partida doble (API y trigger), inmutabilidad, reverso, periodos cerrados (servicio y BD), reapertura controlada, estados financieros cuadrados, cierre anual, conciliación bancaria |
| `test_concurrency.py` | 5 confirmaciones simultáneas sobre el mismo stock, 10 numeraciones simultáneas, 4 pagos simultáneos con la misma clave |
| `test_einvoicing_unit.py` | dígitos de verificación NIT/RIF, CUFE según fórmula del anexo, validaciones DIAN, montos en Bs. para SENIAT, reintentos y alerta ante caídas del proveedor |
| `test_imports.py` | plantillas, mapeo, errores por fila, corrección y reintento, duplicados, saldos iniciales con aprobación y contabilización |
| `test_kpi.py` | sin datos → "sin datos" (nunca cifras inventadas), cálculo desde transacciones, metas/estado, alertas sin duplicados, permisos por módulo, tendencia |
| `test_operations.py` | módulo desactivable, costeo real de producción, WIP en cero tras el cierre, orden de servicio |
| `test_venezuela.py` | empresa VES, venta en USD con tasa, imprenta digital sandbox, IGTF 3 %, retención de IVA 75 %, balance cuadrado |
| `frontend/src/screens.test.tsx` | recaudo con retenciones (cálculo, valor aplicado, idempotencia), pago sin retenciones, nota crédito y validación de nota débito |
| `test_backup_restore.py` | `pg_dump` → `pg_restore` en otra base → conteos, balance y triggers idénticos |
