from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from biensoxe.db import Base


class Tinh(Base):
    """Danh mục 34 tỉnh/thành phố (FR-001)."""

    __tablename__ = "tinh"
    __table_args__ = (
        CheckConstraint(
            "loai_don_vi IN ('Tỉnh', 'Thành phố')",
            name="ck_tinh_loai_don_vi",
        ),
    )

    ma: Mapped[str] = mapped_column(String(2), primary_key=True)
    ten: Mapped[str] = mapped_column(String(150), nullable=False)
    loai_don_vi: Mapped[str] = mapped_column(String(30), nullable=False)
    stt: Mapped[int] = mapped_column(Integer, nullable=False)


class XaPhuong(Base):
    """Danh mục 3.321 xã/phường/đặc khu (FR-001, FR-004)."""

    __tablename__ = "xa_phuong"
    __table_args__ = (
        CheckConstraint(
            "loai_don_vi IN ('Xã', 'Phường', 'Đặc khu')",
            name="ck_xa_phuong_loai_don_vi",
        ),
        UniqueConstraint("ma", "tinh_ma", name="ux_xa_phuong_ma_tinh"),
    )

    ma: Mapped[str] = mapped_column(String(8), primary_key=True)
    ten: Mapped[str] = mapped_column(String(200), nullable=False)
    loai_don_vi: Mapped[str] = mapped_column(String(30), nullable=False)
    tinh_ma: Mapped[str] = mapped_column(
        String(2), ForeignKey("tinh.ma", ondelete="RESTRICT"), nullable=False, index=True
    )
    stt: Mapped[int] = mapped_column(Integer, nullable=False)


class LoaiPT(Base):
    """Danh mục loại phương tiện suy ra từ SeriChu (FR-032, FR-033, FR-037)."""

    __tablename__ = "loai_pt"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stt: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    seri_chu: Mapped[str] = mapped_column(String(10), nullable=False, unique=True, index=True)
    ten: Mapped[str] = mapped_column(String(100), nullable=False)
    dang_dung: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class NenBien(Base):
    """Danh mục nền biển và màu sắc tự hiển thị (FR-034, FR-037)."""

    __tablename__ = "nen_bien"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    stt: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    ten: Mapped[str] = mapped_column(String(150), nullable=False, unique=True)
    mau_sac: Mapped[str] = mapped_column(String(50), nullable=False)
    dang_dung: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class MaBienTinh(Base):
    """Danh mục mã biển (D1D2) -> tỉnh/thành phục vụ cảnh báo ngoại tỉnh (FR-038, G-16)."""

    __tablename__ = "ma_bien_tinh"
    __table_args__ = (
        UniqueConstraint("ma_bien", "tinh_ma", name="ux_ma_bien_tinh"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ma_bien: Mapped[str] = mapped_column(String(2), nullable=False)
    tinh_ma: Mapped[str] = mapped_column(
        String(2), ForeignKey("tinh.ma", ondelete="RESTRICT"), nullable=False, index=True
    )
    dang_dung: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

