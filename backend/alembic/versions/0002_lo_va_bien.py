"""Lo, bien, ban_giao, import_job, sync_job

Revision ID: 0002_lo_va_bien
Revises: 0001_initial_schema
Create Date: 2026-10-28 22:52:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_lo_va_bien"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lo",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("loai", sa.String(length=20), nullable=False),
        sa.Column("tinh_ma", sa.String(length=2), nullable=False),
        sa.Column("xa_ma", sa.String(length=8), nullable=True),
        sa.Column("so_cong_van", sa.String(length=50), nullable=False),
        sa.Column("so_cv_chuan", sa.String(length=50), nullable=False),
        sa.Column("ma_lo", sa.String(length=80), nullable=False),
        sa.Column("trang_thai", sa.String(length=40), nullable=False),
        sa.Column("lo_cha_id", sa.Integer(), nullable=True),
        sa.Column("so_lan_dat", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("ghi_chu", sa.Text(), nullable=True),
        sa.Column("ly_do", sa.Text(), nullable=True),
        sa.Column("tao_boi", sa.String(length=64), nullable=False),
        sa.Column("tao_luc", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("loai IN ('XA', 'TINH', 'DAT_NHA_MAY')", name="ck_lo_loai"),
        sa.CheckConstraint(
            "(loai = 'XA' AND xa_ma IS NOT NULL) OR (loai IN ('TINH', 'DAT_NHA_MAY') AND xa_ma IS NULL)",
            name="ck_lo_xa_ma_theo_loai",
        ),
        sa.CheckConstraint(
            "char_length(so_cong_van) >= 1 AND char_length(so_cong_van) <= 50",
            name="ck_lo_so_cong_van_len",
        ),
        sa.ForeignKeyConstraint(["tinh_ma"], ["tinh.ma"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["xa_ma"], ["xa_phuong.ma"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "tinh_ma", name="ux_lo_id_tinh_ma"),
        sa.UniqueConstraint("ma_lo"),
    )
    op.create_foreign_key(
        "fk_lo_cha_cung_tinh",
        "lo",
        "lo",
        ["lo_cha_id", "tinh_ma"],
        ["id", "tinh_ma"],
        ondelete="SET NULL",
    )
    op.create_index("ix_lo_loai", "lo", ["loai"])
    op.create_index("ix_lo_tinh_ma", "lo", ["tinh_ma"])
    op.create_index("ix_lo_xa_ma", "lo", ["xa_ma"])
    op.create_index("ix_lo_ma_lo", "lo", ["ma_lo"])
    op.create_index("ix_lo_trang_thai", "lo", ["trang_thai"])
    op.create_index("ix_lo_lo_cha_id", "lo", ["lo_cha_id"])
    op.create_index("ix_lo_tao_luc", "lo", ["tao_luc"])
    op.create_index(
        "ux_lo_xa_so_cv",
        "lo",
        ["xa_ma", "so_cv_chuan"],
        unique=True,
        postgresql_where=sa.text("loai = 'XA'"),
    )
    op.create_index(
        "ux_lo_tinh_dnm_so_cv",
        "lo",
        ["tinh_ma", "so_cv_chuan"],
        unique=True,
        postgresql_where=sa.text("loai IN ('TINH', 'DAT_NHA_MAY')"),
    )

    op.create_table(
        "lo_lich_su",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lo_id", sa.Integer(), nullable=False),
        sa.Column("tu", sa.String(length=40), nullable=True),
        sa.Column("den", sa.String(length=40), nullable=False),
        sa.Column("nguoi", sa.String(length=64), nullable=False),
        sa.Column("luc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ly_do", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["lo_id"], ["lo.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_lo_lich_su_lo_id", "lo_lich_su", ["lo_id"])

    op.create_table(
        "ban_giao",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lo_xa_id", sa.Integer(), nullable=False),
        sa.Column("so_bien_ban", sa.String(length=100), nullable=False),
        sa.Column("nguoi_nhan", sa.String(length=150), nullable=False),
        sa.Column("chuc_vu", sa.String(length=150), nullable=False),
        sa.Column("ngay_nhan", sa.Date(), nullable=False),
        sa.Column("tao_boi", sa.String(length=64), nullable=False),
        sa.Column("tao_luc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["lo_xa_id"], ["lo.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ban_giao_lo_xa_id", "ban_giao", ["lo_xa_id"])

    op.create_table(
        "bien",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lo_id", sa.Integer(), nullable=False),
        sa.Column("stt", sa.Integer(), nullable=False),
        sa.Column("bien_so_day_du", sa.String(length=32), nullable=False),
        sa.Column("ma_tinh_bien", sa.String(length=2), nullable=False),
        sa.Column("seri_chu", sa.String(length=10), nullable=False),
        sa.Column("seri_so", sa.String(length=10), nullable=False),
        sa.Column("dau_so", sa.String(length=3), nullable=False),
        sa.Column("loai_pt_id", sa.Integer(), nullable=False),
        sa.Column("nen_bien_id", sa.Integer(), nullable=False),
        sa.Column("ghi_chu", sa.Text(), nullable=True),
        sa.Column("tinh_ma", sa.String(length=2), nullable=False),
        sa.Column("xa_ma", sa.String(length=8), nullable=True),
        sa.Column("tinh_trang", sa.String(length=32), nullable=False, server_default="Chưa đặt"),
        sa.Column("giao", sa.String(length=32), nullable=True),
        sa.Column("ngay_gio_tra", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ban_giao_id", sa.Integer(), nullable=True),
        sa.Column("ngay_nhap_kho", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ly_do_huy", sa.Text(), nullable=True),
        sa.Column("ly_do_thu_hoi", sa.Text(), nullable=True),
        sa.Column("dat_lai_xac_nhan", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("ngoai_tinh", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("loi_ly_do", sa.Text(), nullable=True),
        sa.Column("giu_cho", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.CheckConstraint(
            "tinh_trang IN ('Chưa đặt', 'Đã đặt', 'Tồn kho tỉnh', 'Tồn kho xã', 'Đã hủy')",
            name="ck_bien_tinh_trang",
        ),
        sa.CheckConstraint(
            "giao IS NULL OR giao IN ('Chưa trả', 'Đã trả', 'Thu hồi về xã')",
            name="ck_bien_giao",
        ),
        sa.ForeignKeyConstraint(["ban_giao_id"], ["ban_giao.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lo_id"], ["lo.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["loai_pt_id"], ["loai_pt.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["nen_bien_id"], ["nen_bien.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tinh_ma"], ["tinh.ma"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["xa_ma"], ["xa_phuong.ma"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bien_lo_id", "bien", ["lo_id"])
    op.create_index("ix_bien_bien_so_day_du", "bien", ["bien_so_day_du"])
    op.create_index("ix_bien_ma_tinh_bien", "bien", ["ma_tinh_bien"])
    op.create_index("ix_bien_seri_chu", "bien", ["seri_chu"])
    op.create_index("ix_bien_dau_so", "bien", ["dau_so"])
    op.create_index("ix_bien_loai_pt_id", "bien", ["loai_pt_id"])
    op.create_index("ix_bien_nen_bien_id", "bien", ["nen_bien_id"])
    op.create_index("ix_bien_tinh_ma", "bien", ["tinh_ma"])
    op.create_index("ix_bien_xa_ma", "bien", ["xa_ma"])
    op.create_index("ix_bien_tinh_trang", "bien", ["tinh_trang"])
    op.create_index("ix_bien_giao", "bien", ["giao"])
    op.create_index("ix_bien_ban_giao_id", "bien", ["ban_giao_id"])
    op.create_index("ix_bien_ngoai_tinh", "bien", ["ngoai_tinh"])
    op.create_index(
        "ux_bien_lo_so",
        "bien",
        ["lo_id", "bien_so_day_du"],
        unique=True,
        postgresql_where=sa.text("tinh_trang <> 'Đã hủy'"),
    )
    op.create_index(
        "ux_bien_giu_cho",
        "bien",
        ["tinh_ma", "bien_so_day_du"],
        unique=True,
        postgresql_where=sa.text("giu_cho"),
    )
    op.create_index(
        "ix_bien_tinh_bien_so_pattern",
        "bien",
        ["tinh_ma", "bien_so_day_du"],
        postgresql_ops={"bien_so_day_du": "varchar_pattern_ops"},
    )
    op.create_index(
        "ix_bien_xa_bien_so_pattern",
        "bien",
        ["xa_ma", "bien_so_day_du"],
        postgresql_ops={"bien_so_day_du": "varchar_pattern_ops"},
    )
    op.create_index("ix_bien_tinh_seri_chu", "bien", ["tinh_ma", "seri_chu"])
    op.create_index("ix_bien_tinh_dau_so", "bien", ["tinh_ma", "dau_so"])
    op.create_index("ix_bien_tinh_tinh_trang", "bien", ["tinh_ma", "tinh_trang"])
    op.create_index("ix_bien_tinh_ngoai_tinh", "bien", ["tinh_ma", "ngoai_tinh"])
    op.create_index("ix_bien_xa_giao", "bien", ["xa_ma", "giao"])

    op.create_table(
        "bien_lich_su",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("bien_id", sa.Integer(), nullable=False),
        sa.Column("su_kien", sa.String(length=64), nullable=False),
        sa.Column("tu", sa.String(length=40), nullable=True),
        sa.Column("den", sa.String(length=40), nullable=False),
        sa.Column("ly_do", sa.Text(), nullable=True),
        sa.Column("nguoi", sa.String(length=64), nullable=False),
        sa.Column("luc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["bien_id"], ["bien.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_bien_lich_su_bien_id", "bien_lich_su", ["bien_id"])

    op.create_table(
        "import_job",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("tai_khoan_id", sa.Integer(), nullable=False),
        sa.Column("lo_id", sa.Integer(), nullable=False),
        sa.Column("loai_import", sa.String(length=32), nullable=False, server_default="TAO_BIEN"),
        sa.Column("trang_thai", sa.String(length=32), nullable=False),
        sa.Column("loi", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("dong_hop_le", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("trung_da_tra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("het_han_luc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["lo_id"], ["lo.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tai_khoan_id"], ["tai_khoan.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_import_job_tai_khoan_id", "import_job", ["tai_khoan_id"])
    op.create_index("ix_import_job_lo_id", "import_job", ["lo_id"])

    op.create_table(
        "sync_job",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("lo_id", sa.Integer(), nullable=False),
        sa.Column("trang_thai", sa.String(length=32), nullable=False, server_default="CHO_DONG_BO"),
        sa.Column("lan_thu", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("lan_tiep_theo_luc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("loi_cuoi", sa.Text(), nullable=True),
        sa.Column("tao_luc", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["lo_id"], ["lo.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lo_id"),
    )
    op.create_index("ix_sync_job_lo_id", "sync_job", ["lo_id"])
    op.create_index("ix_sync_job_trang_thai", "sync_job", ["trang_thai"])
    op.create_index("ix_sync_job_lan_tiep_theo_luc", "sync_job", ["lan_tiep_theo_luc"])


def downgrade() -> None:
    op.drop_table("sync_job")
    op.drop_table("import_job")
    op.drop_table("bien_lich_su")
    op.drop_table("bien")
    op.drop_table("ban_giao")
    op.drop_table("lo_lich_su")
    op.drop_table("lo")

