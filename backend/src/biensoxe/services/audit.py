from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from biensoxe.logging import scrub_value
from biensoxe.models.audit import AuditLog


def log_audit(
    db: Session,
    *,
    nguoi_dung: str,
    hanh_dong: str,
    doi_tuong: str,
    ket_qua: str = "THANH_CONG",
    ip: str | None = None,
    chi_tiet: dict[str, Any] | None = None,
    thoi_diem: datetime | None = None,
) -> AuditLog:
    """Ghi nhật ký thao tác bất biến, tự động che các trường nhạy cảm (FR-020, FR-021)."""
    entry = AuditLog(
        thoi_diem=thoi_diem or datetime.now(timezone.utc),
        nguoi_dung=nguoi_dung,
        hanh_dong=hanh_dong,
        doi_tuong=doi_tuong,
        ket_qua=ket_qua,
        ip=ip or "127.0.0.1",
        chi_tiet=scrub_value(chi_tiet) if chi_tiet is not None else None,
    )
    db.add(entry)
    return entry


write_audit_log = log_audit
