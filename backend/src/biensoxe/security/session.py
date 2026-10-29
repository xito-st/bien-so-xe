from datetime import datetime, timedelta, timezone
import hashlib
import secrets

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from biensoxe.config import get_settings
from biensoxe.models.tai_khoan import PhienDangNhap

SESSION_COOKIE_NAME = "sid"
CSRF_HEADER_NAME = "X-CSRF-Token"


def hash_session_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_server_session(
    db: Session,
    tai_khoan_id: int,
    ip: str | None = None,
    now: datetime | None = None,
) -> tuple[str, str]:
    """Tạo phiên phía server, trả về (raw_session_token, csrf_token) (D-05, FR-022)."""
    current = now or datetime.now(timezone.utc)
    raw_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_hex(32)
    token_hash = hash_session_token(raw_token)
    session_obj = PhienDangNhap(
        token_hash=token_hash,
        tai_khoan_id=tai_khoan_id,
        csrf_token=csrf_token,
        so_lan_sai_doi_mk=0,
        tao_luc=current,
        hoat_dong_luc=current,
        huy_luc=None,
        ip=ip or "127.0.0.1",
    )
    db.add(session_obj)
    db.flush()
    return raw_token, csrf_token


def get_valid_session(
    db: Session,
    raw_token: str | None,
    now: datetime | None = None,
    touch: bool = True,
) -> PhienDangNhap | None:
    """Kiểm tra phiên hợp lệ và chưa hết hạn không hoạt động 30 phút (FR-022, AC-16)."""
    if not raw_token:
        return None
    current = now or datetime.now(timezone.utc)
    token_hash = hash_session_token(raw_token)
    sess = db.scalar(
        select(PhienDangNhap).where(
            PhienDangNhap.token_hash == token_hash,
            PhienDangNhap.huy_luc.is_(None),
        )
    )
    if sess is None:
        return None

    hoat_dong_luc = sess.hoat_dong_luc
    if hoat_dong_luc.tzinfo is None:
        hoat_dong_luc = hoat_dong_luc.replace(tzinfo=timezone.utc)

    idle_limit = timedelta(minutes=get_settings().session_idle_timeout_minutes)
    if current - hoat_dong_luc > idle_limit:
        sess.huy_luc = current
        db.flush()
        return None

    if touch:
        sess.hoat_dong_luc = current
        db.flush()
    return sess


def revoke_session(db: Session, raw_token: str | None, now: datetime | None = None) -> None:
    if not raw_token:
        return
    current = now or datetime.now(timezone.utc)
    token_hash = hash_session_token(raw_token)
    db.execute(
        update(PhienDangNhap)
        .where(PhienDangNhap.token_hash == token_hash, PhienDangNhap.huy_luc.is_(None))
        .values(huy_luc=current)
    )


def revoke_all_user_sessions(
    db: Session, tai_khoan_id: int, now: datetime | None = None
) -> None:
    """Hủy tức thì mọi phiên đang hoạt động của tài khoản khi đổi MK / khóa / đặt lại MK (FR-012, FR-015, FR-017)."""
    current = now or datetime.now(timezone.utc)
    db.execute(
        update(PhienDangNhap)
        .where(PhienDangNhap.tai_khoan_id == tai_khoan_id, PhienDangNhap.huy_luc.is_(None))
        .values(huy_luc=current)
    )
