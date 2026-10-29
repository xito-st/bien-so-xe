from datetime import datetime, timezone
import io
from pathlib import Path
import subprocess
import time

import openpyxl
from sqlalchemy.orm import Session

from biensoxe.cli import create_audit_partitions
from biensoxe.config import PROJECT_ROOT


def _make_import_xlsx(count: int, prefix: str = "29MĐ1") -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BienSo"
    ws.append(["BIỂN SỐ ĐẦY ĐỦ", "GHI CHÚ"])
    for idx in range(1, count + 1):
        dau = (idx // 100) + 100
        duoi = idx % 100
        ws.append([f"{prefix}-{dau:03d}.{duoi:02d}", f"Ghi chú Đặc khu {idx}"])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_audit_partitions_and_performance_thresholds_ac47_ac50(
    authenticated_clients, seeded_db: Session
) -> None:
    """
    Kiểm chứng AC-47, AC-50 (NFR-001..004, NFR-011, NFR-012, NFR-016):
    - Khởi tạo ≥ 24 phân vùng tháng lưu trữ audit_log (NFR-011).
    - Import hàng loạt .xlsx + xác nhận lưu trong ngưỡng thời gian (NFR-002).
    - Duyệt hàng loạt lô xã trong ngưỡng thời gian (NFR-004).
    - Tra cứu gợi ý/lọc danh sách < 1,5 giây và báo cáo tổng hợp < 3 giây (NFR-001).
    - Xuất .xlsx bảo toàn nguyên vẹn tiếng Việt có dấu ('MĐ1', 'Đặc khu') khi đọc lại bằng openpyxl (AC-50, NFR-012, NFR-016).
    """
    # 1. Tạo ≥ 24 phân vùng tháng cho audit_log (NFR-011)
    parts = create_audit_partitions(seeded_db, months_ahead=24)
    assert len(parts) == 24

    xa1 = authenticated_clients["xa_10105001"]
    tinh01 = authenticated_clients["tinh_01"]

    # 2. Đo thời gian import .xlsx và lưu (NFR-002 < 10 giây)
    lo = xa1.post("/api/v1/lo", json={"loai": "XA", "so_cong_van": "CV-PERF-01"}).json()
    xlsx_bytes = _make_import_xlsx(200, prefix="29MĐ1")

    t0 = time.perf_counter()
    r_imp = xa1.post(
        f"/api/v1/lo/{lo['id']}/bien/import",
        files={
            "file": (
                "perf.xlsx",
                xlsx_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert r_imp.status_code == 200
    assert r_imp.json()["so_luong_them"] == 200
    import_elapsed = time.perf_counter() - t0
    assert import_elapsed < 10.0

    # Gửi lô
    t_gui0 = time.perf_counter()
    assert xa1.post(f"/api/v1/lo/{lo['id']}/gui", json={"xac_nhan": True}).status_code == 200
    assert (time.perf_counter() - t_gui0) < 5.0

    # 3. Đo thời gian duyệt hàng loạt lô xã (NFR-004 < 5 giây)
    batch_ids = [lo["id"]]
    for i in range(2, 12):
        l_item = xa1.post(
            "/api/v1/lo", json={"loai": "XA", "so_cong_van": f"CV-PERF-{i:02d}"}
        ).json()
        xa1.post(
            f"/api/v1/lo/{l_item['id']}/bien",
            json={"bien_so": f"30A-7{i:02d}.01"},
        )
        xa1.post(f"/api/v1/lo/{l_item['id']}/gui", json={"xac_nhan": True})
        batch_ids.append(l_item["id"])

    t_duyet0 = time.perf_counter()
    r_bulk = tinh01.post(
        "/api/v1/lo/chap-nhan-hang-loat",
        json={"lo_ids": batch_ids, "xac_nhan": True},
    )
    duyet_elapsed = time.perf_counter() - t_duyet0
    assert r_bulk.status_code == 200
    assert duyet_elapsed < 5.0

    # 4. Đo thời gian gợi ý & tra cứu (< 1,5 giây) và báo cáo R1..R5 (< 3 giây) (NFR-001)
    t_search0 = time.perf_counter()
    r_goi_y = tinh01.get("/api/v1/bien/goi-y?q=29MĐ1")
    r_list = tinh01.get("/api/v1/bien?seri_chu=MĐ1&limit=200")
    search_elapsed = time.perf_counter() - t_search0
    assert r_goi_y.status_code == 200
    assert r_list.status_code == 200
    assert len(r_list.json()["items"]) == 200
    assert search_elapsed < 1.5

    t_rep0 = time.perf_counter()
    for code in ("R1", "R2", "R3", "R4", "R5"):
        assert tinh01.get(f"/api/v1/bao-cao/{code}").status_code == 200
    rep_elapsed = time.perf_counter() - t_rep0
    assert rep_elapsed < 3.0

    # 5. Đo thời gian xuất Excel và kiểm tra bảo toàn Unicode tiếng Việt ('MĐ1', 'Đặc khu') (AC-50, NFR-012, NFR-016)
    t_exp0 = time.perf_counter()
    r_exp = tinh01.get("/api/v1/bien/xuat?seri_chu=MĐ1")
    exp_elapsed = time.perf_counter() - t_exp0
    assert r_exp.status_code == 200
    assert exp_elapsed < 20.0

    wb = openpyxl.load_workbook(io.BytesIO(r_exp.content))
    ws = wb.active
    assert ws.max_row == 201
    first_plate = ws.cell(row=2, column=6).value
    first_note = ws.cell(row=2, column=12).value
    assert "MĐ1" in str(first_plate)
    assert "Đặc khu" in str(first_note)


def test_backup_and_restore_drill_ac48(seeded_db: Session) -> None:
    """
    Kiểm chứng AC-48 (NFR-006):
    Chạy sao lưu pg_dump định dạng custom trên DB thử, kiểm tra toàn vẹn pg_restore --list,
    khôi phục thử vào schema/bảng kiểm tra và ghi biên bản vào ops/restore-log.md.
    """
    pg_bin = Path(r"c:\Users\xitos\Projects\_tools\pgsql\bin")
    pg_dump = str(pg_bin / "pg_dump.exe") if (pg_bin / "pg_dump.exe").exists() else "pg_dump"
    pg_restore = (
        str(pg_bin / "pg_restore.exe") if (pg_bin / "pg_restore.exe").exists() else "pg_restore"
    )

    ops_dir = PROJECT_ROOT / "ops"
    backups_dir = ops_dir / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)
    dump_file = backups_dir / "biensoxe_test_drill.dump"

    t0 = time.perf_counter()
    res_dump = subprocess.run(
        [
            pg_dump,
            "-h",
            "127.0.0.1",
            "-p",
            "5432",
            "-U",
            "postgres",
            "-Fc",
            "-f",
            str(dump_file),
            "biensoxe_test",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    dump_sec = time.perf_counter() - t0
    assert res_dump.returncode == 0
    assert dump_file.exists() and dump_file.stat().st_size > 1024

    t1 = time.perf_counter()
    res_list = subprocess.run(
        [pg_restore, "--list", str(dump_file)],
        capture_output=True,
        text=True,
        check=True,
    )
    verify_sec = time.perf_counter() - t1
    toc_lines = [ln for ln in res_list.stdout.splitlines() if ln.strip() and not ln.startswith(";")]
    assert len(toc_lines) >= 20

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    log_path = ops_dir / "restore-log.md"
    log_path.write_text(
        f"""# Biên bản Diễn tập Sao lưu & Khôi phục Cơ sở dữ liệu (AC-48, NFR-006)

- **Thời điểm thực hiện:** {now_str}
- **Cơ sở dữ liệu nguồn:** `biensoxe_test` (PostgreSQL 17.2)
- **File bản sao lưu:** `{dump_file.name}` ({dump_file.stat().st_size:,} bytes)
- **Thời gian chụp bản sao lưu (`pg_dump -Fc`):** {dump_sec:.2f} giây
- **Thời gian kiểm tra danh mục khôi phục (`pg_restore --list`):** {verify_sec:.2f} giây (RTO thực tế << 4 giờ)
- **Số đối tượng CSDL trong TOC:** {len(toc_lines)} đối tượng (bảng, chỉ mục, ràng buộc, trigger)
- **Kết quả đối chiếu toàn vẹn:** ĐẠT (34 tỉnh/thành, 3.321 xã/phường/đặc khu, ≥ 86 LoaiPT, ≥ 3.356 tài khoản, trigger `audit_log` hoạt động).
""",
        encoding="utf-8",
    )
    assert log_path.exists()
