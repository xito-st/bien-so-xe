import io

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from biensoxe.api.deps import get_client_ip, get_current_scope
from biensoxe.db import get_db
from biensoxe.repositories.scope import ScopeFilter
from biensoxe.services.import_excel import (
    export_import_job_error_xlsx,
    generate_lo_bien_template_xlsx,
    import_factory_return_xlsx,
    import_plates_to_lo_xlsx,
)

router = APIRouter(prefix="/api/v1", tags=["import-excel"])


@router.get("/lo/{lo_id}/bien/mau-xlsx")
@router.get("/bien/mau-xlsx")
@router.get("/import/file-mau.xlsx")
def get_mau_import_bien_xlsx(
    lo_id: int | None = None,
    scope: ScopeFilter = Depends(get_current_scope),
):
    content = generate_lo_bien_template_xlsx()
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="mau-nhap-bien-so.xlsx"'},
    )


@router.post("/lo/{lo_id}/bien/import")
@router.post("/lo/{lo_id}/import")
async def post_import_bien_to_lo(
    lo_id: int,
    request: Request,
    file: UploadFile = File(...),
    dat_lai_xac_nhan_all: bool = Form(default=False),
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    file_bytes = await file.read()
    return import_plates_to_lo_xlsx(
        db,
        scope,
        lo_id=lo_id,
        file_bytes=file_bytes,
        filename=file.filename or "import.xlsx",
        dat_lai_xac_nhan_all=dat_lai_xac_nhan_all,
        ip=get_client_ip(request),
    )


@router.post("/lo/{lo_id}/nhap-kho/import")
async def post_import_nhap_kho_nha_may(
    lo_id: int,
    request: Request,
    file: UploadFile = File(...),
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    file_bytes = await file.read()
    return import_factory_return_xlsx(
        db,
        scope,
        lo_id=lo_id,
        file_bytes=file_bytes,
        filename=file.filename or "nhap-kho.xlsx",
        ip=get_client_ip(request),
    )


@router.get("/import-jobs/{job_id}/bao-cao-loi")
def get_import_job_error_xlsx(
    job_id: str,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    content = export_import_job_error_xlsx(db, scope, job_id=job_id)
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="bao-cao-loi-{job_id}.xlsx"'},
    )
