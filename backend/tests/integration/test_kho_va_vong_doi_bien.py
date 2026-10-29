from datetime import date, datetime, timedelta, timezone
import io

import openpyxl


def _make_factory_xlsx(plates: list[str]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "NhaMayTraVe"
    ws.append(["BIỂN SỐ ĐẦY ĐỦ"])
    for p in plates:
        ws.append([p])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_dat_thanh_cong_post_order_adjustment_nhap_kho_and_factory_import_ac40_ac41_ac54(
    authenticated_clients,
):
    """Kiểm chứng AC-40 (Đặt thành công + điều chỉnh sau đặt), AC-41 (nhập kho từng phần/cả lô), AC-54 (import nhà máy trả về tất cả hoặc không)."""
    xa1 = authenticated_clients["xa_10105001"]
    tinh01 = authenticated_clients["tinh_01"]

    # 1. Tạo lô xã (2 biển) và lô tỉnh (1 biển), duyệt sang Chấp nhận
    lo_xa = xa1.post("/api/v1/lo", json={"loai": "XA", "so_cong_van": "CV-P5-XA1"}).json()
    b_xa1 = xa1.post(f"/api/v1/lo/{lo_xa['id']}/bien", json={"bien_so": "30A-500.01"}).json()
    b_xa2 = xa1.post(f"/api/v1/lo/{lo_xa['id']}/bien", json={"bien_so": "30A-500.02"}).json()
    xa1.post(f"/api/v1/lo/{lo_xa['id']}/gui", json={"xac_nhan": True})
    tinh01.post(f"/api/v1/lo/{lo_xa['id']}/duyet", json={"xac_nhan": True})

    lo_tinh = tinh01.post("/api/v1/lo", json={"loai": "TINH", "so_cong_van": "CV-P5-TINH1"}).json()
    b_tinh1 = tinh01.post(f"/api/v1/lo/{lo_tinh['id']}/bien", json={"bien_so": "30A-500.03"}).json()
    tinh01.post(f"/api/v1/lo/{lo_tinh['id']}/gui", json={"xac_nhan": True})
    tinh01.post(f"/api/v1/lo/{lo_tinh['id']}/duyet", json={"xac_nhan": True})

    # 2. Tạo lô đặt nhà máy, gửi duyệt, tự duyệt -> Chấp nhận
    dnm = tinh01.post(
        "/api/v1/lo",
        json={
            "loai": "DAT_NHA_MAY",
            "so_cong_van": "DNM-P5-01",
            "lo_con_ids": [lo_xa["id"], lo_tinh["id"]],
        },
    ).json()
    tinh01.post(f"/api/v1/lo/{dnm['id']}/gui", json={"xac_nhan": True})
    tinh01.post(f"/api/v1/lo/{dnm['id']}/duyet", json={"xac_nhan": True})

    # 3. AC-40: Xác nhận Đặt thành công -> dnm, lo_xa, lo_tinh sang Đặt thành công; mọi biển sang Đã đặt
    r_dtc = tinh01.post(f"/api/v1/lo/{dnm['id']}/dat-thanh-cong", json={"xac_nhan": True})
    assert r_dtc.status_code == 200, r_dtc.text
    assert r_dtc.json()["trang_thai"] == "Đặt thành công"
    assert tinh01.get(f"/api/v1/lo/{lo_xa['id']}").json()["trang_thai"] == "Đặt thành công"
    assert tinh01.get(f"/api/v1/lo/{lo_tinh['id']}").json()["trang_thai"] == "Đặt thành công"

    dnm_plates = tinh01.get(f"/api/v1/lo/{dnm['id']}/bien").json()["items"]
    assert all(p["tinh_trang"] == "Đã đặt" for p in dnm_plates)

    # Không thể bật Cho phép điều chỉnh hay Hủy lô đặt nhà máy sau khi đã Đặt thành công (AC-39, FR-049)
    assert tinh01.post(f"/api/v1/lo/{lo_xa['id']}/cho-phep-dieu-chinh").status_code == 409
    assert (
        tinh01.post(
            f"/api/v1/lo/{dnm['id']}/huy", json={"ly_do": "Thử hủy", "xac_nhan": True}
        ).status_code
        == 409
    )

    # 4. AC-40: Điều chỉnh sau Đặt thành công
    # Thiếu xac_nhan hoặc thiếu ly_do -> 400
    assert (
        tinh01.post(
            f"/api/v1/lo/{dnm['id']}/dieu-chinh-sau-dat",
            json={
                "hanh_dong": "THEM_BIEN",
                "lo_con_id": lo_xa["id"],
                "bien_so": "30A-500.04",
                "ly_do": "",
                "xac_nhan": True,
            },
        ).status_code
        == 400
    )

    # Thêm biển mới vào lo_xa -> vào thẳng Đã đặt, dnm vẫn giữ trạng thái Đặt thành công
    r_add_after = tinh01.post(
        f"/api/v1/lo/{dnm['id']}/dieu-chinh-sau-dat",
        json={
            "hanh_dong": "THEM_BIEN",
            "lo_con_id": lo_xa["id"],
            "bien_so": "30A-500.04",
            "ly_do": "Bổ sung theo công văn đính chính",
            "xac_nhan": True,
        },
    )
    assert r_add_after.status_code == 200, r_add_after.text
    b_xa3_id = r_add_after.json()["id"]
    assert r_add_after.json()["tinh_trang"] == "Đã đặt"
    assert tinh01.get(f"/api/v1/lo/{dnm['id']}").json()["trang_thai"] == "Đặt thành công"

    # Sửa biển đang ở Đã đặt -> thành công
    r_edit_after = tinh01.post(
        f"/api/v1/lo/{dnm['id']}/dieu-chinh-sau-dat",
        json={
            "hanh_dong": "SUA_BIEN",
            "bien_id": b_xa3_id,
            "bien_so": "30A-500.40",
            "ly_do": "Đính chính số cuối",
            "xac_nhan": True,
        },
    )
    assert r_edit_after.status_code == 200
    assert r_edit_after.json()["bien_so_day_du"] == "30A-500.40"

    # 5. AC-41: Nhập kho tỉnh từng phần (nhập trước 1 biển b_xa1) -> tiến độ 1/4, chưa Đã nhập kho
    r_nk1 = tinh01.post(
        f"/api/v1/lo/{dnm['id']}/nhap-kho",
        json={"ca_lo": False, "bien_ids": [b_xa1["id"]]},
    )
    assert r_nk1.status_code == 200
    assert r_nk1.json()["so_luong_nhap_kho"] == 1
    assert r_nk1.json()["so_luong_bien"] == 4
    assert r_nk1.json()["trang_thai"] == "Đặt thành công"

    # Thử sửa biển b_xa1 đã nhập kho tỉnh -> bị chặn 409 (AC-40)
    assert (
        tinh01.post(
            f"/api/v1/lo/{dnm['id']}/dieu-chinh-sau-dat",
            json={
                "hanh_dong": "SUA_BIEN",
                "bien_id": b_xa1["id"],
                "bien_so": "30A-599.99",
                "ly_do": "Thử sửa biển đã nhập kho",
                "xac_nhan": True,
            },
        ).status_code
        == 409
    )

    # 6. AC-54: Import file .xlsx nhà máy trả về
    # Nếu file chứa biển không thuộc lô hoặc biển đã nhập kho (30A-500.01) -> từ chối toàn bộ (400) + xuất báo cáo lỗi
    bad_factory_xlsx = _make_factory_xlsx(["30A-500.02", "30A-500.01", "99A-999.99"])
    r_imp_bad = tinh01.post(
        f"/api/v1/lo/{dnm['id']}/nhap-kho/import",
        files={
            "file": (
                "factory_bad.xlsx",
                bad_factory_xlsx,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert r_imp_bad.status_code == 400
    assert len(r_imp_bad.json()["errors"]) == 2
    err_job_id = r_imp_bad.json()["import_job_id"]
    assert tinh01.get(f"/api/v1/import-jobs/{err_job_id}/bao-cao-loi").status_code == 200
    # Đảm bảo 30A-500.02 vẫn chưa bị nhập kho (tất cả hoặc không)
    assert tinh01.get(f"/api/v1/lo/{dnm['id']}").json()["so_luong_nhap_kho"] == 1

    # Import đúng 3 biển còn lại (gồm "30A-500.4" tự chuẩn hóa thành "30A-500.40" theo FR-035)
    # -> toàn bộ 4/4 biển đã nhập kho -> lo_tinh và dnm tự động chuyển sang 'Đã nhập kho' (AC-41, AC-54)
    good_factory_xlsx = _make_factory_xlsx(["30A-500.02", "30A-500.03", "30A-500.4"])
    r_imp_ok = tinh01.post(
        f"/api/v1/lo/{dnm['id']}/nhap-kho/import",
        files={
            "file": (
                "factory_good.xlsx",
                good_factory_xlsx,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert r_imp_ok.status_code == 200, r_imp_ok.text
    assert r_imp_ok.json()["so_luong_nhap_kho"] == 3
    assert r_imp_ok.json()["trang_thai_lo"] == "Đã nhập kho"
    assert tinh01.get(f"/api/v1/lo/{lo_tinh['id']}").json()["trang_thai"] == "Đã nhập kho"


def test_chuyen_xa_tra_bien_thu_hoi_and_huy_bien_ac34_ac35_ac42_ac44(
    authenticated_clients,
):
    """Kiểm chứng AC-34, AC-35, AC-42, AC-44, G-6, G-17."""
    xa1 = authenticated_clients["xa_10105001"]
    tinh01 = authenticated_clients["tinh_01"]

    # Chuẩn bị 1 lô xã (3 biển) và 1 lô tỉnh (1 biển) đã nhập kho tỉnh
    lo_xa = xa1.post("/api/v1/lo", json={"loai": "XA", "so_cong_van": "CV-P5-XA2"}).json()
    bx1 = xa1.post(f"/api/v1/lo/{lo_xa['id']}/bien", json={"bien_so": "30A-600.01"}).json()
    bx2 = xa1.post(f"/api/v1/lo/{lo_xa['id']}/bien", json={"bien_so": "30A-600.02"}).json()
    bx3 = xa1.post(f"/api/v1/lo/{lo_xa['id']}/bien", json={"bien_so": "30A-600.03"}).json()
    xa1.post(f"/api/v1/lo/{lo_xa['id']}/gui", json={"xac_nhan": True})
    tinh01.post(f"/api/v1/lo/{lo_xa['id']}/duyet", json={"xac_nhan": True})

    lo_tinh = tinh01.post("/api/v1/lo", json={"loai": "TINH", "so_cong_van": "CV-P5-TINH2"}).json()
    bt1 = tinh01.post(f"/api/v1/lo/{lo_tinh['id']}/bien", json={"bien_so": "30A-600.04"}).json()
    tinh01.post(f"/api/v1/lo/{lo_tinh['id']}/gui", json={"xac_nhan": True})
    tinh01.post(f"/api/v1/lo/{lo_tinh['id']}/duyet", json={"xac_nhan": True})

    dnm = tinh01.post(
        "/api/v1/lo",
        json={
            "loai": "DAT_NHA_MAY",
            "so_cong_van": "DNM-P5-02",
            "lo_con_ids": [lo_xa["id"], lo_tinh["id"]],
        },
    ).json()
    tinh01.post(f"/api/v1/lo/{dnm['id']}/gui", json={"xac_nhan": True})
    tinh01.post(f"/api/v1/lo/{dnm['id']}/duyet", json={"xac_nhan": True})
    tinh01.post(f"/api/v1/lo/{dnm['id']}/dat-thanh_cong" if False else f"/api/v1/lo/{dnm['id']}/dat-thanh-cong", json={"xac_nhan": True})
    tinh01.post(f"/api/v1/lo/{dnm['id']}/nhap-kho", json={"ca_lo": True})

    today_str = date.today().isoformat()
    tomorrow_str = (date.today() + timedelta(days=2)).isoformat()

    # 1. AC-42: Chuyển xã thiếu trường hoặc ngày nhận tương lai hoặc chuyển cho lô tỉnh -> bị chặn
    assert (
        tinh01.post(
            f"/api/v1/lo/{lo_xa['id']}/chuyen-xa",
            json={
                "bien_ids": [bx1["id"]],
                "so_bien_ban": "",
                "nguoi_nhan": "Nguyễn Văn A",
                "chuc_vu": "Cán bộ Công an xã",
                "ngay_nhan": today_str,
                "xac_nhan": True,
            },
        ).status_code
        == 400
    )
    assert (
        tinh01.post(
            f"/api/v1/lo/{lo_xa['id']}/chuyen-xa",
            json={
                "bien_ids": [bx1["id"]],
                "so_bien_ban": "BB-01",
                "nguoi_nhan": "Nguyễn Văn A",
                "chuc_vu": "Cán bộ Công an xã",
                "ngay_nhan": tomorrow_str,
                "xac_nhan": True,
            },
        ).status_code
        == 400
    )
    assert (
        tinh01.post(
            f"/api/v1/lo/{lo_tinh['id']}/chuyen-xa",
            json={
                "bien_ids": [bt1["id"]],
                "so_bien_ban": "BB-TINH",
                "nguoi_nhan": "Nguyễn Văn A",
                "chuc_vu": "Cán bộ",
                "ngay_nhan": today_str,
                "xac_nhan": True,
            },
        ).status_code
        == 400
    )

    # Chuyển đợt 1 (2 biển bx1, bx2) -> lo_xa vẫn giữ Đặt thành công
    r_cx1 = tinh01.post(
        f"/api/v1/lo/{lo_xa['id']}/chuyen-xa",
        json={
            "bien_ids": [bx1["id"], bx2["id"]],
            "so_bien_ban": "BB-01/2026",
            "nguoi_nhan": "Nguyễn Văn A",
            "chuc_vu": "Trưởng Công an xã",
            "ngay_nhan": today_str,
            "xac_nhan": True,
        },
    )
    assert r_cx1.status_code == 200, r_cx1.text
    assert r_cx1.json()["lo_xa"]["trang_thai"] == "Đặt thành công"

    # Chuyển đợt 2 (biển bx3 còn lại) -> lo_xa sang 'Đã nhận', dnm sang 'Đã chuyển Xã/phường' (AC-42)
    r_cx2 = tinh01.post(
        f"/api/v1/lo/{lo_xa['id']}/chuyen-xa",
        json={
            "bien_ids": [bx3["id"]],
            "so_bien_ban": "BB-02/2026",
            "nguoi_nhan": "Trần Thị B",
            "chuc_vu": "Phó Trưởng Công an xã",
            "ngay_nhan": today_str,
            "xac_nhan": True,
        },
    )
    assert r_cx2.status_code == 200
    assert r_cx2.json()["lo_xa"]["trang_thai"] == "Đã nhận"
    assert tinh01.get(f"/api/v1/lo/{dnm['id']}").json()["trang_thai"] == "Đã chuyển Xã/phường"

    # 2. FR-052: Xã xem danh sách biển đã nhận kèm thông tin biên bản bàn giao
    da_nhan_list = xa1.get(f"/api/v1/bien/da-nhan?lo_id={lo_xa['id']}").json()["items"]
    assert len(da_nhan_list) == 3
    assert any(item["so_bien_ban"] == "BB-01/2026" for item in da_nhan_list)

    # 3. AC-34: Trả biển cho người dân
    # Thử gửi ngày giờ trả trong tương lai -> 400
    future_ts = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    assert (
        xa1.post(
            "/api/v1/bien/tra-bien",
            json={"bien_ids": [bx1["id"]], "ngay_gio_tra": future_ts},
        ).status_code
        == 400
    )

    # Thử gửi kèm dữ liệu cá nhân công dân (PII) -> bị từ chối (422)
    assert (
        xa1.post(
            "/api/v1/bien/tra-bien",
            json={"bien_ids": [bx1["id"]], "ho_ten_cong_dan": "Nguyễn Văn Dân"},
        ).status_code
        == 422
    )

    # Trả biển bx1 hợp lệ -> giao = 'Đã trả'
    r_tra = xa1.post("/api/v1/bien/tra-bien", json={"bien_ids": [bx1["id"]]})
    assert r_tra.status_code == 200
    assert r_tra.json()["items"][0]["giao"] == "Đã trả"

    # G-6: Tỉnh cũng trả được trực tiếp biển bt1 của lô tỉnh đang ở Tồn kho tỉnh
    r_tra_tinh = tinh01.post(f"/api/v1/bien/{bt1['id']}/tra", json={})
    assert r_tra_tinh.status_code == 200
    assert r_tra_tinh.json()["items"][0]["giao"] == "Đã trả"

    # 4. AC-35, G-17: Thu hồi biển bx1 đã trả -> trạng thái cuối 'Thu hồi về xã'
    # Không được hủy biển đã trả
    assert (
        xa1.post(
            f"/api/v1/bien/{bx1['id']}/huy",
            json={"ly_do": "Thử hủy biển đã trả", "xac_nhan": True},
        ).status_code
        == 409
    )

    r_thu_hoi = xa1.post(
        f"/api/v1/bien/{bx1['id']}/thu-hoi",
        json={"ly_do": "Chủ xe chuyển vùng đăng ký", "xac_nhan": True},
    )
    assert r_thu_hoi.status_code == 200
    assert r_thu_hoi.json()["giao"] == "Thu hồi về xã"

    # 'Thu hồi về xã' là trạng thái cuối: không trả lại hay hủy tiếp được (AC-35)
    assert xa1.post(f"/api/v1/bien/{bx1['id']}/tra", json={}).status_code == 409
    assert (
        xa1.post(
            f"/api/v1/bien/{bx1['id']}/huy",
            json={"ly_do": "Thử hủy sau thu hồi", "xac_nhan": True},
        ).status_code
        == 409
    )

    # G-17: Đặt lại biển 30A-600.01 đã 'Thu hồi về xã' yêu cầu dat_lai_xac_nhan=True
    lo_xa_new = xa1.post("/api/v1/lo", json={"loai": "XA", "so_cong_van": "CV-P5-XA3"}).json()
    assert (
        xa1.post(
            f"/api/v1/lo/{lo_xa_new['id']}/bien",
            json={"bien_so": "30A-600.01", "dat_lai_xac_nhan": False},
        ).status_code
        == 409
    )
    assert (
        xa1.post(
            f"/api/v1/lo/{lo_xa_new['id']}/bien",
            json={"bien_so": "30A-600.01", "dat_lai_xac_nhan": True},
        ).status_code
        == 201
    )

    # 5. AC-35, AC-44: Hủy biển bx2 (đang Tồn kho xã / Chưa trả) -> Đã hủy, giải phóng số không cần xác nhận đặt lại
    r_huy_xa = xa1.post(
        f"/api/v1/bien/{bx2['id']}/huy",
        json={"ly_do": "Biển bị trầy xước khi vận chuyển", "xac_nhan": True},
    )
    assert r_huy_xa.status_code == 200
    assert r_huy_xa.json()["tinh_trang"] == "Đã hủy"
    assert r_huy_xa.json()["giu_cho"] is False

    # Đặt lại biển 30A-600.02 đã hủy không cần dat_lai_xac_nhan
    assert (
        xa1.post(
            f"/api/v1/lo/{lo_xa_new['id']}/bien",
            json={"bien_so": "30A-600.02", "dat_lai_xac_nhan": False},
        ).status_code
        == 201
    )

