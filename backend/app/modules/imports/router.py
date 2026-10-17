import json
from datetime import date

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.crud import get_owned
from app.core.db import get_db
from app.core.deps import Principal, require
from app.core.errors import BusinessRuleViolation
from app.core.serialize import to_dict
from app.modules.imports import service as svc
from app.modules.imports.models import ImportJob, ImportRow, OpeningBalanceBatch

router = APIRouter(prefix="/imports", tags=["Importación de datos"])


def _perm_for(entity: str) -> str:
    return "imports.opening.create" if entity.startswith("opening_") else "imports.job.create"


@router.get("/entities")
def entities(_: Principal = Depends(require("imports.job.read"))):
    return {k: [{"field": f, "required": r, "type": t, "description": d} for f, (r, t, d) in v.items()]
            for k, v in svc.SPECS.items()}


@router.get("/templates/{entity}")
def template(entity: str, fmt: str = Query("xlsx", pattern="^(xlsx|csv)$"),
             _: Principal = Depends(require("imports.job.read"))):
    if entity not in svc.SPECS:
        raise BusinessRuleViolation("Entidad no importable")
    data, ctype = svc.template(entity, fmt)
    return Response(data, media_type=ctype, headers={"Content-Disposition": f'attachment; filename="plantilla_{entity}.{fmt}"'})


@router.post("/jobs", status_code=201)
async def upload(entity: str = Form(...), file: UploadFile = File(...), mapping: str | None = Form(None),
                 opening_batch_id: int | None = Form(None), p: Principal = Depends(require("imports.job.create")),
                 db: Session = Depends(get_db)):
    if not p.has(_perm_for(entity)):
        from app.core.errors import Forbidden

        raise Forbidden("Permiso insuficiente para esta importación")
    data = await file.read(get_settings().max_upload_mb * 1024 * 1024 + 1)
    if len(data) > get_settings().max_upload_mb * 1024 * 1024:
        raise BusinessRuleViolation("Archivo demasiado grande")
    if not (file.filename or "").lower().endswith((".csv", ".xlsx")):
        raise BusinessRuleViolation("Formatos admitidos: .csv, .xlsx")
    try:
        mapping_dict = json.loads(mapping) if mapping else None
    except json.JSONDecodeError as exc:
        raise BusinessRuleViolation("El mapeo de columnas debe ser JSON") from exc
    job = svc.upload(db, p, entity, file.filename, data, mapping_dict, opening_batch_id)
    svc.validate(db, p, job.id)
    db.commit()
    return _job(job)


def _job(job: ImportJob) -> dict:
    return {k: v for k, v in to_dict(job).items() if k != "column_mapping"} | {"column_mapping": job.column_mapping}


@router.get("/jobs")
def list_jobs(limit: int = Query(50, le=200), p: Principal = Depends(require("imports.job.read")),
              db: Session = Depends(get_db)):
    return [_job(j) for j in db.scalars(select(ImportJob).where(ImportJob.company_id == p.company_id)
                                        .order_by(ImportJob.id.desc()).limit(limit))]


@router.get("/jobs/{job_id}")
def get_job(job_id: int, p: Principal = Depends(require("imports.job.read")), db: Session = Depends(get_db)):
    return _job(get_owned(db, ImportJob, job_id, p.company_id))


@router.get("/jobs/{job_id}/rows")
def rows(job_id: int, status: str | None = None, limit: int = Query(100, le=1000), offset: int = 0,
         p: Principal = Depends(require("imports.job.read")), db: Session = Depends(get_db)):
    job = get_owned(db, ImportJob, job_id, p.company_id)
    stmt = select(ImportRow).where(ImportRow.job_id == job.id)
    if status:
        stmt = stmt.where(ImportRow.status == status)
    return [to_dict(r) for r in db.scalars(stmt.order_by(ImportRow.row_number).limit(limit).offset(offset))]


@router.post("/jobs/{job_id}/validate")
def validate(job_id: int, p: Principal = Depends(require("imports.job.create")), db: Session = Depends(get_db)):
    job = svc.validate(db, p, job_id)
    db.commit()
    return _job(job)


class RowPatch(BaseModel):
    data: dict


@router.patch("/rows/{row_id}")
def patch_row(row_id: int, body: RowPatch, p: Principal = Depends(require("imports.job.create")),
              db: Session = Depends(get_db)):
    row = svc.update_row(db, p, row_id, body.data)
    svc.validate(db, p, row.job_id)
    db.commit()
    return to_dict(row)


@router.post("/jobs/{job_id}/commit")
def commit(job_id: int, p: Principal = Depends(require("imports.job.post")), db: Session = Depends(get_db)):
    job = svc.commit(db, p, job_id)
    db.commit()
    return _job(job)


@router.get("/jobs/{job_id}/reconciliation")
def reconcile(job_id: int, p: Principal = Depends(require("imports.job.read")), db: Session = Depends(get_db)):
    return svc.reconcile_job(db, p, job_id)


class BatchIn(BaseModel):
    kind: str = Field(pattern="^(stock|receivables|payables)$")
    cutoff_date: date
    source_description: str = Field(min_length=10, max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)


@router.get("/opening-batches")
def list_batches(p: Principal = Depends(require("imports.opening.read")), db: Session = Depends(get_db)):
    return [to_dict(b) for b in db.scalars(select(OpeningBalanceBatch).where(
        OpeningBalanceBatch.company_id == p.company_id).order_by(OpeningBalanceBatch.id.desc()))]


@router.post("/opening-batches", status_code=201)
def create_batch(body: BatchIn, p: Principal = Depends(require("imports.opening.create")),
                 db: Session = Depends(get_db)):
    b = svc.create_opening_batch(db, p, body.model_dump())
    db.commit()
    return to_dict(b)


@router.get("/opening-batches/{batch_id}")
def batch_summary(batch_id: int, p: Principal = Depends(require("imports.opening.read")),
                  db: Session = Depends(get_db)):
    return svc.batch_summary(db, p, batch_id)


@router.post("/opening-batches/{batch_id}/approve")
def approve_batch(batch_id: int, p: Principal = Depends(require("imports.opening.approve")),
                  db: Session = Depends(get_db)):
    b = svc.approve_batch(db, p, batch_id)
    db.commit()
    return to_dict(b)


@router.post("/opening-batches/{batch_id}/post")
def post_batch(batch_id: int, p: Principal = Depends(require("imports.opening.post")),
               db: Session = Depends(get_db)):
    b = svc.post_batch(db, p, batch_id)
    db.commit()
    return to_dict(b)
