"""Paquetes de parametrización por jurisdicción (Colombia y Venezuela).

IMPORTANTE: los planes de cuentas y tarifas son una base inicial de referencia. Antes de producción deben ser
revisados y aprobados por el contador/revisor fiscal de cada empresa (tarifas municipales de ICA, bases mínimas
en UVT, calidad de agente de retención, contribuyente especial, etc.). Todo es editable desde la aplicación.

Formato de cuenta: (código, nombre, tipo, es_movimiento, opciones)
"""

CO_ACCOUNTS = [
    ("1", "ACTIVO", "asset", False, {}),
    ("11", "Disponible", "asset", False, {}),
    ("110505", "Caja general", "asset", True, {"is_cash": True}),
    ("111005", "Bancos moneda nacional", "asset", True, {"is_cash": True}),
    ("111010", "Bancos moneda extranjera", "asset", True, {"is_cash": True}),
    ("13", "Deudores", "asset", False, {}),
    ("130505", "Clientes nacionales", "asset", True, {"requires_party": True}),
    ("135515", "Anticipo de impuestos - Retención en la fuente", "asset", True, {}),
    ("135517", "Anticipo de impuestos - Retención de IVA", "asset", True, {}),
    ("135518", "Anticipo de impuestos - Retención de ICA", "asset", True, {}),
    ("14", "Inventarios", "asset", False, {}),
    ("140505", "Materias primas", "asset", True, {}),
    ("141005", "Productos en proceso", "asset", True, {}),
    ("143005", "Productos terminados", "asset", True, {}),
    ("143505", "Mercancías no fabricadas por la empresa", "asset", True, {}),
    ("2", "PASIVO", "liability", False, {}),
    ("220505", "Proveedores nacionales", "liability", True, {"requires_party": True}),
    ("233595", "Recepciones de mercancía pendientes de factura", "liability", True, {}),
    ("236525", "Retención en la fuente - Servicios", "liability", True, {}),
    ("236540", "Retención en la fuente - Compras", "liability", True, {}),
    ("236701", "Impuesto a las ventas retenido", "liability", True, {}),
    ("236801", "Impuesto de industria y comercio retenido", "liability", True, {}),
    ("240805", "IVA generado", "liability", True, {}),
    ("240810", "IVA descontable", "liability", True, {"normal": "debit"}),
    ("241005", "Impuesto nacional al consumo", "liability", True, {}),
    ("3", "PATRIMONIO", "equity", False, {}),
    ("310505", "Capital autorizado", "equity", True, {}),
    ("370505", "Utilidades acumuladas", "equity", True, {}),
    ("399995", "Saldos iniciales por conciliar (cuenta puente)", "equity", True, {}),
    ("4", "INGRESOS", "revenue", False, {}),
    ("413505", "Venta de mercancías", "revenue", True, {}),
    ("417505", "Devoluciones en ventas", "revenue", True, {"normal": "debit"}),
    ("421020", "Diferencia en cambio (ingreso)", "revenue", True, {}),
    ("425050", "Recuperaciones - Ajustes de inventario", "revenue", True, {}),
    ("5", "GASTOS", "expense", False, {}),
    ("513550", "Transportes, fletes y acarreos", "expense", True, {}),
    ("519530", "Pérdidas y bajas de inventario", "expense", True, {}),
    ("530525", "Diferencia en cambio (gasto)", "expense", True, {}),
    ("6", "COSTO DE VENTAS", "cost", False, {}),
    ("613505", "Costo de mercancía vendida", "cost", True, {}),
    ("7", "COSTOS DE PRODUCCIÓN", "cost", False, {}),
    ("710595", "Variaciones de producción", "cost", True, {}),
]

CO_POSTING = {
    "inventory": "143505", "grni": "233595", "accounts_payable": "220505", "accounts_receivable": "130505",
    "revenue": "413505", "sales_returns": "417505", "cogs": "613505", "inventory_adjustment_gain": "425050",
    "inventory_adjustment_loss": "519530", "scrap_expense": "519530", "wip": "141005",
    "production_variance": "710595", "opening_balance": "399995", "fx_difference": "530525",
    "freight_expense": "513550", "purchase_price_variance": "613505", "applied_labor": "710595",
    "retained_earnings": "370505",
}

# (código, nombre, tipo, tarifa %, base, aplica, cuenta ventas, cuenta compras, código electrónico)
CO_TAXES = [
    ("IVA19", "IVA 19%", "vat", "19", "subtotal", "both", "240805", "240810", "01"),
    ("IVA5", "IVA 5%", "vat", "5", "subtotal", "both", "240805", "240810", "01"),
    ("IVA0", "IVA exento / excluido 0%", "vat", "0", "subtotal", "both", "240805", "240810", "01"),
    ("INC8", "Impuesto nacional al consumo 8%", "consumption", "8", "subtotal", "sales", "241005", None, "04"),
    ("RTEC25", "Retención en la fuente compras 2,5%", "withholding_income", "2.5", "subtotal", "both", "135515",
     "236540", "06"),
    ("RTES4", "Retención en la fuente servicios 4%", "withholding_income", "4", "subtotal", "both", "135515",
     "236525", "06"),
    ("RIVA15", "Retención de IVA 15%", "withholding_vat", "15", "vat", "both", "135517", "236701", "05"),
    ("RICA", "Retención de ICA (verificar tarifa municipal)", "withholding_ica", "0.966", "subtotal", "both",
     "135518", "236801", "07"),
]

VE_ACCOUNTS = [
    ("1", "ACTIVO", "asset", False, {}),
    ("1.1.01", "Efectivo y equivalentes", "asset", False, {}),
    ("1.1.01.01", "Caja", "asset", True, {"is_cash": True}),
    ("1.1.01.02", "Bancos nacionales (Bs.)", "asset", True, {"is_cash": True}),
    ("1.1.01.03", "Bancos en moneda extranjera", "asset", True, {"is_cash": True}),
    ("1.1.02.01", "Cuentas por cobrar clientes", "asset", True, {"requires_party": True}),
    ("1.1.03.01", "IVA crédito fiscal", "asset", True, {}),
    ("1.1.03.02", "IVA retenido por clientes", "asset", True, {}),
    ("1.1.03.03", "ISLR retenido por clientes", "asset", True, {}),
    ("1.1.04", "Inventarios", "asset", False, {}),
    ("1.1.04.01", "Inventario de mercancía", "asset", True, {}),
    ("1.1.04.02", "Inventario de materia prima", "asset", True, {}),
    ("1.1.04.03", "Productos en proceso", "asset", True, {}),
    ("2", "PASIVO", "liability", False, {}),
    ("2.1.01.01", "Proveedores", "liability", True, {"requires_party": True}),
    ("2.1.02.01", "Recepciones pendientes de factura", "liability", True, {}),
    ("2.1.03.01", "IVA débito fiscal", "liability", True, {}),
    ("2.1.03.02", "IVA retenido a proveedores por enterar", "liability", True, {}),
    ("2.1.03.03", "ISLR retenido por enterar", "liability", True, {}),
    ("2.1.03.04", "IGTF percibido por enterar", "liability", True, {}),
    ("3", "PATRIMONIO", "equity", False, {}),
    ("3.1.01", "Capital social", "equity", True, {}),
    ("3.2.01", "Resultados acumulados", "equity", True, {}),
    ("3.9.01", "Saldos iniciales por conciliar (cuenta puente)", "equity", True, {}),
    ("4", "INGRESOS", "revenue", False, {}),
    ("4.1.01", "Ventas de mercancía", "revenue", True, {}),
    ("4.1.02", "Devoluciones en ventas", "revenue", True, {"normal": "debit"}),
    ("4.2.01", "Ganancia por diferencial cambiario", "revenue", True, {}),
    ("4.2.02", "Ajustes de inventario (ganancia)", "revenue", True, {}),
    ("5", "COSTOS", "cost", False, {}),
    ("5.1.01", "Costo de ventas", "cost", True, {}),
    ("5.2.01", "Variaciones de producción", "cost", True, {}),
    ("6", "GASTOS", "expense", False, {}),
    ("6.1.01", "Fletes y transporte", "expense", True, {}),
    ("6.1.02", "Pérdidas y mermas de inventario", "expense", True, {}),
    ("6.2.01", "Pérdida por diferencial cambiario", "expense", True, {}),
    ("6.2.02", "Impuesto a las grandes transacciones financieras (IGTF)", "expense", True, {}),
]

VE_POSTING = {
    "inventory": "1.1.04.01", "grni": "2.1.02.01", "accounts_payable": "2.1.01.01",
    "accounts_receivable": "1.1.02.01", "revenue": "4.1.01", "sales_returns": "4.1.02", "cogs": "5.1.01",
    "inventory_adjustment_gain": "4.2.02", "inventory_adjustment_loss": "6.1.02", "scrap_expense": "6.1.02",
    "wip": "1.1.04.03", "production_variance": "5.2.01", "opening_balance": "3.9.01", "fx_difference": "6.2.01",
    "freight_expense": "6.1.01", "purchase_price_variance": "5.1.01", "applied_labor": "5.2.01",
    "retained_earnings": "3.2.01",
}

VE_TAXES = [
    ("IVA16", "IVA alícuota general 16%", "vat", "16", "subtotal", "both", "2.1.03.01", "1.1.03.01", "IVA"),
    ("IVA8", "IVA alícuota reducida 8%", "vat", "8", "subtotal", "both", "2.1.03.01", "1.1.03.01", "IVA"),
    ("EXENTO", "Exento de IVA", "vat", "0", "subtotal", "both", "2.1.03.01", "1.1.03.01", "EX"),
    ("RIVA75", "Retención de IVA 75%", "withholding_vat", "75", "vat", "both", "1.1.03.02", "2.1.03.02", "RIVA"),
    ("RIVA100", "Retención de IVA 100%", "withholding_vat", "100", "vat", "both", "1.1.03.02", "2.1.03.02", "RIVA"),
    ("RISLR2", "Retención de ISLR servicios 2%", "withholding_income", "2", "subtotal", "both", "1.1.03.03",
     "2.1.03.03", "ISLR"),
    ("IGTF3", "IGTF 3% (pagos en divisas)", "igtf", "3", "subtotal", "both", "2.1.03.04", "6.2.02", "IGTF"),
]

PACKS = {
    "CO": {"currency": "COP", "accounts": CO_ACCOUNTS, "posting": CO_POSTING, "taxes": CO_TAXES,
           "bank_account": "111005", "fx_bank_account": "111010"},
    "VE": {"currency": "VES", "accounts": VE_ACCOUNTS, "posting": VE_POSTING, "taxes": VE_TAXES,
           "bank_account": "1.1.01.02", "fx_bank_account": "1.1.01.03"},
}

CURRENCIES = [("COP", "Peso colombiano", 2), ("VES", "Bolívar", 2), ("USD", "Dólar estadounidense", 2),
              ("EUR", "Euro", 2)]

UOMS = [("UND", "Unidad", "unit"), ("CAJ", "Caja", "unit"), ("PAQ", "Paquete", "unit"), ("KG", "Kilogramo", "weight"),
        ("G", "Gramo", "weight"), ("L", "Litro", "volume"), ("ML", "Mililitro", "volume"), ("M", "Metro", "length"),
        ("HR", "Hora", "time")]
