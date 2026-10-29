from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from biensoxe.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BanGiao(Base):
    """Biên bản bàn giao biển số từng phần từ tỉnh về xã/phường (FR-068, AC-42)."""

    __tablename__ = "ban_giao"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lo_xa_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lo.id", ondelete="CASCADE"), nullable=False, index=True
    )
    so_bien_ban: Mapped[str] = mapped_column(String(100), nullable=False)
    nguoi_nhan: Mapped[str] = mapped_column(String(150), nullable=False)
    chuc_vu: Mapped[str] = mapped_column(String(150), nullable=False)
    ngay_nhan: Mapped[date] = mapped_column(Date, nullable=False)
    tao_boi: Mapped[str] = mapped_column(String(64), nullable=False)
    tao_luc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class Bien(Base):
    """Biển số xe với 2 trục trạng thái (tinh_trang, giao) và cờ giữ chỗ nguyên tử (FR-030..038, 4.I, §5.3)."""

    __tablename__ = "bien"
    __table_args__ = (
        CheckConstraint(
            "tinh_trang IN ('Chưa đặt', 'Đã đặt', 'Tồn kho tỉnh', 'Tồn kho xã', 'Đã hủy')",
            name="ck_bien_tinh_trang",
        ),
        CheckConstraint(
            "giao IS NULL OR giao IN ('Chưa trả', 'Đã trả', 'Thu hồi về xã')",
            name="ck_bien_giao",
        ),
        Index(
            "ux_bien_lo_so",
            "lo_id",
            "bien_so_day_du",
            unique=True,
            postgresql_where=text("tinh_trang <> 'Đã hủy'"),
        ),
        Index(
            "ux_bien_giu_cho",
            "tinh_ma",
            "bien_so_day_du",
            unique=True,
            postgresql_where=text("giu_cho"),
        ),
        Index(
            "ix_bien_tinh_bien_so_pattern",
            "tinh_ma",
            "bien_so_day_du",
            postgresql_ops={"bien_so_day_du": "varchar_pattern_ops"},
        ),
        Index(
            "ix_bien_xa_bien_so_pattern",
            "xa_ma",
            "bien_so_day_du",
            postgresql_ops={"bien_so_day_du": "varchar_pattern_ops"},
        ),
        Index("ix_bien_tinh_seri_chu", "tinh_ma", "seri_chu"),
        Index("ix_bien_tinh_dau_so", "tinh_ma", "dau_so"),
        Index("ix_bien_tinh_tinh_trang", "tinh_ma", "tinh_trang"),
        Index("ix_bien_tinh_ngoai_tinh", "tinh_ma", "ngoai_tinh"),
        Index("ix_bien_xa_giao", "xa_ma", "giao"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lo_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("lo.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stt: Mapped[int] = mapped_column(Integer, nullable=False)
    bien_so_day_du: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    ma_tinh_bien: Mapped[str] = mapped_column(String(2), nullable=False, index=True)
    seri_chu: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    seri_so: Mapped[str] = mapped_column(String(10), nullable=False)
    dau_so: Mapped[str] = mapped_column(String(3), nullable=False, index=True)
    loai_pt_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("loai_pt.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    nen_bien_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("nen_bien.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    ghi_chu: Mapped[str | None] = mapped_column(Text, nullable=True)
    tinh_ma: Mapped[str] = mapped_column(
        String(2), ForeignKey("tinh.ma", ondelete="RESTRICT"), nullable=False, index=True
    )
    xa_ma: Mapped[str | None] = mapped_column(
        String(8), ForeignKey("xa_phuong.ma", ondelete="RESTRICT"), nullable=True, index=True
    )
    tinh_trang: Mapped[str] = mapped_column(
        String(32), nullable=False, default="Chưa đặt", index=True
    )
    giao: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    ngay_gio_tra: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ban_giao_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("ban_giao.id", ondelete="SET NULL"), nullable=True, index=True
    )
    ngay_nhap_kho: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ly_do_huy: Mapped[str | None] = mapped_column(Text, nullable=True)
    ly_do_thu_hoi: Mapped[str | None] = mapped_column(Text, nullable=True)
    dat_lai_xac_nhan: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ngoai_tinh: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    loi_ly_do: Mapped[str | None] = mapped_column(Text, nullable=True)
    giu_cho: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class BienLichSu(Base):
    """Lịch sử sự kiện của từng biển số (nhập kho, chuyển xã, trả, thu hồi, hủy, điều chỉnh) (FR-054, FR-066)."""

    __tablename__ = "bien_lich_su"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bien_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("bien.id", ondelete="CASCADE"), nullable=False, index=True
    )
    su_kien: Mapped[str] = mapped_column(String(64), nullable=False)
    tu: Mapped[str | None] = mapped_column(String(40), nullable=True)
    den: Mapped[str] = mapped_column(String(40), nullable=False)
    ly_do: Mapped[str | None] = mapped_column(Text, nullable=True)
    nguoi: Mapped[str] = mapped_column(String(64), nullable=False)
    luc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
