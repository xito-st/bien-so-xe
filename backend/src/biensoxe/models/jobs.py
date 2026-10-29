from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from biensoxe.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ImportJob(Base):
    """Lưu tạm kết quả kiểm tra import để tải file báo cáo lỗi hoặc xác nhận đặt lại biển Đã trả/Thu hồi (FR-036d, FR-042, FR-072)."""

    __tablename__ = "import_job"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tai_khoan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tai_khoan.id", ondelete="CASCADE"), nullable=False, index=True
    )
    lo_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lo.id", ondelete="CASCADE"), nullable=False, index=True
    )
    loai_import: Mapped[str] = mapped_column(String(32), nullable=False, default="TAO_BIEN")
    trang_thai: Mapped[str] = mapped_column(String(32), nullable=False)
    loi: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    dong_hop_le: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    trung_da_tra: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    het_han_luc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SyncJob(Base):
    """Hàng đợi đồng bộ lô xã lên tỉnh/thành có thử lại lũy tiến (FR-044, D-10)."""

    __tablename__ = "sync_job"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lo_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lo.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    trang_thai: Mapped[str] = mapped_column(
        String(32), nullable=False, default="CHO_DONG_BO", index=True
    )
    lan_thu: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    lan_tiep_theo_luc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True
    )
    loi_cuoi: Mapped[str | None] = mapped_column(Text, nullable=True)
    tao_luc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
