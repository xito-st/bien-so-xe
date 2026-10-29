import io

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from biensoxe.api.deps import get_current_scope
from biensoxe.db import get_db
from biensoxe.repositories.scope import ScopeFilter
from biensoxe.services.tra_cuu import (
    export_search_bien_xlsx,
    search_bien,
    suggest_tra_cuu,
)

router = APIRouter(prefix="/api/v1", tags=["tra-cuu"])


@router.get("/bien/goi-y")
@router.get("/tra-cuu/goi-y")
def get_goi_y_tra_cuu(
    q: str | None = None,
    limit: int = 20,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    items = suggest_tra_cuu(db, scope, q=q, limit=limit)
    return {"items": items}


@router.get("/bien")
@router.get("/tra-cuu/bien")
def get_tra_cuu_bien(
    q: str | None = None,
    ma_lo: str | None = None,
    bien_so: str | None = None,
    seri_chu: str | None = None,
    dau_so: str | None = None,
    loai_pt_id: int | None = None,
    loai_pt: str | None = None,
    ma_tinh_bien: str | None = None,
    tinh_ma: str | None = None,
    xa_ma: str | None = None,
    trang_thai_lo: str | None = None,
    tinh_trang: str | None = None,
    giao: str | None = None,
    ngoai_tinh: bool | None = None,
    limit: int = 200,
    offset: int = 0,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    items = search_bien(
        db,
        scope,
        q=q,
        ma_lo=ma_lo,
        bien_so=bien_so,
        seri_chu=seri_chu,
        dau_so=dau_so,
        loai_pt_id=loai_pt_id,
        loai_pt=loai_pt,
        ma_tinh_bien=ma_tinh_bien,
        tinh_ma=tinh_ma,
        xa_ma=xa_ma,
        trang_thai_lo=trang_thai_lo,
        tinh_trang=tinh_trang,
        giao=giao,
        ngoai_tinh=ngoai_tinh,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "total": len(items)}


@router.get("/bien/xuat")
@router.get("/tra-cuu/bien/xuat")
def get_xuat_tra_cuu_bien(
    q: str | None = None,
    ma_lo: str | None = None,
    bien_so: str | None = None,
    seri_chu: str | None = None,
    dau_so: str | None = None,
    loai_pt_id: int | None = None,
    loai_pt: str | None = None,
    ma_tinh_bien: str | None = None,
    tinh_ma: str | None = None,
    xa_ma: str | None = None,
    trang_thai_lo: str | None = None,
    tinh_trang: str | None = None,
    giao: str | None = None,
    ngoai_tinh: bool | None = None,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    content = export_search_bien_xlsx(
        db,
        scope,
        q=q,
        ma_lo=ma_lo,
        bien_so=bien_so,
        seri_chu=seri_chu,
        dau_so=dau_so,
        loai_pt_id=loai_pt_id,
        loai_pt=loai_pt,
        ma_tinh_bien=ma_tinh_bien,
        tinh_ma=tinh_ma,
        xa_ma=xa_ma,
        trang_thai_lo=trang_thai_lo,
        tinh_trang=tinh_trang,
        giao=giao,
        ngoai_tinh=ngoai_tinh,
    )
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="tra-cuu-bien-so.xlsx"'},
    )
