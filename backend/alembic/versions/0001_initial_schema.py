"""Initial schema: danh muc, tai khoan, session, audit_log

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-28 22:35:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tinh",
        sa.Column("ma", sa.String(length=2), nullable=False),
        sa.Column("ten", sa.String(length=150), nullable=False),
        sa.Column("loai_don_vi", sa.String(length=30), nullable=False),
        sa.Column("stt", sa.Integer(), nullable=False),
        sa.CheckConstraint("loai_don_vi IN ('Tỉnh', 'Thành phố')", name="ck_tinh_loai_don_vi"),
        sa.PrimaryKeyConstraint("ma"),
    )

    op.create_table(
        "xa_phuong",
        sa.Column("ma", sa.String(length=8), nullable=False),
        sa.Column("ten", sa.String(length=200), nullable=False),
        sa.Column("loai_don_vi", sa.String(length=30), nullable=False),
        sa.Column("tinh_ma", sa.String(length=2), nullable=False),
        sa.Column("stt", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "loai_don_vi IN ('Xã', 'Phường', 'Đặc khu')",
            name="ck_xa_phuong_loai_don_vi",
        ),
        sa.ForeignKeyConstraint(["tinh_ma"], ["tinh.ma"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("ma"),
        sa.UniqueConstraint("ma", "tinh_ma", name="ux_xa_phuong_ma_tinh"),
    )
    op.create_index("ix_xa_phuong_tinh_ma", "xa_phuong", ["tinh_ma"])

    op.create_table(
        "loai_pt",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stt", sa.Integer(), nullable=False),
        sa.Column("seri_chu", sa.String(length=10), nullable=False),
        sa.Column("ten", sa.String(length=100), nullable=False),
        sa.Column("dang_dung", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stt"),
        sa.UniqueConstraint("seri_chu"),
    )
    op.create_index("ix_loai_pt_seri_chu", "loai_pt", ["seri_chu"])

    op.create_table(
        "nen_bien",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stt", sa.Integer(), nullable=False),
        sa.Column("ten", sa.String(length=150), nullable=False),
        sa.Column("mau_sac", sa.String(length=50), nullable=False),
        sa.Column("dang_dung", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stt"),
        sa.UniqueConstraint("ten"),
    )

    op.create_table(
        "ma_bien_tinh",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ma_bien", sa.String(length=2), nullable=False),
        sa.Column("tinh_ma", sa.String(length=2), nullable=False),
        sa.Column("dang_dung", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["tinh_ma"], ["tinh.ma"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ma_bien", "tinh_ma", name="ux_ma_bien_tinh"),
    )
    op.create_index("ix_ma_bien_tinh_tinh_ma", "ma_bien_tinh", ["tinh_ma"])

    op.create_table(
        "tai_khoan",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ten_dang_nhap", sa.String(length=64), nullable=False),
        sa.Column("vai_tro", sa.String(length=16), nullable=False),
        sa.Column("tinh_ma", sa.String(length=2), nullable=True),
        sa.Column("xa_ma", sa.String(length=8), nullable=True),
        sa.Column("mat_khau_hash", sa.String(length=255), nullable=False),
        sa.Column("bat_buoc_doi_mk", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("mk_doi_luc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("so_lan_sai", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("khoa_den", sa.DateTime(timezone=True), nullable=True),
        sa.Column("khoa_thu_cong", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("ly_do_khoa", sa.Text(), nullable=True),
        sa.Column("totp_secret_enc", sa.Text(), nullable=True),
        sa.Column("totp_da_bat", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("tao_boi", sa.String(length=64), nullable=True),
        sa.Column("tao_luc", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("vai_tro IN ('ADMIN', 'TINH', 'XA')", name="ck_tai_khoan_vai_tro"),
        sa.CheckConstraint(
            "(vai_tro = 'ADMIN' AND tinh_ma IS NULL AND xa_ma IS NULL) OR "
            "(vai_tro = 'TINH' AND tinh_ma IS NOT NULL AND xa_ma IS NULL) OR "
            "(vai_tro = 'XA' AND tinh_ma IS NOT NULL AND xa_ma IS NOT NULL)",
            name="ck_tai_khoan_don_vi_theo_vai_tro",
        ),
        sa.ForeignKeyConstraint(["tinh_ma"], ["tinh.ma"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["xa_ma"], ["xa_phuong.ma"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["xa_ma", "tinh_ma"],
            ["xa_phuong.ma", "xa_phuong.tinh_ma"],
            name="fk_tai_khoan_xa_thuoc_tinh",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ten_dang_nhap"),
    )
    op.create_index("ix_tai_khoan_ten_dang_nhap", "tai_khoan", ["ten_dang_nhap"])
    op.create_index("ix_tai_khoan_vai_tro", "tai_khoan", ["vai_tro"])
    op.create_index("ix_tai_khoan_tinh_ma", "tai_khoan", ["tinh_ma"])
    op.create_index("ix_tai_khoan_xa_ma", "tai_khoan", ["xa_ma"])

    op.create_table(
        "lich_su_mat_khau",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tai_khoan_id", sa.Integer(), nullable=False),
        sa.Column("hash", sa.String(length=255), nullable=False),
        sa.Column("tao_luc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tai_khoan_id"], ["tai_khoan.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lich_su_mat_khau_tai_khoan_id", "lich_su_mat_khau", ["tai_khoan_id"])

    op.create_table(
        "ma_khoi_phuc_2fa",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tai_khoan_id", sa.Integer(), nullable=False),
        sa.Column("hash", sa.String(length=255), nullable=False),
        sa.Column("dung_luc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tao_luc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["tai_khoan_id"], ["tai_khoan.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ma_khoi_phuc_2fa_tai_khoan_id", "ma_khoi_phuc_2fa", ["tai_khoan_id"])

    op.create_table(
        "session",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("tai_khoan_id", sa.Integer(), nullable=False),
        sa.Column("csrf_token", sa.String(length=64), nullable=False),
        sa.Column("so_lan_sai_doi_mk", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("tao_luc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hoat_dong_luc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("huy_luc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["tai_khoan_id"], ["tai_khoan.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    op.create_index("ix_session_tai_khoan_id", "session", ["tai_khoan_id"])

    op.create_table(
        "yeu_cau_cap_lai_mk",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ten_dang_nhap", sa.String(length=64), nullable=False),
        sa.Column("lien_he", sa.String(length=255), nullable=False),
        sa.Column("trang_thai", sa.String(length=20), nullable=False, server_default="CHO_XU_LY"),
        sa.Column("xu_ly_boi", sa.String(length=64), nullable=True),
        sa.Column("xu_ly_luc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ly_do_tu_choi", sa.Text(), nullable=True),
        sa.Column("tao_luc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            "trang_thai IN ('CHO_XU_LY', 'DA_DAT_LAI', 'TU_CHOI')",
            name="ck_yeu_cau_cap_lai_mk_trang_thai",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_yeu_cau_cap_lai_mk_ten_dang_nhap", "yeu_cau_cap_lai_mk", ["ten_dang_nhap"])
    op.create_index("ix_yeu_cau_cap_lai_mk_tao_luc", "yeu_cau_cap_lai_mk", ["tao_luc"])
    op.create_index("ix_yeu_cau_cap_lai_mk_ip", "yeu_cau_cap_lai_mk", ["ip"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("thoi_diem", sa.DateTime(timezone=True), nullable=False),
        sa.Column("nguoi_dung", sa.String(length=64), nullable=False),
        sa.Column("hanh_dong", sa.String(length=64), nullable=False),
        sa.Column("doi_tuong", sa.String(length=128), nullable=False),
        sa.Column("ket_qua", sa.String(length=32), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("chi_tiet", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_thoi_diem", "audit_log", ["thoi_diem"])
    op.create_index("ix_audit_log_nguoi_dung", "audit_log", ["nguoi_dung"])
    op.create_index("ix_audit_log_hanh_dong", "audit_log", ["hanh_dong"])
    op.create_index("ix_audit_log_doi_tuong", "audit_log", ["doi_tuong"])

    op.execute(
        """
        CREATE OR REPLACE FUNCTION fn_prevent_audit_log_mutation()
        RETURNS trigger AS $$
        BEGIN
            IF TG_OP = 'TRUNCATE' AND current_setting('biensoxe.allow_test_truncate', true) = '1' THEN
                RETURN NULL;
            END IF;
            RAISE EXCEPTION 'audit_log là nhật ký bất biến, không được phép sửa hoặc xóa (FR-021)';
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_audit_log_no_update_delete
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION fn_prevent_audit_log_mutation();

        CREATE TRIGGER trg_audit_log_no_truncate
        BEFORE TRUNCATE ON audit_log
        FOR EACH STATEMENT EXECUTE FUNCTION fn_prevent_audit_log_mutation();
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_audit_log_no_truncate ON audit_log;
        DROP TRIGGER IF EXISTS trg_audit_log_no_update_delete ON audit_log;
        DROP FUNCTION IF EXISTS fn_prevent_audit_log_mutation();
        """
    )
    op.drop_table("audit_log")
    op.drop_table("yeu_cau_cap_lai_mk")
    op.drop_table("session")
    op.drop_table("ma_khoi_phuc_2fa")
    op.drop_table("lich_su_mat_khau")
    op.drop_table("tai_khoan")
    op.drop_table("ma_bien_tinh")
    op.drop_table("nen_bien")
    op.drop_table("loai_pt")
    op.drop_table("xa_phuong")
    op.drop_table("tinh")
