from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from biensoxe.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Lo(Base):
    """Bảng chung cho cả 3 loại lô: XA, TINH, DAT_NHA_MAY (FR-040..049, FR-061..071, G-2, G-15)."""

    __tablename__ = "lo"
    __table_args__ = (
        CheckConstraint(
            "loai IN ('XA', 'TINH', 'DAT_NHA_MAY')",
            name="ck_lo_loai",
        ),
        CheckConstraint(
            "(loai = 'XA' AND xa_ma IS NOT NULL) OR (loai IN ('TINH', 'DAT_NHA_MAY') AND xa_ma IS NULL)",
            name="ck_lo_xa_ma_theo_loai",
        ),
        CheckConstraint(
            "char_length(so_cong_van) >= 1 AND char_length(so_cong_van) <= 50",
            name="ck_lo_so_cong_van_len",
        ),
        UniqueConstraint("id", "tinh_ma", name="ux_lo_id_tinh_ma"),
        ForeignKeyConstraint(
            ["lo_cha_id", "tinh_ma"],
            ["lo.id", "lo.tinh_ma"],
            name="fk_lo_cha_cung_tinh",
            ondelete="SET NULL",
        ),
        Index(
            "ux_lo_xa_so_cv",
            "xa_ma",
            "so_cv_chuan",
            unique=True,
            postgresql_where=text("loai = 'XA'"),
        ),
        Index(
            "ux_lo_tinh_dnm_so_cv",
            "tinh_ma",
            "so_cv_chuan",
            unique=True,
            postgresql_where=text("loai IN ('TINH', 'DAT_NHA_MAY')"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    loai: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    tinh_ma: Mapped[str] = mapped_column(
        String(2), ForeignKey("tinh.ma", ondelete="RESTRICT"), nullable=False, index=True
    )
    xa_ma: Mapped[str | None] = mapped_column(
        String(8), ForeignKey("xa_phuong.ma", ondelete="RESTRICT"), nullable=True, index=True
    )
    so_cong_van: Mapped[str] = mapped_column(String(50), nullable=False)
    so_cv_chuan: Mapped[str] = mapped_column(String(50), nullable=False)
    ma_lo: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    trang_thai: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    lo_cha_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    so_lan_dat: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ghi_chu: Mapped[str | None] = mapped_column(Text, nullable=True)
    ly_do: Mapped[str | None] = mapped_column(Text, nullable=True)
    tao_boi: Mapped[str] = mapped_column(String(64), nullable=False)
    tao_luc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True
    )


class LoLichSu(Base):
    """Lịch sử chuyển trạng thái và điều chỉnh của lô (FR-048, FR-066, AC-31)."""

    __tablename__ = "lo_lich_su"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lo_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lo.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tu: Mapped[str | None] = mapped_column(String(40), nullable=True)
    den: Mapped[str] = mapped_column(String(40), nullable=False)
    nguoi: Mapped[str] = mapped_column(String(64), nullable=False)
    luc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    ly_do: Mapped[str | None] = mapped_column(Text, nullable=True)
