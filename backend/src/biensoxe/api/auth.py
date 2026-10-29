from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from biensoxe.api.deps import AuthContext, get_auth_context, get_client_ip
from biensoxe.config import get_settings
from biensoxe.db import get_db
from biensoxe.domain.password_policy import check_password_expiration
from biensoxe.security.session import SESSION_COOKIE_NAME
from biensoxe.services.auth import (
    authenticate_user,
    change_password_four_steps,
    confirm_admin_totp,
    logout_user,
    setup_admin_totp,
    submit_forgot_password_request,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class LoginRequest(BaseModel):
    ten_dang_nhap: str
    mat_khau: str
    ma_totp: str | None = None


class DoiMatKhauRequest(BaseModel):
    mat_khau_hien_tai: str
    mat_khau_moi: str
    mat_khau_nhap_lai: str


class TotpConfirmRequest(BaseModel):
    ma_totp: str


class QuenMatKhauRequest(BaseModel):
    ten_dang_nhap: str
    lien_he: str


@router.post("/login")
def login_endpoint(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    result = authenticate_user(
        db,
        ten_dang_nhap=payload.ten_dang_nhap,
        mat_khau=payload.mat_khau,
        ma_totp=payload.ma_totp,
        ip=get_client_ip(request),
    )
    settings = get_settings()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=result["session_token"],
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    return {
        "csrf_token": result["csrf_token"],
        "user": result["user"],
    }


@router.post("/logout")
def logout_endpoint(
    response: Response,
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    logout_user(db, raw_token=ctx.raw_token, user=ctx.user, ip=ctx.ip)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return {"detail": "Đã đăng xuất."}


@router.get("/me")
def me_endpoint(ctx: AuthContext = Depends(get_auth_context)):
    user = ctx.user
    settings = get_settings()
    exp = check_password_expiration(
        user.mk_doi_luc,
        expire_days=settings.password_expire_days,
        warn_days=settings.password_warn_days,
    )
    return {
        "csrf_token": ctx.session.csrf_token,
        "user": {
            "id": user.id,
            "ten_dang_nhap": user.ten_dang_nhap,
            "vai_tro": user.vai_tro,
            "tinh_ma": user.tinh_ma,
            "xa_ma": user.xa_ma,
            "bat_buoc_doi_mk": user.bat_buoc_doi_mk or exp.is_expired,
            "yeu_cau_thiet_lap_2fa": user.vai_tro == "ADMIN" and not user.totp_da_bat,
            "canh_bao_het_han_mk": exp.should_warn,
            "so_ngay_con_lai_mk": exp.days_remaining,
        },
    }


@router.post("/doi-mat-khau")
def doi_mat_khau_endpoint(
    payload: DoiMatKhauRequest,
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    res = change_password_four_steps(
        db,
        session_obj=ctx.session,
        mat_khau_hien_tai=payload.mat_khau_hien_tai,
        mat_khau_moi=payload.mat_khau_moi,
        mat_khau_nhap_lai=payload.mat_khau_nhap_lai,
        ip=ctx.ip,
    )
    resp = JSONResponse(
        status_code=res["status_code"],
        content={"detail": res["detail"], "ok": res["ok"], "locked": res["locked"]},
    )
    if res["ok"] or res["locked"]:
        resp.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
    return resp


@router.post("/totp/thiet-lap")
def thiet_lap_totp_endpoint(
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    return setup_admin_totp(db, user=ctx.user, ip=ctx.ip)


@router.post("/totp/xac-nhan")
def xac_nhan_totp_endpoint(
    payload: TotpConfirmRequest,
    ctx: AuthContext = Depends(get_auth_context),
    db: Session = Depends(get_db),
):
    return confirm_admin_totp(db, user=ctx.user, ma_totp=payload.ma_totp, ip=ctx.ip)


@router.post("/quen-mat-khau")
def quen_mat_khau_endpoint(
    payload: QuenMatKhauRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    return submit_forgot_password_request(
        db,
        ten_dang_nhap=payload.ten_dang_nhap,
        lien_he=payload.lien_he,
        ip=get_client_ip(request),
    )

