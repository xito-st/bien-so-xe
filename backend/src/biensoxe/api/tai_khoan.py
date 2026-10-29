from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from biensoxe.api.deps import get_client_ip, get_current_scope
from biensoxe.db import get_db
from biensoxe.models.tai_khoan import TaiKhoan, YeuCauCapLaiMK
from biensoxe.repositories.scope import ScopeFilter
from biensoxe.services.tai_khoan import (
    create_supplementary_account,
    list_forgot_password_requests,
    list_tai_khoan,
    lock_account_manually,
    process_forgot_password_request,
    reset_account_password,
    unlock_account,
)

router = APIRouter(prefix="/api/v1", tags=["tai-khoan"])


class CreateTaiKhoanRequest(BaseModel):
    ten_dang_nhap: str
    vai_tro: str
    tinh_ma: str | None = None
    xa_ma: str | None = None


class KhoaTaiKhoanRequest(BaseModel):
    ly_do: str


class XuLyQuenMatKhauRequest(BaseModel):
    hanh_dong: str  # 'DAT_LAI' | 'TU_CHOI'
    ly_do_tu_choi: str | None = None


def _serialize_tk(tk: TaiKhoan) -> dict:
    """Không bao giờ trả mật khẩu hoặc băm mật khẩu ra API (FR-017, FR-020)."""
    return {
        "id": tk.id,
        "ten_dang_nhap": tk.ten_dang_nhap,
        "vai_tro": tk.vai_tro,
        "tinh_ma": tk.tinh_ma,
        "xa_ma": tk.xa_ma,
        "bat_buoc_doi_mk": tk.bat_buoc_doi_mk,
        "mk_doi_luc": tk.mk_doi_luc.isoformat() if tk.mk_doi_luc else None,
        "so_lan_sai": tk.so_lan_sai,
        "khoa_den": tk.khoa_den.isoformat() if tk.khoa_den else None,
        "khoa_thu_cong": tk.khoa_thu_cong,
        "ly_do_khoa": tk.ly_do_khoa,
        "totp_da_bat": tk.totp_da_bat,
        "tao_boi": tk.tao_boi,
        "tao_luc": tk.tao_luc.isoformat() if tk.tao_luc else None,
    }


def _serialize_yc(yc: YeuCauCapLaiMK) -> dict:
    return {
        "id": yc.id,
        "ten_dang_nhap": yc.ten_dang_nhap,
        "lien_he": yc.lien_he,
        "trang_thai": yc.trang_thai,
        "xu_ly_boi": yc.xu_ly_boi,
        "xu_ly_luc": yc.xu_ly_luc.isoformat() if yc.xu_ly_luc else None,
        "ly_do_tu_choi": yc.ly_do_tu_choi,
        "tao_luc": yc.tao_luc.isoformat() if yc.tao_luc else None,
        "ip": yc.ip,
    }


@router.get("/tai-khoan")
@router.get("/admin/tai-khoan")
def get_tai_khoan_list(
    vai_tro: str | None = None,
    tinh_ma: str | None = None,
    xa_ma: str | None = None,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    items = list_tai_khoan(
        db,
        scope,
        vai_tro=vai_tro,
        tinh_ma=tinh_ma,
        xa_ma=xa_ma,
        q=q,
        limit=limit,
        offset=offset,
    )
    return {"items": [_serialize_tk(tk) for tk in items]}


@router.post("/tai-khoan", status_code=status.HTTP_201_CREATED)
@router.post("/admin/tai-khoan", status_code=status.HTTP_201_CREATED)
def post_tao_tai_khoan(
    payload: CreateTaiKhoanRequest,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    tk = create_supplementary_account(
        db,
        scope,
        ten_dang_nhap=payload.ten_dang_nhap,
        vai_tro=payload.vai_tro,
        tinh_ma=payload.tinh_ma,
        xa_ma=payload.xa_ma,
        ip=get_client_ip(request),
    )
    return _serialize_tk(tk)


@router.post("/admin/tai-khoan/{tai_khoan_id}/khoa")
def post_khoa_tai_khoan(
    tai_khoan_id: int,
    payload: KhoaTaiKhoanRequest,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    tk = lock_account_manually(
        db,
        scope,
        tai_khoan_id=tai_khoan_id,
        ly_do=payload.ly_do,
        ip=get_client_ip(request),
    )
    return _serialize_tk(tk)


@router.post("/admin/tai-khoan/{tai_khoan_id}/mo-khoa")
def post_mo_khoa_tai_khoan(
    tai_khoan_id: int,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    tk = unlock_account(
        db,
        scope,
        tai_khoan_id=tai_khoan_id,
        ip=get_client_ip(request),
    )
    return _serialize_tk(tk)


@router.post("/admin/tai-khoan/{tai_khoan_id}/dat-lai-mat-khau")
def post_dat_lai_mat_khau(
    tai_khoan_id: int,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    tk = reset_account_password(
        db,
        scope,
        tai_khoan_id=tai_khoan_id,
        ip=get_client_ip(request),
    )
    return _serialize_tk(tk)


@router.get("/admin/yeu-cau-cap-lai-mk")
def get_yeu_cau_cap_lai_mk(
    trang_thai: str | None = None,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    items = list_forgot_password_requests(db, scope, trang_thai=trang_thai)
    return {"items": [_serialize_yc(yc) for yc in items]}


@router.post("/admin/yeu-cau-cap-lai-mk/{req_id}")
def post_xu_ly_yeu_cau_cap_lai_mk(
    req_id: int,
    payload: XuLyQuenMatKhauRequest,
    request: Request,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    yc = process_forgot_password_request(
        db,
        scope,
        req_id=req_id,
        hanh_dong=payload.hanh_dong,
        ly_do_tu_choi=payload.ly_do_tu_choi,
        ip=get_client_ip(request),
    )
    return _serialize_yc(yc)

