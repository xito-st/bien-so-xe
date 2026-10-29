import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys
import unicodedata

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from biensoxe.config import PROJECT_ROOT, get_settings
from biensoxe.db import Base, get_engine, get_session_factory, transaction
import biensoxe.models  # noqa: F401
from biensoxe.models.audit import AuditLog
from biensoxe.models.danh_muc import LoaiPT, NenBien, Tinh, XaPhuong
from biensoxe.models.tai_khoan import PhienDangNhap, TaiKhoan
from biensoxe.security.hashing import hash_password, hash_passwords_batch

DEFAULT_TINH_PASSWORD = "Abc@!321"
DEFAULT_XA_PASSWORD = "Abc@321"


def _resolve_data_dir() -> Path:
    backend_data = Path(__file__).resolve().parents[2] / "data"
    spec_data = PROJECT_ROOT / "specs" / "001-quan-ly-bien-so-xe" / "data"
    backend_data.mkdir(parents=True, exist_ok=True)
    for fname in (
        "danh-muc-don-vi-hanh-chinh.csv",
        "danh-muc-loai-phuong-tien.csv",
        "danh-muc-nen-bien.csv",
    ):
        target = backend_data / fname
        source = spec_data / fname
        if not target.exists() and source.exists():
            shutil.copyfile(source, target)
    return backend_data if (backend_data / "danh-muc-don-vi-hanh-chinh.csv").exists() else spec_data


def _infer_loai_tinh(ten_tinh: str) -> str:
    ten_norm = unicodedata.normalize("NFC", ten_tinh).strip()
    if ten_norm.startswith("Thành phố"):
        return "Thành phố"
    if ten_norm.startswith("Tỉnh"):
        return "Tỉnh"
    raise ValueError(f"Không xác định được loại đơn vị tỉnh/thành từ tên: '{ten_tinh}'")


def _infer_loai_xa(ten_xa: str) -> str:
    ten_norm = unicodedata.normalize("NFC", ten_xa).strip()
    if ten_norm.startswith("Phường"):
        return "Phường"
    if ten_norm.startswith("Đặc khu"):
        return "Đặc khu"
    if ten_norm.startswith("Xã"):
        return "Xã"
    raise ValueError(f"Không xác định được loại đơn vị xã/phường/đặc khu từ tên: '{ten_xa}'")


def seed_database(db: Session) -> None:
    """Nạp danh mục đơn vị hành chính, LoaiPT, nền biển và tự sinh 3.356 tài khoản (FR-001, FR-002, FR-033, FR-034)."""
    data_dir = _resolve_data_dir()
    settings = get_settings()
    now = datetime.now(timezone.utc)

    with transaction(db):
        # 1. Nạp danh mục tỉnh/thành và xã/phường/đặc khu
        existing_tinh = {t.ma for t in db.scalars(select(Tinh)).all()}
        existing_xa = {x.ma for x in db.scalars(select(XaPhuong)).all()}

        tinh_seen: dict[str, tuple[str, str, int]] = {}
        xa_rows: list[tuple[str, str, str, str, int]] = []

        with open(data_dir / "danh-muc-don-vi-hanh-chinh.csv", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                stt = int(row["STT"].strip())
                ma_tinh = row["MaTinh"].strip().zfill(2)
                ten_tinh = unicodedata.normalize("NFC", row["TenTinh"].strip())
                if ten_tinh.startswith("Tp ") or ten_tinh.startswith("Tp."):
                    ten_tinh = "Thành phố " + ten_tinh.split(" ", 1)[1].lstrip(".")
                loai_tinh = _infer_loai_tinh(ten_tinh)
                if ma_tinh not in tinh_seen:
                    tinh_seen[ma_tinh] = (ten_tinh, loai_tinh, len(tinh_seen) + 1)

                ma_xa = row["MaPhuongXa"].strip()
                ten_xa = unicodedata.normalize("NFC", row["TenPhuongXa"].strip())
                loai_xa = _infer_loai_xa(ten_xa)
                xa_rows.append((ma_xa, ten_xa, loai_xa, ma_tinh, stt))

        for ma_tinh, (ten_tinh, loai_tinh, stt_tinh) in tinh_seen.items():
            if ma_tinh not in existing_tinh:
                db.add(Tinh(ma=ma_tinh, ten=ten_tinh, loai_don_vi=loai_tinh, stt=stt_tinh))

        db.flush()

        for ma_xa, ten_xa, loai_xa, ma_tinh, stt_xa in xa_rows:
            if ma_xa not in existing_xa:
                db.add(
                    XaPhuong(
                        ma=ma_xa,
                        ten=ten_xa,
                        loai_don_vi=loai_xa,
                        tinh_ma=ma_tinh,
                        stt=stt_xa,
                    )
                )

        # 2. Nạp danh mục LoaiPT (86 mục)
        existing_loai_pt = {lp.seri_chu for lp in db.scalars(select(LoaiPT)).all()}
        with open(data_dir / "danh-muc-loai-phuong-tien.csv", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                seri_chu = unicodedata.normalize("NFC", row["SeriChu"].strip()).upper()
                if seri_chu not in existing_loai_pt:
                    db.add(
                        LoaiPT(
                            stt=int(row["STT"].strip()),
                            seri_chu=seri_chu,
                            ten=unicodedata.normalize("NFC", row["LoaiPT"].strip()),
                            dang_dung=True,
                        )
                    )

        # 3. Nạp danh mục nền biển (3 mục)
        existing_nen = {nb.ten for nb in db.scalars(select(NenBien)).all()}
        with open(data_dir / "danh-muc-nen-bien.csv", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ten_nen = unicodedata.normalize("NFC", row["NenBien"].strip())
                if ten_nen not in existing_nen:
                    db.add(
                        NenBien(
                            stt=int(row["STT"].strip()),
                            ten=ten_nen,
                            mau_sac=unicodedata.normalize("NFC", row["MauSac"].strip()),
                            dang_dung=True,
                        )
                    )

        db.flush()

        # 4. Tự sinh 1 Admin + 34 tỉnh + 3.321 xã (FR-002)
        existing_usernames = set(db.scalars(select(TaiKhoan.ten_dang_nhap)).all())
        pending_accounts: list[tuple[str, str, str | None, str | None, str]] = []

        if "ADMINS" not in existing_usernames:
            pending_accounts.append(
                ("ADMINS", "ADMIN", None, None, settings.admin_initial_password)
            )

        for ma_tinh in tinh_seen:
            if ma_tinh not in existing_usernames:
                pending_accounts.append(
                    (ma_tinh, "TINH", ma_tinh, None, DEFAULT_TINH_PASSWORD)
                )

        for ma_xa, _, _, ma_tinh, _ in xa_rows:
            if ma_xa not in existing_usernames:
                pending_accounts.append(
                    (ma_xa, "XA", ma_tinh, ma_xa, DEFAULT_XA_PASSWORD)
                )

        if pending_accounts:
            passwords = [item[4] for item in pending_accounts]
            hashes = hash_passwords_batch(passwords)
            for (username, role, tinh_ma, xa_ma, _), pw_hash in zip(
                pending_accounts, hashes, strict=True
            ):
                db.add(
                    TaiKhoan(
                        ten_dang_nhap=username,
                        vai_tro=role,
                        tinh_ma=tinh_ma,
                        xa_ma=xa_ma,
                        mat_khau_hash=pw_hash,
                        bat_buoc_doi_mk=True,
                        mk_doi_luc=now,
                        so_lan_sai=0,
                        khoa_thu_cong=False,
                        totp_da_bat=False,
                        tao_boi="SYSTEM_SEED",
                        tao_luc=now,
                    )
                )


def reset_admin_account(db: Session, new_password: str | None = None) -> None:
    """Quy trình vận hành khôi phục mật khẩu & 2FA cho Admin và ghi audit log (FR-018)."""
    settings = get_settings()
    pw = new_password or settings.admin_initial_password
    now = datetime.now(timezone.utc)
    with transaction(db):
        admin = db.scalar(select(TaiKhoan).where(TaiKhoan.ten_dang_nhap == "ADMINS"))
        if admin is None:
            raise ValueError("Không tìm thấy tài khoản ADMINS.")
        admin.mat_khau_hash = hash_password(pw)
        admin.bat_buoc_doi_mk = True
        admin.totp_da_bat = False
        admin.totp_secret_enc = None
        admin.so_lan_sai = 0
        admin.khoa_den = None
        admin.khoa_thu_cong = False
        for s in db.scalars(
            select(PhienDangNhap).where(
                PhienDangNhap.tai_khoan_id == admin.id,
                PhienDangNhap.huy_luc.is_(None),
            )
        ).all():
            s.huy_luc = now
        db.add(
            AuditLog(
                thoi_diem=now,
                nguoi_dung="OPS_CLI",
                hanh_dong="DAT_LAI_MAT_KHAU_ADMIN",
                doi_tuong="ADMINS",
                ket_qua="THANH_CONG",
                ip="127.0.0.1",
                chi_tiet={"ly_do": "Khôi phục vận hành qua CLI (FR-018)"},
            )
        )


def create_audit_partitions(db: Session, months_ahead: int = 24) -> list[str]:
    """Đảm bảo phân vùng lưu trữ audit_log tối thiểu 24 tháng theo NFR-011."""
    now = datetime.now(timezone.utc)
    created: list[str] = []
    with transaction(db):
        db.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS audit_log_archive (
                    id INTEGER NOT NULL,
                    thoi_diem TIMESTAMPTZ NOT NULL,
                    nguoi_dung VARCHAR(64) NOT NULL,
                    hanh_dong VARCHAR(80) NOT NULL,
                    doi_tuong VARCHAR(120) NOT NULL,
                    ket_qua VARCHAR(32) NOT NULL,
                    ip VARCHAR(64),
                    chi_tiet JSONB
                ) PARTITION BY RANGE (thoi_diem);
                """
            )
        )
        year = now.year
        month = now.month
        for i in range(months_ahead):
            m = (month - 1 + i) % 12 + 1
            y = year + (month - 1 + i) // 12
            next_m = m % 12 + 1
            next_y = y + (1 if m == 12 else 0)
            part_name = f"audit_log_p{y:04d}_{m:02d}"
            start_str = f"{y:04d}-{m:02d}-01 00:00:00+00"
            end_str = f"{next_y:04d}-{next_m:02d}-01 00:00:00+00"
            db.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS {part_name}
                    PARTITION OF audit_log_archive
                    FOR VALUES FROM ('{start_str}') TO ('{end_str}');
                    """
                )
            )
            created.append(part_name)
    return created


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(prog="biensoxe", description="CLI quản trị hệ thống biển số xe")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed", help="Nạp danh mục và khởi tạo 3.356 tài khoản")
    sub.add_parser("reset-admin", help="Khôi phục mật khẩu và 2FA của Admin theo quy trình vận hành")
    sub.add_parser("create-partitions", help="Khởi tạo các phân vùng tháng cho lưu trữ audit_log (≥ 24 tháng)")
    serve_parser = sub.add_parser("serve", help="Khởi tạo DB (nếu cần) và chạy máy chủ Web")
    serve_parser.add_argument("--host", default="127.0.0.1", help="Địa chỉ lắng nghe (mặc định 127.0.0.1)")
    serve_parser.add_argument("--port", type=int, default=8000, help="Cổng lắng nghe (mặc định 8000)")

    args = parser.parse_args()
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    session_factory = get_session_factory(engine)
    with session_factory() as db:
        if args.command == "seed":
            seed_database(db)
            print("Seed dữ liệu danh mục và tài khoản hoàn tất.")
        elif args.command == "reset-admin":
            reset_admin_account(db)
            print("Đã đặt lại tài khoản ADMINS và ghi audit log.")
        elif args.command == "create-partitions":
            parts = create_audit_partitions(db, months_ahead=24)
            print(f"Đã đảm bảo {len(parts)} phân vùng lưu trữ audit_log.")
        elif args.command == "serve":
            if db.scalar(select(Tinh).limit(1)) is None:
                print("Khởi tạo dữ liệu danh mục và 3.356 tài khoản lần đầu...")
                seed_database(db)
                create_audit_partitions(db, months_ahead=24)
                print("Hoàn tất khởi tạo dữ liệu ban đầu.")

    if args.command == "serve":
        import uvicorn

        from biensoxe.main import create_app

        uvicorn.run(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
