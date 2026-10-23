"""Trazabilidad entre módulos: cadena documental de un documento hacia atrás y hacia adelante.

Compras:  solicitud → solicitud de cotización → orden → recepción → inspección → factura de proveedor → pago
Ventas:   cotización → pedido → despacho → devolución / factura → nota crédito o débito → recaudo
Cada documento enlaza además los comprobantes contables que generó (journal_entries.source_type/source_id).

El recorrido es en anchura sobre las relaciones reales de la base de datos, acotado en número de nodos. Los
documentos de módulos que el usuario no puede consultar se muestran solo con su tipo, sin datos ni enlace.
"""
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.deps import Principal
from app.core.errors import Forbidden, NotFound
from app.modules.accounting.models import JournalEntry, OpenItem, Payment, PaymentAllocation
from app.modules.einvoicing.models import SalesInvoice
from app.modules.logistics.models import CustomerReturn, DispatchOrder
from app.modules.masters.models import Party
from app.modules.purchasing.models import (
    GoodsReceipt,
    GoodsReceiptLine,
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequisition,
    RequestForQuotation,
    SupplierInvoice,
    SupplierInvoiceLine,
    SupplierQuote,
)
from app.modules.quality.models import Inspection
from app.modules.sales.models import SalesOrder, SalesQuote

MAX_NODES = 150

Key = tuple[str, int]


@dataclass(frozen=True)
class NodeType:
    model: type
    permission: str
    label: str
    flow: str  # purchasing | sales | accounting
    stage: int  # orden dentro del flujo
    route: str | None  # ruta del frontend; {id} se reemplaza


TYPES: dict[str, NodeType] = {
    "purchase_requisition": NodeType(PurchaseRequisition, "purchasing.requisition.read", "Solicitud de compra",
                                     "purchasing", 1, "/compras/solicitudes"),
    "rfq": NodeType(RequestForQuotation, "purchasing.rfq.read", "Solicitud de cotización", "purchasing", 2,
                    "/compras/solicitudes"),
    "purchase_order": NodeType(PurchaseOrder, "purchasing.order.read", "Orden de compra", "purchasing", 3,
                               "/compras/ordenes/{id}"),
    "goods_receipt": NodeType(GoodsReceipt, "purchasing.receipt.read", "Recepción", "purchasing", 4,
                              "/compras/recepciones"),
    "inspection": NodeType(Inspection, "quality.inspection.read", "Inspección de calidad", "purchasing", 5,
                           "/calidad/inspecciones"),
    "supplier_invoice": NodeType(SupplierInvoice, "purchasing.invoice.read", "Factura de proveedor", "purchasing", 6,
                                 "/compras/facturas"),
    "sales_quote": NodeType(SalesQuote, "sales.quote.read", "Cotización", "sales", 1, "/ventas/cotizaciones"),
    "sales_order": NodeType(SalesOrder, "sales.order.read", "Pedido de venta", "sales", 2, "/ventas/pedidos/{id}"),
    "dispatch": NodeType(DispatchOrder, "logistics.dispatch.read", "Despacho", "sales", 3,
                         "/logistica/despachos/{id}"),
    "customer_return": NodeType(CustomerReturn, "logistics.return.read", "Devolución de cliente", "sales", 4,
                                "/logistica/devoluciones"),
    "sales_invoice": NodeType(SalesInvoice, "einvoicing.invoice.read", "Factura electrónica", "sales", 5,
                              "/facturacion"),
    "payment": NodeType(Payment, "accounting.payments.read", "Pago / recaudo", "accounting", 7,
                        "/contabilidad/pagos"),
    "journal_entry": NodeType(JournalEntry, "accounting.journal.read", "Comprobante contable", "accounting", 8,
                              "/contabilidad/comprobantes"),
}

# source_type de journal_entries → tipo de nodo
JOURNAL_SOURCES = {"goods_receipt": "goods_receipt", "supplier_invoice": "supplier_invoice", "dispatch": "dispatch",
                   "customer_return": "customer_return", "sales_invoice": "sales_invoice", "payment": "payment",
                   "inspection": "inspection"}
NOTE_LABELS = {"credit_note": "Nota crédito", "debit_note": "Nota débito"}


def _ids(db: Session, stmt) -> list[int]:
    return [i for i in db.scalars(stmt).all() if i is not None]


def _journal(db: Session, source_type: str, source_id: int) -> list[Key]:
    return [("journal_entry", i) for i in _ids(db, select(JournalEntry.id).where(
        JournalEntry.source_type == source_type, JournalEntry.source_id == source_id))]


def _payments_for(db: Session, document_type: str, document_id: int) -> list[Key]:
    stmt = (select(PaymentAllocation.payment_id).join(OpenItem, OpenItem.id == PaymentAllocation.open_item_id)
            .where(OpenItem.document_type == document_type, OpenItem.document_id == document_id))
    return [("payment", i) for i in set(_ids(db, stmt))]


def _requisition(db, o: PurchaseRequisition) -> list[Key]:
    return ([("rfq", i) for i in _ids(db, select(RequestForQuotation.id).where(RequestForQuotation.requisition_id == o.id))]
            + [("purchase_order", i) for i in _ids(db, select(PurchaseOrder.id).where(PurchaseOrder.requisition_id == o.id))])


def _rfq(db, o: RequestForQuotation) -> list[Key]:
    quotes = select(SupplierQuote.id).where(SupplierQuote.rfq_id == o.id)
    return ([("purchase_requisition", o.requisition_id)]
            + [("purchase_order", i) for i in _ids(db, select(PurchaseOrder.id).where(PurchaseOrder.quote_id.in_(quotes)))])


def _purchase_order(db, o: PurchaseOrder) -> list[Key]:
    out: list[Key] = []
    if o.requisition_id:
        out.append(("purchase_requisition", o.requisition_id))
    if o.quote_id:
        rfq_id = db.scalar(select(SupplierQuote.rfq_id).where(SupplierQuote.id == o.quote_id))
        if rfq_id:
            out.append(("rfq", rfq_id))
    out += [("goods_receipt", i) for i in _ids(db, select(GoodsReceipt.id).where(GoodsReceipt.purchase_order_id == o.id))]
    po_lines = select(PurchaseOrderLine.id).where(PurchaseOrderLine.purchase_order_id == o.id)
    invoices = select(SupplierInvoice.id).where(or_(
        SupplierInvoice.purchase_order_id == o.id,
        SupplierInvoice.id.in_(select(SupplierInvoiceLine.invoice_id).where(SupplierInvoiceLine.po_line_id.in_(po_lines)))))
    out += [("supplier_invoice", i) for i in set(_ids(db, invoices))]
    return out


def _goods_receipt(db, o: GoodsReceipt) -> list[Key]:
    lines = select(GoodsReceiptLine.id).where(GoodsReceiptLine.receipt_id == o.id)
    invoices = select(SupplierInvoiceLine.invoice_id).where(SupplierInvoiceLine.receipt_line_id.in_(lines))
    inspections = select(Inspection.id).where(Inspection.source_type == "goods_receipt_line",
                                              Inspection.source_id.in_(lines))
    return ([("purchase_order", o.purchase_order_id)]
            + [("supplier_invoice", i) for i in set(_ids(db, invoices))]
            + [("inspection", i) for i in _ids(db, inspections)]
            + _journal(db, "goods_receipt", o.id))


def _inspection(db, o: Inspection) -> list[Key]:
    out: list[Key] = []
    if o.source_type == "goods_receipt_line":
        rid = db.scalar(select(GoodsReceiptLine.receipt_id).where(GoodsReceiptLine.id == o.source_id))
        if rid:
            out.append(("goods_receipt", rid))
    return out + _journal(db, "inspection", o.id)


def _supplier_invoice(db, o: SupplierInvoice) -> list[Key]:
    out: list[Key] = [("purchase_order", o.purchase_order_id)] if o.purchase_order_id else []
    receipts = select(GoodsReceiptLine.receipt_id).where(GoodsReceiptLine.id.in_(
        select(SupplierInvoiceLine.receipt_line_id).where(SupplierInvoiceLine.invoice_id == o.id)))
    out += [("goods_receipt", i) for i in set(_ids(db, receipts))]
    return out + _payments_for(db, "supplier_invoice", o.id) + _journal(db, "supplier_invoice", o.id)


def _sales_quote(db, o: SalesQuote) -> list[Key]:
    return [("sales_order", o.sales_order_id)] if o.sales_order_id else []


def _sales_order(db, o: SalesOrder) -> list[Key]:
    return ([("sales_quote", i) for i in _ids(db, select(SalesQuote.id).where(SalesQuote.sales_order_id == o.id))]
            + [("dispatch", i) for i in _ids(db, select(DispatchOrder.id).where(DispatchOrder.sales_order_id == o.id))]
            + [("sales_invoice", i) for i in _ids(db, select(SalesInvoice.id).where(SalesInvoice.sales_order_id == o.id))])


def _dispatch(db, o: DispatchOrder) -> list[Key]:
    return ([("sales_order", o.sales_order_id)]
            + [("sales_invoice", i) for i in _ids(db, select(SalesInvoice.id).where(SalesInvoice.dispatch_id == o.id))]
            + [("customer_return", i) for i in _ids(db, select(CustomerReturn.id).where(CustomerReturn.dispatch_id == o.id))]
            + _journal(db, "dispatch", o.id))


def _customer_return(db, o: CustomerReturn) -> list[Key]:
    return [("dispatch", o.dispatch_id)] + _journal(db, "customer_return", o.id)


def _sales_invoice(db, o: SalesInvoice) -> list[Key]:
    out: list[Key] = []
    if o.sales_order_id:
        out.append(("sales_order", o.sales_order_id))
    if o.dispatch_id:
        out.append(("dispatch", o.dispatch_id))
    if o.reference_invoice_id:
        out.append(("sales_invoice", o.reference_invoice_id))
    out += [("sales_invoice", i) for i in _ids(db, select(SalesInvoice.id).where(SalesInvoice.reference_invoice_id == o.id))]
    if o.journal_entry_id:
        out.append(("journal_entry", o.journal_entry_id))
    return out + _payments_for(db, o.doc_type, o.id) + _journal(db, "sales_invoice", o.id)


def _payment(db, o: Payment) -> list[Key]:
    docs = db.execute(select(OpenItem.document_type, OpenItem.document_id).join(
        PaymentAllocation, PaymentAllocation.open_item_id == OpenItem.id).where(PaymentAllocation.payment_id == o.id)).all()
    out: list[Key] = []
    for dtype, did in docs:
        if dtype == "supplier_invoice":
            out.append(("supplier_invoice", did))
        elif dtype in ("invoice", "credit_note", "debit_note"):
            out.append(("sales_invoice", did))
    if o.journal_entry_id:
        out.append(("journal_entry", o.journal_entry_id))
    return out + _journal(db, "payment", o.id)


def _journal_entry(db, o: JournalEntry) -> list[Key]:
    out: list[Key] = []
    if o.source_type in JOURNAL_SOURCES and o.source_id:
        out.append((JOURNAL_SOURCES[o.source_type], o.source_id))
    if o.reversal_of_id:
        out.append(("journal_entry", o.reversal_of_id))
    out += [("journal_entry", i) for i in _ids(db, select(JournalEntry.id).where(JournalEntry.reversal_of_id == o.id))]
    return out


NEIGHBORS: dict[str, Callable] = {
    "purchase_requisition": _requisition, "rfq": _rfq, "purchase_order": _purchase_order,
    "goods_receipt": _goods_receipt, "inspection": _inspection, "supplier_invoice": _supplier_invoice,
    "sales_quote": _sales_quote, "sales_order": _sales_order, "dispatch": _dispatch,
    "customer_return": _customer_return, "sales_invoice": _sales_invoice, "payment": _payment,
    "journal_entry": _journal_entry,
}


def _party_names(db: Session, ids: set[int]) -> dict[int, str]:
    if not ids:
        return {}
    return dict(db.execute(select(Party.id, Party.legal_name).where(Party.id.in_(ids))).all())


def _describe(t: str, o) -> dict:
    """Datos comunes del documento para la línea de tiempo."""
    number = getattr(o, "full_number", None) or getattr(o, "number", None) or f"#{o.id}"
    date_ = next((getattr(o, a) for a in ("entry_date", "payment_date", "issue_date", "invoice_date", "receipt_date",
                                          "return_date", "order_date", "quote_date", "due_date") if getattr(o, a, None)),
                 None) or (o.created_at.date() if getattr(o, "created_at", None) else None)
    amount = next((getattr(o, a) for a in ("total", "amount", "total_estimated") if getattr(o, a, None) is not None), None)
    party = next((getattr(o, a) for a in ("customer_id", "supplier_id", "party_id") if getattr(o, a, None)), None)
    label = TYPES[t].label
    if t == "sales_invoice":
        label = NOTE_LABELS.get(o.doc_type, label)
    elif t == "payment":
        label = "Recaudo de cliente" if o.kind == "receipt" else "Pago a proveedor"
    detail = None
    if t == "journal_entry":
        detail = o.description
    elif t == "sales_invoice":
        detail = f"DIAN/SENIAT: {o.edoc_status}"
    return {"number": str(number), "date": date_, "status": getattr(o, "status", None), "amount": amount,
            "currency": getattr(o, "currency", None), "party_id": party, "label": label, "detail": detail}


def trace(db: Session, p: Principal, doc_type: str, doc_id: int) -> dict:
    if doc_type not in TYPES:
        raise NotFound("Tipo de documento no soportado para trazabilidad")
    start = db.get(TYPES[doc_type].model, doc_id)
    if start is None or start.company_id != p.company_id:
        raise NotFound("Documento no encontrado")
    if not p.has(TYPES[doc_type].permission):
        raise Forbidden("Permiso insuficiente", details={"missing": [TYPES[doc_type].permission]})

    seen: dict[Key, object] = {(doc_type, doc_id): start}
    edges: set[tuple[Key, Key]] = set()
    queue: deque[Key] = deque([(doc_type, doc_id)])
    truncated = False
    while queue:
        key = queue.popleft()
        for nb in NEIGHBORS[key[0]](db, seen[key]):
            if nb[1] is None or nb == key:
                continue
            edges.add(tuple(sorted((key, nb))))
            if nb in seen:
                continue
            if len(seen) >= MAX_NODES:
                truncated = True
                continue
            obj = db.get(TYPES[nb[0]].model, nb[1])
            if obj is None or obj.company_id != p.company_id:
                continue
            seen[nb] = obj
            queue.append(nb)

    nodes = []
    for (t, i), o in seen.items():
        meta = TYPES[t]
        node = {"key": f"{t}:{i}", "type": t, "id": i, "flow": meta.flow, "stage": meta.stage,
                "is_start": (t, i) == (doc_type, doc_id), "allowed": p.has(meta.permission)}
        if node["allowed"]:
            node.update(_describe(t, o))
            node["route"] = meta.route.replace("{id}", str(i)) if meta.route else None
        else:
            node.update({"label": meta.label, "number": None, "route": None})
        nodes.append(node)
    names = _party_names(db, {n["party_id"] for n in nodes if n.get("party_id")})
    for n in nodes:
        if n.get("party_id"):
            n["party"] = names.get(n["party_id"])
    order = {"purchasing": 0, "sales": 1, "accounting": 2}
    nodes.sort(key=lambda n: (order[n["flow"]], n["stage"], str(n.get("date") or ""), n["id"]))
    return {"start": f"{doc_type}:{doc_id}", "truncated": truncated, "nodes": nodes,
            "edges": [{"from": f"{a[0]}:{a[1]}", "to": f"{b[0]}:{b[1]}"} for a, b in sorted(edges)]}


SEARCHABLE = ("purchase_requisition", "purchase_order", "goods_receipt", "supplier_invoice", "sales_quote",
              "sales_order", "dispatch", "customer_return", "sales_invoice", "payment", "journal_entry")


def search(db: Session, p: Principal, q: str, limit: int = 20) -> list[dict]:
    """Busca documentos por número (incluido el número del proveedor y el consecutivo fiscal)."""
    like = f"%{q.strip().upper()}%"
    out = []
    for t in SEARCHABLE:
        meta = TYPES[t]
        if not p.has(meta.permission):
            continue
        m = meta.model
        cols = [m.number] if t != "sales_invoice" else [m.full_number]
        if t == "supplier_invoice":
            cols.append(m.supplier_invoice_number)
        stmt = select(m).where(m.company_id == p.company_id, or_(*[func.upper(c).like(like) for c in cols])) \
            .order_by(m.id.desc()).limit(limit)
        for o in db.scalars(stmt):
            out.append({"type": t, "id": o.id, **_describe(t, o)})
    names = _party_names(db, {r["party_id"] for r in out if r.get("party_id")})
    for r in out:
        r["party"] = names.get(r.get("party_id"))
    return out[:limit * 2]
