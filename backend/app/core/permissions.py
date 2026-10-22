"""Catálogo de permisos granulares y roles predefinidos.

Formato: <módulo>.<recurso>.<acción>, con acciones read, create, approve, post, void, export, admin.
"""

_RESOURCES: dict[str, dict[str, tuple[str, ...]]] = {
    "admin": {
        "users": ("read", "create", "admin"),
        "roles": ("read", "admin"),
        "audit": ("read", "export"),
        "company": ("read", "admin"),
    },
    "masters": {
        "parties": ("read", "create", "export"),
        "items": ("read", "create", "export"),
        "taxes": ("read", "admin"),
        "config": ("read", "admin"),
    },
    "purchasing": {
        "requisition": ("read", "create", "approve"),
        "rfq": ("read", "create", "approve"),
        "order": ("read", "create", "approve", "void", "export"),
        "receipt": ("read", "create", "post"),
        "invoice": ("read", "create", "post", "void"),
        "supplier_eval": ("read", "create"),
    },
    "inventory": {
        "stock": ("read", "export"),
        "document": ("read", "create", "approve", "post"),
        "count": ("read", "create", "approve"),
        "config": ("read", "admin"),
    },
    "quality": {
        "plan": ("read", "admin"),
        "inspection": ("read", "create", "approve"),
        "nonconformity": ("read", "create", "approve"),
    },
    "sales": {
        "quote": ("read", "create"),
        "order": ("read", "create", "approve", "void"),
        "pricing": ("read", "admin"),
    },
    "logistics": {
        "dispatch": ("read", "create", "post", "void"),
        "route": ("read", "admin"),
        "return": ("read", "create", "post"),
    },
    "operations": {
        "work_order": ("read", "create", "approve", "post"),
    },
    "accounting": {
        "journal": ("read", "create", "post", "void", "export"),
        "accounts": ("read", "admin"),
        "period": ("read", "admin"),
        "reports": ("read", "export"),
        "tax_reports": ("read", "export"),
        "payments": ("read", "create", "void"),
        "bank": ("read", "create", "approve"),
        "budget": ("read", "create", "approve"),
    },
    "einvoicing": {
        "invoice": ("read", "create", "post", "void", "export"),
        "numbering": ("read", "admin"),
    },
    "kpi": {
        "dashboard": ("read", "export"),
        "config": ("admin",),
        "alerts": ("read", "approve"),
    },
    "imports": {
        "job": ("read", "create", "post"),
        "opening": ("read", "create", "approve", "post"),
    },
}

MODULE_LABELS = {
    "admin": "Administración", "masters": "Datos maestros", "purchasing": "Compras", "inventory": "Inventario",
    "quality": "Calidad", "sales": "Ventas", "logistics": "Logística", "operations": "Operaciones",
    "accounting": "Contabilidad", "einvoicing": "Facturación electrónica", "kpi": "Indicadores",
    "imports": "Importación de datos",
}
RESOURCE_LABELS = {
    "admin.users": "Usuarios", "admin.roles": "Roles y permisos", "admin.audit": "Auditoría",
    "admin.company": "Empresa, sedes y políticas",
    "masters.parties": "Terceros", "masters.items": "Artículos", "masters.taxes": "Impuestos",
    "masters.config": "Parámetros",
    "purchasing.requisition": "Solicitudes de compra", "purchasing.rfq": "Cotizaciones",
    "purchasing.order": "Órdenes de compra", "purchasing.receipt": "Recepciones",
    "purchasing.invoice": "Facturas de proveedor", "purchasing.supplier_eval": "Evaluación de proveedores",
    "inventory.stock": "Existencias y kardex", "inventory.document": "Movimientos y ajustes",
    "inventory.count": "Conteos físicos", "inventory.config": "Bodegas y ubicaciones",
    "quality.plan": "Planes de inspección", "quality.inspection": "Inspecciones",
    "quality.nonconformity": "No conformidades",
    "sales.quote": "Cotizaciones", "sales.order": "Pedidos de venta", "sales.pricing": "Listas de precios y promociones",
    "logistics.dispatch": "Despachos", "logistics.route": "Rutas", "logistics.return": "Devoluciones",
    "operations.work_order": "Órdenes de trabajo",
    "accounting.journal": "Comprobantes", "accounting.accounts": "Plan de cuentas",
    "accounting.period": "Periodos contables", "accounting.reports": "Estados financieros",
    "accounting.tax_reports": "Libros y reportes fiscales",
    "accounting.payments": "Cartera y pagos", "accounting.bank": "Bancos", "accounting.budget": "Presupuestos",
    "einvoicing.invoice": "Facturas electrónicas", "einvoicing.numbering": "Numeración autorizada",
    "kpi.dashboard": "Tablero", "kpi.config": "Configuración de indicadores", "kpi.alerts": "Alertas",
    "imports.job": "Cargues de datos", "imports.opening": "Saldos iniciales",
}
ACTION_LABELS = {
    "read": "Consultar", "create": "Crear y editar", "approve": "Aprobar", "post": "Contabilizar / ejecutar",
    "void": "Anular", "export": "Exportar", "admin": "Administrar",
}

PERMISSIONS: list[tuple[str, str, str]] = [
    (f"{module}.{resource}.{action}", module,
     f"{ACTION_LABELS[action]} · {RESOURCE_LABELS.get(f'{module}.{resource}', resource)}")
    for module, resources in _RESOURCES.items()
    for resource, actions in resources.items()
    for action in actions
]
ALL_CODES = {p[0] for p in PERMISSIONS}


def _pick(*patterns: str) -> list[str]:
    """Selecciona permisos por prefijo o sufijo: 'purchasing.' o '*.read'."""
    out = set()
    for pat in patterns:
        if pat.startswith("*."):
            out |= {c for c in ALL_CODES if c.endswith(pat[1:])}
        else:
            out |= {c for c in ALL_CODES if c.startswith(pat)}
    return sorted(out)


ROLES: dict[str, tuple[str, list[str]]] = {
    "admin": ("Administrador del sistema", sorted(ALL_CODES)),
    "gerente": ("Gerencia", _pick("*.read", "*.export", "kpi.", "accounting.budget.approve")),
    "auditor": ("Auditor (solo lectura)", _pick("*.read", "*.export")),
    "comprador": (
        "Comprador",
        _pick("purchasing.requisition.read", "purchasing.requisition.create", "purchasing.rfq.", "purchasing.order.read",
              "purchasing.order.create", "purchasing.supplier_eval.", "masters.parties.", "masters.items.read",
              "inventory.stock.read", "kpi.dashboard.read"),
    ),
    "aprobador_compras": (
        "Aprobador de compras",
        _pick("purchasing.requisition.read", "purchasing.requisition.approve", "purchasing.order.read",
              "purchasing.order.approve", "purchasing.rfq.read", "purchasing.rfq.approve", "kpi.dashboard.read"),
    ),
    "almacenista": (
        "Almacenista",
        _pick("inventory.", "purchasing.receipt.", "purchasing.order.read", "logistics.dispatch.read",
              "logistics.return.", "masters.items.read", "kpi.dashboard.read"),
    ),
    "inspector_calidad": ("Inspector de calidad", _pick("quality.", "inventory.stock.read", "kpi.dashboard.read")),
    "vendedor": (
        "Vendedor",
        _pick("sales.quote.", "sales.order.read", "sales.order.create", "sales.pricing.read", "masters.parties.",
              "masters.items.read", "inventory.stock.read", "einvoicing.invoice.read", "kpi.dashboard.read"),
    ),
    "despachador": ("Despachador", _pick("logistics.", "sales.order.read", "inventory.stock.read", "kpi.dashboard.read")),
    "facturador": ("Facturación", _pick("einvoicing.invoice.", "sales.order.read", "logistics.dispatch.read",
                                         "masters.parties.read", "kpi.dashboard.read")),
    "contador": (
        "Contador",
        _pick("accounting.", "einvoicing.invoice.read", "purchasing.invoice.", "imports.", "masters.taxes.",
              "kpi.dashboard.read"),
    ),
    "tesorero": ("Tesorería", _pick("accounting.payments.", "accounting.bank.", "accounting.reports.read",
                                    "kpi.dashboard.read")),
    "operaciones": ("Operaciones / producción", _pick("operations.", "inventory.stock.read", "inventory.document.read",
                                                      "quality.inspection.read", "kpi.dashboard.read")),
}
