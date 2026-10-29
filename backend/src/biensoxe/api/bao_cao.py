from datetime import datetime
import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from biensoxe.api.deps import get_current_scope
from biensoxe.db import get_db
from biensoxe.repositories.scope import ScopeFilter
from biensoxe.services.bao_cao import (
    export_report_xlsx,
    get_report_data,
    get_report_drilldown_plates,
)

router = APIRouter(prefix="/api/v1/bao-cao", tags=["bao-cao"])


@router.get("/chi-tiet/bien")
def get_drilldown_plates(
    tinh_ma: str | None = None,
    xa_ma: str | None = None,
    is_cap_tinh: bool = False,
    loai_lo: str | None = None,
    trang_thai_lo: str | None = None,
    tinh_trang: str | None = None,
    giao: str | None = None,
    loai_pt: str | None = None,
    seri_chu: str | None = None,
    tu_ngay: datetime | None = None,
    den_ngay: datetime | None = None,
    limit: int = 500,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    """Truy vấn danh sách biển số chi tiết khi người dùng bấm tương tác (drill-down) vào dòng thống kê."""
    items = get_report_drilldown_plates(
        db,
        scope,
        tinh_ma=tinh_ma,
        xa_ma=xa_ma,
        is_cap_tinh=is_cap_tinh,
        loai_lo=loai_lo,
        trang_thai_lo=trang_thai_lo,
        tinh_trang=tinh_trang,
        giao=giao,
        loai_pt=loai_pt,
        seri_chu=seri_chu,
        tu_ngay=tu_ngay,
        den_ngay=den_ngay,
        limit=limit,
    )
    return {"items": items, "total": len(items)}


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

