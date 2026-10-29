from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column

from biensoxe.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaiKhoan(Base):
    """Tài khoản người dùng 3 cấp: ADMIN, TINH, XA (FR-002, FR-003, FR-004, FR-010..020)."""

    __tablename__ = "tai_khoan"
    __table_args__ = (
        CheckConstraint(
            "vai_tro IN ('ADMIN', 'TINH', 'XA')",
            name="ck_tai_khoan_vai_tro",
        ),
        CheckConstraint(
            "(vai_tro = 'ADMIN' AND tinh_ma IS NULL AND xa_ma IS NULL) OR "
            "(vai_tro = 'TINH' AND tinh_ma IS NOT NULL AND xa_ma IS NULL) OR "
            "(vai_tro = 'XA' AND tinh_ma IS NOT NULL AND xa_ma IS NOT NULL)",
            name="ck_tai_khoan_don_vi_theo_vai_tro",
        ),
        ForeignKeyConstraint(
            ["xa_ma", "tinh_ma"],
            ["xa_phuong.ma", "xa_phuong.tinh_ma"],
            name="fk_tai_khoan_xa_thuoc_tinh",
            ondelete="RESTRICT",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ten_dang_nhap: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    vai_tro: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    tinh_ma: Mapped[str | None] = mapped_column(
        String(2), ForeignKey("tinh.ma", ondelete="RESTRICT"), nullable=True, index=True
    )
    xa_ma: Mapped[str | None] = mapped_column(
        String(8), ForeignKey("xa_phuong.ma", ondelete="RESTRICT"), nullable=True, index=True
    )
    mat_khau_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    bat_buoc_doi_mk: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    mk_doi_luc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    so_lan_sai: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    khoa_den: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    khoa_thu_cong: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ly_do_khoa: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_secret_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    totp_da_bat: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tao_boi: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tao_luc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class LichSuMatKhau(Base):
    """Lưu lịch sử mật khẩu để chặn trùng 5 mật khẩu gần nhất (FR-013)."""

    __tablename__ = "lich_su_mat_khau"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tai_khoan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tai_khoan.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hash: Mapped[str] = mapped_column(String(255), nullable=False)
    tao_luc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class MaKhoiPhuc2FA(Base):
    """Mã khôi phục dùng một lần cho 2FA Admin (FR-019)."""

    __tablename__ = "ma_khoi_phuc_2fa"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tai_khoan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tai_khoan.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hash: Mapped[str] = mapped_column(String(255), nullable=False)
    dung_luc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tao_luc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


class PhienDangNhap(Base):
    """Phiên phía server có thể hủy tức thì và hết hạn idle 30 phút (FR-015, FR-017, FR-022, D-05)."""

    __tablename__ = "session"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    tai_khoan_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("tai_khoan.id", ondelete="CASCADE"), nullable=False, index=True
    )
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    so_lan_sai_doi_mk: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tao_luc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    hoat_dong_luc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    huy_luc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)


class YeuCauCapLaiMK(Base):
    """Hàng đợi yêu cầu quên mật khẩu cho tỉnh/thành và xã/phường (FR-018)."""

    __tablename__ = "yeu_cau_cap_lai_mk"
    __table_args__ = (
        CheckConstraint(
            "trang_thai IN ('CHO_XU_LY', 'DA_DAT_LAI', 'TU_CHOI')",
            name="ck_yeu_cau_cap_lai_mk_trang_thai",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ten_dang_nhap: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    lien_he: Mapped[str] = mapped_column(String(255), nullable=False)
    trang_thai: Mapped[str] = mapped_column(String(20), nullable=False, default="CHO_XU_LY")
    xu_ly_boi: Mapped[str | None] = mapped_column(String(64), nullable=True)
    xu_ly_luc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ly_do_tu_choi: Mapped[str | None] = mapped_column(Text, nullable=True)
    tao_luc: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, index=True
    )
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

