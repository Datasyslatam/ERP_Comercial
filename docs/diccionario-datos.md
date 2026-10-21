# Diccionario de datos

Generado automáticamente desde los modelos SQLAlchemy (`python -m app.tools.gen_docs`). Convenciones: `id` BIGINT identidad; importes NUMERIC(18,2); cantidades NUMERIC(18,6); tasas NUMERIC(20,8); fechas-hora con zona horaria (UTC).

## Identidad y auditoría

### `users`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `email` | VARCHAR(254) | no |  |  |
| `full_name` | VARCHAR(200) | no |  |  |
| `job_title` | VARCHAR(120) | sí |  |  |
| `phone` | VARCHAR(40) | sí |  |  |
| `password_hash` | VARCHAR(255) | sí |  |  |
| `external_subject` | VARCHAR(255) | sí |  |  |
| `is_active` | BOOLEAN | no | True |  |
| `is_superadmin` | BOOLEAN | no | False |  |
| `failed_login_count` | BIGINT | no | 0 |  |
| `locked_until` | DATETIME | sí |  |  |
| `last_login_at` | DATETIME | sí |  |  |
| `password_changed_at` | DATETIME | sí |  |  |
| `must_change_password` | BOOLEAN | no | false |  |
| `id` (PK) | BIGINT | no |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (external_subject)
- Índice único `uq_users_email_lower`: (lower(email))

### `roles`

Roles del sistema (company_id nulo, comunes a todas las empresas) o propios de una empresa.

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `code` | VARCHAR(60) | no |  |  |
| `name` | VARCHAR(120) | no |  |  |
| `description` | TEXT | sí |  |  |
| `is_system` | BOOLEAN | no | False |  |
| `company_id` | BIGINT | sí |  | companies.id |
| `id` (PK) | BIGINT | no |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Índice `ix_roles_company_id`: (roles.company_id)
- Índice único `uq_roles_company_code`: (roles.company_id, roles.code)
- Índice único `uq_roles_system_code`: (roles.code)

### `permissions`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `code` | VARCHAR(120) | no |  |  |
| `module` | VARCHAR(40) | no |  |  |
| `description` | VARCHAR(255) | no |  |  |
| `id` (PK) | BIGINT | no |  |  |

- Única: (code)

### `role_permissions`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `role_id` (PK) | BIGINT | no |  | roles.id |
| `permission_id` (PK) | BIGINT | no |  | permissions.id |

### `user_company_roles`

Un usuario recibe roles por empresa; opcionalmente restringidos a una sede y con vigencia hasta una fecha (reemplazos por vacaciones, auditorías externas, accesos temporales).

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `user_id` | BIGINT | no |  | users.id |
| `company_id` | BIGINT | no |  | companies.id |
| `role_id` | BIGINT | no |  | roles.id |
| `site_id` | BIGINT | sí |  | sites.id |
| `expires_on` | DATE | sí |  |  |
| `granted_by_id` | BIGINT | sí |  | users.id |
| `granted_at` | DATETIME | sí | now() |  |
| `note` | VARCHAR(255) | sí |  |  |
| `id` (PK) | BIGINT | no |  |  |

- Única: (user_id, company_id, role_id, site_id)
- Índice `ix_user_company_roles_company_id`: (user_company_roles.company_id)
- Índice `ix_user_company_roles_user_id`: (user_company_roles.user_id)

### `refresh_tokens`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `user_id` | BIGINT | no |  | users.id |
| `token_hash` | VARCHAR(128) | no |  |  |
| `expires_at` | DATETIME | no |  |  |
| `revoked_at` | DATETIME | sí |  |  |
| `created_at` | DATETIME | no | now() |  |
| `created_ip` | VARCHAR(64) | sí |  |  |
| `user_agent` | VARCHAR(255) | sí |  |  |
| `id` (PK) | BIGINT | no |  |  |

- Única: (token_hash)
- Índice `ix_refresh_tokens_user_id`: (refresh_tokens.user_id)

### `login_attempts`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `email` | VARCHAR(254) | no |  |  |
| `user_id` | BIGINT | sí |  | users.id |
| `ip` | VARCHAR(64) | sí |  |  |
| `success` | BOOLEAN | no |  |  |
| `reason` | VARCHAR(80) | sí |  |  |
| `created_at` | DATETIME | no | now() |  |
| `id` (PK) | BIGINT | no |  |  |

- Índice `ix_login_attempts_created_at`: (login_attempts.created_at)
- Índice `ix_login_attempts_email`: (login_attempts.email)

### `audit_log`

Bitácora inmutable (protegida por trigger) de cambios y acciones sensibles.

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `occurred_at` | DATETIME | no | now() |  |
| `user_id` | BIGINT | sí |  | users.id |
| `company_id` | BIGINT | sí |  | companies.id |
| `ip` | VARCHAR(64) | sí |  |  |
| `request_id` | VARCHAR(64) | sí |  |  |
| `action` | VARCHAR(40) | no |  |  |
| `entity_type` | VARCHAR(80) | no |  |  |
| `entity_id` | VARCHAR(64) | sí |  |  |
| `changes` | JSONB | sí |  |  |
| `summary` | VARCHAR(500) | sí |  |  |
| `id` (PK) | BIGINT | no |  |  |

- Índice `ix_audit_entity`: (audit_log.entity_type, audit_log.entity_id)
- Índice `ix_audit_log_occurred_at`: (audit_log.occurred_at)

### `approval_limits`

Monto máximo (moneda funcional) que un rol puede aprobar por tipo de documento.

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `company_id` | BIGINT | no |  | companies.id |
| `role_id` | BIGINT | no |  | roles.id |
| `document_type` | VARCHAR(40) | no |  |  |
| `max_amount` | NUMERIC(18, 2) | no |  |  |
| `id` (PK) | BIGINT | no |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, role_id, document_type)

## Organización y configuración

### `companies`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `code` | VARCHAR(20) | no |  |  |
| `legal_name` | VARCHAR(200) | no |  |  |
| `trade_name` | VARCHAR(200) | sí |  |  |
| `tax_id` | VARCHAR(30) | no |  |  |
| `tax_id_check_digit` | VARCHAR(2) | sí |  |  |
| `country_code` | VARCHAR(2) | no |  |  |
| `functional_currency` | VARCHAR(3) | no |  | currencies.code |
| `fiscal_regime` | VARCHAR(60) | sí |  |  |
| `is_withholding_agent` | BOOLEAN | no | False |  |
| `is_special_taxpayer` | BOOLEAN | no | False |  |
| `address` | VARCHAR(255) | sí |  |  |
| `city` | VARCHAR(100) | sí |  |  |
| `city_code` | VARCHAR(10) | sí |  |  |
| `email` | VARCHAR(254) | sí |  |  |
| `phone` | VARCHAR(40) | sí |  |  |
| `settings` | JSONB | no |  |  |
| `is_active` | BOOLEAN | no | True |  |
| `id` (PK) | BIGINT | no |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (code)
- Verificación `ck_companies_country_supported`: `country_code in ('CO','VE')`

### `company_modules`

Activación de módulos por empresa (p. ej. producción desactivada en comercializadoras).

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `company_id` (PK) | BIGINT | no |  | companies.id |
| `module_code` (PK) | VARCHAR(40) | no |  |  |
| `enabled` | BOOLEAN | no | True |  |

### `sites`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `company_id` | BIGINT | no |  | companies.id |
| `code` | VARCHAR(20) | no |  |  |
| `name` | VARCHAR(120) | no |  |  |
| `address` | VARCHAR(255) | sí |  |  |
| `city` | VARCHAR(100) | sí |  |  |
| `is_active` | BOOLEAN | no | True |  |
| `id` (PK) | BIGINT | no |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, code)
- Índice `ix_sites_company_id`: (sites.company_id)

### `business_units`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `company_id` | BIGINT | no |  | companies.id |
| `code` | VARCHAR(20) | no |  |  |
| `name` | VARCHAR(120) | no |  |  |
| `is_active` | BOOLEAN | no | True |  |
| `id` (PK) | BIGINT | no |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, code)
- Índice `ix_business_units_company_id`: (business_units.company_id)

### `cost_centers`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `company_id` | BIGINT | no |  | companies.id |
| `code` | VARCHAR(20) | no |  |  |
| `name` | VARCHAR(120) | no |  |  |
| `parent_id` | BIGINT | sí |  | cost_centers.id |
| `business_unit_id` | BIGINT | sí |  | business_units.id |
| `site_id` | BIGINT | sí |  | sites.id |
| `is_active` | BOOLEAN | no | True |  |
| `id` (PK) | BIGINT | no |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, code)
- Índice `ix_cost_centers_company_id`: (cost_centers.company_id)

### `currencies`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `code` (PK) | VARCHAR(3) | no |  |  |
| `name` | VARCHAR(60) | no |  |  |
| `decimals` | BIGINT | no | 2 |  |

### `exchange_rates`

Tasa oficial por fecha y fuente (p. ej. TRM Banco de la República, BCV).

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `from_currency` | VARCHAR(3) | no |  | currencies.code |
| `to_currency` | VARCHAR(3) | no |  | currencies.code |
| `rate_date` | DATE | no |  |  |
| `rate` | NUMERIC(20, 8) | no |  |  |
| `source` | VARCHAR(40) | no |  |  |
| `id` (PK) | BIGINT | no |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (from_currency, to_currency, rate_date, source)
- Índice `ix_exchange_rates_rate_date`: (exchange_rates.rate_date)
- Verificación `ck_exchange_rates_rate_positive`: `rate > 0`

### `document_sequences`

Numeración interna correlativa por empresa y tipo de documento (bloqueo por fila al asignar).

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `company_id` | BIGINT | no |  | companies.id |
| `doc_type` | VARCHAR(40) | no |  |  |
| `prefix` | VARCHAR(20) | no |  |  |
| `next_number` | BIGINT | no | 1 |  |
| `padding` | BIGINT | no | 6 |  |
| `id` (PK) | BIGINT | no |  |  |

- Única: (company_id, doc_type)

### `attachments`

Documento adjunto (evidencias de calidad, soportes de entrega, XML fiscales, archivos importados).

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `company_id` | BIGINT | no |  | companies.id |
| `entity_type` | VARCHAR(60) | no |  |  |
| `entity_id` | BIGINT | no |  |  |
| `filename` | VARCHAR(255) | no |  |  |
| `content_type` | VARCHAR(120) | no |  |  |
| `size_bytes` | BIGINT | no |  |  |
| `sha256` | VARCHAR(64) | no |  |  |
| `storage_key` | VARCHAR(400) | no |  |  |
| `description` | TEXT | sí |  |  |
| `uploaded_by_id` | BIGINT | sí |  | users.id |
| `created_at` | DATETIME | no | now() |  |
| `id` (PK) | BIGINT | no |  |  |

- Índice `ix_attachments_company_id`: (attachments.company_id)

### `integration_events`

Bandeja de salida (outbox) para integraciones con reintentos seguros e idempotencia.

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `company_id` | BIGINT | no |  | companies.id |
| `event_type` | VARCHAR(60) | no |  |  |
| `payload` | JSONB | no |  |  |
| `status` | VARCHAR(20) | no | pending |  |
| `attempts` | BIGINT | no | 0 |  |
| `max_attempts` | BIGINT | no | 8 |  |
| `next_attempt_at` | DATETIME | no | now() |  |
| `last_error` | TEXT | sí |  |  |
| `idempotency_key` | VARCHAR(160) | no |  |  |
| `created_at` | DATETIME | no | now() |  |
| `processed_at` | DATETIME | sí |  |  |
| `id` (PK) | BIGINT | no |  |  |

- Única: (idempotency_key)
- Índice `ix_integration_events_company_id`: (integration_events.company_id)
- Índice `ix_integration_events_status`: (integration_events.status)

### `idempotency_records`

Respuestas almacenadas por cabecera Idempotency-Key para reintentos de clientes.

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `company_id` | BIGINT | no |  | companies.id |
| `scope` | VARCHAR(80) | no |  |  |
| `key` | VARCHAR(120) | no |  |  |
| `request_hash` | VARCHAR(64) | no |  |  |
| `response_status` | BIGINT | no |  |  |
| `response_body` | JSONB | no |  |  |
| `created_at` | DATETIME | no | now() |  |
| `id` (PK) | BIGINT | no |  |  |

- Única: (company_id, scope, key)

## Datos maestros

### `parties`

Tercero: cliente, proveedor y/o transportista.

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `company_id` | BIGINT | no |  | companies.id |
| `code` | VARCHAR(30) | no |  |  |
| `person_type` | VARCHAR(12) | no | organization |  |
| `legal_name` | VARCHAR(200) | no |  |  |
| `trade_name` | VARCHAR(200) | sí |  |  |
| `id_type` | VARCHAR(10) | no |  |  |
| `tax_id` | VARCHAR(30) | no |  |  |
| `check_digit` | VARCHAR(2) | sí |  |  |
| `is_customer` | BOOLEAN | no | False |  |
| `is_supplier` | BOOLEAN | no | False |  |
| `is_carrier` | BOOLEAN | no | False |  |
| `fiscal_regime` | VARCHAR(60) | sí |  |  |
| `is_withholding_agent` | BOOLEAN | no | False |  |
| `is_special_taxpayer` | BOOLEAN | no | False |  |
| `email` | VARCHAR(254) | sí |  |  |
| `phone` | VARCHAR(40) | sí |  |  |
| `address` | VARCHAR(255) | sí |  |  |
| `city` | VARCHAR(100) | sí |  |  |
| `city_code` | VARCHAR(10) | sí |  |  |
| `country_code` | VARCHAR(2) | no | CO |  |
| `payment_term_id` | BIGINT | sí |  | payment_terms.id |
| `credit_limit` | NUMERIC(18, 2) | no | 0 |  |
| `is_active` | BOOLEAN | no | True |  |
| `id` (PK) | BIGINT | no |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, id_type, tax_id)
- Única: (company_id, code)
- Índice `ix_parties_company_id`: (parties.company_id)
- Verificación `ck_parties_has_role`: `is_customer or is_supplier or is_carrier`

### `party_withholdings`

Retenciones aplicables: en compras las practicamos al proveedor; en ventas nos las practica el cliente.

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `party_id` (PK) | BIGINT | no |  | parties.id |
| `tax_id` (PK) | BIGINT | no |  | taxes.id |

### `items`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `company_id` | BIGINT | no |  | companies.id |
| `sku` | VARCHAR(40) | no |  |  |
| `name` | VARCHAR(200) | no |  |  |
| `description` | TEXT | sí |  |  |
| `barcode` | VARCHAR(60) | sí |  |  |
| `item_type` | VARCHAR(20) | no |  |  |
| `category_id` | BIGINT | sí |  | item_categories.id |
| `base_uom_id` | BIGINT | no |  | uoms.id |
| `is_stocked` | BOOLEAN | no | True |  |
| `track_lots` | BOOLEAN | no | False |  |
| `track_expiry` | BOOLEAN | no | False |  |
| `track_serials` | BOOLEAN | no | False |  |
| `requires_inspection` | BOOLEAN | no | False |  |
| `sales_tax_id` | BIGINT | sí |  | taxes.id |
| `purchase_tax_id` | BIGINT | sí |  | taxes.id |
| `min_stock` | NUMERIC(18, 6) | no | 0 |  |
| `max_stock` | NUMERIC(18, 6) | no | 0 |  |
| `list_price` | NUMERIC(18, 2) | no | 0 |  |
| `is_active` | BOOLEAN | no | True |  |
| `id` (PK) | BIGINT | no |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, sku)
- Índice `ix_items_company_id`: (items.company_id)
- Verificación `ck_items_type_valid`: `item_type in ('raw_material','supply','wip','finished_good','merchandise','service')`
- Verificación `ck_items_minmax_nonneg`: `min_stock >= 0 and max_stock >= 0`
- Verificación `ck_items_service_not_stocked`: `not (item_type = 'service' and is_stocked)`

### `item_categories`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `company_id` | BIGINT | no |  | companies.id |
| `code` | VARCHAR(20) | no |  |  |
| `name` | VARCHAR(120) | no |  |  |
| `parent_id` | BIGINT | sí |  | item_categories.id |
| `inventory_account_id` | BIGINT | sí |  | accounts.id |
| `revenue_account_id` | BIGINT | sí |  | accounts.id |
| `cogs_account_id` | BIGINT | sí |  | accounts.id |
| `expense_account_id` | BIGINT | sí |  | accounts.id |
| `id` (PK) | BIGINT | no |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, code)
- Índice `ix_item_categories_company_id`: (item_categories.company_id)

### `uoms`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `code` | VARCHAR(10) | no |  |  |
| `name` | VARCHAR(60) | no |  |  |
| `category` | VARCHAR(20) | no |  |  |
| `id` (PK) | BIGINT | no |  |  |

- Única: (code)

### `uom_conversions`

Factor: 1 from_uom = factor * to_uom. item_id nulo => conversión general.

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `item_id` | BIGINT | sí |  | items.id |
| `from_uom_id` | BIGINT | no |  | uoms.id |
| `to_uom_id` | BIGINT | no |  | uoms.id |
| `factor` | NUMERIC(18, 6) | no |  |  |
| `id` (PK) | BIGINT | no |  |  |

- Única: (item_id, from_uom_id, to_uom_id)
- Verificación `ck_uom_conversions_factor_positive`: `factor > 0`

### `taxes`

Impuesto o retención parametrizable. Las tarifas deben validarse con el asesor tributario.

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `company_id` | BIGINT | no |  | companies.id |
| `code` | VARCHAR(20) | no |  |  |
| `name` | VARCHAR(120) | no |  |  |
| `kind` | VARCHAR(30) | no |  |  |
| `rate` | NUMERIC(18, 6) | no |  |  |
| `base` | VARCHAR(10) | no | subtotal |  |
| `min_base_amount` | NUMERIC(18, 2) | no | 0 |  |
| `applies_to` | VARCHAR(10) | no | both |  |
| `electronic_code` | VARCHAR(10) | sí |  |  |
| `sales_account_id` | BIGINT | sí |  | accounts.id |
| `purchase_account_id` | BIGINT | sí |  | accounts.id |
| `is_active` | BOOLEAN | no | True |  |
| `id` (PK) | BIGINT | no |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, code)
- Índice `ix_taxes_company_id`: (taxes.company_id)
- Verificación `ck_taxes_applies_valid`: `applies_to in ('sales','purchases','both')`
- Verificación `ck_taxes_rate_range`: `rate >= 0 and rate <= 100`
- Verificación `ck_taxes_base_valid`: `base in ('subtotal','vat')`

### `payment_terms`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `company_id` | BIGINT | no |  | companies.id |
| `code` | VARCHAR(20) | no |  |  |
| `name` | VARCHAR(80) | no |  |  |
| `days` | BIGINT | no | 0 |  |
| `id` (PK) | BIGINT | no |  |  |

- Única: (company_id, code)
- Verificación `ck_payment_terms_days_nonneg`: `days >= 0`

## Compras

### `purchase_requisitions`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `number` | VARCHAR(30) | no |  |  |
| `site_id` | BIGINT | no |  | sites.id |
| `cost_center_id` | BIGINT | sí |  | cost_centers.id |
| `requested_by_id` | BIGINT | no |  | users.id |
| `needed_by` | DATE | sí |  |  |
| `justification` | TEXT | sí |  |  |
| `status` | VARCHAR(12) | no | draft |  |
| `total_estimated` | NUMERIC(18, 2) | no | 0 |  |
| `submitted_at` | DATETIME | sí |  |  |
| `approved_by_id` | BIGINT | sí |  | users.id |
| `approved_at` | DATETIME | sí |  |  |
| `rejection_reason` | TEXT | sí |  |  |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, number)
- Índice `ix_purchase_requisitions_company_id`: (purchase_requisitions.company_id)
- Verificación `ck_purchase_requisitions_status_valid`: `status in ('draft','submitted','approved','rejected','cancelled','ordered')`

### `purchase_requisition_lines`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `requisition_id` | BIGINT | no |  | purchase_requisitions.id |
| `item_id` | BIGINT | no |  | items.id |
| `description` | VARCHAR(255) | sí |  |  |
| `quantity` | NUMERIC(18, 6) | no |  |  |
| `estimated_unit_price` | NUMERIC(18, 6) | no | 0 |  |
| `id` (PK) | BIGINT | no |  |  |

- Índice `ix_purchase_requisition_lines_requisition_id`: (purchase_requisition_lines.requisition_id)
- Verificación `ck_purchase_requisition_lines_qty_positive`: `quantity > 0`

### `rfqs`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `number` | VARCHAR(30) | no |  |  |
| `requisition_id` | BIGINT | no |  | purchase_requisitions.id |
| `due_date` | DATE | sí |  |  |
| `status` | VARCHAR(10) | no | open |  |
| `created_by_id` | BIGINT | sí |  | users.id |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, number)
- Índice `ix_rfqs_company_id`: (rfqs.company_id)
- Verificación `ck_rfqs_status_valid`: `status in ('open','awarded','cancelled')`

### `supplier_quotes`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `rfq_id` | BIGINT | no |  | rfqs.id |
| `supplier_id` | BIGINT | no |  | parties.id |
| `quote_reference` | VARCHAR(60) | sí |  |  |
| `quote_date` | DATE | no |  |  |
| `valid_until` | DATE | sí |  |  |
| `currency` | VARCHAR(3) | no |  | currencies.code |
| `delivery_days` | BIGINT | no | 0 |  |
| `payment_term_id` | BIGINT | sí |  | payment_terms.id |
| `status` | VARCHAR(10) | no | received |  |
| `total` | NUMERIC(18, 2) | no | 0 |  |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (rfq_id, supplier_id)
- Índice `ix_supplier_quotes_company_id`: (supplier_quotes.company_id)
- Índice `ix_supplier_quotes_rfq_id`: (supplier_quotes.rfq_id)
- Verificación `ck_supplier_quotes_status_valid`: `status in ('received','selected','rejected')`

### `supplier_quote_lines`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `quote_id` | BIGINT | no |  | supplier_quotes.id |
| `requisition_line_id` | BIGINT | no |  | purchase_requisition_lines.id |
| `item_id` | BIGINT | no |  | items.id |
| `quantity` | NUMERIC(18, 6) | no |  |  |
| `unit_price` | NUMERIC(18, 6) | no |  |  |
| `tax_id` | BIGINT | sí |  | taxes.id |
| `id` (PK) | BIGINT | no |  |  |

- Índice `ix_supplier_quote_lines_quote_id`: (supplier_quote_lines.quote_id)
- Verificación `ck_supplier_quote_lines_values_valid`: `quantity > 0 and unit_price >= 0`

### `purchase_orders`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `number` | VARCHAR(30) | no |  |  |
| `site_id` | BIGINT | no |  | sites.id |
| `supplier_id` | BIGINT | no |  | parties.id |
| `requisition_id` | BIGINT | sí |  | purchase_requisitions.id |
| `quote_id` | BIGINT | sí |  | supplier_quotes.id |
| `warehouse_id` | BIGINT | no |  | warehouses.id |
| `cost_center_id` | BIGINT | sí |  | cost_centers.id |
| `order_date` | DATE | no |  |  |
| `expected_date` | DATE | sí |  |  |
| `currency` | VARCHAR(3) | no |  | currencies.code |
| `exchange_rate` | NUMERIC(20, 8) | no | 1 |  |
| `payment_term_id` | BIGINT | sí |  | payment_terms.id |
| `status` | VARCHAR(20) | no | draft |  |
| `subtotal` | NUMERIC(18, 2) | no | 0 |  |
| `tax_total` | NUMERIC(18, 2) | no | 0 |  |
| `total` | NUMERIC(18, 2) | no | 0 |  |
| `notes` | TEXT | sí |  |  |
| `created_by_id` | BIGINT | sí |  | users.id |
| `approved_by_id` | BIGINT | sí |  | users.id |
| `approved_at` | DATETIME | sí |  |  |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, number)
- Índice `ix_purchase_orders_company_id`: (purchase_orders.company_id)
- Índice `ix_purchase_orders_supplier_id`: (purchase_orders.supplier_id)
- Verificación `ck_purchase_orders_status_valid`: `status in ('draft','submitted','approved','rejected','partially_received','received','closed','cancelled')`

### `purchase_order_lines`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `purchase_order_id` | BIGINT | no |  | purchase_orders.id |
| `line_no` | BIGINT | no |  |  |
| `item_id` | BIGINT | no |  | items.id |
| `requisition_line_id` | BIGINT | sí |  | purchase_requisition_lines.id |
| `description` | VARCHAR(255) | sí |  |  |
| `quantity` | NUMERIC(18, 6) | no |  |  |
| `unit_price` | NUMERIC(18, 6) | no |  |  |
| `tax_id` | BIGINT | sí |  | taxes.id |
| `qty_received` | NUMERIC(18, 6) | no | 0 |  |
| `qty_rejected` | NUMERIC(18, 6) | no | 0 |  |
| `qty_invoiced` | NUMERIC(18, 6) | no | 0 |  |
| `id` (PK) | BIGINT | no |  |  |

- Única: (purchase_order_id, line_no)
- Índice `ix_purchase_order_lines_item_id`: (purchase_order_lines.item_id)
- Índice `ix_purchase_order_lines_purchase_order_id`: (purchase_order_lines.purchase_order_id)
- Verificación `ck_purchase_order_lines_values_valid`: `quantity > 0 and unit_price >= 0`
- Verificación `ck_purchase_order_lines_progress_nonneg`: `qty_received >= 0 and qty_invoiced >= 0 and qty_rejected >= 0`

### `goods_receipts`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `number` | VARCHAR(30) | no |  |  |
| `purchase_order_id` | BIGINT | no |  | purchase_orders.id |
| `supplier_id` | BIGINT | no |  | parties.id |
| `location_id` | BIGINT | no |  | locations.id |
| `receipt_date` | DATE | no |  |  |
| `supplier_delivery_note` | VARCHAR(60) | sí |  |  |
| `status` | VARCHAR(10) | no | draft |  |
| `received_by_id` | BIGINT | sí |  | users.id |
| `posted_at` | DATETIME | sí |  |  |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, number)
- Índice `ix_goods_receipts_company_id`: (goods_receipts.company_id)
- Índice `ix_goods_receipts_purchase_order_id`: (goods_receipts.purchase_order_id)
- Verificación `ck_goods_receipts_status_valid`: `status in ('draft','posted','cancelled')`

### `goods_receipt_lines`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `receipt_id` | BIGINT | no |  | goods_receipts.id |
| `po_line_id` | BIGINT | no |  | purchase_order_lines.id |
| `item_id` | BIGINT | no |  | items.id |
| `quantity` | NUMERIC(18, 6) | no |  |  |
| `lot_number` | VARCHAR(60) | sí |  |  |
| `expiry_date` | DATE | sí |  |  |
| `lot_id` | BIGINT | sí |  | lots.id |
| `unit_cost` | NUMERIC(18, 6) | no | 0 |  |
| `qty_accepted` | NUMERIC(18, 6) | no | 0 |  |
| `qty_rejected` | NUMERIC(18, 6) | no | 0 |  |
| `qty_invoiced` | NUMERIC(18, 6) | no | 0 |  |
| `inspection_status` | VARCHAR(14) | no | not_required |  |
| `id` (PK) | BIGINT | no |  |  |

- Índice `ix_goods_receipt_lines_po_line_id`: (goods_receipt_lines.po_line_id)
- Índice `ix_goods_receipt_lines_receipt_id`: (goods_receipt_lines.receipt_id)
- Verificación `ck_goods_receipt_lines_qty_positive`: `quantity > 0`
- Verificación `ck_goods_receipt_lines_insp_valid`: `inspection_status in ('not_required','pending','accepted','rejected','partial')`

### `supplier_invoices`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `number` | VARCHAR(30) | no |  |  |
| `supplier_id` | BIGINT | no |  | parties.id |
| `supplier_invoice_number` | VARCHAR(60) | no |  |  |
| `supplier_cufe` | VARCHAR(120) | sí |  |  |
| `purchase_order_id` | BIGINT | sí |  | purchase_orders.id |
| `invoice_date` | DATE | no |  |  |
| `due_date` | DATE | no |  |  |
| `currency` | VARCHAR(3) | no |  | currencies.code |
| `exchange_rate` | NUMERIC(20, 8) | no | 1 |  |
| `subtotal` | NUMERIC(18, 2) | no | 0 |  |
| `tax_total` | NUMERIC(18, 2) | no | 0 |  |
| `withholding_total` | NUMERIC(18, 2) | no | 0 |  |
| `total` | NUMERIC(18, 2) | no | 0 |  |
| `payable_total` | NUMERIC(18, 2) | no | 0 |  |
| `status` | VARCHAR(10) | no | draft |  |
| `match_status` | VARCHAR(20) | sí |  |  |
| `match_notes` | TEXT | sí |  |  |
| `journal_entry_id` | BIGINT | sí |  | journal_entries.id |
| `created_by_id` | BIGINT | sí |  | users.id |
| `posted_by_id` | BIGINT | sí |  | users.id |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, supplier_id, supplier_invoice_number)
- Única: (company_id, number)
- Índice `ix_supplier_invoices_company_id`: (supplier_invoices.company_id)
- Índice `ix_supplier_invoices_supplier_id`: (supplier_invoices.supplier_id)
- Verificación `ck_supplier_invoices_status_valid`: `status in ('draft','posted','cancelled')`

### `supplier_invoice_lines`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `invoice_id` | BIGINT | no |  | supplier_invoices.id |
| `receipt_line_id` | BIGINT | sí |  | goods_receipt_lines.id |
| `po_line_id` | BIGINT | sí |  | purchase_order_lines.id |
| `item_id` | BIGINT | sí |  | items.id |
| `expense_account_id` | BIGINT | sí |  | accounts.id |
| `cost_center_id` | BIGINT | sí |  | cost_centers.id |
| `description` | VARCHAR(255) | no |  |  |
| `quantity` | NUMERIC(18, 6) | no |  |  |
| `unit_price` | NUMERIC(18, 6) | no |  |  |
| `tax_id` | BIGINT | sí |  | taxes.id |
| `line_subtotal` | NUMERIC(18, 2) | no | 0 |  |
| `id` (PK) | BIGINT | no |  |  |

- Índice `ix_supplier_invoice_lines_invoice_id`: (supplier_invoice_lines.invoice_id)
- Verificación `ck_supplier_invoice_lines_values_valid`: `quantity > 0 and unit_price >= 0`

### `supplier_invoice_taxes`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `invoice_id` | BIGINT | no |  | supplier_invoices.id |
| `tax_id` | BIGINT | no |  | taxes.id |
| `base` | NUMERIC(18, 2) | no |  |  |
| `rate` | NUMERIC(18, 6) | no |  |  |
| `amount` | NUMERIC(18, 2) | no |  |  |
| `is_withholding` | BOOLEAN | no | False |  |
| `id` (PK) | BIGINT | no |  |  |

- Índice `ix_supplier_invoice_taxes_invoice_id`: (supplier_invoice_taxes.invoice_id)

## Inventario

### `warehouses`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `site_id` | BIGINT | no |  | sites.id |
| `code` | VARCHAR(20) | no |  |  |
| `name` | VARCHAR(120) | no |  |  |
| `is_active` | BOOLEAN | no | True |  |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, code)
- Índice `ix_warehouses_company_id`: (warehouses.company_id)

### `locations`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `warehouse_id` | BIGINT | no |  | warehouses.id |
| `code` | VARCHAR(30) | no |  |  |
| `name` | VARCHAR(120) | no |  |  |
| `zone` | VARCHAR(40) | sí |  |  |
| `location_type` | VARCHAR(20) | no | storage |  |
| `is_active` | BOOLEAN | no | True |  |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (warehouse_id, code)
- Índice `ix_locations_company_id`: (locations.company_id)
- Índice `ix_locations_warehouse_id`: (locations.warehouse_id)
- Verificación `ck_locations_type_valid`: `location_type in ('receiving','storage','quality','dispatch','production','scrap','transit')`

### `lots`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `item_id` | BIGINT | no |  | items.id |
| `lot_number` | VARCHAR(60) | no |  |  |
| `expiry_date` | DATE | sí |  |  |
| `manufactured_date` | DATE | sí |  |  |
| `supplier_id` | BIGINT | sí |  | parties.id |
| `status` | VARCHAR(12) | no | released |  |
| `status_reason` | VARCHAR(255) | sí |  |  |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, item_id, lot_number)
- Índice `ix_lots_company_id`: (lots.company_id)
- Índice `ix_lots_item_id`: (lots.item_id)
- Verificación `ck_lots_status_valid`: `status in ('quarantine','released','blocked')`

### `stock_balances`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `item_id` | BIGINT | no |  | items.id |
| `location_id` | BIGINT | no |  | locations.id |
| `lot_id` | BIGINT | sí |  | lots.id |
| `qty_on_hand` | NUMERIC(18, 6) | no | 0 |  |
| `qty_reserved` | NUMERIC(18, 6) | no | 0 |  |
| `updated_at` | DATETIME | no | now() |  |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |

- Índice `ix_stock_balances_company_id`: (stock_balances.company_id)
- Índice `ix_stock_balances_item_id`: (stock_balances.item_id)
- Índice `ix_stock_balances_location_id`: (stock_balances.location_id)
- Índice único `uq_stock_balance_key`: (stock_balances.item_id, stock_balances.location_id, coalesce(lot_id, :coalesce_1))
- Verificación `ck_stock_balances_no_negative_stock`: `qty_on_hand >= 0`
- Verificación `ck_stock_balances_reserved_within_onhand`: `qty_reserved >= 0 and qty_reserved <= qty_on_hand`

### `item_costs`

Costo promedio ponderado perpetuo por empresa y artículo.

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `item_id` (PK) | BIGINT | no |  | items.id |
| `company_id` (PK) | BIGINT | no |  | companies.id |
| `avg_cost` | NUMERIC(18, 6) | no | 0 |  |
| `qty_total` | NUMERIC(18, 6) | no | 0 |  |
| `updated_at` | DATETIME | no | now() |  |

- Verificación `ck_item_costs_cost_nonneg`: `avg_cost >= 0`
- Verificación `ck_item_costs_qty_nonneg`: `qty_total >= 0`

### `stock_moves`

Movimiento de inventario inmutable. Todo movimiento tiene fecha, responsable, motivo y documento origen.

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `move_date` | DATETIME | no | now() |  |
| `move_type` | VARCHAR(24) | no |  |  |
| `item_id` | BIGINT | no |  | items.id |
| `lot_id` | BIGINT | sí |  | lots.id |
| `from_location_id` | BIGINT | sí |  | locations.id |
| `to_location_id` | BIGINT | sí |  | locations.id |
| `quantity` | NUMERIC(18, 6) | no |  |  |
| `unit_cost` | NUMERIC(18, 6) | no |  |  |
| `total_cost` | NUMERIC(18, 2) | no |  |  |
| `source_type` | VARCHAR(40) | no |  |  |
| `source_id` | BIGINT | no |  |  |
| `source_line_id` | BIGINT | sí |  |  |
| `reference` | VARCHAR(80) | sí |  |  |
| `reason` | VARCHAR(255) | no |  |  |
| `created_by_id` | BIGINT | sí |  | users.id |
| `created_at` | DATETIME | no | now() |  |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |

- Índice `ix_stock_moves_company_id`: (stock_moves.company_id)
- Índice `ix_stock_moves_item_date`: (stock_moves.company_id, stock_moves.item_id, stock_moves.move_date)
- Índice `ix_stock_moves_source`: (stock_moves.source_type, stock_moves.source_id)
- Verificación `ck_stock_moves_qty_positive`: `quantity > 0`
- Verificación `ck_stock_moves_has_location`: `from_location_id is not null or to_location_id is not null`

### `stock_reservations`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `item_id` | BIGINT | no |  | items.id |
| `location_id` | BIGINT | no |  | locations.id |
| `lot_id` | BIGINT | sí |  | lots.id |
| `quantity` | NUMERIC(18, 6) | no |  |  |
| `quantity_consumed` | NUMERIC(18, 6) | no | 0 |  |
| `status` | VARCHAR(10) | no | active |  |
| `source_type` | VARCHAR(40) | no |  |  |
| `source_id` | BIGINT | no |  |  |
| `source_line_id` | BIGINT | no |  |  |
| `created_at` | DATETIME | no | now() |  |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |

- Índice `ix_reservations_source`: (stock_reservations.source_type, stock_reservations.source_line_id)
- Índice `ix_stock_reservations_company_id`: (stock_reservations.company_id)
- Verificación `ck_stock_reservations_consumed_within`: `quantity_consumed >= 0 and quantity_consumed <= quantity`
- Verificación `ck_stock_reservations_status_valid`: `status in ('active','consumed','released')`
- Verificación `ck_stock_reservations_qty_positive`: `quantity > 0`

### `inventory_documents`

Transferencias, ajustes, consumos internos y bajas. Los ajustes requieren aprobación.

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `number` | VARCHAR(30) | no |  |  |
| `doc_type` | VARCHAR(20) | no |  |  |
| `status` | VARCHAR(12) | no | draft |  |
| `doc_date` | DATE | no |  |  |
| `reason` | VARCHAR(255) | no |  |  |
| `cost_center_id` | BIGINT | sí |  | cost_centers.id |
| `created_by_id` | BIGINT | sí |  | users.id |
| `approved_by_id` | BIGINT | sí |  | users.id |
| `posted_at` | DATETIME | sí |  |  |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, number)
- Índice `ix_inventory_documents_company_id`: (inventory_documents.company_id)
- Verificación `ck_inventory_documents_type_valid`: `doc_type in ('transfer','adjustment','consumption','scrap')`
- Verificación `ck_inventory_documents_status_valid`: `status in ('draft','approved','posted','cancelled')`

### `inventory_document_lines`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `document_id` | BIGINT | no |  | inventory_documents.id |
| `item_id` | BIGINT | no |  | items.id |
| `lot_id` | BIGINT | sí |  | lots.id |
| `from_location_id` | BIGINT | sí |  | locations.id |
| `to_location_id` | BIGINT | sí |  | locations.id |
| `quantity` | NUMERIC(18, 6) | no |  |  |
| `unit_cost` | NUMERIC(18, 6) | sí |  |  |
| `id` (PK) | BIGINT | no |  |  |

- Índice `ix_inventory_document_lines_document_id`: (inventory_document_lines.document_id)
- Verificación `ck_inventory_document_lines_qty_nonzero`: `quantity <> 0`

### `physical_counts`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `number` | VARCHAR(30) | no |  |  |
| `warehouse_id` | BIGINT | no |  | warehouses.id |
| `count_date` | DATE | no |  |  |
| `status` | VARCHAR(12) | no | open |  |
| `notes` | TEXT | sí |  |  |
| `created_by_id` | BIGINT | sí |  | users.id |
| `approved_by_id` | BIGINT | sí |  | users.id |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, number)
- Índice `ix_physical_counts_company_id`: (physical_counts.company_id)
- Verificación `ck_physical_counts_status_valid`: `status in ('open','counted','posted','cancelled')`

### `physical_count_lines`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `count_id` | BIGINT | no |  | physical_counts.id |
| `item_id` | BIGINT | no |  | items.id |
| `location_id` | BIGINT | no |  | locations.id |
| `lot_id` | BIGINT | sí |  | lots.id |
| `system_qty` | NUMERIC(18, 6) | no |  |  |
| `counted_qty` | NUMERIC(18, 6) | sí |  |  |
| `id` (PK) | BIGINT | no |  |  |

- Índice `ix_physical_count_lines_count_id`: (physical_count_lines.count_id)

## Calidad

### `inspection_plans`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `code` | VARCHAR(30) | no |  |  |
| `name` | VARCHAR(200) | no |  |  |
| `stage` | VARCHAR(12) | no |  |  |
| `item_id` | BIGINT | sí |  | items.id |
| `category_id` | BIGINT | sí |  | item_categories.id |
| `sampling_rule` | VARCHAR(255) | sí |  |  |
| `is_active` | BOOLEAN | no | True |  |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, code)
- Índice `ix_inspection_plans_company_id`: (inspection_plans.company_id)
- Verificación `ck_inspection_plans_stage_valid`: `stage in ('receiving','in_process','final','dispatch')`

### `inspection_characteristics`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `plan_id` | BIGINT | no |  | inspection_plans.id |
| `name` | VARCHAR(120) | no |  |  |
| `kind` | VARCHAR(10) | no |  |  |
| `target` | NUMERIC(18, 6) | sí |  |  |
| `lower_limit` | NUMERIC(18, 6) | sí |  |  |
| `upper_limit` | NUMERIC(18, 6) | sí |  |  |
| `unit` | VARCHAR(20) | sí |  |  |
| `acceptance_criteria` | VARCHAR(255) | sí |  |  |
| `is_critical` | BOOLEAN | no | False |  |
| `id` (PK) | BIGINT | no |  |  |

- Índice `ix_inspection_characteristics_plan_id`: (inspection_characteristics.plan_id)
- Verificación `ck_inspection_characteristics_kind_valid`: `kind in ('numeric','boolean','text')`

### `inspections`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `number` | VARCHAR(30) | no |  |  |
| `plan_id` | BIGINT | sí |  | inspection_plans.id |
| `stage` | VARCHAR(12) | no |  |  |
| `item_id` | BIGINT | no |  | items.id |
| `lot_id` | BIGINT | sí |  | lots.id |
| `supplier_id` | BIGINT | sí |  | parties.id |
| `source_type` | VARCHAR(40) | no |  |  |
| `source_id` | BIGINT | no |  |  |
| `quantity` | NUMERIC(18, 6) | no |  |  |
| `qty_accepted` | NUMERIC(18, 6) | no | 0 |  |
| `qty_rejected` | NUMERIC(18, 6) | no | 0 |  |
| `status` | VARCHAR(10) | no | pending |  |
| `due_date` | DATE | sí |  |  |
| `inspector_id` | BIGINT | sí |  | users.id |
| `inspected_at` | DATETIME | sí |  |  |
| `notes` | TEXT | sí |  |  |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, number)
- Índice `ix_inspections_company_id`: (inspections.company_id)
- Índice `ix_inspections_item_id`: (inspections.item_id)
- Índice `ix_inspections_source`: (inspections.source_type, inspections.source_id)
- Índice `ix_inspections_supplier_id`: (inspections.supplier_id)
- Verificación `ck_inspections_qty_nonneg`: `qty_accepted >= 0 and qty_rejected >= 0`
- Verificación `ck_inspections_status_valid`: `status in ('pending','accepted','rejected','partial','cancelled')`

### `inspection_results`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `inspection_id` | BIGINT | no |  | inspections.id |
| `characteristic_id` | BIGINT | sí |  | inspection_characteristics.id |
| `name` | VARCHAR(120) | no |  |  |
| `numeric_value` | NUMERIC(18, 6) | sí |  |  |
| `bool_value` | BOOLEAN | sí |  |  |
| `text_value` | VARCHAR(255) | sí |  |  |
| `is_conforming` | BOOLEAN | no |  |  |
| `id` (PK) | BIGINT | no |  |  |

- Índice `ix_inspection_results_inspection_id`: (inspection_results.inspection_id)

### `nonconformities`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `number` | VARCHAR(30) | no |  |  |
| `source` | VARCHAR(12) | no |  |  |
| `inspection_id` | BIGINT | sí |  | inspections.id |
| `item_id` | BIGINT | sí |  | items.id |
| `lot_id` | BIGINT | sí |  | lots.id |
| `supplier_id` | BIGINT | sí |  | parties.id |
| `customer_id` | BIGINT | sí |  | parties.id |
| `category` | VARCHAR(60) | sí |  |  |
| `description` | TEXT | no |  |  |
| `severity` | VARCHAR(10) | no | minor |  |
| `quantity_affected` | NUMERIC(18, 6) | no | 0 |  |
| `cost_impact` | NUMERIC(18, 2) | no | 0 |  |
| `disposition` | VARCHAR(20) | sí |  |  |
| `root_cause` | TEXT | sí |  |  |
| `root_cause_method` | VARCHAR(20) | sí |  |  |
| `status` | VARCHAR(14) | no | open |  |
| `detected_at` | DATETIME | no |  |  |
| `closed_at` | DATETIME | sí |  |  |
| `responsible_id` | BIGINT | sí |  | users.id |
| `created_by_id` | BIGINT | sí |  | users.id |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, number)
- Índice `ix_nonconformities_company_id`: (nonconformities.company_id)
- Índice `ix_nonconformities_item_id`: (nonconformities.item_id)
- Índice `ix_nonconformities_supplier_id`: (nonconformities.supplier_id)
- Verificación `ck_nonconformities_source_valid`: `source in ('inspection','customer','internal','supplier','delivery','production')`
- Verificación `ck_nonconformities_status_valid`: `status in ('open','analysis','action','verification','closed')`
- Verificación `ck_nonconformities_severity_valid`: `severity in ('minor','major','critical')`

### `capa_actions`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `nonconformity_id` | BIGINT | no |  | nonconformities.id |
| `action_type` | VARCHAR(12) | no |  |  |
| `description` | TEXT | no |  |  |
| `responsible_id` | BIGINT | sí |  | users.id |
| `due_date` | DATE | sí |  |  |
| `completed_at` | DATETIME | sí |  |  |
| `effectiveness_notes` | TEXT | sí |  |  |
| `status` | VARCHAR(10) | no | open |  |
| `id` (PK) | BIGINT | no |  |  |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Índice `ix_capa_actions_nonconformity_id`: (capa_actions.nonconformity_id)
- Verificación `ck_capa_actions_type_valid`: `action_type in ('containment','corrective','preventive')`
- Verificación `ck_capa_actions_status_valid`: `status in ('open','done','verified','cancelled')`

## Ventas y logística

### `sales_orders`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `number` | VARCHAR(30) | no |  |  |
| `site_id` | BIGINT | no |  | sites.id |
| `customer_id` | BIGINT | no |  | parties.id |
| `warehouse_id` | BIGINT | no |  | warehouses.id |
| `order_date` | DATE | no |  |  |
| `promised_date` | DATE | sí |  |  |
| `currency` | VARCHAR(3) | no |  | currencies.code |
| `exchange_rate` | NUMERIC(20, 8) | no | 1 |  |
| `payment_term_id` | BIGINT | sí |  | payment_terms.id |
| `delivery_address` | VARCHAR(255) | sí |  |  |
| `status` | VARCHAR(22) | no | draft |  |
| `subtotal` | NUMERIC(18, 2) | no | 0 |  |
| `tax_total` | NUMERIC(18, 2) | no | 0 |  |
| `total` | NUMERIC(18, 2) | no | 0 |  |
| `notes` | TEXT | sí |  |  |
| `created_by_id` | BIGINT | sí |  | users.id |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, number)
- Índice `ix_sales_orders_company_id`: (sales_orders.company_id)
- Índice `ix_sales_orders_customer_id`: (sales_orders.customer_id)
- Verificación `ck_sales_orders_status_valid`: `status in ('draft','confirmed','partially_dispatched','dispatched','closed','cancelled')`

### `sales_order_lines`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `sales_order_id` | BIGINT | no |  | sales_orders.id |
| `line_no` | BIGINT | no |  |  |
| `item_id` | BIGINT | no |  | items.id |
| `description` | VARCHAR(255) | sí |  |  |
| `quantity` | NUMERIC(18, 6) | no |  |  |
| `unit_price` | NUMERIC(18, 6) | no |  |  |
| `discount_pct` | NUMERIC(18, 6) | no | 0 |  |
| `tax_id` | BIGINT | sí |  | taxes.id |
| `qty_reserved` | NUMERIC(18, 6) | no | 0 |  |
| `qty_dispatched` | NUMERIC(18, 6) | no | 0 |  |
| `qty_invoiced` | NUMERIC(18, 6) | no | 0 |  |
| `qty_returned` | NUMERIC(18, 6) | no | 0 |  |
| `id` (PK) | BIGINT | no |  |  |

- Única: (sales_order_id, line_no)
- Índice `ix_sales_order_lines_item_id`: (sales_order_lines.item_id)
- Índice `ix_sales_order_lines_sales_order_id`: (sales_order_lines.sales_order_id)
- Verificación `ck_sales_order_lines_discount_valid`: `discount_pct >= 0 and discount_pct <= 100`
- Verificación `ck_sales_order_lines_dispatch_within_qty`: `qty_dispatched <= quantity`
- Verificación `ck_sales_order_lines_values_valid`: `quantity > 0 and unit_price >= 0`

### `delivery_routes`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `code` | VARCHAR(20) | no |  |  |
| `name` | VARCHAR(120) | no |  |  |
| `description` | TEXT | sí |  |  |
| `site_id` | BIGINT | sí |  | sites.id |
| `standard_lead_days` | BIGINT | no | 1 |  |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, code)
- Índice `ix_delivery_routes_company_id`: (delivery_routes.company_id)

### `dispatch_orders`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `number` | VARCHAR(30) | no |  |  |
| `sales_order_id` | BIGINT | no |  | sales_orders.id |
| `customer_id` | BIGINT | no |  | parties.id |
| `warehouse_id` | BIGINT | no |  | warehouses.id |
| `status` | VARCHAR(20) | no | draft |  |
| `promised_date` | DATE | sí |  |  |
| `delivery_address` | VARCHAR(255) | sí |  |  |
| `carrier_id` | BIGINT | sí |  | parties.id |
| `route_id` | BIGINT | sí |  | delivery_routes.id |
| `planned_ship_date` | DATE | sí |  |  |
| `vehicle_plate` | VARCHAR(20) | sí |  |  |
| `driver_name` | VARCHAR(120) | sí |  |  |
| `tracking_number` | VARCHAR(60) | sí |  |  |
| `freight_cost` | NUMERIC(18, 2) | no | 0 |  |
| `packages_count` | BIGINT | no | 0 |  |
| `gross_weight_kg` | NUMERIC(18, 6) | no | 0 |  |
| `picked_at` | DATETIME | sí |  |  |
| `packed_at` | DATETIME | sí |  |  |
| `shipped_at` | DATETIME | sí |  |  |
| `delivered_at` | DATETIME | sí |  |  |
| `pod_received_by` | VARCHAR(120) | sí |  |  |
| `pod_notes` | TEXT | sí |  |  |
| `created_by_id` | BIGINT | sí |  | users.id |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, number)
- Índice `ix_dispatch_orders_company_id`: (dispatch_orders.company_id)
- Índice `ix_dispatch_orders_customer_id`: (dispatch_orders.customer_id)
- Índice `ix_dispatch_orders_sales_order_id`: (dispatch_orders.sales_order_id)
- Verificación `ck_dispatch_orders_freight_nonneg`: `freight_cost >= 0`
- Verificación `ck_dispatch_orders_status_valid`: `status in ('draft','picking','picked','packed','shipped','delivered','partially_delivered','cancelled')`

### `dispatch_lines`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `dispatch_id` | BIGINT | no |  | dispatch_orders.id |
| `so_line_id` | BIGINT | no |  | sales_order_lines.id |
| `item_id` | BIGINT | no |  | items.id |
| `qty_requested` | NUMERIC(18, 6) | no |  |  |
| `qty_picked` | NUMERIC(18, 6) | no | 0 |  |
| `qty_shipped` | NUMERIC(18, 6) | no | 0 |  |
| `qty_delivered` | NUMERIC(18, 6) | no | 0 |  |
| `qty_returned` | NUMERIC(18, 6) | no | 0 |  |
| `qty_invoiced` | NUMERIC(18, 6) | no | 0 |  |
| `unit_cost` | NUMERIC(18, 6) | sí |  |  |
| `id` (PK) | BIGINT | no |  |  |

- Índice `ix_dispatch_lines_dispatch_id`: (dispatch_lines.dispatch_id)
- Índice `ix_dispatch_lines_so_line_id`: (dispatch_lines.so_line_id)
- Verificación `ck_dispatch_lines_picked_within_requested`: `qty_picked <= qty_requested`
- Verificación `ck_dispatch_lines_delivered_within_shipped`: `qty_delivered <= qty_shipped`
- Verificación `ck_dispatch_lines_qty_positive`: `qty_requested > 0`
- Verificación `ck_dispatch_lines_returned_within_shipped`: `qty_returned <= qty_shipped`
- Verificación `ck_dispatch_lines_shipped_within_picked`: `qty_shipped <= qty_picked`

### `shipment_events`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `dispatch_id` | BIGINT | no |  | dispatch_orders.id |
| `event_time` | DATETIME | no |  |  |
| `status` | VARCHAR(30) | no |  |  |
| `location_text` | VARCHAR(200) | sí |  |  |
| `notes` | TEXT | sí |  |  |
| `created_by_id` | BIGINT | sí |  | users.id |
| `id` (PK) | BIGINT | no |  |  |

- Índice `ix_shipment_events_dispatch_id`: (shipment_events.dispatch_id)

### `delivery_incidents`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `dispatch_id` | BIGINT | no |  | dispatch_orders.id |
| `incident_type` | VARCHAR(10) | no |  |  |
| `description` | TEXT | no |  |  |
| `status` | VARCHAR(10) | no | open |  |
| `resolution` | TEXT | sí |  |  |
| `resolved_at` | DATETIME | sí |  |  |
| `created_by_id` | BIGINT | sí |  | users.id |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Índice `ix_delivery_incidents_company_id`: (delivery_incidents.company_id)
- Índice `ix_delivery_incidents_dispatch_id`: (delivery_incidents.dispatch_id)
- Verificación `ck_delivery_incidents_type_valid`: `incident_type in ('damaged','missing','late','rejected','address','other')`
- Verificación `ck_delivery_incidents_status_valid`: `status in ('open','resolved')`

### `customer_returns`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `number` | VARCHAR(30) | no |  |  |
| `dispatch_id` | BIGINT | no |  | dispatch_orders.id |
| `customer_id` | BIGINT | no |  | parties.id |
| `location_id` | BIGINT | no |  | locations.id |
| `return_date` | DATE | no |  |  |
| `reason` | VARCHAR(255) | no |  |  |
| `status` | VARCHAR(10) | no | draft |  |
| `created_by_id` | BIGINT | sí |  | users.id |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, number)
- Índice `ix_customer_returns_company_id`: (customer_returns.company_id)
- Índice `ix_customer_returns_dispatch_id`: (customer_returns.dispatch_id)
- Verificación `ck_customer_returns_status_valid`: `status in ('draft','received','cancelled')`

### `customer_return_lines`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `return_id` | BIGINT | no |  | customer_returns.id |
| `dispatch_line_id` | BIGINT | no |  | dispatch_lines.id |
| `item_id` | BIGINT | no |  | items.id |
| `lot_id` | BIGINT | sí |  | lots.id |
| `quantity` | NUMERIC(18, 6) | no |  |  |
| `condition` | VARCHAR(12) | no | resellable |  |
| `id` (PK) | BIGINT | no |  |  |

- Índice `ix_customer_return_lines_return_id`: (customer_return_lines.return_id)
- Verificación `ck_customer_return_lines_qty_positive`: `quantity > 0`
- Verificación `ck_customer_return_lines_condition_valid`: `condition in ('resellable','damaged')`

## Operaciones

### `boms`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `code` | VARCHAR(30) | no |  |  |
| `item_id` | BIGINT | no |  | items.id |
| `base_quantity` | NUMERIC(18, 6) | no | 1 |  |
| `is_active` | BOOLEAN | no | True |  |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, code)
- Índice `ix_boms_company_id`: (boms.company_id)
- Verificación `ck_boms_base_pos`: `base_quantity > 0`

### `bom_lines`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `bom_id` | BIGINT | no |  | boms.id |
| `component_item_id` | BIGINT | no |  | items.id |
| `quantity` | NUMERIC(18, 6) | no |  |  |
| `scrap_pct` | NUMERIC(18, 6) | no | 0 |  |
| `id` (PK) | BIGINT | no |  |  |

- Índice `ix_bom_lines_bom_id`: (bom_lines.bom_id)
- Verificación `ck_bom_lines_values_valid`: `quantity > 0 and scrap_pct >= 0`

### `work_orders`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `number` | VARCHAR(30) | no |  |  |
| `wo_type` | VARCHAR(12) | no |  |  |
| `site_id` | BIGINT | no |  | sites.id |
| `item_id` | BIGINT | sí |  | items.id |
| `bom_id` | BIGINT | sí |  | boms.id |
| `customer_id` | BIGINT | sí |  | parties.id |
| `project_name` | VARCHAR(200) | sí |  |  |
| `description` | TEXT | sí |  |  |
| `deliverables` | TEXT | sí |  |  |
| `production_location_id` | BIGINT | sí |  | locations.id |
| `output_location_id` | BIGINT | sí |  | locations.id |
| `planned_qty` | NUMERIC(18, 6) | no | 0 |  |
| `produced_qty` | NUMERIC(18, 6) | no | 0 |  |
| `scrap_qty` | NUMERIC(18, 6) | no | 0 |  |
| `rework_qty` | NUMERIC(18, 6) | no | 0 |  |
| `planned_hours` | NUMERIC(18, 6) | no | 0 |  |
| `estimated_cost` | NUMERIC(18, 2) | no | 0 |  |
| `status` | VARCHAR(12) | no | draft |  |
| `planned_start` | DATE | sí |  |  |
| `planned_end` | DATE | sí |  |  |
| `actual_start` | DATETIME | sí |  |  |
| `actual_end` | DATETIME | sí |  |  |
| `progress_pct` | NUMERIC(18, 6) | no | 0 |  |
| `responsible_id` | BIGINT | sí |  | users.id |
| `cost_center_id` | BIGINT | sí |  | cost_centers.id |
| `created_by_id` | BIGINT | sí |  | users.id |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, number)
- Índice `ix_work_orders_company_id`: (work_orders.company_id)
- Verificación `ck_work_orders_status_valid`: `status in ('draft','released','in_progress','completed','closed','cancelled')`
- Verificación `ck_work_orders_type_valid`: `wo_type in ('production','service','maintenance')`
- Verificación `ck_work_orders_qty_nonneg`: `planned_qty >= 0 and produced_qty >= 0 and scrap_qty >= 0 and rework_qty >= 0`

### `work_order_materials`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `work_order_id` | BIGINT | no |  | work_orders.id |
| `item_id` | BIGINT | no |  | items.id |
| `planned_qty` | NUMERIC(18, 6) | no |  |  |
| `issued_qty` | NUMERIC(18, 6) | no | 0 |  |
| `issued_cost` | NUMERIC(18, 2) | no | 0 |  |
| `estimated_unit_cost` | NUMERIC(18, 6) | no | 0 |  |
| `id` (PK) | BIGINT | no |  |  |

- Índice `ix_work_order_materials_work_order_id`: (work_order_materials.work_order_id)
- Verificación `ck_work_order_materials_qty_nonneg`: `planned_qty >= 0 and issued_qty >= 0`

### `work_order_time_logs`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `work_order_id` | BIGINT | no |  | work_orders.id |
| `log_date` | DATE | no |  |  |
| `resource_name` | VARCHAR(120) | no |  |  |
| `user_id` | BIGINT | sí |  | users.id |
| `activity` | VARCHAR(200) | no |  |  |
| `hours` | NUMERIC(18, 6) | no |  |  |
| `cost_per_hour` | NUMERIC(18, 6) | no | 0 |  |
| `id` (PK) | BIGINT | no |  |  |

- Índice `ix_work_order_time_logs_work_order_id`: (work_order_time_logs.work_order_id)
- Verificación `ck_work_order_time_logs_values_valid`: `hours > 0 and cost_per_hour >= 0`

### `work_order_incidents`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `work_order_id` | BIGINT | no |  | work_orders.id |
| `incident_type` | VARCHAR(30) | no |  |  |
| `description` | TEXT | no |  |  |
| `downtime_minutes` | BIGINT | no | 0 |  |
| `created_at` | DATETIME | no |  |  |
| `created_by_id` | BIGINT | sí |  | users.id |
| `id` (PK) | BIGINT | no |  |  |

- Índice `ix_work_order_incidents_work_order_id`: (work_order_incidents.work_order_id)

## Contabilidad y finanzas

### `accounts`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `code` | VARCHAR(20) | no |  |  |
| `name` | VARCHAR(200) | no |  |  |
| `account_type` | VARCHAR(10) | no |  |  |
| `normal_balance` | VARCHAR(6) | no |  |  |
| `parent_id` | BIGINT | sí |  | accounts.id |
| `is_postable` | BOOLEAN | no | True |  |
| `requires_party` | BOOLEAN | no | False |  |
| `requires_cost_center` | BOOLEAN | no | False |  |
| `is_cash` | BOOLEAN | no | False |  |
| `cash_flow_activity` | VARCHAR(12) | sí |  |  |
| `is_active` | BOOLEAN | no | True |  |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, code)
- Índice `ix_accounts_company_id`: (accounts.company_id)
- Verificación `ck_accounts_normal_valid`: `normal_balance in ('debit','credit')`
- Verificación `ck_accounts_type_valid`: `account_type in ('asset','liability','equity','revenue','expense','cost')`

### `posting_accounts`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `key` | VARCHAR(40) | no |  |  |
| `account_id` | BIGINT | no |  | accounts.id |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |

- Única: (company_id, key)
- Índice `ix_posting_accounts_company_id`: (posting_accounts.company_id)

### `fiscal_periods`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `year` | BIGINT | no |  |  |
| `month` | BIGINT | no |  |  |
| `start_date` | DATE | no |  |  |
| `end_date` | DATE | no |  |  |
| `status` | VARCHAR(8) | no | open |  |
| `closed_by_id` | BIGINT | sí |  | users.id |
| `closed_at` | DATETIME | sí |  |  |
| `reopened_by_id` | BIGINT | sí |  | users.id |
| `reopened_at` | DATETIME | sí |  |  |
| `reopen_reason` | TEXT | sí |  |  |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, year, month)
- Índice `ix_fiscal_periods_company_id`: (fiscal_periods.company_id)
- Verificación `ck_fiscal_periods_status_valid`: `status in ('open','closed')`
- Verificación `ck_fiscal_periods_month_valid`: `month between 1 and 12`

### `journal_entries`

Comprobante contable. Una vez contabilizado es inmutable (trigger); se corrige por reverso.

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `number` | VARCHAR(30) | no |  |  |
| `entry_date` | DATE | no |  |  |
| `period_id` | BIGINT | no |  | fiscal_periods.id |
| `journal_type` | VARCHAR(20) | no |  |  |
| `description` | VARCHAR(500) | no |  |  |
| `status` | VARCHAR(10) | no | draft |  |
| `source_type` | VARCHAR(40) | sí |  |  |
| `source_id` | BIGINT | sí |  |  |
| `idempotency_key` | VARCHAR(160) | no |  |  |
| `reversal_of_id` | BIGINT | sí |  | journal_entries.id |
| `created_by_id` | BIGINT | sí |  | users.id |
| `posted_by_id` | BIGINT | sí |  | users.id |
| `posted_at` | DATETIME | sí |  |  |
| `total_debit` | NUMERIC(18, 2) | no | 0 |  |
| `total_credit` | NUMERIC(18, 2) | no | 0 |  |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, idempotency_key)
- Única: (company_id, number)
- Índice `ix_journal_date`: (journal_entries.company_id, journal_entries.entry_date)
- Índice `ix_journal_entries_company_id`: (journal_entries.company_id)
- Índice `ix_journal_source`: (journal_entries.source_type, journal_entries.source_id)
- Verificación `ck_journal_entries_status_valid`: `status in ('draft','posted','reversed')`

### `journal_lines`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `entry_id` | BIGINT | no |  | journal_entries.id |
| `line_no` | BIGINT | no |  |  |
| `account_id` | BIGINT | no |  | accounts.id |
| `debit` | NUMERIC(18, 2) | no | 0 |  |
| `credit` | NUMERIC(18, 2) | no | 0 |  |
| `description` | VARCHAR(255) | sí |  |  |
| `party_id` | BIGINT | sí |  | parties.id |
| `cost_center_id` | BIGINT | sí |  | cost_centers.id |
| `currency` | VARCHAR(3) | sí |  | currencies.code |
| `amount_currency` | NUMERIC(18, 2) | sí |  |  |
| `exchange_rate` | NUMERIC(20, 8) | sí |  |  |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |

- Índice `ix_journal_lines_account`: (journal_lines.company_id, journal_lines.account_id)
- Índice `ix_journal_lines_company_id`: (journal_lines.company_id)
- Índice `ix_journal_lines_entry_id`: (journal_lines.entry_id)
- Verificación `ck_journal_lines_one_side`: `debit >= 0 and credit >= 0 and (debit = 0 or credit = 0) and debit + credit > 0`

### `open_items`

Partida abierta de cartera: CxC (receivable) o CxP (payable). Importes en moneda del documento.

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `kind` | VARCHAR(10) | no |  |  |
| `party_id` | BIGINT | no |  | parties.id |
| `document_type` | VARCHAR(30) | no |  |  |
| `document_id` | BIGINT | no |  |  |
| `document_number` | VARCHAR(60) | no |  |  |
| `issue_date` | DATE | no |  |  |
| `due_date` | DATE | no |  |  |
| `currency` | VARCHAR(3) | no |  | currencies.code |
| `exchange_rate` | NUMERIC(20, 8) | no | 1 |  |
| `original_amount` | NUMERIC(18, 2) | no |  |  |
| `open_amount` | NUMERIC(18, 2) | no |  |  |
| `status` | VARCHAR(10) | no | open |  |
| `journal_entry_id` | BIGINT | sí |  | journal_entries.id |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, kind, document_type, document_id)
- Índice `ix_open_items_company_id`: (open_items.company_id)
- Índice `ix_open_items_party`: (open_items.company_id, open_items.kind, open_items.party_id)
- Verificación `ck_open_items_kind_valid`: `kind in ('receivable','payable')`
- Verificación `ck_open_items_status_valid`: `status in ('open','partial','paid','cancelled')`
- Verificación `ck_open_items_open_within`: `open_amount >= 0 and open_amount <= original_amount`

### `payments`

Recaudo de cliente (receipt) o pago a proveedor (disbursement).

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `number` | VARCHAR(30) | no |  |  |
| `kind` | VARCHAR(12) | no |  |  |
| `party_id` | BIGINT | no |  | parties.id |
| `payment_date` | DATE | no |  |  |
| `bank_account_id` | BIGINT | no |  | bank_accounts.id |
| `method` | VARCHAR(20) | no |  |  |
| `currency` | VARCHAR(3) | no |  | currencies.code |
| `exchange_rate` | NUMERIC(20, 8) | no | 1 |  |
| `amount` | NUMERIC(18, 2) | no |  |  |
| `withholding_amount` | NUMERIC(18, 2) | no | 0 |  |
| `igtf_amount` | NUMERIC(18, 2) | no | 0 |  |
| `reference` | VARCHAR(80) | sí |  |  |
| `status` | VARCHAR(8) | no | posted |  |
| `idempotency_key` | VARCHAR(160) | no |  |  |
| `journal_entry_id` | BIGINT | sí |  | journal_entries.id |
| `created_by_id` | BIGINT | sí |  | users.id |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, number)
- Única: (company_id, idempotency_key)
- Índice `ix_payments_company_id`: (payments.company_id)
- Verificación `ck_payments_status_valid`: `status in ('posted','voided')`
- Verificación `ck_payments_amount_positive`: `amount > 0`
- Verificación `ck_payments_kind_valid`: `kind in ('receipt','disbursement')`

### `payment_allocations`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `payment_id` | BIGINT | no |  | payments.id |
| `open_item_id` | BIGINT | no |  | open_items.id |
| `amount` | NUMERIC(18, 2) | no |  |  |
| `id` (PK) | BIGINT | no |  |  |

- Índice `ix_payment_allocations_open_item_id`: (payment_allocations.open_item_id)
- Índice `ix_payment_allocations_payment_id`: (payment_allocations.payment_id)
- Verificación `ck_payment_allocations_amount_positive`: `amount > 0`

### `payment_withholdings`

Retenciones que el cliente nos practica al pagar (o que practicamos al pagar, si aplica).

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `payment_id` | BIGINT | no |  | payments.id |
| `tax_id` | BIGINT | no |  | taxes.id |
| `base` | NUMERIC(18, 2) | no |  |  |
| `amount` | NUMERIC(18, 2) | no |  |  |
| `id` (PK) | BIGINT | no |  |  |

- Índice `ix_payment_withholdings_payment_id`: (payment_withholdings.payment_id)

### `bank_accounts`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `name` | VARCHAR(120) | no |  |  |
| `bank_name` | VARCHAR(120) | no |  |  |
| `account_number_masked` | VARCHAR(40) | no |  |  |
| `currency` | VARCHAR(3) | no |  | currencies.code |
| `gl_account_id` | BIGINT | no |  | accounts.id |
| `is_active` | BOOLEAN | no | True |  |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, name)
- Índice `ix_bank_accounts_company_id`: (bank_accounts.company_id)

### `bank_statements`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `bank_account_id` | BIGINT | no |  | bank_accounts.id |
| `statement_date` | DATE | no |  |  |
| `opening_balance` | NUMERIC(18, 2) | no |  |  |
| `closing_balance` | NUMERIC(18, 2) | no |  |  |
| `source_filename` | VARCHAR(255) | sí |  |  |
| `imported_by_id` | BIGINT | sí |  | users.id |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Índice `ix_bank_statements_company_id`: (bank_statements.company_id)

### `bank_statement_lines`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `statement_id` | BIGINT | no |  | bank_statements.id |
| `txn_date` | DATE | no |  |  |
| `description` | VARCHAR(255) | no |  |  |
| `reference` | VARCHAR(80) | sí |  |  |
| `amount` | NUMERIC(18, 2) | no |  |  |
| `status` | VARCHAR(10) | no | unmatched |  |
| `matched_journal_line_id` | BIGINT | sí |  | journal_lines.id |
| `matched_by_id` | BIGINT | sí |  | users.id |
| `id` (PK) | BIGINT | no |  |  |

- Única: (matched_journal_line_id)
- Índice `ix_bank_statement_lines_statement_id`: (bank_statement_lines.statement_id)
- Verificación `ck_bank_statement_lines_status_valid`: `status in ('unmatched','matched','ignored')`

### `budget_lines`

Presupuesto mensual por dimensión. category: purchases, expenses, revenue.

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `year` | BIGINT | no |  |  |
| `month` | BIGINT | no |  |  |
| `category` | VARCHAR(12) | no |  |  |
| `cost_center_id` | BIGINT | sí |  | cost_centers.id |
| `account_id` | BIGINT | sí |  | accounts.id |
| `site_id` | BIGINT | sí |  | sites.id |
| `amount` | NUMERIC(18, 2) | no |  |  |
| `approved_by_id` | BIGINT | sí |  | users.id |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, year, month, category, cost_center_id, account_id, site_id)
- Índice `ix_budget_lines_company_id`: (budget_lines.company_id)
- Verificación `ck_budget_lines_amount_nonneg`: `amount >= 0`
- Verificación `ck_budget_lines_category_valid`: `category in ('purchases','expenses','revenue')`

### `strategic_goals`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `code` | VARCHAR(30) | no |  |  |
| `name` | VARCHAR(200) | no |  |  |
| `description` | TEXT | sí |  |  |
| `kpi_code` | VARCHAR(60) | no |  |  |
| `target_value` | NUMERIC(20, 8) | no |  |  |
| `period_start` | DATE | no |  |  |
| `period_end` | DATE | no |  |  |
| `owner_id` | BIGINT | sí |  | users.id |
| `weight` | NUMERIC(18, 2) | no | 1 |  |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, code)
- Índice `ix_strategic_goals_company_id`: (strategic_goals.company_id)

## Facturación electrónica

### `numbering_ranges`

Numeración autorizada (resolución DIAN o asignación de la imprenta digital SENIAT).

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `doc_type` | VARCHAR(12) | no |  |  |
| `prefix` | VARCHAR(10) | no |  |  |
| `range_from` | BIGINT | no |  |  |
| `range_to` | BIGINT | no |  |  |
| `next_number` | BIGINT | no |  |  |
| `valid_from` | DATE | no |  |  |
| `valid_to` | DATE | no |  |  |
| `authorization_number` | VARCHAR(60) | no |  |  |
| `technical_key` | VARCHAR(120) | sí |  |  |
| `environment` | VARCHAR(10) | no | sandbox |  |
| `is_active` | BOOLEAN | no | True |  |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, doc_type, prefix, range_from)
- Índice `ix_numbering_ranges_company_id`: (numbering_ranges.company_id)
- Verificación `ck_numbering_ranges_range_valid`: `range_to >= range_from and next_number >= range_from`
- Verificación `ck_numbering_ranges_env_valid`: `environment in ('sandbox','production')`
- Verificación `ck_numbering_ranges_doctype_valid`: `doc_type in ('invoice','credit_note','debit_note')`

### `sales_invoices`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `doc_type` | VARCHAR(12) | no | invoice |  |
| `prefix` | VARCHAR(10) | sí |  |  |
| `number` | BIGINT | sí |  |  |
| `full_number` | VARCHAR(40) | sí |  |  |
| `numbering_range_id` | BIGINT | sí |  | numbering_ranges.id |
| `site_id` | BIGINT | no |  | sites.id |
| `customer_id` | BIGINT | no |  | parties.id |
| `sales_order_id` | BIGINT | sí |  | sales_orders.id |
| `dispatch_id` | BIGINT | sí |  | dispatch_orders.id |
| `reference_invoice_id` | BIGINT | sí |  | sales_invoices.id |
| `correction_code` | VARCHAR(4) | sí |  |  |
| `correction_reason` | VARCHAR(255) | sí |  |  |
| `issue_date` | DATE | no |  |  |
| `issued_at` | DATETIME | sí |  |  |
| `due_date` | DATE | no |  |  |
| `payment_form` | VARCHAR(10) | no | credit |  |
| `currency` | VARCHAR(3) | no |  | currencies.code |
| `exchange_rate` | NUMERIC(20, 8) | no | 1 |  |
| `subtotal` | NUMERIC(18, 2) | no | 0 |  |
| `discount_total` | NUMERIC(18, 2) | no | 0 |  |
| `tax_total` | NUMERIC(18, 2) | no | 0 |  |
| `total` | NUMERIC(18, 2) | no | 0 |  |
| `status` | VARCHAR(10) | no | draft |  |
| `edoc_status` | VARCHAR(10) | no | draft |  |
| `edoc_environment` | VARCHAR(10) | sí |  |  |
| `edoc_adapter` | VARCHAR(40) | sí |  |  |
| `fiscal_uid` | VARCHAR(120) | sí |  |  |
| `control_number` | VARCHAR(40) | sí |  |  |
| `legal_validity` | BOOLEAN | no | False |  |
| `edoc_message` | TEXT | sí |  |  |
| `journal_entry_id` | BIGINT | sí |  | journal_entries.id |
| `idempotency_key` | VARCHAR(160) | no |  |  |
| `notes` | TEXT | sí |  |  |
| `created_by_id` | BIGINT | sí |  | users.id |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |
| `created_at` | DATETIME | no | now() |  |
| `updated_at` | DATETIME | no | now() |  |

- Única: (company_id, doc_type, prefix, number)
- Única: (company_id, idempotency_key)
- Índice `ix_sales_invoices_company_id`: (sales_invoices.company_id)
- Índice `ix_sales_invoices_customer_id`: (sales_invoices.customer_id)
- Verificación `ck_sales_invoices_edoc_status_valid`: `edoc_status in ('draft','pending','sent','accepted','rejected','error')`
- Verificación `ck_sales_invoices_notes_reference`: `doc_type = 'invoice' or reference_invoice_id is not null`
- Verificación `ck_sales_invoices_doctype_valid`: `doc_type in ('invoice','credit_note','debit_note')`
- Verificación `ck_sales_invoices_status_valid`: `status in ('draft','issued','cancelled')`

### `sales_invoice_lines`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `invoice_id` | BIGINT | no |  | sales_invoices.id |
| `line_no` | BIGINT | no |  |  |
| `item_id` | BIGINT | no |  | items.id |
| `description` | VARCHAR(255) | no |  |  |
| `quantity` | NUMERIC(18, 6) | no |  |  |
| `uom_code` | VARCHAR(10) | no |  |  |
| `unit_price` | NUMERIC(18, 6) | no |  |  |
| `discount_pct` | NUMERIC(18, 6) | no | 0 |  |
| `discount_amount` | NUMERIC(18, 2) | no | 0 |  |
| `tax_id` | BIGINT | sí |  | taxes.id |
| `tax_amount` | NUMERIC(18, 2) | no | 0 |  |
| `line_subtotal` | NUMERIC(18, 2) | no | 0 |  |
| `so_line_id` | BIGINT | sí |  | sales_order_lines.id |
| `dispatch_line_id` | BIGINT | sí |  | dispatch_lines.id |
| `id` (PK) | BIGINT | no |  |  |

- Índice `ix_sales_invoice_lines_invoice_id`: (sales_invoice_lines.invoice_id)
- Verificación `ck_sales_invoice_lines_values_valid`: `quantity > 0 and unit_price >= 0`
- Verificación `ck_sales_invoice_lines_discount_valid`: `discount_pct >= 0 and discount_pct <= 100`

### `sales_invoice_taxes`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `invoice_id` | BIGINT | no |  | sales_invoices.id |
| `tax_id` | BIGINT | no |  | taxes.id |
| `base` | NUMERIC(18, 2) | no |  |  |
| `rate` | NUMERIC(18, 6) | no |  |  |
| `amount` | NUMERIC(18, 2) | no |  |  |
| `id` (PK) | BIGINT | no |  |  |

- Índice `ix_sales_invoice_taxes_invoice_id`: (sales_invoice_taxes.invoice_id)

### `einvoice_submissions`

Cada intento de envío/consulta al proveedor tecnológico queda registrado (trazabilidad y conservación).

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `invoice_id` | BIGINT | no |  | sales_invoices.id |
| `attempt_no` | BIGINT | no |  |  |
| `operation` | VARCHAR(10) | no |  |  |
| `adapter` | VARCHAR(40) | no |  |  |
| `environment` | VARCHAR(10) | no |  |  |
| `document_sha256` | VARCHAR(64) | sí |  |  |
| `document_attachment_id` | BIGINT | sí |  | attachments.id |
| `result_status` | VARCHAR(10) | no |  |  |
| `provider_code` | VARCHAR(40) | sí |  |  |
| `provider_message` | TEXT | sí |  |  |
| `provider_tracking_id` | VARCHAR(120) | sí |  |  |
| `created_at` | DATETIME | no | now() |  |
| `id` (PK) | BIGINT | no |  |  |

- Única: (invoice_id, attempt_no)
- Índice `ix_einvoice_submissions_invoice_id`: (einvoice_submissions.invoice_id)

## Indicadores e importación

### `kpi_targets`

Meta y umbrales de un KPI para una empresa (opcionalmente por sede).

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `kpi_code` | VARCHAR(60) | no |  |  |
| `site_id` | BIGINT | sí |  | sites.id |
| `target` | NUMERIC(20, 8) | sí |  |  |
| `warning_threshold` | NUMERIC(20, 8) | sí |  |  |
| `critical_threshold` | NUMERIC(20, 8) | sí |  |  |
| `owner_id` | BIGINT | sí |  | users.id |
| `alerts_enabled` | BOOLEAN | no | True |  |
| `updated_at` | DATETIME | no | now() |  |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |

- Única: (company_id, kpi_code, site_id)
- Índice `ix_kpi_targets_company_id`: (kpi_targets.company_id)

### `kpi_snapshots`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `kpi_code` | VARCHAR(60) | no |  |  |
| `period_start` | DATE | no |  |  |
| `period_end` | DATE | no |  |  |
| `filters` | JSONB | no |  |  |
| `value` | NUMERIC(20, 8) | sí |  |  |
| `status` | VARCHAR(10) | no |  |  |
| `confidence` | VARCHAR(10) | no |  |  |
| `details` | JSONB | no |  |  |
| `computed_at` | DATETIME | no | now() |  |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |

- Índice `ix_kpi_snap`: (kpi_snapshots.company_id, kpi_snapshots.kpi_code, kpi_snapshots.period_end)
- Índice `ix_kpi_snapshots_company_id`: (kpi_snapshots.company_id)

### `alerts`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `source` | VARCHAR(60) | no |  |  |
| `dedupe_key` | VARCHAR(160) | no |  |  |
| `severity` | VARCHAR(10) | no |  |  |
| `message` | TEXT | no |  |  |
| `value` | NUMERIC(20, 8) | sí |  |  |
| `threshold` | NUMERIC(20, 8) | sí |  |  |
| `link` | VARCHAR(255) | sí |  |  |
| `status` | VARCHAR(14) | no | open |  |
| `created_at` | DATETIME | no | now() |  |
| `acknowledged_by_id` | BIGINT | sí |  | users.id |
| `acknowledged_at` | DATETIME | sí |  |  |
| `notes` | TEXT | sí |  |  |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |

- Índice `ix_alerts_company_id`: (alerts.company_id)
- Índice `ix_alerts_open`: (alerts.company_id, alerts.status)
- Verificación `ck_alerts_severity_valid`: `severity in ('info','warning','critical')`
- Verificación `ck_alerts_status_valid`: `status in ('open','acknowledged','closed')`

### `import_jobs`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `entity` | VARCHAR(40) | no |  |  |
| `filename` | VARCHAR(255) | no |  |  |
| `file_sha256` | VARCHAR(64) | no |  |  |
| `column_mapping` | JSONB | no |  |  |
| `status` | VARCHAR(20) | no | uploaded |  |
| `total_rows` | BIGINT | no | 0 |  |
| `valid_rows` | BIGINT | no | 0 |  |
| `invalid_rows` | BIGINT | no | 0 |  |
| `imported_rows` | BIGINT | no | 0 |  |
| `opening_batch_id` | BIGINT | sí |  | opening_balance_batches.id |
| `uploaded_by_id` | BIGINT | sí |  | users.id |
| `created_at` | DATETIME | no | now() |  |
| `finished_at` | DATETIME | sí |  |  |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |

- Índice `ix_import_jobs_company_id`: (import_jobs.company_id)
- Índice `ix_import_jobs_file_sha256`: (import_jobs.file_sha256)
- Verificación `ck_import_jobs_status_valid`: `status in ('uploaded','validated','partially_imported','imported','failed','cancelled')`

### `import_rows`

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `job_id` | BIGINT | no |  | import_jobs.id |
| `row_number` | BIGINT | no |  |  |
| `data` | JSONB | no |  |  |
| `status` | VARCHAR(10) | no | pending |  |
| `errors` | JSONB | no |  |  |
| `created_entity_id` | BIGINT | sí |  |  |
| `id` (PK) | BIGINT | no |  |  |

- Índice `ix_import_rows_job_status`: (import_rows.job_id, import_rows.status)
- Verificación `ck_import_rows_status_valid`: `status in ('pending','valid','invalid','imported','rejected')`

### `opening_balance_batches`

Saldos iniciales: documentan fecha de corte, origen y aprobación responsable antes de contabilizarse.

| Columna | Tipo | Nulo | Por defecto | Referencia |
|---|---|---|---|---|
| `kind` | VARCHAR(12) | no |  |  |
| `cutoff_date` | DATE | no |  |  |
| `source_description` | TEXT | no |  |  |
| `status` | VARCHAR(10) | no | draft |  |
| `created_by_id` | BIGINT | sí |  | users.id |
| `approved_by_id` | BIGINT | sí |  | users.id |
| `approved_at` | DATETIME | sí |  |  |
| `posted_at` | DATETIME | sí |  |  |
| `journal_entry_id` | BIGINT | sí |  | journal_entries.id |
| `notes` | TEXT | sí |  |  |
| `created_at` | DATETIME | no | now() |  |
| `id` (PK) | BIGINT | no |  |  |
| `company_id` | BIGINT | no |  | companies.id |

- Índice `ix_opening_balance_batches_company_id`: (opening_balance_batches.company_id)
- Verificación `ck_opening_balance_batches_kind_valid`: `kind in ('stock','receivables','payables','gl')`
- Verificación `ck_opening_balance_batches_status_valid`: `status in ('draft','approved','posted','cancelled')`

## Reglas en base de datos (migración 0002)

- `trg_journal_lines_balanced`: trigger diferido que rechaza al confirmar cualquier asiento contabilizado desbalanceado o con menos de dos líneas.
- `trg_journal_lines_immutable` / `trg_journal_entries_guard`: asientos contabilizados inmutables (solo se permite `posted → reversed`); prohíbe contabilizar en periodos cerrados.
- `trg_stock_moves_append_only`, `trg_audit_log_append_only`: tablas de solo inserción.
