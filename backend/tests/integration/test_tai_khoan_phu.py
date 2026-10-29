from sqlalchemy import select

from biensoxe.models.audit import AuditLog
from biensoxe.models.tai_khoan import TaiKhoan
from biensoxe.security.hashing import verify_password


def test_tao_tai_khoan_phu_ac52(authenticated_clients, db_session):
    """Kiểm chứng AC-52 (FR-003): tạo tài khoản phụ theo phân quyền Admin / Tỉnh / Xã."""
    admin_client = authenticated_clients["admin"]
    tinh_01_client = authenticated_clients["tinh_01"]
    xa_01_client = authenticated_clients["xa_10105001"]

    # 1. Admin tạo tài khoản phụ cho xã 10105001 (tỉnh 01)
    r1 = admin_client.post(
        "/api/v1/tai-khoan",
        json={
            "ten_dang_nhap": "xa_10105001_phu1",
            "vai_tro": "XA",
            "tinh_ma": "01",
            "xa_ma": "10105001",
        },
    )
    assert r1.status_code == 201, r1.text
    tk_xa_phu = db_session.scalar(
        select(TaiKhoan).where(TaiKhoan.ten_dang_nhap == "xa_10105001_phu1")
    )
    assert tk_xa_phu is not None
    assert tk_xa_phu.vai_tro == "XA"
    assert tk_xa_phu.tinh_ma == "01"
    assert tk_xa_phu.xa_ma == "10105001"
    assert tk_xa_phu.bat_buoc_doi_mk is True
    assert verify_password("Abc@321", tk_xa_phu.mat_khau_hash)

    # Kiểm tra audit log
    audit = db_session.scalar(
        select(AuditLog).where(
            AuditLog.hanh_dong == "TAO_TAI_KHOAN",
            AuditLog.doi_tuong == "xa_10105001_phu1",
        )
    )
    assert audit is not None
    assert audit.ket_qua == "THANH_CONG"

    # 2. Admin tạo tài khoản phụ cho tỉnh 01
    r2 = admin_client.post(
        "/api/v1/tai-khoan",
        json={
            "ten_dang_nhap": "tinh_01_phu1",
            "vai_tro": "TINH",
            "tinh_ma": "01",
        },
    )
    assert r2.status_code == 201, r2.text
    tk_tinh_phu = db_session.scalar(
        select(TaiKhoan).where(TaiKhoan.ten_dang_nhap == "tinh_01_phu1")
    )
    assert tk_tinh_phu is not None
    assert tk_tinh_phu.vai_tro == "TINH"
    assert tk_tinh_phu.tinh_ma == "01"
    assert tk_tinh_phu.bat_buoc_doi_mk is True
    assert verify_password("Abc@!321", tk_tinh_phu.mat_khau_hash)

    # 3. Tỉnh 01 tạo tài khoản phụ cho xã thuộc tỉnh 01 -> thành công
    r3 = tinh_01_client.post(
        "/api/v1/tai-khoan",
        json={
            "ten_dang_nhap": "xa_10105001_phu2",
            "vai_tro": "XA",
            "tinh_ma": "01",
            "xa_ma": "10105001",
        },
    )
    assert r3.status_code == 201, r3.text

    # 4. Tỉnh 01 tạo cho xã thuộc tỉnh khác hoặc tạo tài khoản cấp tỉnh -> bị từ chối
    r4_other_tinh = tinh_01_client.post(
        "/api/v1/tai-khoan",
        json={
            "ten_dang_nhap": "xa_tinh02_phu",
            "vai_tro": "XA",
            "tinh_ma": "02",
            "xa_ma": "22113001",
        },
    )
    assert r4_other_tinh.status_code in (403, 404)

    r4_tinh_role = tinh_01_client.post(
        "/api/v1/tai-khoan",
        json={
            "ten_dang_nhap": "tinh_01_phu2",
            "vai_tro": "TINH",
            "tinh_ma": "01",
        },
    )
    assert r4_tinh_role.status_code == 403

    # 5. Xã đăng nhập không có quyền tạo tài khoản
    r5 = xa_01_client.post(
        "/api/v1/tai-khoan",
        json={
            "ten_dang_nhap": "xa_10105001_phu3",
            "vai_tro": "XA",
            "tinh_ma": "01",
            "xa_ma": "10105001",
        },
    )
    assert r5.status_code == 403

    # 6. Tên đăng nhập đã tồn tại -> 409
    r6 = admin_client.post(
        "/api/v1/tai-khoan",
        json={
            "ten_dang_nhap": "xa_10105001_phu1",
            "vai_tro": "XA",
            "tinh_ma": "01",
            "xa_ma": "10105001",
        },
    )
    assert r6.status_code == 409
