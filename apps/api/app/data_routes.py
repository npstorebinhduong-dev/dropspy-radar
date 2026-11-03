from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session as DBSession

from .data_import import ImportOptions, MAX_BYTES, create_preview, job_summary, start_import
from .db import Session
from .models import ImportJob
from .sources import list_sources

router = APIRouter(prefix="/v1")


def data_db():
    with Session() as session:
        yield session


@router.get("/sources")
def sources(session: DBSession = Depends(data_db)):
    return {"items": list_sources(session)}


@router.post("/imports/preview")
async def preview(file: UploadFile = File(...), options: str = Form(...), session: DBSession = Depends(data_db)):
    try:
        if file.content_type not in {"application/json", "text/csv", "application/vnd.ms-excel", "application/octet-stream", "text/plain"}:
            raise HTTPException(415, "Unsupported file content type")
        if len(options) > 20000:
            raise HTTPException(413, "Mapping options too large")
        parsed = ImportOptions.model_validate_json(options)
        payload = await file.read(MAX_BYTES + 1)
        if len(payload) > MAX_BYTES:
            raise HTTPException(413, "File exceeds 2 MiB")
        return create_preview(session, payload, file.filename or "", parsed)
    except ValidationError as exc:
        raise HTTPException(422, [{"field": ".".join(map(str, item["loc"])), "message": item["msg"]} for item in exc.errors()]) from None
    except ValueError as exc:
        session.rollback()
        raise HTTPException(422, str(exc)) from None
    finally:
        await file.close()


@router.get("/imports")
def imports(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), session: DBSession = Depends(data_db)):
    from sqlalchemy import func

    total = session.scalar(select(func.count()).select_from(ImportJob))
    jobs = session.scalars(select(ImportJob).order_by(ImportJob.created_at.desc(), ImportJob.id).offset((page - 1) * page_size).limit(page_size))
    return {"items": [job_summary(job) for job in jobs], "total": total, "page": page, "page_size": page_size}


def get_job(session, id):
    job = session.get(ImportJob, id)
    if not job:
        raise HTTPException(404, "Import not found")
    return job


@router.get("/imports/{id}")
def import_status(id: str, session: DBSession = Depends(data_db)):
    return job_summary(get_job(session, id), preview=True)


@router.post("/imports/{id}/start")
def start(id: str, session: DBSession = Depends(data_db)):
    try:
        return start_import(session, id)
    except LookupError:
        raise HTTPException(404, "Import not found") from None
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None


@router.post("/imports/{id}/retry")
def retry(id: str, session: DBSession = Depends(data_db)):
    job = get_job(session, id)
    if job.status != "failed" or not job.normalized_rows:
        raise HTTPException(409, "Only failed imports with retained data can be retried")
    from .sources import require_import_source

    try:
        require_import_source(session, job.source_id, job.data_label, job.corpus)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    session.execute(update(ImportJob).where(ImportJob.id == id, ImportJob.status == "failed").values(status="queued"))
    session.commit()
    session.refresh(job)
    return job_summary(job)


@router.get("/imports/{id}/errors")
def error_report(id: str, session: DBSession = Depends(data_db)):
    from fastapi.responses import JSONResponse

    job = get_job(session, id)
    return JSONResponse(
        {"job_id": job.id, "validation_error_count": job.error_count, "errors": job.errors}, headers={"Content-Disposition": f'attachment; filename="import-{job.id}-errors.json"'}
    )
