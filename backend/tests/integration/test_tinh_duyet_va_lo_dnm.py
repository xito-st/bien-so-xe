def test_tinh_bulk_approve_and_reject_with_error_plates_ac32_ac36(authenticated_clients):
    """Kiểm chứng AC-32 (từ chối + đánh dấu biển lỗi + tăng so_lan_dat) và AC-36 (duyệt hàng loạt mỗi lô 1 transaction)."""
    xa1 = authenticated_clients["xa_10105001"]
    xa2 = authenticated_clients["xa_10105002"]
    tinh01 = authenticated_clients["tinh_01"]

    # Lập 3 lô xã ở tỉnh 01: 2 lô gửi hợp lệ, 1 lô vẫn đang ở Khởi tạo (không hợp lệ để duyệt)
    lo1 = xa1.post("/api/v1/lo", json={"loai": "XA", "so_cong_van": "CV-P4-01"}).json()
    b1 = xa1.post(f"/api/v1/lo/{lo1['id']}/bien", json={"bien_so": "30A-310.01"}).json()
    xa1.post(f"/api/v1/lo/{lo1['id']}/gui", json={"xac_nhan": True})

    lo2 = xa2.post("/api/v1/lo", json={"loai": "XA", "so_cong_van": "CV-P4-02"}).json()
    xa2.post(f"/api/v1/lo/{lo2['id']}/bien", json={"bien_so": "30A-310.02"})
    xa2.post(f"/api/v1/lo/{lo2['id']}/gui", json={"xac_nhan": True})

    lo3_draft = xa1.post("/api/v1/lo", json={"loai": "XA", "so_cong_van": "CV-P4-03"}).json()

    # AC-32: Tỉnh từ chối lo1 kèm lý do và đánh dấu biển b1 lỗi
    r_rej = tinh01.post(
        f"/api/v1/lo/{lo1['id']}/tu-choi",
        json={
            "ly_do": "Sai seri chữ theo hồ sơ",
            "bien_loi": [{"bien_id": b1["id"], "ly_do": "Seri không khớp đăng ký"}],
            "xac_nhan": True,
        },
    )
    assert r_rej.status_code == 200, r_rej.text
    assert r_rej.json()["trang_thai"] == "Từ chối"
    assert r_rej.json()["so_lan_dat"] == 1

    # Kiểm tra biển b1 có loi_ly_do
    plates_lo1 = xa1.get(f"/api/v1/lo/{lo1['id']}/bien").json()["items"]
    assert plates_lo1[0]["loi_ly_do"] == "Seri không khớp đăng ký"

    # Xã 1 sửa biển b1 ở trạng thái Từ chối và gửi lại -> so_lan_dat tăng lên 2, loi_ly_do được xóa
    assert xa1.put(f"/api/v1/bien/{b1['id']}", json={"bien_so": "30A-319.99"}).status_code == 200
    r_resend = xa1.post(f"/api/v1/lo/{lo1['id']}/gui", json={"xac_nhan": True})
    assert r_resend.status_code == 200
    assert r_resend.json()["trang_thai"] == "Chờ phê duyệt"
    assert r_resend.json()["so_lan_dat"] == 2
    assert xa1.get(f"/api/v1/lo/{lo1['id']}/bien").json()["items"][0]["loi_ly_do"] is None

    # AC-36: Tỉnh duyệt hàng loạt 3 lô (lo1, lo2 hợp lệ; lo3_draft đang ở Khởi tạo -> lỗi)
    r_bulk = tinh01.post(
        "/api/v1/lo/duyet-hang-loat",
        json={"lo_ids": [lo1["id"], lo2["id"], lo3_draft["id"]], "xac_nhan": True},
    )
    assert r_bulk.status_code == 200, r_bulk.text
    bulk_data = r_bulk.json()
    assert bulk_data["so_luong_thanh_cong"] == 2
    assert bulk_data["so_luong_that_bai"] == 1
    assert {item["lo_id"] for item in bulk_data["thanh_cong"]} == {lo1["id"], lo2["id"]}
    assert bulk_data["that_bai"][0]["lo_id"] == lo3_draft["id"]

    assert tinh01.get(f"/api/v1/lo/{lo1['id']}").json()["trang_thai"] == "Chấp nhận"
    assert tinh01.get(f"/api/v1/lo/{lo2['id']}").json()["trang_thai"] == "Chấp nhận"
    assert tinh01.get(f"/api/v1/lo/{lo3_draft['id']}").json()["trang_thai"] == "Khởi tạo"


def test_lo_tinh_shared_namespace_lo_dnm_adjustment_and_cancel_ac37_ac38_ac39_ac43_ac51(
    authenticated_clients,
):
    """Kiểm chứng AC-37, AC-38, AC-39, AC-43, AC-51, G-15."""
    xa1 = authenticated_clients["xa_10105001"]
    tinh01 = authenticated_clients["tinh_01"]

    # 1. Tạo lô xã và duyệt sang Chấp nhận
    lo_xa = xa1.post("/api/v1/lo", json={"loai": "XA", "so_cong_van": "CV-XA-DNM1"}).json()
    xa1.post(f"/api/v1/lo/{lo_xa['id']}/bien", json={"bien_so": "30A-410.01"})
    xa1.post(f"/api/v1/lo/{lo_xa['id']}/gui", json={"xac_nhan": True})
    tinh01.post(f"/api/v1/lo/{lo_xa['id']}/duyet", json={"xac_nhan": True})

    # 2. Tạo Lô tỉnh: kiểm tra Mã lô = {so_cong_van}-{ma_tinh}, gửi duyệt -> tự duyệt (AC-38)
    r_lo_tinh = tinh01.post(
        "/api/v1/lo",
        json={"loai": "TINH", "so_cong_van": "CV-TINH-01", "ghi_chu": "Lô cấp tỉnh"},
    )
    assert r_lo_tinh.status_code == 201, r_lo_tinh.text
    lo_tinh = r_lo_tinh.json()
    assert lo_tinh["ma_lo"] == "CV-TINH-01-01"
    tinh01.post(f"/api/v1/lo/{lo_tinh['id']}/bien", json={"bien_so": "30A-420.01"})
    assert (
        tinh01.post(f"/api/v1/lo/{lo_tinh['id']}/gui", json={"xac_nhan": True}).json()[
            "trang_thai"
        ]
        == "Chờ phê duyệt"
    )
    assert (
        tinh01.post(f"/api/v1/lo/{lo_tinh['id']}/duyet", json={"xac_nhan": True}).json()[
            "trang_thai"
        ]
        == "Chấp nhận"
    )

    # AC-51: Lô đặt nhà máy dùng trùng Số công văn với Lô tỉnh (kể cả khác hoa/thường) -> 409
    r_dup_ns = tinh01.post(
        "/api/v1/lo",
        json={"loai": "DAT_NHA_MAY", "so_cong_van": "cv-tinh-01", "lo_con_ids": [lo_xa["id"]]},
    )
    assert r_dup_ns.status_code == 409

    # AC-38: Lô đặt nhà máy không chọn lô con nào -> 400
    assert (
        tinh01.post(
            "/api/v1/lo",
            json={"loai": "DAT_NHA_MAY", "so_cong_van": "DNM-01", "lo_con_ids": []},
        ).status_code
        == 400
    )

    # 3. Tạo Lô đặt nhà máy gom cả lo_xa và lo_tinh (AC-38)
    r_dnm = tinh01.post(
        "/api/v1/lo",
        json={
            "loai": "DAT_NHA_MAY",
            "so_cong_van": "DNM-01",
            "lo_con_ids": [lo_xa["id"], lo_tinh["id"]],
        },
    )
    assert r_dnm.status_code == 201, r_dnm.text
    dnm = r_dnm.json()
    assert dnm["ma_lo"] == "DNM-01-01"
    assert dnm["so_luong_bien"] == 2

    # Kiểm tra bảng biển của lô đặt nhà máy có cột ma_lo_dat_nha_may = DNM-01-01 (FR-064, AC-38)
    dnm_plates = tinh01.get(f"/api/v1/lo/{dnm['id']}/bien").json()["items"]
    assert len(dnm_plates) == 2
    assert all(p["ma_lo_dat_nha_may"] == "DNM-01-01" for p in dnm_plates)

    # Gửi duyệt -> Chờ phê duyệt -> Tự duyệt -> Chấp nhận
    assert (
        tinh01.post(f"/api/v1/lo/{dnm['id']}/gui", json={"xac_nhan": True}).json()["trang_thai"]
        == "Chờ phê duyệt"
    )
    assert (
        tinh01.post(f"/api/v1/lo/{dnm['id']}/duyet", json={"xac_nhan": True}).json()[
            "trang_thai"
        ]
        == "Chấp nhận"
    )

    # 4. AC-37: Bật 'Cho phép điều chỉnh' trên lo_xa khi đang nằm trong dnm (đang Chấp nhận)
    # -> lo_xa chuyển sang 'Cho phép điều chỉnh', tự gỡ khỏi dnm, và dnm tự động lùi về 'Khởi tạo'
    r_adj = tinh01.post(
        f"/api/v1/lo/{lo_xa['id']}/cho-phep-dieu-chinh",
        json={"ly_do": "Cần bổ sung 1 biển cho xã"},
    )
    assert r_adj.status_code == 200
    assert r_adj.json()["trang_thai"] == "Cho phép điều chỉnh"
    assert r_adj.json()["lo_cha_id"] is None

    dnm_after_adj = tinh01.get(f"/api/v1/lo/{dnm['id']}").json()
    assert dnm_after_adj["trang_thai"] == "Khởi tạo"
    assert dnm_after_adj["so_luong_bien"] == 1

    # Cả xã và tỉnh đều thêm/sửa được biển trong lo_xa khi ở Cho phép điều chỉnh (AC-37)
    assert xa1.post(f"/api/v1/lo/{lo_xa['id']}/bien", json={"bien_so": "30A-410.02"}).status_code == 201
    assert tinh01.post(f"/api/v1/lo/{lo_xa['id']}/bien", json={"bien_so": "30A-410.03"}).status_code == 201

    # Tỉnh bấm Hoàn tất điều chỉnh -> lo_xa sang Chờ phê duyệt -> tỉnh Duyệt lại sang Chấp nhận (FR-049, AC-37)
    r_done_adj = tinh01.post(f"/api/v1/lo/{lo_xa['id']}/hoan-tat-dieu-chinh")
    assert r_done_adj.status_code == 200
    assert r_done_adj.json()["trang_thai"] == "Chờ phê duyệt"
    r_reapprove = tinh01.post(f"/api/v1/lo/{lo_xa['id']}/duyet", json={"xac_nhan": True})
    assert r_reapprove.status_code == 200
    assert r_reapprove.json()["trang_thai"] == "Chấp nhận"

    # 5. AC-39, AC-43: Hủy lô đặt nhà máy DNM-01 -> xóa hẳn lô ĐNM và trả các lô thành phần về Chấp nhận (lo_cha_id = None)
    r_cancel_dnm = tinh01.post(
        f"/api/v1/lo/{dnm['id']}/huy",
        json={"ly_do": "Hủy để gom lại đợt mới", "xac_nhan": True},
    )
    assert r_cancel_dnm.status_code == 200
    assert r_cancel_dnm.json()["da_xoa"] is True
    # Lô ĐNM đã bị xóa hoàn toàn khỏi DB
    assert tinh01.get(f"/api/v1/lo/{dnm['id']}").status_code == 404
    assert tinh01.get(f"/api/v1/lo/{lo_tinh['id']}").json()["lo_cha_id"] is None
    assert tinh01.get(f"/api/v1/lo/{lo_tinh['id']}").json()["trang_thai"] == "Chấp nhận"

    # Tạo lô đặt nhà máy mới DNM-02 chọn lại lo_xa và lo_tinh -> thành công (AC-43)
    r_dnm2 = tinh01.post(
        "/api/v1/lo",
        json={
            "loai": "DAT_NHA_MAY",
            "so_cong_van": "DNM-02",
            "lo_con_ids": [lo_xa["id"], lo_tinh["id"]],
        },
    )
    assert r_dnm2.status_code == 201
    assert r_dnm2.json()["so_luong_bien"] == 4
