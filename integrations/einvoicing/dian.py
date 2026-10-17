"""Colombia (DIAN): validaciones previas, cálculo del CUFE/CUDE y construcción del XML UBL 2.1.

- El CUFE se calcula con la fórmula del Anexo Técnico de Factura Electrónica de Venta (SHA-384 de la
  concatenación NumFac+FecFac+HorFac+ValFac+CodImp1+ValImp1+CodImp2+ValImp2+CodImp3+ValImp3+ValTot+
  NitOFE+NumAdq+ClTec+TipoAmbiente). Para notas (CUDE) se usa el PIN del software en lugar de la ClTec.
- El XML generado sigue la estructura UBL 2.1 pero NO incluye la firma XAdES-EPES ni todas las extensiones
  DIAN (sts:DianExtensions completas, QR, SoftwareSecurityCode). Eso lo aporta el proveedor tecnológico o
  una implementación de firma con el certificado digital de la empresa. Por eso este XML no es un documento
  fiscal válido por sí mismo.
"""
import hashlib
from decimal import Decimal
from xml.etree import ElementTree as ET

from integrations.einvoicing.base import EDocument

NS = {
    "": "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "ext": "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2",
}
ROOT_BY_TYPE = {"invoice": "Invoice", "credit_note": "CreditNote", "debit_note": "DebitNote"}
UOM_UNECE = {"UND": "94", "CAJ": "XBX", "PAQ": "XPK", "KG": "KGM", "G": "GRM", "L": "LTR", "ML": "MLT", "M": "MTR",
             "HR": "HUR"}
DIAN_ID_TYPES = {"NIT": "31", "CC": "13", "CE": "22", "PAS": "41", "EXT": "42"}


def _fmt(v: Decimal) -> str:
    return f"{Decimal(v):.2f}"


def compute_cufe(doc: EDocument, environment_code: str, key: str) -> str:
    """environment_code: '1' producción, '2' pruebas. key: ClTec (facturas) o PIN del software (notas)."""
    by_code = {"01": Decimal("0"), "04": Decimal("0"), "03": Decimal("0")}
    for t in doc.taxes:
        if t.code in by_code:
            by_code[t.code] += t.amount
    parts = [
        doc.full_number, doc.issue_date.isoformat(), doc.issue_time.strftime("%H:%M:%S") + "-05:00",
        _fmt(doc.subtotal), "01", _fmt(by_code["01"]), "04", _fmt(by_code["04"]), "03", _fmt(by_code["03"]),
        _fmt(doc.total), doc.issuer.tax_id, doc.customer.tax_id, key, environment_code,
    ]
    return hashlib.sha384("".join(parts).encode("utf-8")).hexdigest()


def validate(doc: EDocument) -> list[str]:
    errors = []
    if doc.issuer.id_type != "NIT" or not doc.issuer.tax_id.isdigit():
        errors.append("El emisor debe identificarse con NIT numérico")
    if doc.customer.id_type not in DIAN_ID_TYPES:
        errors.append(f"Tipo de documento del adquiriente no soportado: {doc.customer.id_type}")
    if not doc.customer.legal_name:
        errors.append("Falta la razón social del adquiriente")
    if doc.customer.id_type == "NIT" and not doc.customer.email:
        errors.append("El adquiriente persona jurídica requiere correo electrónico para la entrega")
    if not doc.authorization_number:
        errors.append("Falta la resolución de numeración")
    if doc.doc_type == "invoice":
        if doc.authorization_range and not (doc.authorization_range[0] <= doc.number <= doc.authorization_range[1]):
            errors.append("El número está fuera del rango autorizado")
        if doc.authorization_valid and not (doc.authorization_valid[0] <= doc.issue_date <= doc.authorization_valid[1]):
            errors.append("La resolución de numeración no está vigente para la fecha de expedición")
        if not doc.technical_key:
            errors.append("Falta la clave técnica de la resolución")
    else:
        if not doc.reference_uid or not doc.reference_number:
            errors.append("Las notas deben referenciar la factura origen (número y CUFE)")
        if not doc.correction_code:
            errors.append("Las notas requieren el código de concepto de corrección")
    if not doc.lines:
        errors.append("El documento no tiene líneas")
    line_sum = sum((ln.line_subtotal for ln in doc.lines), Decimal("0"))
    if line_sum != doc.subtotal:
        errors.append(f"La suma de líneas ({line_sum}) no coincide con el subtotal ({doc.subtotal})")
    tax_sum = sum((t.amount for t in doc.taxes), Decimal("0"))
    if tax_sum != doc.tax_total or doc.subtotal + doc.tax_total != doc.total:
        errors.append("Los totales del documento no son consistentes")
    for ln in doc.lines:
        if ln.uom_code not in UOM_UNECE:
            errors.append(f"Línea {ln.line_no}: unidad {ln.uom_code} sin código UN/ECE")
    return errors


def _party(parent: ET.Element, tag: str, p) -> None:
    party_wrap = ET.SubElement(parent, f"cac:{tag}")
    ET.SubElement(party_wrap, "cbc:AdditionalAccountID").text = "1" if p.id_type == "NIT" else "2"
    party = ET.SubElement(party_wrap, "cac:Party")
    tax_scheme = ET.SubElement(party, "cac:PartyTaxScheme")
    ET.SubElement(tax_scheme, "cbc:RegistrationName").text = p.legal_name
    cid = ET.SubElement(tax_scheme, "cbc:CompanyID", schemeAgencyID="195", schemeName=DIAN_ID_TYPES.get(p.id_type, "13"))
    if p.check_digit:
        cid.set("schemeID", p.check_digit)
    cid.text = p.tax_id
    if p.address or p.city:
        addr = ET.SubElement(ET.SubElement(tax_scheme, "cac:RegistrationAddress"), "cac:AddressLine")
        ET.SubElement(addr, "cbc:Line").text = ", ".join(x for x in (p.address, p.city) if x)
    if p.email:
        ET.SubElement(ET.SubElement(party, "cac:Contact"), "cbc:ElectronicMail").text = p.email


def _tax_total(parent: ET.Element, t, currency: str) -> None:
    tt = ET.SubElement(parent, "cac:TaxTotal")
    ET.SubElement(tt, "cbc:TaxAmount", currencyID=currency).text = _fmt(t.amount)
    sub = ET.SubElement(tt, "cac:TaxSubtotal")
    ET.SubElement(sub, "cbc:TaxableAmount", currencyID=currency).text = _fmt(t.base)
    ET.SubElement(sub, "cbc:TaxAmount", currencyID=currency).text = _fmt(t.amount)
    cat = ET.SubElement(sub, "cac:TaxCategory")
    ET.SubElement(cat, "cbc:Percent").text = f"{Decimal(t.rate):.2f}"
    scheme = ET.SubElement(cat, "cac:TaxScheme")
    ET.SubElement(scheme, "cbc:ID").text = t.code
    ET.SubElement(scheme, "cbc:Name").text = t.name


def build_ubl(doc: EDocument, uid: str, environment_code: str) -> bytes:
    root_name = ROOT_BY_TYPE[doc.doc_type]
    root = ET.Element(root_name, {
        "xmlns": NS[""].replace("Invoice-2", f"{root_name}-2"), "xmlns:cac": NS["cac"], "xmlns:cbc": NS["cbc"],
        "xmlns:ext": NS["ext"],
    })
    ET.SubElement(ET.SubElement(root, "ext:UBLExtensions"), "ext:UBLExtension")
    ET.SubElement(root, "cbc:UBLVersionID").text = "UBL 2.1"
    ET.SubElement(root, "cbc:CustomizationID").text = "10"
    ET.SubElement(root, "cbc:ProfileID").text = "DIAN 2.1"
    ET.SubElement(root, "cbc:ProfileExecutionID").text = environment_code
    ET.SubElement(root, "cbc:ID").text = doc.full_number
    ET.SubElement(root, "cbc:UUID", schemeID=environment_code,
                  schemeName="CUFE-SHA384" if doc.doc_type == "invoice" else "CUDE-SHA384").text = uid
    ET.SubElement(root, "cbc:IssueDate").text = doc.issue_date.isoformat()
    ET.SubElement(root, "cbc:IssueTime").text = doc.issue_time.strftime("%H:%M:%S") + "-05:00"
    if doc.doc_type == "invoice":
        ET.SubElement(root, "cbc:DueDate").text = doc.due_date.isoformat()
        ET.SubElement(root, "cbc:InvoiceTypeCode").text = "01"
    if doc.notes:
        ET.SubElement(root, "cbc:Note").text = doc.notes
    ET.SubElement(root, "cbc:DocumentCurrencyCode").text = doc.currency
    ET.SubElement(root, "cbc:LineCountNumeric").text = str(len(doc.lines))
    if doc.doc_type != "invoice":
        disc = ET.SubElement(root, "cac:DiscrepancyResponse")
        ET.SubElement(disc, "cbc:ReferenceID").text = doc.reference_number
        ET.SubElement(disc, "cbc:ResponseCode").text = doc.correction_code
        ET.SubElement(disc, "cbc:Description").text = doc.correction_reason or ""
        ref = ET.SubElement(ET.SubElement(root, "cac:BillingReference"), "cac:InvoiceDocumentReference")
        ET.SubElement(ref, "cbc:ID").text = doc.reference_number
        ET.SubElement(ref, "cbc:UUID", schemeName="CUFE-SHA384").text = doc.reference_uid
        if doc.reference_date:
            ET.SubElement(ref, "cbc:IssueDate").text = doc.reference_date.isoformat()
    _party(root, "AccountingSupplierParty", doc.issuer)
    _party(root, "AccountingCustomerParty", doc.customer)
    pm = ET.SubElement(root, "cac:PaymentMeans")
    ET.SubElement(pm, "cbc:ID").text = "1" if doc.payment_form == "cash" else "2"
    ET.SubElement(pm, "cbc:PaymentDueDate").text = doc.due_date.isoformat()
    if doc.currency != "COP":
        rate = ET.SubElement(root, "cac:PaymentExchangeRate")
        ET.SubElement(rate, "cbc:SourceCurrencyCode").text = doc.currency
        ET.SubElement(rate, "cbc:TargetCurrencyCode").text = "COP"
        ET.SubElement(rate, "cbc:CalculationRate").text = f"{doc.exchange_rate}"
    for t in doc.taxes:
        _tax_total(root, t, doc.currency)
    lmt = ET.SubElement(root, "cac:LegalMonetaryTotal" if doc.doc_type != "debit_note" else "cac:RequestedMonetaryTotal")
    ET.SubElement(lmt, "cbc:LineExtensionAmount", currencyID=doc.currency).text = _fmt(doc.subtotal)
    ET.SubElement(lmt, "cbc:TaxExclusiveAmount", currencyID=doc.currency).text = _fmt(doc.subtotal)
    ET.SubElement(lmt, "cbc:TaxInclusiveAmount", currencyID=doc.currency).text = _fmt(doc.total)
    ET.SubElement(lmt, "cbc:PayableAmount", currencyID=doc.currency).text = _fmt(doc.total)
    line_tag = {"invoice": "InvoiceLine", "credit_note": "CreditNoteLine", "debit_note": "DebitNoteLine"}[doc.doc_type]
    qty_tag = {"invoice": "InvoicedQuantity", "credit_note": "CreditedQuantity", "debit_note": "DebitedQuantity"}
    for ln in doc.lines:
        el = ET.SubElement(root, f"cac:{line_tag}")
        ET.SubElement(el, "cbc:ID").text = str(ln.line_no)
        ET.SubElement(el, f"cbc:{qty_tag[doc.doc_type]}", unitCode=UOM_UNECE.get(ln.uom_code, "94")).text = \
            f"{Decimal(ln.quantity):.6f}"
        ET.SubElement(el, "cbc:LineExtensionAmount", currencyID=doc.currency).text = _fmt(ln.line_subtotal)
        if ln.discount_amount:
            ac = ET.SubElement(el, "cac:AllowanceCharge")
            ET.SubElement(ac, "cbc:ChargeIndicator").text = "false"
            ET.SubElement(ac, "cbc:Amount", currencyID=doc.currency).text = _fmt(ln.discount_amount)
        if ln.tax:
            _tax_total(el, ln.tax, doc.currency)
        item = ET.SubElement(el, "cac:Item")
        ET.SubElement(item, "cbc:Description").text = ln.description
        ET.SubElement(ET.SubElement(item, "cac:SellersItemIdentification"), "cbc:ID").text = ln.sku
        price = ET.SubElement(el, "cac:Price")
        ET.SubElement(price, "cbc:PriceAmount", currencyID=doc.currency).text = f"{Decimal(ln.unit_price):.2f}"
        ET.SubElement(price, "cbc:BaseQuantity", unitCode=UOM_UNECE.get(ln.uom_code, "94")).text = "1.000000"
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
