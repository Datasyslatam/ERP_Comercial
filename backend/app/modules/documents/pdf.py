"""Representación gráfica en PDF de los documentos comerciales (cotización, pedido, orden de compra y factura).

Se genera al vuelo desde los datos vigentes del documento; no se almacena. Usa las fuentes base de PDF
(Latin-1), suficientes para el español; los caracteres fuera de ese juego se sustituyen.
"""
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from fpdf import FPDF

NAVY = (10, 25, 47)
COBALT = (0, 82, 204)
MUTED = (91, 107, 130)
BORDER = (220, 227, 236)
ZEBRA = (247, 249, 252)

_REPLACE = {"—": "-", "–": "-", "“": '"', "”": '"', "‘": "'", "’": "'", "→": "->", "•": "-", "…": "...", "€": "EUR"}


def latin(text) -> str:
    s = "" if text is None else str(text)
    for a, b in _REPLACE.items():
        s = s.replace(a, b)
    return s.encode("latin-1", "replace").decode("latin-1")


def money(v, decimals: int = 2) -> str:
    """Formato local: 1.234.567,89"""
    if v is None or v == "":
        return "-"
    q = f"{Decimal(v):,.{decimals}f}"
    return q.replace(",", "_").replace(".", ",").replace("_", ".")


def qty(v) -> str:
    d = Decimal(v).normalize()
    return money(d, max(0, -d.as_tuple().exponent)) if d != d.to_integral() else money(d, 0)


def fdate(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, datetime):
        return v.strftime("%d/%m/%Y %H:%M")
    if isinstance(v, date):
        return v.strftime("%d/%m/%Y")
    return str(v)


@dataclass
class Line:
    code: str
    description: str
    quantity: Decimal
    unit_price: Decimal
    subtotal: Decimal
    uom: str = ""
    discount_pct: Decimal = Decimal("0")


@dataclass
class DocData:
    title: str
    number: str
    company: dict
    party_label: str
    party: dict
    fields: list[tuple[str, str]]
    lines: list[Line]
    totals: list[tuple[str, str, bool]]
    currency: str
    notes: str | None = None
    fiscal: list[tuple[str, str]] = field(default_factory=list)
    notice: str | None = None  # p. ej. "Documento de PRUEBAS: sin validez fiscal"
    terms: str | None = None


class _Pdf(FPDF):
    def __init__(self, data: DocData):
        super().__init__(orientation="P", unit="mm", format="Letter")
        self.data = data
        self.set_auto_page_break(auto=True, margin=18)
        self.set_margins(14, 14, 14)
        self.alias_nb_pages()
        self.set_title(latin(f"{data.title} {data.number}"))
        self.set_author(latin(data.company.get("name")))
        self.set_creator("DATASYS ERP")

    def header(self):
        d, c = self.data, self.data.company
        self.set_fill_color(*NAVY)
        self.rect(0, 0, self.w, 4, "F")
        self.set_xy(14, 9)
        self.set_text_color(*NAVY)
        # El nombre se ajusta en varias líneas para no invadir el título del documento (columna derecha).
        self.set_font("helvetica", "B", 12)
        self.multi_cell(100, 5.5, latin(c.get("name")), align="L", new_x="LEFT", new_y="NEXT")
        self.set_font("helvetica", "", 8.5)
        self.set_text_color(*MUTED)
        for row in (c.get("tax_id"), c.get("address"), c.get("contact")):
            if row:
                self.multi_cell(100, 4.2, latin(row), new_x="LEFT", new_y="NEXT")
        left_bottom = self.get_y()
        self.set_xy(self.w - 14 - 75, 9)
        self.set_text_color(*COBALT)
        self.set_font("helvetica", "B", 12)
        self.cell(75, 6, latin(d.title.upper()), align="R", new_x="LEFT", new_y="NEXT")
        self.set_text_color(*NAVY)
        self.set_font("helvetica", "B", 11)
        self.cell(75, 6, latin(d.number), align="R", new_x="LEFT", new_y="NEXT")
        self.set_y(max(self.get_y(), left_bottom, 28) + 2)
        self.set_draw_color(*BORDER)
        self.line(14, self.get_y(), self.w - 14, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-13)
        self.set_font("helvetica", "", 7.5)
        self.set_text_color(*MUTED)
        self.cell(0, 4, latin(f"Generado por DATASYS ERP el {fdate(datetime.now())}"), align="L")
        self.set_x(14)
        self.cell(0, 4, latin(f"Página {self.page_no()}/{{nb}}"), align="R")


def _label_value(pdf: _Pdf, x: float, w: float, label: str, value: str) -> None:
    pdf.set_x(x)
    pdf.set_font("helvetica", "B", 7.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(w, 3.8, latin(label.upper()), new_x="LEFT", new_y="NEXT")
    pdf.set_x(x)
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(*NAVY)
    pdf.multi_cell(w, 4.4, latin(value or "-"), new_x="LEFT", new_y="NEXT")


def render(data: DocData) -> bytes:
    pdf = _Pdf(data)
    pdf.add_page()

    if data.notice:
        pdf.set_fill_color(253, 241, 220)
        pdf.set_text_color(154, 88, 0)
        pdf.set_font("helvetica", "B", 9)
        pdf.multi_cell(0, 6, latin(data.notice), fill=True, align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(2)

    # Tercero (izquierda) y datos del documento (derecha)
    top = pdf.get_y()
    p = data.party
    _label_value(pdf, 14, 105, data.party_label, p.get("name"))
    for label, key in (("Identificación", "tax_id"), ("Dirección", "address"), ("Contacto", "contact")):
        if p.get(key):
            _label_value(pdf, 14, 105, label, p[key])
    left_end = pdf.get_y()
    y = top
    for i in range(0, len(data.fields), 2):
        ends = []
        for j, (label, value) in enumerate(data.fields[i:i + 2]):
            pdf.set_y(y)
            _label_value(pdf, 125 + j * 38, 36, label, value)
            ends.append(pdf.get_y())
        y = max(ends) + 1
    pdf.set_y(max(left_end, y) + 4)

    # Líneas
    show_disc = any(ln.discount_pct for ln in data.lines)
    cols = [("Código", 24, "L"), ("Descripción", 72 if show_disc else 86, "L"), ("Cant.", 16, "R"),
            ("Und", 12, "C"), ("Precio unit.", 24, "R")]
    if show_disc:
        cols.append(("Desc. %", 14, "R"))
    cols.append(("Subtotal", 26, "R"))

    def head():
        pdf.set_fill_color(*NAVY)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("helvetica", "B", 8)
        for title, w, align in cols:
            pdf.cell(w, 6.5, latin(title), border=0, align=align, fill=True)
        pdf.ln()

    head()
    pdf.set_font("helvetica", "", 8.5)
    for i, ln in enumerate(data.lines):
        values = [ln.code, ln.description, qty(ln.quantity), ln.uom, money(ln.unit_price)]
        if show_disc:
            values.append(qty(ln.discount_pct))
        values.append(money(ln.subtotal))
        desc_w = cols[1][1]
        lines_needed = max(1, len(pdf.multi_cell(desc_w, 4.6, latin(ln.description), dry_run=True, output="LINES")))
        h = 4.6 * lines_needed + 1.4
        if pdf.get_y() + h > pdf.h - 22:
            pdf.add_page()
            head()
            pdf.set_font("helvetica", "", 8.5)
        y = pdf.get_y()
        pdf.set_fill_color(*(ZEBRA if i % 2 else (255, 255, 255)))
        pdf.rect(14, y, sum(w for _, w, _ in cols), h, "F")
        pdf.set_text_color(*NAVY)
        x = 14
        for k, ((_, w, align), v) in enumerate(zip(cols, values, strict=True)):
            pdf.set_xy(x, y + 0.7)
            if k == 1:
                pdf.multi_cell(w, 4.6, latin(v), align="L")
            else:
                pdf.cell(w, 4.6, latin(v), align=align)
            x += w
        pdf.set_xy(14, y + h)
    pdf.set_draw_color(*BORDER)
    pdf.line(14, pdf.get_y(), pdf.w - 14, pdf.get_y())
    pdf.ln(3)

    # Totales a la derecha; observaciones a la izquierda
    top = pdf.get_y()
    if pdf.get_y() + 8 * len(data.totals) > pdf.h - 22:
        pdf.add_page()
        top = pdf.get_y()
    for label, value, bold in data.totals:
        pdf.set_x(pdf.w - 14 - 80)
        pdf.set_font("helvetica", "B" if bold else "", 10 if bold else 9)
        pdf.set_text_color(*(NAVY if bold else MUTED))
        pdf.cell(44, 6, latin(label), align="R")
        pdf.set_text_color(*NAVY)
        pdf.cell(36, 6, latin(value), align="R", new_x="LMARGIN", new_y="NEXT")
    totals_end = pdf.get_y()
    pdf.set_y(top)
    if data.notes or data.terms:
        for label, text in (("Observaciones", data.notes), ("Condiciones", data.terms)):
            if text:
                _label_value(pdf, 14, 100, label, text)
                pdf.ln(1)
    pdf.set_y(max(totals_end, pdf.get_y()) + 4)

    if data.fiscal:
        pdf.set_font("helvetica", "B", 8)
        pdf.set_text_color(*MUTED)
        pdf.cell(0, 4.5, latin("INFORMACIÓN FISCAL"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("helvetica", "", 8)
        pdf.set_text_color(*NAVY)
        for label, value in data.fiscal:
            pdf.multi_cell(0, 4.2, latin(f"{label}: {value}"), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())
