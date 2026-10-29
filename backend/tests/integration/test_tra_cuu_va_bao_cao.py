from datetime import date, datetime, timezone
import io

import openpyxl


def test_tra_cuu_goi_y_combined_filters_scope_and_xlsx_export_ac33(
    authenticated_clients,
) -> None:
    admin = authenticated_clients["admin"]
    tinh01 = authenticated_clients["tinh_01"]
    xa1 = authenticated_clients["xa_10105001"]
    xa2 = authenticated_clients["xa_10105002"]
    xa_other_tinh = authenticated_clients["xa_22113001"]

    # Admin khai báo mã biển 29, 30 cho tỉnh 01 để kiểm tra lọc ngoai_tinh
    admin.post("/api/v1/danh-muc/ma-bien-tinh", json={"ma_bien": "29", "tinh_ma": "01"})
    admin.post("/api/v1/danh-muc/ma-bien-tinh", json={"ma_bien": "30", "tinh_ma": "01"})

    # Xã 1 (tỉnh 01) tạo lô và gửi
    lo1 = xa1.post("/api/v1/lo", json={"loai": "XA", "so_cong_van": "CV-TC-XA1"}).json()
    xa1.post(f"/api/v1/lo/{lo1['id']}/bien", json={"bien_so": "29A-600.01"})
    xa1.post(f"/api/v1/lo/{lo1['id']}/bien", json={"bien_so": "29MĐ1-600.02"})
    # Biển ngoại tỉnh (99 thuộc Bắc Ninh, nhập ở tỉnh 01 -> ngoai_tinh=True)
    b_nt = xa1.post(f"/api/v1/lo/{lo1['id']}/bien", json={"bien_so": "99A-600.03"}).json()
    assert b_nt["ngoai_tinh"] is True
    xa1.post(f"/api/v1/lo/{lo1['id']}/gui", json={"xac_nhan": True})

    # Xã 2 (cùng tỉnh 01) tạo lô và gửi
    lo2 = xa2.post("/api/v1/lo", json={"loai": "XA", "so_cong_van": "CV-TC-XA2"}).json()
    xa2.post(f"/api/v1/lo/{lo2['id']}/bien", json={"bien_so": "30B-600.04"})
    xa2.post(f"/api/v1/lo/{lo2['id']}/gui", json={"xac_nhan": True})

    # Xã thuộc tỉnh 02 tạo lô và gửi
    lo_t2 = xa_other_tinh.post(
        "/api/v1/lo", json={"loai": "XA", "so_cong_van": "CV-TC-TINH2"}
    ).json()
    xa_other_tinh.post(f"/api/v1/lo/{lo_t2['id']}/bien", json={"bien_so": "99C-700.01"})
    xa_other_tinh.post(f"/api/v1/lo/{lo_t2['id']}/gui", json={"xac_nhan": True})

    # 1. Gợi ý dưới 2 ký tự trả rỗng; từ ký tự thứ 2 trở đi trả gợi ý đúng phạm vi (FR-050, AC-33)
    assert xa1.get("/api/v1/bien/goi-y?q=6").json()["items"] == []
    goi_y_xa1 = xa1.get("/api/v1/bien/goi-y?q=60").json()["items"]
    assert len(goi_y_xa1) == 3
    # Xã 1 không thấy biển 30B-600.04 của Xã 2
    assert all(item["bien_so_day_du"] != "30B-600.04" for item in goi_y_xa1)

    # Tỉnh 01 gõ "60" thấy cả 4 biển của xã 1 và xã 2 nhưng không thấy biển tỉnh 02
    goi_y_tinh01 = tinh01.get("/api/v1/bien/goi-y?q=60").json()["items"]
    assert len(goi_y_tinh01) == 4
    assert len(tinh01.get("/api/v1/bien/goi-y?q=700").json()["items"]) == 0

    # 2. Lọc kết hợp nhiều tiêu chí (FR-050, FR-060, AC-33)
    r_filter_md1 = tinh01.get("/api/v1/bien?seri_chu=MĐ1&dau_so=600")
    assert r_filter_md1.status_code == 200
    items_md1 = r_filter_md1.json()["items"]
    assert len(items_md1) == 1
    assert items_md1[0]["bien_so_day_du"] == "29MĐ1-600.02"

    # Lọc theo cờ ngoại tỉnh tại tỉnh 01
    r_nt = tinh01.get("/api/v1/bien?ngoai_tinh=true&dau_so=600")
    assert r_nt.status_code == 200
    nt_items = r_nt.json()["items"]
    assert len(nt_items) == 1
    assert nt_items[0]["bien_so_day_du"] == "99A-600.03"

    # Admin tra cứu toàn hệ thống (FR-082)
    r_admin_all = admin.get("/api/v1/bien?bien_so=700.01")
    assert r_admin_all.status_code == 200
    assert len(r_admin_all.json()["items"]) == 1
    assert r_admin_all.json()["items"][0]["bien_so_day_du"] == "99C-700.01"

    # 3. Xuất Excel danh sách tra cứu khớp bộ lọc và bảo toàn tiếng Việt có dấu (FR-081)
    r_xlsx = tinh01.get("/api/v1/bien/xuat?dau_so=600")
    assert r_xlsx.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(r_xlsx.content))
    ws = wb.active
    exported_plates = [ws.cell(row=r, column=6).value for r in range(2, ws.max_row + 1)]
    assert len(exported_plates) == 4
    assert "29MĐ1-600.02" in exported_plates


def test_five_reports_r1_to_r5_and_xlsx_export_matching_counts_ac45(
    authenticated_clients,
) -> None:
    admin = authenticated_clients["admin"]
    tinh01 = authenticated_clients["tinh_01"]
    xa1 = authenticated_clients["xa_10105001"]

    # Tạo 1 luồng đầy đủ để cả 5 báo cáo R1..R5 đều có số liệu thực tế:
    lo_xa = xa1.post("/api/v1/lo", json={"loai": "XA", "so_cong_van": "CV-BC-XA1"}).json()
    b1 = xa1.post(f"/api/v1/lo/{lo_xa['id']}/bien", json={"bien_so": "30A-810.01"}).json()
    b2 = xa1.post(f"/api/v1/lo/{lo_xa['id']}/bien", json={"bien_so": "30A-810.02"}).json()
    b3 = xa1.post(f"/api/v1/lo/{lo_xa['id']}/bien", json={"bien_so": "30A-810.03"}).json()
    xa1.post(f"/api/v1/lo/{lo_xa['id']}/gui", json={"xac_nhan": True})
    tinh01.post(f"/api/v1/lo/{lo_xa['id']}/duyet", json={"xac_nhan": True})

    dnm = tinh01.post(
        "/api/v1/lo",
        json={"loai": "DAT_NHA_MAY", "so_cong_van": "CV-BC-DNM1", "lo_con_ids": [lo_xa["id"]]},
    ).json()
    tinh01.post(f"/api/v1/lo/{dnm['id']}/gui", json={"xac_nhan": True})
    tinh01.post(f"/api/v1/lo/{dnm['id']}/duyet", json={"xac_nhan": True})
    tinh01.post(f"/api/v1/lo/{dnm['id']}/dat-thanh-cong", json={"xac_nhan": True})
    tinh01.post(f"/api/v1/lo/{dnm['id']}/nhap-kho", json={"ca_lo": True})

    # Chuyển cả 3 biển về xã 1
    tinh01.post(
        f"/api/v1/lo/{lo_xa['id']}/chuyen-xa",
        json={
            "bien_ids": [b1["id"], b2["id"], b3["id"]],
            "so_bien_ban": "BB-BC-01",
            "nguoi_nhan": "Nguyễn Văn Báo Cáo",
            "chuc_vu": "Cán bộ",
            "ngay_nhan": date.today().isoformat(),
            "xac_nhan": True,
        },
    )

    # b1: trả biển rồi thu hồi; b2: trả biển; b3: hủy biển tại xã
    now_iso = datetime.now(timezone.utc).isoformat()
    xa1.post("/api/v1/bien/tra", json={"bien_ids": [b1["id"], b2["id"]], "ngay_gio_tra": now_iso})
    xa1.post(
        "/api/v1/bien/thu-hoi",
        json={"bien_ids": [b1["id"]], "ly_do": "Thu hồi theo quyết định संग tên khác tỉnh"},
    )
    xa1.post(
        "/api/v1/bien/huy",
        json={"bien_ids": [b3["id"]], "ly_do": "Biển bị trầy xước khi vận chuyển"},
    )

    # Kiểm tra R1..R5 cho Xã 1 và đối chiếu với kết quả tra cứu trực tiếp (AC-45)
    all_xa1_plates = xa1.get("/api/v1/bien").json()["items"]

    r1 = xa1.get("/api/v1/bao-cao/R1").json()
    assert r1["tong_so_bien"] == len(all_xa1_plates)

    r2 = xa1.get("/api/v1/bao-cao/R2").json()
    expected_ton_xa = sum(1 for p in all_xa1_plates if p["tinh_trang"] == "Tồn kho xã")
    assert r2["ton_kho_xa"] == expected_ton_xa

    r3 = xa1.get("/api/v1/bao-cao/R3").json()
    assert r3["da_nhan"] >= 1

    r4 = xa1.get("/api/v1/bao-cao/R4").json()
    expected_da_tra = sum(1 for p in all_xa1_plates if p["giao"] == "Đã trả")
    expected_thu_hoi = sum(1 for p in all_xa1_plates if p["giao"] == "Thu hồi về xã")
    assert r4["tong_da_tra"] == expected_da_tra
    assert r4["tong_thu_hoi_ve_xa"] == expected_thu_hoi
    assert r4["tong_da_tra"] >= 1
    assert r4["tong_thu_hoi_ve_xa"] >= 1

    r5 = xa1.get("/api/v1/bao-cao/R5").json()
    expected_da_huy = sum(1 for p in all_xa1_plates if p["tinh_trang"] == "Đã hủy")
    assert r5["tong_da_huy"] == expected_da_huy
    assert r5["tong_thu_hoi_ve_xa"] == expected_thu_hoi
    assert r5["tong_so"] == expected_da_huy + expected_thu_hoi

    # Kiểm tra xuất Excel cho cả 5 báo cáo R1..R5 với quyền Admin
    for code in ("R1", "R2", "R3", "R4", "R5"):
        resp_json = admin.get(f"/api/v1/bao-cao/{code}")
        assert resp_json.status_code == 200
        resp_xlsx = admin.get(f"/api/v1/bao-cao/{code}/xuat")
        assert resp_xlsx.status_code == 200
        assert resp_xlsx.content[:2] == b"PK"
        wb = openpyxl.load_workbook(io.BytesIO(resp_xlsx.content))
        ws = wb.active
        assert ws.max_row - 1 == len(resp_json.json()["rows"])
