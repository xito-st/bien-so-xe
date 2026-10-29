from datetime import date, datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from biensoxe.api.deps import get_client_ip, get_current_scope
from biensoxe.db import get_db
from biensoxe.repositories.scope import ScopeFilter
from biensoxe.services.kho import (
    adjust_after_dat_thanh_cong,
    chuyen_bien_cho_xa,
    huy_bien,
    list_bien_da_nhan,
    mark_dnm_dat_thanh_cong,
    nhap_kho_tinh,
    thu_hoi_bien,
    tra_bien_cho_dan,
)

router = APIRouter(prefix="/api/v1", tags=["kho-va-vong-doi-bien"])


class DatThanhCongRequest(BaseModel):
    xac_nhan: bool = True


class DieuChinhSauDatRequest(BaseModel):
    hanh_dong: str  # 'THEM_BIEN' | 'SUA_BIEN'
    ly_do: str
    xac_nhan: bool = False
    lo_con_id: int | None = None
    bien_id: int | None = None
    bien_so: str | None = None
    nen_bien: str | None = None
    nen_bien_id: int | None = None
    ghi_chu: str | None = None
    dat_lai_xac_nhan: bool = False


class NhapKhoRequest(BaseModel):
    ca_lo: bool = False
    bien_ids: list[int] | None = None


class ChuyenXaRequest(BaseModel):
    bien_ids: list[int]
    so_bien_ban: str
    nguoi_nhan: str
    chuc_vu: str
    ngay_nhan: date
    lo_xa_id: int | None = None
    xac_nhan: bool = True


class TraBienRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bien_ids: list[int] | None = None
    ngay_gio_tra: datetime | None = None


class ThuHoiOrHuyBienRequest(BaseModel):
    bien_id: int | None = None
    bien_ids: list[int] | None = None
    ly_do: str
    xac_nhan: bool = True


@router.post("/lo/{lo_id}/dat-thanh-cong")
def post_dat_thanh_cong(
    lo_id: int,
    request: Request,
    payload: DatThanhCongRequest | None = None,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    return mark_dnm_dat_thanh_cong(
        db,
        scope,
        lo_id=lo_id,
        xac_nhan=payload.xac_nhan if payload else True,
        ip=get_client_ip(request),
    )


@router.post("/lo/{lo_id}/dieu-chinh-sau-dat")
def post_dieu_chinh_sau_dat(
    lo_id: int,
    payload: DieuChinhSauDatRequest,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    return adjust_after_dat_thanh_cong(
        db,
        scope,
        dnm_lo_id=lo_id,
        hanh_dong=payload.hanh_dong,
        ly_do=payload.ly_do,
        xac_nhan=payload.xac_nhan,
        lo_con_id=payload.lo_con_id,
        bien_id=payload.bien_id,
        bien_so=payload.bien_so,
        nen_bien=payload.nen_bien,
        nen_bien_id=payload.nen_bien_id,
        ghi_chu=payload.ghi_chu,
        dat_lai_xac_nhan=payload.dat_lai_xac_nhan,
        ip=get_client_ip(request),
    )


@router.post("/lo/{lo_id}/nhap-kho")
def post_nhap_kho_tinh(
    lo_id: int,
    payload: NhapKhoRequest,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    return nhap_kho_tinh(
        db,
        scope,
        lo_id=lo_id,
        ca_lo=payload.ca_lo,
        bien_ids=payload.bien_ids,
        ip=get_client_ip(request),
    )


@router.post("/lo/{lo_id}/chuyen-xa")
def post_chuyen_bien_cho_xa(
    lo_id: int,
    payload: ChuyenXaRequest,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    return chuyen_bien_cho_xa(
        db,
        scope,
        lo_id=lo_id,
        bien_ids=payload.bien_ids,
        so_bien_ban=payload.so_bien_ban,
        nguoi_nhan=payload.nguoi_nhan,
        chuc_vu=payload.chuc_vu,
        ngay_nhan=payload.ngay_nhan,
        xac_nhan=payload.xac_nhan,
        lo_xa_id=payload.lo_xa_id,
        ip=get_client_ip(request),
    )


@router.get("/bien/da-nhan")
@router.get("/bien-da-nhan")
def get_bien_da_nhan_list(
    lo_id: int | None = None,
    giao: str | None = None,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    return {"items": list_bien_da_nhan(db, scope, lo_id=lo_id, giao=giao)}


@router.post("/bien/tra-bien")
@router.post("/bien/tra")
def post_tra_bien_bulk(
    payload: TraBienRequest,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    return tra_bien_cho_dan(
        db,
        scope,
        bien_ids=payload.bien_ids or [],
        ngay_gio_tra=payload.ngay_gio_tra,
        ip=get_client_ip(request),
    )


@router.post("/bien/{bien_id}/tra")
def post_tra_single_bien(
    bien_id: int,
    request: Request,
    payload: TraBienRequest | None = None,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    return tra_bien_cho_dan(
        db,
        scope,
        bien_ids=[bien_id],
        ngay_gio_tra=payload.ngay_gio_tra if payload else None,
        ip=get_client_ip(request),
    )


@router.post("/bien/{bien_id}/thu-hoi")
def post_thu_hoi_bien(
    bien_id: int,
    payload: ThuHoiOrHuyBienRequest,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    return thu_hoi_bien(
        db,
        scope,
        bien_id=bien_id,
        ly_do=payload.ly_do,
        xac_nhan=payload.xac_nhan,
        ip=get_client_ip(request),
    )


@router.post("/bien/thu-hoi")
def post_thu_hoi_bien_batch(
    payload: ThuHoiOrHuyBienRequest,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    ids = payload.bien_ids or ([payload.bien_id] if payload.bien_id else [])
    results = [
        thu_hoi_bien(
            db,
            scope,
            bien_id=bid,
            ly_do=payload.ly_do,
            xac_nhan=payload.xac_nhan,
            ip=get_client_ip(request),
        )
        for bid in ids
    ]
    return results[0] if len(results) == 1 else {"items": results}


@router.post("/bien/{bien_id}/huy")
def post_huy_bien(
    bien_id: int,
    payload: ThuHoiOrHuyBienRequest,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    return huy_bien(
        db,
        scope,
        bien_id=bien_id,
        ly_do=payload.ly_do,
        xac_nhan=payload.xac_nhan,
        ip=get_client_ip(request),
    )


@router.post("/bien/huy")
def post_huy_bien_batch(
    payload: ThuHoiOrHuyBienRequest,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    ids = payload.bien_ids or ([payload.bien_id] if payload.bien_id else [])
    results = [
        huy_bien(
            db,
            scope,
            bien_id=bid,
            ly_do=payload.ly_do,
            xac_nhan=payload.xac_nhan,
            ip=get_client_ip(request),
        )
        for bid in ids
    ]
    return results[0] if len(results) == 1 else {"items": results}
