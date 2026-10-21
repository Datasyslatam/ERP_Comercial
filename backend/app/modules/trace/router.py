from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import Principal, get_principal
from app.modules.trace import service

router = APIRouter(prefix="/trace", tags=["Trazabilidad"])


@router.get("/search")
def search(q: str = Query(min_length=2, max_length=60), p: Principal = Depends(get_principal),
           db: Session = Depends(get_db)):
    """Documentos cuyo número coincide, solo de los módulos que el usuario puede consultar."""
    return service.search(db, p, q)


@router.get("/{doc_type}/{doc_id}")
def trace(doc_type: str, doc_id: int, p: Principal = Depends(get_principal), db: Session = Depends(get_db)):
    """Cadena documental completa (hacia atrás y hacia adelante) con sus comprobantes contables."""
    return service.trace(db, p, doc_type, doc_id)
