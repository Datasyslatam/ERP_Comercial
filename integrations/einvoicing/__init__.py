"""Registro de adaptadores de facturación electrónica.

Para integrar un proveedor real: implementar una clase que cumpla `EInvoiceAdapter` (base.py), registrarla
en ADAPTERS y configurar EINVOICE_ADAPTER_CO / EINVOICE_ADAPTER_VE. Las credenciales se leen de variables de
entorno o del gestor de secretos, nunca del repositorio.
"""
from integrations.einvoicing.base import EInvoiceAdapter
from integrations.einvoicing.sandbox import SandboxDianAdapter, SandboxSeniatAdapter

ADAPTERS: dict[str, type] = {
    "sandbox_dian": SandboxDianAdapter,
    "sandbox_seniat": SandboxSeniatAdapter,
}


def get_adapter(name: str) -> EInvoiceAdapter:
    try:
        return ADAPTERS[name]()
    except KeyError as exc:
        raise ValueError(f"Adaptador de facturación no registrado: {name}") from exc
