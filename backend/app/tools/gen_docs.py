"""Genera documentación a partir del código fuente (siempre sincronizada con el modelo real):

  docs/diccionario-datos.md   tablas, columnas, tipos, nulabilidad, claves, restricciones, índices
  docs/modelo-er.md           diagrama entidad-relación (Mermaid) por dominio
  docs/openapi.json           especificación OpenAPI de la API

Uso: python -m app.tools.gen_docs  (desde /backend, con DATABASE_URL definido aunque no se conecta)
"""
import json
from collections import defaultdict
from pathlib import Path

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.orm import configure_mappers

import app.models  # noqa: F401  (registra todas las tablas)
from app.core.db import Base

DOCS = Path(__file__).resolve().parents[3] / "docs"

DOMAINS = {
    "Identidad y auditoría": ["users", "roles", "permissions", "role_permissions", "user_company_roles", "refresh_tokens",
                              "login_attempts", "audit_log", "approval_limits"],
    "Organización y configuración": ["companies", "company_modules", "sites", "business_units", "cost_centers",
                                     "currencies", "exchange_rates", "document_sequences", "attachments",
                                     "integration_events", "idempotency_records"],
    "Datos maestros": ["parties", "party_withholdings", "items", "item_categories", "uoms", "uom_conversions", "taxes",
                       "payment_terms"],
    "Compras": ["purchase_requisitions", "purchase_requisition_lines", "rfqs", "supplier_quotes", "supplier_quote_lines",
                "purchase_orders", "purchase_order_lines", "goods_receipts", "goods_receipt_lines", "supplier_invoices",
                "supplier_invoice_lines", "supplier_invoice_taxes"],
    "Inventario": ["warehouses", "locations", "lots", "stock_balances", "item_costs", "stock_moves",
                   "stock_reservations", "inventory_documents", "inventory_document_lines", "physical_counts",
                   "physical_count_lines"],
    "Calidad": ["inspection_plans", "inspection_characteristics", "inspections", "inspection_results",
                "nonconformities", "capa_actions"],
    "Ventas y logística": ["sales_orders", "sales_order_lines", "delivery_routes", "dispatch_orders", "dispatch_lines",
                           "shipment_events", "delivery_incidents", "customer_returns", "customer_return_lines"],
    "Operaciones": ["boms", "bom_lines", "work_orders", "work_order_materials", "work_order_time_logs",
                    "work_order_incidents"],
    "Contabilidad y finanzas": ["accounts", "posting_accounts", "fiscal_periods", "journal_entries", "journal_lines",
                                "open_items", "payments", "payment_allocations", "payment_withholdings", "bank_accounts",
                                "bank_statements", "bank_statement_lines", "budget_lines", "strategic_goals"],
    "Facturación electrónica": ["numbering_ranges", "sales_invoices", "sales_invoice_lines", "sales_invoice_taxes",
                                "einvoice_submissions"],
    "Indicadores e importación": ["kpi_targets", "kpi_snapshots", "alerts", "import_jobs", "import_rows",
                                  "opening_balance_batches"],
}


def _model_doc(table_name: str) -> str:
    for mapper in Base.registry.mappers:
        if mapper.local_table.name == table_name:
            return " ".join((mapper.class_.__doc__ or "").split())
    return ""


def data_dictionary() -> str:
    md = ["# Diccionario de datos", "",
          "Generado automáticamente desde los modelos SQLAlchemy (`python -m app.tools.gen_docs`). "
          "Convenciones: `id` BIGINT identidad; importes NUMERIC(18,2); cantidades NUMERIC(18,6); "
          "tasas NUMERIC(20,8); fechas-hora con zona horaria (UTC).", ""]
    tables = Base.metadata.tables
    listed = {t for ts in DOMAINS.values() for t in ts}
    extra = sorted(set(tables) - listed)
    for domain, names in list(DOMAINS.items()) + ([("Otras", extra)] if extra else []):
        md += [f"## {domain}", ""]
        for name in names:
            t = tables[name]
            md += [f"### `{name}`", ""]
            doc = _model_doc(name)
            if doc:
                md += [doc, ""]
            md += ["| Columna | Tipo | Nulo | Por defecto | Referencia |", "|---|---|---|---|---|"]
            for c in t.columns:
                default = ""
                if c.server_default is not None:
                    default = str(getattr(c.server_default, "arg", "")).replace("|", "\\|")
                elif c.default is not None and not callable(getattr(c.default, "arg", None)):
                    default = str(c.default.arg)
                fk = ", ".join(f"{f.column.table.name}.{f.column.name}" for f in c.foreign_keys)
                pk = " (PK)" if c.primary_key else ""
                md.append(f"| `{c.name}`{pk} | {c.type} | {'sí' if c.nullable else 'no'} | {default} | {fk} |")
            checks = [c for c in t.constraints if isinstance(c, CheckConstraint)]
            uniques = [c for c in t.constraints if isinstance(c, UniqueConstraint)]
            if uniques or checks or t.indexes:
                md.append("")
            for u in uniques:
                md.append(f"- Única: ({', '.join(c.name for c in u.columns)})")
            for ix in sorted(t.indexes, key=lambda i: i.name or ""):
                cols = ", ".join(str(e) for e in ix.expressions)
                md.append(f"- Índice{' único' if ix.unique else ''} `{ix.name}`: ({cols})")
            for ck in checks:
                md.append(f"- Verificación `{ck.name}`: `{ck.sqltext}`")
            md.append("")
    md += ["## Reglas en base de datos (migración 0002)", "",
           "- `trg_journal_lines_balanced`: trigger diferido que rechaza al confirmar cualquier asiento contabilizado "
           "desbalanceado o con menos de dos líneas.",
           "- `trg_journal_lines_immutable` / `trg_journal_entries_guard`: asientos contabilizados inmutables "
           "(solo se permite `posted → reversed`); prohíbe contabilizar en periodos cerrados.",
           "- `trg_stock_moves_append_only`, `trg_audit_log_append_only`: tablas de solo inserción.", ""]
    return "\n".join(md)


def er_diagram() -> str:
    md = ["# Modelo entidad-relación", "",
          "Diagramas Mermaid generados desde los modelos. Se muestran claves primarias, foráneas y relaciones por dominio "
          "(las relaciones hacia tablas de otros dominios se listan al final de cada diagrama).", ""]
    tables = Base.metadata.tables
    for domain, names in DOMAINS.items():
        md += [f"## {domain}", "", "```mermaid", "erDiagram"]
        rels = set()
        for name in names:
            t = tables[name]
            md.append(f"    {name} {{")
            for c in t.columns:
                if c.primary_key or c.foreign_keys or c.name in ("number", "code", "status", "sku", "doc_type", "kind"):
                    key = "PK" if c.primary_key else ("FK" if c.foreign_keys else "")
                    typ = str(c.type).split("(")[0].replace(" ", "_")
                    md.append(f"        {typ} {c.name} {key}".rstrip())
            md.append("    }")
            for c in t.columns:
                for f in c.foreign_keys:
                    target = f.column.table.name
                    if target in names and target != name:
                        rels.add(f"    {target} ||--o{{ {name} : \"{c.name}\"")
        md += sorted(rels)
        md += ["```", ""]
        external = defaultdict(set)
        for name in names:
            for c in tables[name].columns:
                for f in c.foreign_keys:
                    if f.column.table.name not in names:
                        external[name].add(f.column.table.name)
        if external:
            md.append("Relaciones con otros dominios: " + "; ".join(
                f"`{k}` → {', '.join(sorted(v))}" for k, v in sorted(external.items())) + ".")
            md.append("")
    return "\n".join(md)


def main() -> None:
    configure_mappers()
    DOCS.mkdir(exist_ok=True)
    (DOCS / "diccionario-datos.md").write_text(data_dictionary(), encoding="utf-8")
    (DOCS / "modelo-er.md").write_text(er_diagram(), encoding="utf-8")
    from app.main import app

    (DOCS / "openapi.json").write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Documentación generada en {DOCS}: {len(Base.metadata.tables)} tablas, "
          f"{len(app.openapi()['paths'])} rutas")


if __name__ == "__main__":
    main()
