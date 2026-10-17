# Modelo entidad-relación

Diagramas Mermaid generados desde los modelos. Se muestran claves primarias, foráneas y relaciones por dominio (las relaciones hacia tablas de otros dominios se listan al final de cada diagrama).

## Identidad y auditoría

```mermaid
erDiagram
    users {
        BIGINT id PK
    }
    roles {
        VARCHAR code
        BIGINT id PK
    }
    permissions {
        VARCHAR code
        BIGINT id PK
    }
    role_permissions {
        BIGINT role_id PK
        BIGINT permission_id PK
    }
    user_company_roles {
        BIGINT user_id FK
        BIGINT company_id FK
        BIGINT role_id FK
        BIGINT site_id FK
        BIGINT id PK
    }
    refresh_tokens {
        BIGINT user_id FK
        BIGINT id PK
    }
    login_attempts {
        BIGINT user_id FK
        BIGINT id PK
    }
    audit_log {
        BIGINT user_id FK
        BIGINT company_id FK
        BIGINT id PK
    }
    approval_limits {
        BIGINT company_id FK
        BIGINT role_id FK
        BIGINT id PK
    }
    permissions ||--o{ role_permissions : "permission_id"
    roles ||--o{ approval_limits : "role_id"
    roles ||--o{ role_permissions : "role_id"
    roles ||--o{ user_company_roles : "role_id"
    users ||--o{ audit_log : "user_id"
    users ||--o{ login_attempts : "user_id"
    users ||--o{ refresh_tokens : "user_id"
    users ||--o{ user_company_roles : "user_id"
```

Relaciones con otros dominios: `approval_limits` → companies; `audit_log` → companies; `user_company_roles` → companies, sites.

## Organización y configuración

```mermaid
erDiagram
    companies {
        VARCHAR code
        VARCHAR functional_currency FK
        BIGINT id PK
    }
    company_modules {
        BIGINT company_id PK
        VARCHAR module_code PK
    }
    sites {
        BIGINT company_id FK
        VARCHAR code
        BIGINT id PK
    }
    business_units {
        BIGINT company_id FK
        VARCHAR code
        BIGINT id PK
    }
    cost_centers {
        BIGINT company_id FK
        VARCHAR code
        BIGINT parent_id FK
        BIGINT business_unit_id FK
        BIGINT site_id FK
        BIGINT id PK
    }
    currencies {
        VARCHAR code PK
    }
    exchange_rates {
        VARCHAR from_currency FK
        VARCHAR to_currency FK
        BIGINT id PK
    }
    document_sequences {
        BIGINT company_id FK
        VARCHAR doc_type
        BIGINT id PK
    }
    attachments {
        BIGINT company_id FK
        BIGINT uploaded_by_id FK
        BIGINT id PK
    }
    integration_events {
        BIGINT company_id FK
        VARCHAR status
        BIGINT id PK
    }
    idempotency_records {
        BIGINT company_id FK
        BIGINT id PK
    }
    business_units ||--o{ cost_centers : "business_unit_id"
    companies ||--o{ attachments : "company_id"
    companies ||--o{ business_units : "company_id"
    companies ||--o{ company_modules : "company_id"
    companies ||--o{ cost_centers : "company_id"
    companies ||--o{ document_sequences : "company_id"
    companies ||--o{ idempotency_records : "company_id"
    companies ||--o{ integration_events : "company_id"
    companies ||--o{ sites : "company_id"
    currencies ||--o{ companies : "functional_currency"
    currencies ||--o{ exchange_rates : "from_currency"
    currencies ||--o{ exchange_rates : "to_currency"
    sites ||--o{ cost_centers : "site_id"
```

Relaciones con otros dominios: `attachments` → users.

## Datos maestros

```mermaid
erDiagram
    parties {
        BIGINT company_id FK
        VARCHAR code
        BIGINT payment_term_id FK
        BIGINT id PK
    }
    party_withholdings {
        BIGINT party_id PK
        BIGINT tax_id PK
    }
    items {
        BIGINT company_id FK
        VARCHAR sku
        BIGINT category_id FK
        BIGINT base_uom_id FK
        BIGINT sales_tax_id FK
        BIGINT purchase_tax_id FK
        BIGINT id PK
    }
    item_categories {
        BIGINT company_id FK
        VARCHAR code
        BIGINT parent_id FK
        BIGINT inventory_account_id FK
        BIGINT revenue_account_id FK
        BIGINT cogs_account_id FK
        BIGINT expense_account_id FK
        BIGINT id PK
    }
    uoms {
        VARCHAR code
        BIGINT id PK
    }
    uom_conversions {
        BIGINT item_id FK
        BIGINT from_uom_id FK
        BIGINT to_uom_id FK
        BIGINT id PK
    }
    taxes {
        BIGINT company_id FK
        VARCHAR code
        VARCHAR kind
        BIGINT sales_account_id FK
        BIGINT purchase_account_id FK
        BIGINT id PK
    }
    payment_terms {
        BIGINT company_id FK
        VARCHAR code
        BIGINT id PK
    }
    item_categories ||--o{ items : "category_id"
    items ||--o{ uom_conversions : "item_id"
    parties ||--o{ party_withholdings : "party_id"
    payment_terms ||--o{ parties : "payment_term_id"
    taxes ||--o{ items : "purchase_tax_id"
    taxes ||--o{ items : "sales_tax_id"
    taxes ||--o{ party_withholdings : "tax_id"
    uoms ||--o{ items : "base_uom_id"
    uoms ||--o{ uom_conversions : "from_uom_id"
    uoms ||--o{ uom_conversions : "to_uom_id"
```

Relaciones con otros dominios: `item_categories` → accounts, companies; `items` → companies; `parties` → companies; `payment_terms` → companies; `taxes` → accounts, companies.

## Compras

```mermaid
erDiagram
    purchase_requisitions {
        VARCHAR number
        BIGINT site_id FK
        BIGINT cost_center_id FK
        BIGINT requested_by_id FK
        VARCHAR status
        BIGINT approved_by_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    purchase_requisition_lines {
        BIGINT requisition_id FK
        BIGINT item_id FK
        BIGINT id PK
    }
    rfqs {
        VARCHAR number
        BIGINT requisition_id FK
        VARCHAR status
        BIGINT created_by_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    supplier_quotes {
        BIGINT rfq_id FK
        BIGINT supplier_id FK
        VARCHAR currency FK
        BIGINT payment_term_id FK
        VARCHAR status
        BIGINT id PK
        BIGINT company_id FK
    }
    supplier_quote_lines {
        BIGINT quote_id FK
        BIGINT requisition_line_id FK
        BIGINT item_id FK
        BIGINT tax_id FK
        BIGINT id PK
    }
    purchase_orders {
        VARCHAR number
        BIGINT site_id FK
        BIGINT supplier_id FK
        BIGINT requisition_id FK
        BIGINT quote_id FK
        BIGINT warehouse_id FK
        BIGINT cost_center_id FK
        VARCHAR currency FK
        BIGINT payment_term_id FK
        VARCHAR status
        BIGINT created_by_id FK
        BIGINT approved_by_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    purchase_order_lines {
        BIGINT purchase_order_id FK
        BIGINT item_id FK
        BIGINT requisition_line_id FK
        BIGINT tax_id FK
        BIGINT id PK
    }
    goods_receipts {
        VARCHAR number
        BIGINT purchase_order_id FK
        BIGINT supplier_id FK
        BIGINT location_id FK
        VARCHAR status
        BIGINT received_by_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    goods_receipt_lines {
        BIGINT receipt_id FK
        BIGINT po_line_id FK
        BIGINT item_id FK
        BIGINT lot_id FK
        BIGINT id PK
    }
    supplier_invoices {
        VARCHAR number
        BIGINT supplier_id FK
        BIGINT purchase_order_id FK
        VARCHAR currency FK
        VARCHAR status
        BIGINT journal_entry_id FK
        BIGINT created_by_id FK
        BIGINT posted_by_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    supplier_invoice_lines {
        BIGINT invoice_id FK
        BIGINT receipt_line_id FK
        BIGINT po_line_id FK
        BIGINT item_id FK
        BIGINT expense_account_id FK
        BIGINT cost_center_id FK
        BIGINT tax_id FK
        BIGINT id PK
    }
    supplier_invoice_taxes {
        BIGINT invoice_id FK
        BIGINT tax_id FK
        BIGINT id PK
    }
    goods_receipt_lines ||--o{ supplier_invoice_lines : "receipt_line_id"
    goods_receipts ||--o{ goods_receipt_lines : "receipt_id"
    purchase_order_lines ||--o{ goods_receipt_lines : "po_line_id"
    purchase_order_lines ||--o{ supplier_invoice_lines : "po_line_id"
    purchase_orders ||--o{ goods_receipts : "purchase_order_id"
    purchase_orders ||--o{ purchase_order_lines : "purchase_order_id"
    purchase_orders ||--o{ supplier_invoices : "purchase_order_id"
    purchase_requisition_lines ||--o{ purchase_order_lines : "requisition_line_id"
    purchase_requisition_lines ||--o{ supplier_quote_lines : "requisition_line_id"
    purchase_requisitions ||--o{ purchase_orders : "requisition_id"
    purchase_requisitions ||--o{ purchase_requisition_lines : "requisition_id"
    purchase_requisitions ||--o{ rfqs : "requisition_id"
    rfqs ||--o{ supplier_quotes : "rfq_id"
    supplier_invoices ||--o{ supplier_invoice_lines : "invoice_id"
    supplier_invoices ||--o{ supplier_invoice_taxes : "invoice_id"
    supplier_quotes ||--o{ purchase_orders : "quote_id"
    supplier_quotes ||--o{ supplier_quote_lines : "quote_id"
```

Relaciones con otros dominios: `goods_receipt_lines` → items, lots; `goods_receipts` → companies, locations, parties, users; `purchase_order_lines` → items, taxes; `purchase_orders` → companies, cost_centers, currencies, parties, payment_terms, sites, users, warehouses; `purchase_requisition_lines` → items; `purchase_requisitions` → companies, cost_centers, sites, users; `rfqs` → companies, users; `supplier_invoice_lines` → accounts, cost_centers, items, taxes; `supplier_invoice_taxes` → taxes; `supplier_invoices` → companies, currencies, journal_entries, parties, users; `supplier_quote_lines` → items, taxes; `supplier_quotes` → companies, currencies, parties, payment_terms.

## Inventario

```mermaid
erDiagram
    warehouses {
        BIGINT site_id FK
        VARCHAR code
        BIGINT id PK
        BIGINT company_id FK
    }
    locations {
        BIGINT warehouse_id FK
        VARCHAR code
        BIGINT id PK
        BIGINT company_id FK
    }
    lots {
        BIGINT item_id FK
        BIGINT supplier_id FK
        VARCHAR status
        BIGINT id PK
        BIGINT company_id FK
    }
    stock_balances {
        BIGINT item_id FK
        BIGINT location_id FK
        BIGINT lot_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    item_costs {
        BIGINT item_id PK
        BIGINT company_id PK
    }
    stock_moves {
        BIGINT item_id FK
        BIGINT lot_id FK
        BIGINT from_location_id FK
        BIGINT to_location_id FK
        BIGINT created_by_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    stock_reservations {
        BIGINT item_id FK
        BIGINT location_id FK
        BIGINT lot_id FK
        VARCHAR status
        BIGINT id PK
        BIGINT company_id FK
    }
    inventory_documents {
        VARCHAR number
        VARCHAR doc_type
        VARCHAR status
        BIGINT cost_center_id FK
        BIGINT created_by_id FK
        BIGINT approved_by_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    inventory_document_lines {
        BIGINT document_id FK
        BIGINT item_id FK
        BIGINT lot_id FK
        BIGINT from_location_id FK
        BIGINT to_location_id FK
        BIGINT id PK
    }
    physical_counts {
        VARCHAR number
        BIGINT warehouse_id FK
        VARCHAR status
        BIGINT created_by_id FK
        BIGINT approved_by_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    physical_count_lines {
        BIGINT count_id FK
        BIGINT item_id FK
        BIGINT location_id FK
        BIGINT lot_id FK
        BIGINT id PK
    }
    inventory_documents ||--o{ inventory_document_lines : "document_id"
    locations ||--o{ inventory_document_lines : "from_location_id"
    locations ||--o{ inventory_document_lines : "to_location_id"
    locations ||--o{ physical_count_lines : "location_id"
    locations ||--o{ stock_balances : "location_id"
    locations ||--o{ stock_moves : "from_location_id"
    locations ||--o{ stock_moves : "to_location_id"
    locations ||--o{ stock_reservations : "location_id"
    lots ||--o{ inventory_document_lines : "lot_id"
    lots ||--o{ physical_count_lines : "lot_id"
    lots ||--o{ stock_balances : "lot_id"
    lots ||--o{ stock_moves : "lot_id"
    lots ||--o{ stock_reservations : "lot_id"
    physical_counts ||--o{ physical_count_lines : "count_id"
    warehouses ||--o{ locations : "warehouse_id"
    warehouses ||--o{ physical_counts : "warehouse_id"
```

Relaciones con otros dominios: `inventory_document_lines` → items; `inventory_documents` → companies, cost_centers, users; `item_costs` → companies, items; `locations` → companies; `lots` → companies, items, parties; `physical_count_lines` → items; `physical_counts` → companies, users; `stock_balances` → companies, items; `stock_moves` → companies, items, users; `stock_reservations` → companies, items; `warehouses` → companies, sites.

## Calidad

```mermaid
erDiagram
    inspection_plans {
        VARCHAR code
        BIGINT item_id FK
        BIGINT category_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    inspection_characteristics {
        BIGINT plan_id FK
        VARCHAR kind
        BIGINT id PK
    }
    inspections {
        VARCHAR number
        BIGINT plan_id FK
        BIGINT item_id FK
        BIGINT lot_id FK
        BIGINT supplier_id FK
        VARCHAR status
        BIGINT inspector_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    inspection_results {
        BIGINT inspection_id FK
        BIGINT characteristic_id FK
        BIGINT id PK
    }
    nonconformities {
        VARCHAR number
        BIGINT inspection_id FK
        BIGINT item_id FK
        BIGINT lot_id FK
        BIGINT supplier_id FK
        BIGINT customer_id FK
        VARCHAR status
        BIGINT responsible_id FK
        BIGINT created_by_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    capa_actions {
        BIGINT nonconformity_id FK
        BIGINT responsible_id FK
        VARCHAR status
        BIGINT id PK
    }
    inspection_characteristics ||--o{ inspection_results : "characteristic_id"
    inspection_plans ||--o{ inspection_characteristics : "plan_id"
    inspection_plans ||--o{ inspections : "plan_id"
    inspections ||--o{ inspection_results : "inspection_id"
    inspections ||--o{ nonconformities : "inspection_id"
    nonconformities ||--o{ capa_actions : "nonconformity_id"
```

Relaciones con otros dominios: `capa_actions` → users; `inspection_plans` → companies, item_categories, items; `inspections` → companies, items, lots, parties, users; `nonconformities` → companies, items, lots, parties, users.

## Ventas y logística

```mermaid
erDiagram
    sales_orders {
        VARCHAR number
        BIGINT site_id FK
        BIGINT customer_id FK
        BIGINT warehouse_id FK
        VARCHAR currency FK
        BIGINT payment_term_id FK
        VARCHAR status
        BIGINT created_by_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    sales_order_lines {
        BIGINT sales_order_id FK
        BIGINT item_id FK
        BIGINT tax_id FK
        BIGINT id PK
    }
    delivery_routes {
        VARCHAR code
        BIGINT site_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    dispatch_orders {
        VARCHAR number
        BIGINT sales_order_id FK
        BIGINT customer_id FK
        BIGINT warehouse_id FK
        VARCHAR status
        BIGINT carrier_id FK
        BIGINT route_id FK
        BIGINT created_by_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    dispatch_lines {
        BIGINT dispatch_id FK
        BIGINT so_line_id FK
        BIGINT item_id FK
        BIGINT id PK
    }
    shipment_events {
        BIGINT dispatch_id FK
        VARCHAR status
        BIGINT created_by_id FK
        BIGINT id PK
    }
    delivery_incidents {
        BIGINT dispatch_id FK
        VARCHAR status
        BIGINT created_by_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    customer_returns {
        VARCHAR number
        BIGINT dispatch_id FK
        BIGINT customer_id FK
        BIGINT location_id FK
        VARCHAR status
        BIGINT created_by_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    customer_return_lines {
        BIGINT return_id FK
        BIGINT dispatch_line_id FK
        BIGINT item_id FK
        BIGINT lot_id FK
        BIGINT id PK
    }
    customer_returns ||--o{ customer_return_lines : "return_id"
    delivery_routes ||--o{ dispatch_orders : "route_id"
    dispatch_lines ||--o{ customer_return_lines : "dispatch_line_id"
    dispatch_orders ||--o{ customer_returns : "dispatch_id"
    dispatch_orders ||--o{ delivery_incidents : "dispatch_id"
    dispatch_orders ||--o{ dispatch_lines : "dispatch_id"
    dispatch_orders ||--o{ shipment_events : "dispatch_id"
    sales_order_lines ||--o{ dispatch_lines : "so_line_id"
    sales_orders ||--o{ dispatch_orders : "sales_order_id"
    sales_orders ||--o{ sales_order_lines : "sales_order_id"
```

Relaciones con otros dominios: `customer_return_lines` → items, lots; `customer_returns` → companies, locations, parties, users; `delivery_incidents` → companies, users; `delivery_routes` → companies, sites; `dispatch_lines` → items; `dispatch_orders` → companies, parties, users, warehouses; `sales_order_lines` → items, taxes; `sales_orders` → companies, currencies, parties, payment_terms, sites, users, warehouses; `shipment_events` → users.

## Operaciones

```mermaid
erDiagram
    boms {
        VARCHAR code
        BIGINT item_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    bom_lines {
        BIGINT bom_id FK
        BIGINT component_item_id FK
        BIGINT id PK
    }
    work_orders {
        VARCHAR number
        BIGINT site_id FK
        BIGINT item_id FK
        BIGINT bom_id FK
        BIGINT customer_id FK
        BIGINT production_location_id FK
        BIGINT output_location_id FK
        VARCHAR status
        BIGINT responsible_id FK
        BIGINT cost_center_id FK
        BIGINT created_by_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    work_order_materials {
        BIGINT work_order_id FK
        BIGINT item_id FK
        BIGINT id PK
    }
    work_order_time_logs {
        BIGINT work_order_id FK
        BIGINT user_id FK
        BIGINT id PK
    }
    work_order_incidents {
        BIGINT work_order_id FK
        BIGINT created_by_id FK
        BIGINT id PK
    }
    boms ||--o{ bom_lines : "bom_id"
    boms ||--o{ work_orders : "bom_id"
    work_orders ||--o{ work_order_incidents : "work_order_id"
    work_orders ||--o{ work_order_materials : "work_order_id"
    work_orders ||--o{ work_order_time_logs : "work_order_id"
```

Relaciones con otros dominios: `bom_lines` → items; `boms` → companies, items; `work_order_incidents` → users; `work_order_materials` → items; `work_order_time_logs` → users; `work_orders` → companies, cost_centers, items, locations, parties, sites, users.

## Contabilidad y finanzas

```mermaid
erDiagram
    accounts {
        VARCHAR code
        BIGINT parent_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    posting_accounts {
        BIGINT account_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    fiscal_periods {
        VARCHAR status
        BIGINT closed_by_id FK
        BIGINT reopened_by_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    journal_entries {
        VARCHAR number
        BIGINT period_id FK
        VARCHAR status
        BIGINT reversal_of_id FK
        BIGINT created_by_id FK
        BIGINT posted_by_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    journal_lines {
        BIGINT entry_id FK
        BIGINT account_id FK
        BIGINT party_id FK
        BIGINT cost_center_id FK
        VARCHAR currency FK
        BIGINT id PK
        BIGINT company_id FK
    }
    open_items {
        VARCHAR kind
        BIGINT party_id FK
        VARCHAR currency FK
        VARCHAR status
        BIGINT journal_entry_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    payments {
        VARCHAR number
        VARCHAR kind
        BIGINT party_id FK
        BIGINT bank_account_id FK
        VARCHAR currency FK
        VARCHAR status
        BIGINT journal_entry_id FK
        BIGINT created_by_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    payment_allocations {
        BIGINT payment_id FK
        BIGINT open_item_id FK
        BIGINT id PK
    }
    payment_withholdings {
        BIGINT payment_id FK
        BIGINT tax_id FK
        BIGINT id PK
    }
    bank_accounts {
        VARCHAR currency FK
        BIGINT gl_account_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    bank_statements {
        BIGINT bank_account_id FK
        BIGINT imported_by_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    bank_statement_lines {
        BIGINT statement_id FK
        VARCHAR status
        BIGINT matched_journal_line_id FK
        BIGINT matched_by_id FK
        BIGINT id PK
    }
    budget_lines {
        BIGINT cost_center_id FK
        BIGINT account_id FK
        BIGINT site_id FK
        BIGINT approved_by_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    strategic_goals {
        VARCHAR code
        BIGINT owner_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    accounts ||--o{ bank_accounts : "gl_account_id"
    accounts ||--o{ budget_lines : "account_id"
    accounts ||--o{ journal_lines : "account_id"
    accounts ||--o{ posting_accounts : "account_id"
    bank_accounts ||--o{ bank_statements : "bank_account_id"
    bank_accounts ||--o{ payments : "bank_account_id"
    bank_statements ||--o{ bank_statement_lines : "statement_id"
    fiscal_periods ||--o{ journal_entries : "period_id"
    journal_entries ||--o{ journal_lines : "entry_id"
    journal_entries ||--o{ open_items : "journal_entry_id"
    journal_entries ||--o{ payments : "journal_entry_id"
    journal_lines ||--o{ bank_statement_lines : "matched_journal_line_id"
    open_items ||--o{ payment_allocations : "open_item_id"
    payments ||--o{ payment_allocations : "payment_id"
    payments ||--o{ payment_withholdings : "payment_id"
```

Relaciones con otros dominios: `accounts` → companies; `bank_accounts` → companies, currencies; `bank_statement_lines` → users; `bank_statements` → companies, users; `budget_lines` → companies, cost_centers, sites, users; `fiscal_periods` → companies, users; `journal_entries` → companies, users; `journal_lines` → companies, cost_centers, currencies, parties; `open_items` → companies, currencies, parties; `payment_withholdings` → taxes; `payments` → companies, currencies, parties, users; `posting_accounts` → companies; `strategic_goals` → companies, users.

## Facturación electrónica

```mermaid
erDiagram
    numbering_ranges {
        VARCHAR doc_type
        BIGINT id PK
        BIGINT company_id FK
    }
    sales_invoices {
        VARCHAR doc_type
        BIGINT number
        BIGINT numbering_range_id FK
        BIGINT site_id FK
        BIGINT customer_id FK
        BIGINT sales_order_id FK
        BIGINT dispatch_id FK
        BIGINT reference_invoice_id FK
        VARCHAR currency FK
        VARCHAR status
        BIGINT journal_entry_id FK
        BIGINT created_by_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    sales_invoice_lines {
        BIGINT invoice_id FK
        BIGINT item_id FK
        BIGINT tax_id FK
        BIGINT so_line_id FK
        BIGINT dispatch_line_id FK
        BIGINT id PK
    }
    sales_invoice_taxes {
        BIGINT invoice_id FK
        BIGINT tax_id FK
        BIGINT id PK
    }
    einvoice_submissions {
        BIGINT invoice_id FK
        BIGINT document_attachment_id FK
        BIGINT id PK
    }
    numbering_ranges ||--o{ sales_invoices : "numbering_range_id"
    sales_invoices ||--o{ einvoice_submissions : "invoice_id"
    sales_invoices ||--o{ sales_invoice_lines : "invoice_id"
    sales_invoices ||--o{ sales_invoice_taxes : "invoice_id"
```

Relaciones con otros dominios: `einvoice_submissions` → attachments; `numbering_ranges` → companies; `sales_invoice_lines` → dispatch_lines, items, sales_order_lines, taxes; `sales_invoice_taxes` → taxes; `sales_invoices` → companies, currencies, dispatch_orders, journal_entries, parties, sales_orders, sites, users.

## Indicadores e importación

```mermaid
erDiagram
    kpi_targets {
        BIGINT site_id FK
        BIGINT owner_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    kpi_snapshots {
        VARCHAR status
        BIGINT id PK
        BIGINT company_id FK
    }
    alerts {
        VARCHAR status
        BIGINT acknowledged_by_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    import_jobs {
        VARCHAR status
        BIGINT opening_batch_id FK
        BIGINT uploaded_by_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    import_rows {
        BIGINT job_id FK
        VARCHAR status
        BIGINT id PK
    }
    opening_balance_batches {
        VARCHAR kind
        VARCHAR status
        BIGINT created_by_id FK
        BIGINT approved_by_id FK
        BIGINT journal_entry_id FK
        BIGINT id PK
        BIGINT company_id FK
    }
    import_jobs ||--o{ import_rows : "job_id"
    opening_balance_batches ||--o{ import_jobs : "opening_batch_id"
```

Relaciones con otros dominios: `alerts` → companies, users; `import_jobs` → companies, users; `kpi_snapshots` → companies; `kpi_targets` → companies, sites, users; `opening_balance_batches` → companies, journal_entries, users.
