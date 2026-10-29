from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from biensoxe.api.deps import get_client_ip, get_current_scope
from biensoxe.db import get_db
from biensoxe.repositories.scope import ScopeFilter
from biensoxe.services.danh_muc import (
    create_loai_pt,
    create_ma_bien_tinh,
    create_nen_bien,
    delete_loai_pt,
    delete_nen_bien,
    list_loai_pt,
    list_ma_bien_tinh,
    list_nen_bien,
    list_tinh,
    list_xa_phuong,
    update_loai_pt,
    update_ma_bien_tinh,
    update_nen_bien,
)

router = APIRouter(prefix="/api/v1/danh-muc", tags=["danh-muc"])


class CreateLoaiPTRequest(BaseModel):
    seri_chu: str
    ten: str


class UpdateLoaiPTRequest(BaseModel):
    ten: str | None = None
    dang_dung: bool | None = None


class CreateNenBienRequest(BaseModel):
    ten: str
    mau_sac: str


class UpdateNenBienRequest(BaseModel):
    ten: str | None = None
    mau_sac: str | None = None
    dang_dung: bool | None = None


class CreateMaBienTinhRequest(BaseModel):
    ma_bien: str
    tinh_ma: str


class UpdateMaBienTinhRequest(BaseModel):
    ma_bien: str | None = None
    dang_dung: bool | None = None


@router.get("/tinh")
def get_tinh(
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    items = list_tinh(db)
    return {
        "items": [
            {"ma": t.ma, "ten": t.ten, "loai_don_vi": t.loai_don_vi, "stt": t.stt}
            for t in items
        ]
    }


@router.get("/xa")
def get_xa(
    tinh_ma: str | None = None,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    items = list_xa_phuong(db, scope, tinh_ma=tinh_ma)
    return {
        "items": [
            {
                "ma": x.ma,
                "ten": x.ten,
                "loai_don_vi": x.loai_don_vi,
                "tinh_ma": x.tinh_ma,
                "stt": x.stt,
            }
            for x in items
        ]
    }


@router.get("/loai-pt")
def get_loai_pt(
    include_inactive: bool = False,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    items = list_loai_pt(db, include_inactive=include_inactive or scope.is_admin)
    return {
        "items": [
            {
                "id": lp.id,
                "stt": lp.stt,
                "seri_chu": lp.seri_chu,
                "ten": lp.ten,
                "dang_dung": lp.dang_dung,
            }
            for lp in items
        ]
    }


@router.post("/loai-pt", status_code=status.HTTP_201_CREATED)
def post_loai_pt(
    payload: CreateLoaiPTRequest,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    lp = create_loai_pt(
        db,
        scope,
        seri_chu=payload.seri_chu,
        ten=payload.ten,
        ip=get_client_ip(request),
    )
    return {
        "id": lp.id,
        "stt": lp.stt,
        "seri_chu": lp.seri_chu,
        "ten": lp.ten,
        "dang_dung": lp.dang_dung,
    }


@router.put("/loai-pt/{loai_pt_id}")
def put_loai_pt(
    loai_pt_id: int,
    payload: UpdateLoaiPTRequest,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    lp = update_loai_pt(
        db,
        scope,
        loai_pt_id=loai_pt_id,
        ten=payload.ten,
        dang_dung=payload.dang_dung,
        ip=get_client_ip(request),
    )
    return {
        "id": lp.id,
        "stt": lp.stt,
        "seri_chu": lp.seri_chu,
        "ten": lp.ten,
        "dang_dung": lp.dang_dung,
    }


@router.post("/loai-pt/{loai_pt_id}/ngung-dung")
def post_ngung_dung_loai_pt(
    loai_pt_id: int,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    lp = update_loai_pt(
        db,
        scope,
        loai_pt_id=loai_pt_id,
        dang_dung=False,
        ip=get_client_ip(request),
    )
    return {
        "id": lp.id,
        "stt": lp.stt,
        "seri_chu": lp.seri_chu,
        "ten": lp.ten,
        "dang_dung": lp.dang_dung,
    }


@router.delete("/loai-pt/{loai_pt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_loai_pt_endpoint(
    loai_pt_id: int,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    delete_loai_pt(db, scope, loai_pt_id=loai_pt_id, ip=get_client_ip(request))


@router.get("/nen-bien")
def get_nen_bien(
    include_inactive: bool = False,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    items = list_nen_bien(db, include_inactive=include_inactive or scope.is_admin)
    return {
        "items": [
            {
                "id": nb.id,
                "stt": nb.stt,
                "ten": nb.ten,
                "mau_sac": nb.mau_sac,
                "dang_dung": nb.dang_dung,
            }
            for nb in items
        ]
    }


@router.post("/nen-bien", status_code=status.HTTP_201_CREATED)
def post_nen_bien(
    payload: CreateNenBienRequest,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    nb = create_nen_bien(
        db,
        scope,
        ten=payload.ten,
        mau_sac=payload.mau_sac,
        ip=get_client_ip(request),
    )
    return {
        "id": nb.id,
        "stt": nb.stt,
        "ten": nb.ten,
        "mau_sac": nb.mau_sac,
        "dang_dung": nb.dang_dung,
    }


@router.put("/nen-bien/{nen_bien_id}")
def put_nen_bien(
    nen_bien_id: int,
    payload: UpdateNenBienRequest,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    nb = update_nen_bien(
        db,
        scope,
        nen_bien_id=nen_bien_id,
        ten=payload.ten,
        mau_sac=payload.mau_sac,
        dang_dung=payload.dang_dung,
        ip=get_client_ip(request),
    )
    return {
        "id": nb.id,
        "stt": nb.stt,
        "ten": nb.ten,
        "mau_sac": nb.mau_sac,
        "dang_dung": nb.dang_dung,
    }


@router.post("/nen-bien/{nen_bien_id}/ngung-dung")
def post_ngung_dung_nen_bien(
    nen_bien_id: int,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    nb = update_nen_bien(
        db,
        scope,
        nen_bien_id=nen_bien_id,
        dang_dung=False,
        ip=get_client_ip(request),
    )
    return {
        "id": nb.id,
        "stt": nb.stt,
        "ten": nb.ten,
        "mau_sac": nb.mau_sac,
        "dang_dung": nb.dang_dung,
    }


@router.delete("/nen-bien/{nen_bien_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_nen_bien_endpoint(
    nen_bien_id: int,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    delete_nen_bien(db, scope, nen_bien_id=nen_bien_id, ip=get_client_ip(request))


@router.get("/ma-bien-tinh")
def get_ma_bien_tinh(
    tinh_ma: str | None = None,
    include_inactive: bool = False,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    items = list_ma_bien_tinh(
        db, tinh_ma=tinh_ma, include_inactive=include_inactive or scope.is_admin
    )
    return {
        "items": [
            {
                "id": m.id,
                "ma_bien": m.ma_bien,
                "tinh_ma": m.tinh_ma,
                "dang_dung": m.dang_dung,
            }
            for m in items
        ]
    }


@router.post("/ma-bien-tinh", status_code=status.HTTP_201_CREATED)
def post_ma_bien_tinh(
    payload: CreateMaBienTinhRequest,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    m = create_ma_bien_tinh(
        db,
        scope,
        ma_bien=payload.ma_bien,
        tinh_ma=payload.tinh_ma,
        ip=get_client_ip(request),
    )
    return {
        "id": m.id,
        "ma_bien": m.ma_bien,
        "tinh_ma": m.tinh_ma,
        "dang_dung": m.dang_dung,
    }


@router.put("/ma-bien-tinh/{item_id}")
def put_ma_bien_tinh(
    item_id: int,
    payload: UpdateMaBienTinhRequest,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    m = update_ma_bien_tinh(
        db,
        scope,
        item_id=item_id,
        ma_bien=payload.ma_bien,
        dang_dung=payload.dang_dung,
        ip=get_client_ip(request),
    )
    return {
        "id": m.id,
        "ma_bien": m.ma_bien,
        "tinh_ma": m.tinh_ma,
        "dang_dung": m.dang_dung,
    }


@router.post("/ma-bien-tinh/{item_id}/ngung-dung")
def post_ngung_dung_ma_bien_tinh(
    item_id: int,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    m = update_ma_bien_tinh(
        db,
        scope,
        item_id=item_id,
        dang_dung=False,
        ip=get_client_ip(request),
    )
    return {
        "id": m.id,
        "ma_bien": m.ma_bien,
        "tinh_ma": m.tinh_ma,
        "dang_dung": m.dang_dung,
    }

