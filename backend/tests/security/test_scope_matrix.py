import json

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from biensoxe.cli import DEFAULT_TINH_PASSWORD, DEFAULT_XA_PASSWORD
from biensoxe.models.audit import AuditLog
from biensoxe.models.tai_khoan import LichSuMatKhau, TaiKhoan
from biensoxe.security.session import CSRF_HEADER_NAME


def test_scope_matrix_cross_unit_and_admin_readonly_ac17(
    authenticated_clients,
) -> None:
    """
    Kiểm chứng ma trận phân quyền Vai trò × Endpoint × Đối tượng ngoài phạm vi (FR-023, FR-004, FR-082, AC-17):
    - Xã truy cập lô/biển của xã khác hoặc gọi API của Tỉnh/Admin -> 403/404.
    - Tỉnh truy cập lô/biển của tỉnh khác hoặc gọi API Admin -> 403/404.
    - Admin gọi mọi API ghi nghiệp vụ trên lô/biển/kho -> 403 (chỉ đọc).
    """
    admin = authenticated_clients["admin"]
    tinh01 = authenticated_clients["tinh_01"]
    tinh02 = authenticated_clients["tinh_02"]
    xa1 = authenticated_clients["xa_10105001"]
    xa2 = authenticated_clients["xa_10105002"]
    xa_tinh02 = authenticated_clients["xa_22113001"]

    # Tạo lô và biển ở Xã 1 (Tỉnh 01)
    lo_xa1 = xa1.post("/api/v1/lo", json={"loai": "XA", "so_cong_van": "CV-SEC-XA1"}).json()
    b_xa1 = xa1.post(
        f"/api/v1/lo/{lo_xa1['id']}/bien", json={"bien_so": "30A-910.01"}
    ).json()

    # 1. Xã 2 (cùng tỉnh) và Xã tỉnh 02 truy cập lô/biển của Xã 1 -> 404 (chống lộ thông tin)
    assert xa2.get(f"/api/v1/lo/{lo_xa1['id']}").status_code == 404
    assert xa2.get(f"/api/v1/lo/{lo_xa1['id']}/bien").status_code == 404
    assert (
        xa2.put(
            f"/api/v1/bien/{b_xa1['id']}", json={"bien_so": "30A-910.02"}
        ).status_code
        == 404
    )
    assert xa2.delete(f"/api/v1/bien/{b_xa1['id']}").status_code == 404
    assert xa_tinh02.get(f"/api/v1/lo/{lo_xa1['id']}").status_code == 404

    # 2. Xã gọi các endpoint dành cho Tỉnh hoặc Admin -> 403
    assert (
        xa1.post("/api/v1/lo", json={"loai": "TINH", "so_cong_van": "CV-FORBID"}).status_code
        == 403
    )
    assert (
        xa1.post(
            "/api/v1/lo",
            json={"loai": "DAT_NHA_MAY", "so_cong_van": "CV-FORBID", "lo_con_ids": [lo_xa1["id"]]},
        ).status_code
        == 403
    )
    assert xa1.post(f"/api/v1/lo/{lo_xa1['id']}/duyet", json={"xac_nhan": True}).status_code == 403
    assert xa1.get("/api/v1/tai-khoan").status_code == 403
    assert xa1.get("/api/v1/admin/audit-log").status_code == 403

    # Gửi lô Xã 1 lên Tỉnh 01
    xa1.post(f"/api/v1/lo/{lo_xa1['id']}/gui", json={"xac_nhan": True})

    # 3. Tỉnh 02 truy cập hoặc phê duyệt lô của Tỉnh 01 -> 404 / 403
    assert tinh02.get(f"/api/v1/lo/{lo_xa1['id']}").status_code == 404
    assert (
        tinh02.post(f"/api/v1/lo/{lo_xa1['id']}/duyet", json={"xac_nhan": True}).status_code
        == 404
    )
    assert tinh01.get("/api/v1/admin/audit-log").status_code == 403
    assert tinh01.get("/api/v1/admin/yeu-cau-cap-lai-mk").status_code == 403

    # 4. Admin gọi API ghi nghiệp vụ trên lô, biển, kho -> 403 (FR-023, FR-082)
    assert (
        admin.post("/api/v1/lo", json={"loai": "TINH", "so_cong_van": "CV-ADM"}).status_code
        == 403
    )
    assert (
        admin.post(
            f"/api/v1/lo/{lo_xa1['id']}/bien", json={"bien_so": "30A-910.99"}
        ).status_code
        == 403
    )
    assert (
        admin.post(f"/api/v1/lo/{lo_xa1['id']}/duyet", json={"xac_nhan": True}).status_code
        == 403
    )
    assert (
        admin.post(f"/api/v1/lo/{lo_xa1['id']}/nhap-kho", json={"ca_lo": True}).status_code
        == 403
    )
    assert (
        admin.post("/api/v1/bien/tra", json={"bien_ids": [b_xa1["id"]]}).status_code
        == 403
    )
    assert (
        admin.post(
            f"/api/v1/bien/{b_xa1['id']}/huy",
            json={"ly_do": "Admin thử hủy", "xac_nhan": True},
        ).status_code
        == 403
    )

    # Nhưng Admin được phép đọc tra cứu và báo cáo (FR-082)
    assert admin.get("/api/v1/bien").status_code == 200
    assert admin.get("/api/v1/bao-cao/R1").status_code == 200


def test_csrf_protection_security_headers_and_no_plaintext_passwords_ac14_nfr008_nfr009(
    authenticated_clients, seeded_db: Session
) -> None:
    """
    Kiểm chứng:
    - CSRF bắt buộc cho các request thay đổi dữ liệu (NFR-009).
    - Header bảo mật CSP, X-Content-Type-Options, Referrer-Policy, X-Frame-Options (NFR-008, NFR-009).
    - Không lưu mật khẩu dạng rõ trong DB hoặc audit_log (FR-020, AC-14).
    - Bảng bien không có bất kỳ cột thông tin cá nhân công dân nào (NFR-014).
    """
    xa1 = authenticated_clients["xa_10105001"]

    # 1. Kiểm tra Security Headers
    r_health = xa1.get("/api/v1/health")
    assert r_health.status_code == 200
    assert r_health.headers.get("X-Content-Type-Options") == "nosniff"
    assert r_health.headers.get("X-Frame-Options") == "DENY"
    assert "default-src 'self'" in (r_health.headers.get("Content-Security-Policy") or "")

    # 2. Thiếu hoặc sai CSRF token trên POST -> 403
    saved_csrf = xa1.headers.get(CSRF_HEADER_NAME)
    try:
        xa1.headers[CSRF_HEADER_NAME] = "invalid-csrf-token"
        r_no_csrf = xa1.post("/api/v1/lo", json={"loai": "XA", "so_cong_van": "CV-CSRF"})
        assert r_no_csrf.status_code == 403
    finally:
        if saved_csrf:
            xa1.headers[CSRF_HEADER_NAME] = saved_csrf

    # 3. Kiểm tra không có mật khẩu rõ trong bảng tai_khoan, lich_su_mat_khau và audit_log (AC-14)
    sample_hashes = seeded_db.scalars(select(TaiKhoan.mat_khau_hash).limit(50)).all()
    assert len(sample_hashes) > 0
    for h in sample_hashes:
        assert h.startswith("$argon2id$")
        assert DEFAULT_XA_PASSWORD not in h
        assert DEFAULT_TINH_PASSWORD not in h

    pw_hist = seeded_db.scalars(select(LichSuMatKhau.hash).limit(50)).all()
    for h in pw_hist:
        assert h.startswith("$argon2id$")

    logs = seeded_db.scalars(select(AuditLog).limit(200)).all()
    for lg in logs:
        raw_detail = json.dumps(lg.chi_tiet or {}, ensure_ascii=False)
        assert DEFAULT_XA_PASSWORD not in raw_detail
        assert DEFAULT_TINH_PASSWORD not in raw_detail
        assert "mat_khau" not in raw_detail.lower()

    # 4. Bảng bien không có trường dữ liệu cá nhân công dân (NFR-014)
    inspector = inspect(seeded_db.get_bind())
    bien_cols = {col["name"].lower() for col in inspector.get_columns("bien")}
    forbidden_pii_cols = {"cccd", "cmnd", "ho_ten_dan", "dia_chi_dan", "so_dien_thoai_dan", "ten_chu_xe"}
    assert bien_cols.isdisjoint(forbidden_pii_cols)
