from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from biensoxe.api.deps import get_client_ip, get_current_scope
from biensoxe.db import get_db
from biensoxe.repositories.scope import ScopeFilter
from biensoxe.services.lo import (
    approve_lo,
    approve_lo_bulk,
    cancel_dnm_lo,
    complete_adjustment_lo,
    create_lo,
    delete_lo,
    enable_adjustment_lo,
    get_lo_detail,
    list_lo,
    list_lo_history,
    reject_lo,
    submit_lo,
    update_lo,
    withdraw_dnm_lo,
)
from biensoxe.services.sync import retry_sync_lo

router = APIRouter(prefix="/api/v1/lo", tags=["lo"])


class CreateLoRequest(BaseModel):
    loai: str = "XA"
    so_cong_van: str
    ghi_chu: str | None = None
    lo_con_ids: list[int] | None = None


class UpdateLoRequest(BaseModel):
    so_cong_van: str | None = None
    ghi_chu: str | None = None
    lo_con_ids: list[int] | None = None


class GuiLoRequest(BaseModel):
    xac_nhan: bool = True
    gia_lap_loi_dong_bo: bool = False


class DuyetLoRequest(BaseModel):
    xac_nhan: bool = True


class DuyetHangLoatRequest(BaseModel):
    lo_ids: list[int]
    xac_nhan: bool = True


class TuChoiLoRequest(BaseModel):
    ly_do: str
    bien_loi: list[dict] | None = None
    xac_nhan: bool = True


class LyDoActionRequest(BaseModel):
    ly_do: str | None = None


class HuyLoRequest(BaseModel):
    ly_do: str
    xac_nhan: bool = True


@router.get("")
def get_lo_list(
    loai: str | None = None,
    trang_thai: str | None = None,
    tinh_ma: str | None = None,
    xa_ma: str | None = None,
    chua_gan_dnm: bool = False,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    return {
        "items": list_lo(
            db,
            scope,
            loai=loai,
            trang_thai=trang_thai,
            tinh_ma=tinh_ma,
            xa_ma=xa_ma,
            chua_gan_dnm=chua_gan_dnm,
        )
    }


@router.post("", status_code=status.HTTP_201_CREATED)
def post_create_lo(
    payload: CreateLoRequest,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    return create_lo(
        db,
        scope,
        loai=payload.loai,
        so_cong_van=payload.so_cong_van,
        ghi_chu=payload.ghi_chu,
        lo_con_ids=payload.lo_con_ids,
        ip=get_client_ip(request),
    )


@router.post("/duyet-hang-loat")
@router.post("/chap-nhan-hang-loat")
def post_duyet_lo_hang_loat(
    payload: DuyetHangLoatRequest,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    return approve_lo_bulk(
        db,
        scope,
        lo_ids=payload.lo_ids,
        xac_nhan=payload.xac_nhan,
        ip=get_client_ip(request),
    )


@router.get("/{lo_id}")
def get_lo_by_id(
    lo_id: int,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    return get_lo_detail(db, scope, lo_id=lo_id)


@router.put("/{lo_id}")
def put_update_lo(
    lo_id: int,
    payload: UpdateLoRequest,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    return update_lo(
        db,
        scope,
        lo_id=lo_id,
        so_cong_van=payload.so_cong_van,
        ghi_chu=payload.ghi_chu,
        lo_con_ids=payload.lo_con_ids,
        ip=get_client_ip(request),
    )


@router.delete("/{lo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_lo_by_id(
    lo_id: int,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    delete_lo(db, scope, lo_id=lo_id, ip=get_client_ip(request))


@router.post("/{lo_id}/gui")
def post_gui_lo(
    lo_id: int,
    payload: GuiLoRequest,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    return submit_lo(
        db,
        scope,
        lo_id=lo_id,
        xac_nhan=payload.xac_nhan,
        gia_lap_loi_dong_bo=payload.gia_lap_loi_dong_bo,
        ip=get_client_ip(request),
    )


@router.post("/{lo_id}/dong-bo-lai")
def post_dong_bo_lai(
    lo_id: int,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    retry_sync_lo(db, scope, lo_id=lo_id, ip=get_client_ip(request))
    return get_lo_detail(db, scope, lo_id=lo_id)


@router.post("/{lo_id}/duyet")
@router.post("/{lo_id}/chap-nhan")
def post_duyet_lo(
    lo_id: int,
    request: Request,
    payload: DuyetLoRequest | None = None,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    xac_nhan = payload.xac_nhan if payload is not None else True
    return approve_lo(
        db,
        scope,
        lo_id=lo_id,
        xac_nhan=xac_nhan,
        ip=get_client_ip(request),
    )


@router.post("/{lo_id}/tu-choi")
def post_tu_choi_lo(
    lo_id: int,
    payload: TuChoiLoRequest,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    return reject_lo(
        db,
        scope,
        lo_id=lo_id,
        ly_do=payload.ly_do,
        bien_loi=payload.bien_loi,
        xac_nhan=payload.xac_nhan,
        ip=get_client_ip(request),
    )


@router.post("/{lo_id}/cho-phep-dieu-chinh")
def post_cho_phep_dieu_chinh_lo(
    lo_id: int,
    request: Request,
    payload: LyDoActionRequest | None = None,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    return enable_adjustment_lo(
        db,
        scope,
        lo_id=lo_id,
        ly_do=payload.ly_do if payload else None,
        ip=get_client_ip(request),
    )


@router.post("/{lo_id}/hoan-tat-dieu-chinh")
def post_hoan_tat_dieu_chinh_lo(
    lo_id: int,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    return complete_adjustment_lo(
        db,
        scope,
        lo_id=lo_id,
        ip=get_client_ip(request),
    )


@router.post("/{lo_id}/rut-ve")
def post_rut_ve_lo_dnm(
    lo_id: int,
    request: Request,
    payload: LyDoActionRequest | None = None,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    return withdraw_dnm_lo(
        db,
        scope,
        lo_id=lo_id,
        ly_do=payload.ly_do if payload else None,
        ip=get_client_ip(request),
    )


@router.post("/{lo_id}/huy")
def post_huy_lo_dnm(
    lo_id: int,
    payload: HuyLoRequest,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    return cancel_dnm_lo(
        db,
        scope,
        lo_id=lo_id,
        ly_do=payload.ly_do,
        xac_nhan=payload.xac_nhan,
        ip=get_client_ip(request),
    )


@router.get("/{lo_id}/lich-su")
def get_lo_lich_su(
    lo_id: int,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    return {"items": list_lo_history(db, scope, lo_id=lo_id)}
