from datetime import datetime
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from biensoxe.api.deps import get_current_scope
from biensoxe.db import get_db
from biensoxe.repositories.scope import ScopeFilter
from biensoxe.services.bao_cao import export_report_xlsx, get_report_data

router = APIRouter(prefix="/api/v1/bao-cao", tags=["bao-cao"])


@router.get("/{report_code}")
def get_bao_cao(
    report_code: str,
    tinh_ma: str | None = None,
    xa_ma: str | None = None,
    tu_ngay: datetime | None = None,
    den_ngay: datetime | None = None,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    return get_report_data(
        db,
        scope,
        report_code=report_code,
        tinh_ma=tinh_ma,
        xa_ma=xa_ma,
        tu_ngay=tu_ngay,
        den_ngay=den_ngay,
    )


@router.get("/{report_code}/xuat")
def get_xuat_bao_cao(
    report_code: str,
    tinh_ma: str | None = None,
    xa_ma: str | None = None,
    tu_ngay: datetime | None = None,
    den_ngay: datetime | None = None,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    content = export_report_xlsx(
        db,
        scope,
        report_code=report_code,
        tinh_ma=tinh_ma,
        xa_ma=xa_ma,
        tu_ngay=tu_ngay,
        den_ngay=den_ngay,
    )
    code_lower = report_code.strip().lower()
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="bao-cao-{code_lower}.xlsx"'},
    )
