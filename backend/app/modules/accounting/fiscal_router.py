"""Libros y reportes fiscales: consulta en pantalla, Excel, PDF y TXT para el SENIAT."""
from datetime import date

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.audit import log_action
from app.core.db import get_db
from app.core.deps import Principal, require, require_module
from app.modules.accounting import fiscal

router = APIRouter(prefix="/fiscal", tags=["Libros y reportes fiscales"],
                   dependencies=[Depends(require_module("accounting"))])

READ, EXPORT = "accounting.tax_reports.read", "accounting.tax_reports.export"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _file(db: Session, data: bytes, media: str, filename: str, entity: str, detail: str) -> Response:
    log_action(db, "export", entity, None, detail)
    db.commit()
    return Response(data, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _period(start: date, end: date) -> str:
    return f"Del {start:%d/%m/%Y} al {end:%d/%m/%Y}"


# ---------------------------------------------------------------- Venezuela
@router.get("/ve/sales-book")
def ve_sales_book(start: date, end: date, p: Principal = Depends(require(READ)), db: Session = Depends(get_db)):
    """Libro de ventas de IVA: facturas, notas y comprobantes de retención recibidos de clientes."""
    return fiscal.out(fiscal.ve_sales_book(db, p.company, start, end))


@router.get("/ve/sales-book.xlsx")
def ve_sales_book_xlsx(start: date, end: date, p: Principal = Depends(require(EXPORT)), db: Session = Depends(get_db)):
    b = fiscal.ve_sales_book(db, p.company, start, end)
    data = fiscal.xlsx("Libro de ventas", b["company"], f"RIF {b['rif']}", f"{_period(start, end)} · {b['currency']}",
                       [(None, fiscal.VE_SALES_COLUMNS, b["rows"], b["totals"])])
    return _file(db, data, XLSX, f"libro_ventas_{start:%Y%m%d}_{end:%Y%m%d}.xlsx", "sales_book",
                 f"Libro de ventas {start}..{end}")


@router.get("/ve/purchase-book")
def ve_purchase_book(start: date, end: date, p: Principal = Depends(require(READ)), db: Session = Depends(get_db)):
    """Libro de compras de IVA con el IVA retenido a cada proveedor y su comprobante."""
    return fiscal.out(fiscal.ve_purchase_book(db, p.company, start, end))


@router.get("/ve/purchase-book.xlsx")
def ve_purchase_book_xlsx(start: date, end: date, p: Principal = Depends(require(EXPORT)),
                          db: Session = Depends(get_db)):
    b = fiscal.ve_purchase_book(db, p.company, start, end)
    data = fiscal.xlsx("Libro de compras", b["company"], f"RIF {b['rif']}", f"{_period(start, end)} · {b['currency']}",
                       [(None, fiscal.VE_PURCHASE_COLUMNS, b["rows"], b["totals"])])
    return _file(db, data, XLSX, f"libro_compras_{start:%Y%m%d}_{end:%Y%m%d}.xlsx", "purchase_book",
                 f"Libro de compras {start}..{end}")


@router.get("/ve/vat-withholdings")
def ve_vat_withholdings(start: date, end: date, p: Principal = Depends(require(READ)), db: Session = Depends(get_db)):
    """Comprobantes de retención de IVA emitidos a proveedores en el periodo."""
    return fiscal.out(fiscal.ve_vat_certificates(db, p.company, start, end))


@router.get("/ve/vat-withholdings.txt")
def ve_vat_withholdings_txt(year: int = Query(ge=2000, le=2100), month: int = Query(ge=1, le=12),
                            half: int = Query(default=0, ge=0, le=2), p: Principal = Depends(require(EXPORT)),
                            db: Session = Depends(get_db)):
    """TXT de retenciones de IVA para el portal del SENIAT (half: 1 primera quincena, 2 segunda, 0 mes)."""
    name, text, warnings = fiscal.ve_vat_txt(db, p.company, year, month, half)
    headers = {"Content-Disposition": f'attachment; filename="{name}"'}
    if warnings:
        headers["X-Fiscal-Warnings"] = str(len(warnings))
    log_action(db, "export", "vat_withholding_txt", None, f"TXT retenciones IVA {year}-{month:02d} q{half}")
    db.commit()
    return Response(text.encode("utf-8"), media_type="text/plain; charset=utf-8", headers=headers)


@router.get("/ve/vat-withholdings/{number}/pdf")
def ve_vat_withholding_pdf(number: str, p: Principal = Depends(require(READ)), db: Session = Depends(get_db)):
    filename, data = fiscal.ve_vat_certificate_pdf(db, p.company, number)
    log_action(db, "export", "vat_withholding_certificate", None, f"Comprobante de retención de IVA {number}")
    db.commit()
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{filename}"'})


# ---------------------------------------------------------------- Colombia
@router.get("/co/vat-auxiliary")
def co_vat_auxiliary(start: date, end: date, p: Principal = Depends(require(READ)), db: Session = Depends(get_db)):
    """Auxiliar de IVA: generado, descontable y retenciones de IVA que nos practicaron."""
    return fiscal.out(fiscal.co_vat_auxiliary(db, p.company, start, end))


@router.get("/co/vat-auxiliary.xlsx")
def co_vat_auxiliary_xlsx(start: date, end: date, p: Principal = Depends(require(EXPORT)),
                          db: Session = Depends(get_db)):
    a = fiscal.co_vat_auxiliary(db, p.company, start, end)
    s = a["summary"]
    summary_rows = [{"concept": "IVA generado", "value": s["generated"]},
                    {"concept": "IVA descontable", "value": s["deductible"]},
                    {"concept": "Saldo (generado − descontable)", "value": s["balance"]},
                    {"concept": "Retenciones de IVA que nos practicaron", "value": s["withheld_from_us"]},
                    {"concept": "Saldo a pagar estimado", "value": s["payable"]}]
    w_cols = [("date", "Fecha"), ("document", "Documento"), ("number", "Número"), ("nit", "NIT"), ("name", "Tercero"),
              ("certificate", "Certificado"), ("tax", "IVA retenido")]
    data = fiscal.xlsx("Auxiliar de IVA", a["company"], f"NIT {a['nit']}", f"{_period(start, end)} · {a['currency']}", [
        ("Resumen", [("concept", "Concepto"), ("value", "Valor")], summary_rows, None),
        ("IVA generado", fiscal.CO_AUX_COLUMNS, a["generated"]["rows"], {"base": sum_(a["generated"]["rows"], "base"),
                                                                         "tax": a["generated"]["total"]}),
        ("IVA descontable", fiscal.CO_AUX_COLUMNS, a["deductible"]["rows"],
         {"base": sum_(a["deductible"]["rows"], "base"), "tax": a["deductible"]["total"]}),
        ("Retenciones de IVA que nos practicaron", w_cols, a["withheld_from_us"]["rows"],
         {"tax": a["withheld_from_us"]["total"]}),
    ])
    return _file(db, data, XLSX, f"auxiliar_iva_{start:%Y%m%d}_{end:%Y%m%d}.xlsx", "vat_auxiliary",
                 f"Auxiliar de IVA {start}..{end}")


def sum_(rows: list[dict], key: str):
    return sum((r[key] for r in rows), fiscal.ZERO)


@router.get("/co/withholding-certificates")
def co_withholding_certificates(start: date, end: date, kind: str = Query(pattern="^(income|vat|ica)$"),
                                p: Principal = Depends(require(READ)), db: Session = Depends(get_db)):
    """Retenciones practicadas por tercero y concepto: base de los certificados del periodo."""
    return fiscal.out(fiscal.co_withholdings(db, p.company, start, end, kind))


@router.get("/co/withholding-certificates/{party_id}/pdf")
def co_withholding_certificate_pdf(party_id: int, start: date, end: date,
                                   kind: str = Query(pattern="^(income|vat|ica)$"),
                                   p: Principal = Depends(require(READ)), db: Session = Depends(get_db)):
    filename, data = fiscal.co_certificate_pdf(db, p.company, party_id, start, end, kind)
    log_action(db, "export", "withholding_certificate", party_id, f"{fiscal.CERT_TITLES[kind]} {start}..{end}")
    db.commit()
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{filename}"'})
