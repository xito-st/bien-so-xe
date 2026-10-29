import base64
from datetime import datetime, timezone
import hashlib
import secrets

from cryptography.fernet import Fernet
import pyotp
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from biensoxe.config import get_settings
from biensoxe.models.tai_khoan import MaKhoiPhuc2FA


def _get_fernet() -> Fernet:
    raw_key = get_settings().totp_enc_key.encode("utf-8")
    try:
        return Fernet(raw_key)
    except Exception:
        digest = hashlib.sha256(raw_key).digest()
        return Fernet(base64.urlsafe_b64encode(digest))


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def encrypt_totp_secret(secret: str) -> str:
    return _get_fernet().encrypt(secret.encode("utf-8")).decode("utf-8")


def decrypt_totp_secret(encrypted: str) -> str:
    return _get_fernet().decrypt(encrypted.encode("utf-8")).decode("utf-8")


def build_totp_provisioning_uri(secret: str, username: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(
        name=username,
        issuer_name="QuanLyBienSoXe",
    )


def verify_totp_code(secret: str, code: str, for_time: datetime | None = None) -> bool:
    cleaned = (code or "").strip().replace(" ", "")
    if not cleaned.isdigit() or len(cleaned) != 6:
        return False
    totp = pyotp.TOTP(secret)
    if for_time is not None:
        return totp.verify(cleaned, for_time=for_time, valid_window=1)
    return totp.verify(cleaned, valid_window=1)


def _hash_recovery_code(code: str) -> str:
    normalized = code.strip().upper().replace("-", "")
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def generate_recovery_codes(
    db: Session, tai_khoan_id: int, count: int = 8, now: datetime | None = None
) -> list[str]:
    """Sinh tối thiểu 8 mã khôi phục dùng 1 lần cho Admin (FR-019, AC-13)."""
    current = now or datetime.now(timezone.utc)
    db.execute(delete(MaKhoiPhuc2FA).where(MaKhoiPhuc2FA.tai_khoan_id == tai_khoan_id))
    codes: list[str] = []
    for _ in range(max(8, count)):
        raw = f"{secrets.token_hex(2).upper()}-{secrets.token_hex(2).upper()}"
        codes.append(raw)
        db.add(
            MaKhoiPhuc2FA(
                tai_khoan_id=tai_khoan_id,
                hash=_hash_recovery_code(raw),
                dung_luc=None,
                tao_luc=current,
            )
        )
    db.flush()
    return codes


def verify_and_consume_recovery_code(
    db: Session, tai_khoan_id: int, code: str, now: datetime | None = None
) -> bool:
    """Kiểm tra và tiêu thụ mã khôi phục dùng một lần (FR-019)."""
    if not code:
        return False
    current = now or datetime.now(timezone.utc)
    target_hash = _hash_recovery_code(code)
    rec = db.scalar(
        select(MaKhoiPhuc2FA).where(
            MaKhoiPhuc2FA.tai_khoan_id == tai_khoan_id,
            MaKhoiPhuc2FA.hash == target_hash,
            MaKhoiPhuc2FA.dung_luc.is_(None),
        )
    )
    if rec is None:
        return False
    rec.dung_luc = current
    db.flush()
    return True
