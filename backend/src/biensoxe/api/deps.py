from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from biensoxe.config import get_settings
from biensoxe.db import get_db
from biensoxe.domain.password_policy import check_password_expiration
from biensoxe.models.tai_khoan import PhienDangNhap, TaiKhoan
from biensoxe.repositories.scope import ScopeFilter
from biensoxe.security.csrf import verify_csrf_if_required
from biensoxe.security.session import SESSION_COOKIE_NAME, get_valid_session


@dataclass
class AuthContext:
    user: TaiKhoan
    session: PhienDangNhap
    raw_token: str
    ip: str


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


def _extract_raw_token(request: Request) -> str | None:
    token = request.cookies.get("__Host-sid") or request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        return token
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return None


def get_auth_context(
    request: Request,
    db: Session = Depends(get_db),
) -> AuthContext:
    """Xác thực phiên đăng nhập (cho phép cả khi đang ở bước bắt buộc đổi mật khẩu hoặc thiết lập 2FA)."""
    raw_token = _extract_raw_token(request)
    now = datetime.now(timezone.utc)
    sess = get_valid_session(db, raw_token, now=now, touch=True)
    if sess is None or raw_token is None:
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên đăng nhập không hợp lệ hoặc đã hết hạn 30 phút không hoạt động.",
        )

    user = db.scalar(select(TaiKhoan).where(TaiKhoan.id == sess.tai_khoan_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản không tồn tại.",
        )

    if user.khoa_thu_cong:
        sess.huy_luc = now
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị khóa bởi quản trị viên.",
        )

    if user.khoa_den is not None:
        khoa_den = user.khoa_den
        if khoa_den.tzinfo is None:
            khoa_den = khoa_den.replace(tzinfo=timezone.utc)
        if now < khoa_den:
            sess.huy_luc = now
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tài khoản đang bị khóa tạm thời.",
            )

    verify_csrf_if_required(request, sess.csrf_token)
    db.commit()
    return AuthContext(
        user=user,
        session=sess,
        raw_token=raw_token,
        ip=get_client_ip(request),
    )


def get_current_scope(
    ctx: AuthContext = Depends(get_auth_context),
) -> ScopeFilter:
    """
    Dependency bắt buộc tài khoản đã đổi mật khẩu lần đầu (FR-011), chưa hết hạn 90 ngày (FR-013),
    và Admin đã thiết lập 2FA (FR-019), trả về ScopeFilter (FR-023).
    """
    user = ctx.user
    if user.bat_buoc_doi_mk:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bắt buộc đổi mật khẩu trước khi truy cập hệ thống (FR-011).",
        )

    settings = get_settings()
    exp = check_password_expiration(
        user.mk_doi_luc,
        expire_days=settings.password_expire_days,
        warn_days=settings.password_warn_days,
    )
    if exp.is_expired:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mật khẩu đã hết hạn 90 ngày. Bắt buộc đổi mật khẩu (FR-013).",
        )

    if user.vai_tro == "ADMIN" and not user.totp_da_bat:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản Admin bắt buộc thiết lập xác thực 2 lớp (2FA) trước khi sử dụng (FR-019).",
        )

    return ScopeFilter(
        user_id=user.id,
        ten_dang_nhap=user.ten_dang_nhap,
        vai_tro=user.vai_tro,
        tinh_ma=user.tinh_ma,
        xa_ma=user.xa_ma,
    )

