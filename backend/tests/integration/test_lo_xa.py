import io

import openpyxl

from biensoxe.models.bien import Bien


def _make_xlsx_bytes(rows: list[tuple[str, str]]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BienSo"
    ws.append(["BIỂN SỐ ĐẦY ĐỦ", "GHI CHÚ"])
    for plate, note in rows:
        ws.append([plate, note])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_lo_xa_create_ma_lo_edit_delete_and_inline_check_ac26_ac28_ac30(
    authenticated_clients, seeded_db
):
    """Kiểm chứng AC-26, AC-28, AC-30, FR-090: tạo lô xã, sinh Mã lô ngay khi lưu, kiểm tra tại chỗ, thêm/sửa/xóa biển, gửi lô."""
    xa_client = authenticated_clients["xa_10105001"]

    # 1. Tạo lô trống ở trạng thái Khởi tạo -> sinh ngay Mã lô = {so_cong_van}-{ma_xa} (AC-30)
    r_create = xa_client.post(
        "/api/v1/lo",
        json={"loai": "XA", "so_cong_van": "CV01/2026", "ghi_chu": "Lô đợt 1"},
    )
    assert r_create.status_code == 201, r_create.text
    lo_data = r_create.json()
    lo_id = lo_data["id"]
    assert lo_data["trang_thai"] == "Khởi tạo"
    assert lo_data["ma_lo"] == "CV01/2026-10105001"
    assert lo_data["so_luong_bien"] == 0

    # Trùng Số công văn trong cùng xã (không phân biệt hoa/thường) -> 409 (AC-30)
    r_dup_cv = xa_client.post(
        "/api/v1/lo",
        json={"loai": "XA", "so_cong_van": "cv01/2026"},
    )
    assert r_dup_cv.status_code == 409

    # Gửi lô trống -> bị chặn (AC-28)
    r_send_empty = xa_client.post(f"/api/v1/lo/{lo_id}/gui", json={"xac_nhan": True})
    assert r_send_empty.status_code == 400

    # 2. Kiểm tra tại chỗ POST /api/v1/bien/kiem-tra (FR-090)
    r_check_ok = xa_client.post(
        "/api/v1/bien/kiem-tra",
        json={"lo_id": lo_id, "bien_so": "30a-123.4", "nen_bien": "TRẮNG"},
    )
    assert r_check_ok.status_code == 200, r_check_ok.text
    chk = r_check_ok.json()
    assert chk["hop_le"] is True
    assert chk["bien_so_day_du"] == "30A-123.40"
    assert chk["seri_chu"] == "A"
    assert chk["dau_so"] == "123"
    assert chk["mau_sac"] == "TRẮNG"

    # 3. Thêm 2 biển vào lô, sửa 1 biển, xóa 1 biển -> STT tự đánh lại 1..N (AC-26)
    r_b1 = xa_client.post(
        f"/api/v1/lo/{lo_id}/bien",
        json={"bien_so": "30A-123.45", "nen_bien": "TRẮNG", "ghi_chu": "Biển 1"},
    )
    assert r_b1.status_code == 201, r_b1.text
    b1_id = r_b1.json()["id"]

    r_b2 = xa_client.post(
        f"/api/v1/lo/{lo_id}/bien",
        json={"bien_so": "29E-123.45", "nen_bien": "VÀNG", "ghi_chu": "Biển 2"},
    )
    assert r_b2.status_code == 201, r_b2.text
    b2_id = r_b2.json()["id"]
    assert r_b2.json()["mau_sac"] == "VÀNG"

    # Sửa biển 1
    r_edit_b1 = xa_client.put(
        f"/api/v1/bien/{b1_id}",
        json={"bien_so": "30A-543.21", "ghi_chu": "Đã sửa"},
    )
    assert r_edit_b1.status_code == 200
    assert r_edit_b1.json()["bien_so_day_du"] == "30A-543.21"

    # Xóa biển 1 -> biển 2 còn lại phải có STT = 1
    r_del_b1 = xa_client.delete(f"/api/v1/bien/{b1_id}")
    assert r_del_b1.status_code == 204

    r_list = xa_client.get(f"/api/v1/lo/{lo_id}/bien")
    assert r_list.status_code == 200
    items = r_list.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == b2_id
    assert items[0]["stt"] == 1

    # 4. Sửa Số công văn khi đang ở Khởi tạo -> Mã lô cập nhật theo (G-1)
    r_update_lo = xa_client.put(
        f"/api/v1/lo/{lo_id}",
        json={"so_cong_van": "CV01B/2026", "ghi_chu": "Đã đổi số CV"},
    )
    assert r_update_lo.status_code == 200
    assert r_update_lo.json()["ma_lo"] == "CV01B/2026-10105001"

    # 5. Gửi lô thiếu xac_nhan=true -> 400 (FR-091); có xac_nhan=true -> Đã gửi -> đồng bộ thành công sang Chờ phê duyệt & khóa sửa/xóa (AC-28)
    assert xa_client.post(f"/api/v1/lo/{lo_id}/gui", json={"xac_nhan": False}).status_code == 400
    r_send = xa_client.post(f"/api/v1/lo/{lo_id}/gui", json={"xac_nhan": True})
    assert r_send.status_code == 200
    assert r_send.json()["trang_thai"] == "Chờ phê duyệt"

    # Thử sửa/xóa biển hoặc xóa lô khi đã gửi -> 409
    assert (
        xa_client.post(
            f"/api/v1/lo/{lo_id}/bien", json={"bien_so": "30A-999.99"}
        ).status_code
        in (400, 409)
    )
    assert xa_client.delete(f"/api/v1/bien/{b2_id}").status_code in (400, 409)
    assert xa_client.delete(f"/api/v1/lo/{lo_id}").status_code in (400, 409)

    # AC-31: Xem lịch sử lô có mốc Khởi tạo -> Đã gửi -> Chờ phê duyệt
    r_hist = xa_client.get(f"/api/v1/lo/{lo_id}/lich-su")
    assert r_hist.status_code == 200
    events = [h["den"] for h in r_hist.json()["items"]]
    assert "Khởi tạo" in events
    assert "Đã gửi" in events
    assert "Chờ phê duyệt" in events


def test_duplicate_plate_rules_and_reorder_confirmation_ac24_ac53(
    authenticated_clients, seeded_db
):
    """Kiểm chứng AC-24 (FR-036 a/b/c/d) và AC-53 (FR-038 ngoai_tinh)."""
    admin_client = authenticated_clients["admin"]
    xa1_client = authenticated_clients["xa_10105001"]
    xa2_client = authenticated_clients["xa_10105002"]

    # Admin khai báo mã biển tỉnh 01 là 29 và 30 (AC-53)
    admin_client.post("/api/v1/danh-muc/ma-bien-tinh", json={"ma_bien": "29", "tinh_ma": "01"})
    admin_client.post("/api/v1/danh-muc/ma-bien-tinh", json={"ma_bien": "30", "tinh_ma": "01"})

    lo1 = xa1_client.post(
        "/api/v1/lo", json={"loai": "XA", "so_cong_van": "CV-DUP-1"}
    ).json()
    lo1_id = lo1["id"]

    # Thêm biển 30A-111.11 (cùng tỉnh -> ngoai_tinh = False) và 51A-222.22 (ngoài tỉnh -> ngoai_tinh = True, không chặn)
    b_in = xa1_client.post(
        f"/api/v1/lo/{lo1_id}/bien", json={"bien_so": "30A-111.11"}
    ).json()
    assert b_in["ngoai_tinh"] is False

    b_out = xa1_client.post(
        f"/api/v1/lo/{lo1_id}/bien", json={"bien_so": "51A-222.22"}
    ).json()
    assert b_out["ngoai_tinh"] is True

    # (a) Trùng trong cùng lô -> chặn 409
    r_same_batch = xa1_client.post(
        f"/api/v1/lo/{lo1_id}/bien", json={"bien_so": "30A-111.11"}
    )
    assert r_same_batch.status_code == 409

    # Gửi lô 1 để giữ chỗ trong toàn tỉnh 01
    assert xa1_client.post(f"/api/v1/lo/{lo1_id}/gui", json={"xac_nhan": True}).status_code == 200

    # (b) Xã 2 cùng tỉnh 01 thêm biển 30A-111.11 đang hoạt động -> bị chặn 409
    lo2 = xa2_client.post(
        "/api/v1/lo", json={"loai": "XA", "so_cong_van": "CV-DUP-2"}
    ).json()
    lo2_id = lo2["id"]
    r_active_dup = xa2_client.post(
        f"/api/v1/lo/{lo2_id}/bien", json={"bien_so": "30A-111.11"}
    )
    assert r_active_dup.status_code == 409

    # (c) Giả lập biển 30A-111.11 chuyển sang Đã hủy (giu_cho = False) -> đặt lại được ngay không cần xác nhận
    bien_db = seeded_db.get(Bien, b_in["id"])
    bien_db.tinh_trang = "Đã hủy"
    bien_db.giu_cho = False
    seeded_db.commit()

    r_after_cancel = xa2_client.post(
        f"/api/v1/lo/{lo2_id}/bien", json={"bien_so": "30A-111.11"}
    )
    assert r_after_cancel.status_code == 201, r_after_cancel.text

    # (d) Giả lập biển 51A-222.22 ở lô 1 đã Đã trả (tinh_trang='Tồn kho xã', giao='Đã trả', giu_cho=False)
    bien_out_db = seeded_db.get(Bien, b_out["id"])
    bien_out_db.tinh_trang = "Tồn kho xã"
    bien_out_db.giao = "Đã trả"
    bien_out_db.giu_cho = False
    seeded_db.commit()

    # Đặt lại 51A-222.22 mà chưa có dat_lai_xac_nhan=True -> 409 yêu cầu xác nhận
    r_need_confirm = xa2_client.post(
        f"/api/v1/lo/{lo2_id}/bien",
        json={"bien_so": "51A-222.22", "dat_lai_xac_nhan": False},
    )
    assert r_need_confirm.status_code == 409
    assert r_need_confirm.json().get("yeu_cau_xac_nhan_dat_lai") is True

    # Có dat_lai_xac_nhan=True -> lưu thành công với cờ dat_lai_xac_nhan=True
    r_confirmed = xa2_client.post(
        f"/api/v1/lo/{lo2_id}/bien",
        json={"bien_so": "51A-222.22", "dat_lai_xac_nhan": True},
    )
    assert r_confirmed.status_code == 201
    assert r_confirmed.json()["dat_lai_xac_nhan"] is True


def test_excel_import_all_or_nothing_and_error_report_ac27(authenticated_clients):
    """Kiểm chứng AC-27 (FR-042): tải mẫu .xlsx, import tất cả hoặc không, xuất file lỗi .xlsx."""
    xa_client = authenticated_clients["xa_10105001"]
    lo = xa_client.post(
        "/api/v1/lo", json={"loai": "XA", "so_cong_van": "CV-IMPORT-01"}
    ).json()
    lo_id = lo["id"]

    # 1. Tải file mẫu .xlsx
    r_tpl = xa_client.get(f"/api/v1/lo/{lo_id}/bien/mau-xlsx")
    assert r_tpl.status_code == 200
    assert (
        r_tpl.headers["content-type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # 2. Import 10 dòng có 1 dòng lỗi định dạng -> từ chối toàn bộ (0 biển được lưu) + trả import_job_id
    bad_rows = [(f"30A-100.0{i}", f"Ghi chú {i}") for i in range(9)] + [
        ("30ZZ-999.99", "Seri không tồn tại")
    ]
    bad_bytes = _make_xlsx_bytes(bad_rows)
    r_bad = xa_client.post(
        f"/api/v1/lo/{lo_id}/bien/import",
        files={
            "file": (
                "import_bad.xlsx",
                bad_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert r_bad.status_code == 400
    bad_json = r_bad.json()
    assert len(bad_json["errors"]) == 1
    assert bad_json["errors"][0]["dong"] == 11
    job_id = bad_json["import_job_id"]

    # Tải báo cáo lỗi .xlsx
    r_err_xlsx = xa_client.get(f"/api/v1/import-jobs/{job_id}/bao-cao-loi")
    assert r_err_xlsx.status_code == 200

    # Đảm bảo 0 biển nào được lưu vào lô
    assert len(xa_client.get(f"/api/v1/lo/{lo_id}/bien").json()["items"]) == 0

    # 3. Import 10 dòng hợp lệ -> lưu đủ 10 biển
    good_rows = [(f"30A-200.0{i}", f"Hợp lệ {i}") for i in range(10)]
    good_bytes = _make_xlsx_bytes(good_rows)
    r_good = xa_client.post(
        f"/api/v1/lo/{lo_id}/bien/import",
        files={
            "file": (
                "import_good.xlsx",
                good_bytes,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert r_good.status_code == 200, r_good.text
    assert r_good.json()["so_luong_them"] == 10
    assert len(xa_client.get(f"/api/v1/lo/{lo_id}/bien").json()["items"]) == 10


def test_sync_retry_idempotent_ac29(authenticated_clients):
    """Kiểm chứng AC-29 (FR-044): gửi lô khi có lỗi đồng bộ giữ ở Đã gửi, bấm Đồng bộ lại sang Chờ phê duyệt và không sinh trùng."""
    xa_client = authenticated_clients["xa_10105001"]
    lo = xa_client.post(
        "/api/v1/lo", json={"loai": "XA", "so_cong_van": "CV-SYNC-01"}
    ).json()
    lo_id = lo["id"]
    xa_client.post(f"/api/v1/lo/{lo_id}/bien", json={"bien_so": "30A-777.77"})

    # Gửi lô kèm cờ giả lập lỗi mạng đồng bộ -> giữ ở Đã gửi
    r_send = xa_client.post(
        f"/api/v1/lo/{lo_id}/gui",
        json={"xac_nhan": True, "gia_lap_loi_dong_bo": True},
    )
    assert r_send.status_code == 200
    assert r_send.json()["trang_thai"] == "Đã gửi"
    assert r_send.json()["trang_thai_dong_bo"] == "LOI_DONG_BO"

    # Bấm Đồng bộ lại -> thành công, chuyển sang Chờ phê duyệt, không tạo trùng lô hay biển
    r_retry = xa_client.post(f"/api/v1/lo/{lo_id}/dong-bo-lai")
    assert r_retry.status_code == 200
    assert r_retry.json()["trang_thai"] == "Chờ phê duyệt"
    assert r_retry.json()["trang_thai_dong_bo"] == "DA_DONG_BO"
    assert len(xa_client.get(f"/api/v1/lo/{lo_id}/bien").json()["items"]) == 1


def test_excel_import_with_color_selection(authenticated_clients):
    """Kiểm tra import tệp Excel mẫu mới có cột MÀU SẮC (TRẮNG, VÀNG, XANH) (FR-042)."""
    xa_client = authenticated_clients["xa_10105001"]
    lo = xa_client.post(
        "/api/v1/lo", json={"loai": "XA", "so_cong_van": "CV-MAUSAC-01"}
    ).json()
    lo_id = lo["id"]

    # Tạo tệp Excel 3 cột: BIỂN SỐ ĐẦY ĐỦ, MÀU SẮC, GHI CHÚ
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["BIỂN SỐ ĐẦY ĐỦ", "MÀU SẮC", "GHI CHÚ"])
    ws.append(["30A-888.88", "TRẮNG", "Xe cá nhân"])
    ws.append(["30E-888.88", "VÀNG", "Xe kinh doanh"])
    ws.append(["30A-008.88", "XANH", "Xe cơ quan"])
    buf = io.BytesIO()
    wb.save(buf)

    r = xa_client.post(
        f"/api/v1/lo/{lo_id}/bien/import",
        files={
            "file": (
                "import_colors.xlsx",
                buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["so_luong_them"] == 3

    plates = xa_client.get(f"/api/v1/lo/{lo_id}/bien").json()["items"]
    plates_by_no = {p["bien_so_day_du"]: p for p in plates}
    assert plates_by_no["30A-888.88"]["mau_sac"] == "TRẮNG"
    assert plates_by_no["30E-888.88"]["mau_sac"] == "VÀNG"
    assert plates_by_no["30A-008.88"]["mau_sac"] == "XANH"

