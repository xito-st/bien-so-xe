from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from biensoxe.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuditLog(Base):
    """Nhật ký thao tác bất biến (append-only) phục vụ kiểm toán (FR-021, NFR-011)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thoi_diem: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True
    )
    nguoi_dung: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    hanh_dong: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    doi_tuong: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    ket_qua: Mapped[str] = mapped_column(String(32), nullable=False)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    chi_tiet: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
