import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from biensoxe.cli import DEFAULT_XA_PASSWORD, reset_admin_account
from biensoxe.models.audit import AuditLog
from biensoxe.models.tai_khoan import TaiKhoan
from biensoxe.security.hashing import verify_password


def test_admin_lock_unlock_reset_password_forgot_queue_and_cli_reset_ac9_ac10_ac11_ac12(
    authenticated_clients, seeded_db: Session
) -> None:
    admin = authenticated_clients["admin"]
    xa2 = authenticated_clients["xa_10105002"]

    xa_tk = seeded_db.scalar(select(TaiKhoan).where(TaiKhoan.ten_dang_nhap == "10105002"))
    assert xa_tk is not None
    xa_id = xa_tk.id

    # 1. Xã đang có phiên hợp lệ
    r_me = xa2.get("/api/v1/auth/me")
    assert r_me.status_code == 200

    # 2. Khóa thủ công không có lý do -> 400 (FR-015, AC-10)
    r_lock_empty = admin.post(
        f"/api/v1/admin/tai-khoan/{xa_id}/khoa",
        json={"ly_do": "   "},
    )
    assert r_lock_empty.status_code == 400

    # Khóa thủ công có lý do -> 200, hủy phiên của xã ngay lập tức (AC-10)
    r_lock = admin.post(
        f"/api/v1/admin/tai-khoan/{xa_id}/khoa",
        json={"ly_do": "Tạm ngưng phục vụ kiểm tra định kỳ"},
    )
    assert r_lock.status_code == 200
    assert r_lock.json()["khoa_thu_cong"] is True
    assert r_lock.json()["ly_do_khoa"] == "Tạm ngưng phục vụ kiểm tra định kỳ"

    # Phiên đang mở của xã bị thu hồi ngay lập tức
    r_me_after_lock = xa2.get("/api/v1/auth/me")
    assert r_me_after_lock.status_code == 401

    # 3. Admin mở khóa tài khoản -> xóa cờ khóa thủ công và bộ đếm (AC-9)
    r_unlock = admin.post(f"/api/v1/admin/tai-khoan/{xa_id}/mo-khoa")
    assert r_unlock.status_code == 200
    assert r_unlock.json()["khoa_thu_cong"] is False
    assert r_unlock.json()["so_lan_sai"] == 0

    # 4. Admin đặt lại mật khẩu mặc định -> buộc đổi mật khẩu lần đầu và hủy phiên (AC-11)
    xa221 = authenticated_clients["xa_22113001"]
    xa221_tk = seeded_db.scalar(select(TaiKhoan).where(TaiKhoan.ten_dang_nhap == "22113001"))
    assert xa221_tk is not None
    assert xa221.get("/api/v1/auth/me").status_code == 200

    r_reset = admin.post(f"/api/v1/admin/tai-khoan/{xa221_tk.id}/dat-lai-mat-khau")
    assert r_reset.status_code == 200
    assert r_reset.json()["bat_buoc_doi_mk"] is True
    # Phiên cũ bị thu hồi ngay
    assert xa221.get("/api/v1/auth/me").status_code == 401
    # Mật khẩu trong DB đã về mặc định của xã
    seeded_db.expire_all()
    xa221_refreshed = seeded_db.scalar(select(TaiKhoan).where(TaiKhoan.id == xa221_tk.id))
    assert xa221_refreshed is not None
    assert verify_password(DEFAULT_XA_PASSWORD, xa221_refreshed.mat_khau_hash)

    # 5. Hàng đợi quên mật khẩu và xử lý của Admin (FR-018, AC-12)
    r_qmk1 = admin.post(
        "/api/v1/auth/quen-mat-khau",
        json={"ten_dang_nhap": "10105002", "lien_he": "SĐT trực ban 0912000111"},
    )
    assert r_qmk1.status_code == 200

    r_qmk2 = admin.post(
        "/api/v1/auth/quen-mat-khau",
        json={"ten_dang_nhap": "22113001", "lien_he": "SĐT trực ban 0912000222"},
    )
    assert r_qmk2.status_code == 200

    # Admin xem danh sách yêu cầu quên mật khẩu
    r_list_yc = admin.get("/api/v1/admin/yeu-cau-cap-lai-mk?trang_thai=CHO_XU_LY")
    assert r_list_yc.status_code == 200
    yc_items = r_list_yc.json()["items"]
    assert len(yc_items) >= 2
    req_101 = next(x for x in yc_items if x["ten_dang_nhap"] == "10105002")
    req_221 = next(x for x in yc_items if x["ten_dang_nhap"] == "22113001")

    # Từ chối thiếu lý do -> 400
    r_reject_bad = admin.post(
        f"/api/v1/admin/yeu-cau-cap-lai-mk/{req_221['id']}",
        json={"hanh_dong": "TU_CHOI", "ly_do_tu_choi": ""},
    )
    assert r_reject_bad.status_code == 400

    # Từ chối hợp lệ -> 200
    r_reject_ok = admin.post(
        f"/api/v1/admin/yeu-cau-cap-lai-mk/{req_221['id']}",
        json={"hanh_dong": "TU_CHOI", "ly_do_tu_choi": "Chưa có xác nhận của lãnh đạo đơn vị"},
    )
    assert r_reject_ok.status_code == 200
    assert r_reject_ok.json()["trang_thai"] == "TU_CHOI"

    # Duyệt đặt lại mật khẩu -> 200
    r_approve_ok = admin.post(
        f"/api/v1/admin/yeu-cau-cap-lai-mk/{req_101['id']}",
        json={"hanh_dong": "DAT_LAI"},
    )
    assert r_approve_ok.status_code == 200
    assert r_approve_ok.json()["trang_thai"] == "DA_DAT_LAI"

    # 6. Quy trình vận hành CLI reset-admin (FR-018)
    reset_admin_account(seeded_db, new_password="OpsResetAdmin#2026!")
    seeded_db.expire_all()
    admin_tk = seeded_db.scalar(select(TaiKhoan).where(TaiKhoan.ten_dang_nhap == "ADMINS"))
    assert admin_tk is not None
    assert admin_tk.bat_buoc_doi_mk is True
    assert admin_tk.totp_da_bat is False
    assert verify_password("OpsResetAdmin#2026!", admin_tk.mat_khau_hash)

    cli_log = seeded_db.scalar(
        select(AuditLog).where(AuditLog.hanh_dong == "DAT_LAI_MAT_KHAU_ADMIN")
    )
    assert cli_log is not None
    assert cli_log.nguoi_dung == "OPS_CLI"


def test_audit_log_query_export_and_immutability_ac15(
    authenticated_clients, seeded_db: Session
) -> None:
    admin = authenticated_clients["admin"]
    tinh01 = authenticated_clients["tinh_01"]

    # Tỉnh không được xem audit log -> 403
    assert tinh01.get("/api/v1/admin/audit-log").status_code == 403

    # Admin tạo 1 thao tác để đảm bảo có audit log
    admin.post(
        "/api/v1/danh-muc/ma-bien-tinh",
        json={"ma_bien": "39", "tinh_ma": "02"},
    )

    # Admin lọc audit log
    r_logs = admin.get("/api/v1/admin/audit-log?hanh_dong=THEM_MA_BIEN_TINH")
    assert r_logs.status_code == 200
    items = r_logs.json()["items"]
    assert len(items) >= 1
    log_id = items[0]["id"]

    # Admin xuất file .xlsx audit log
    r_export = admin.get("/api/v1/admin/audit-log/xuat?hanh_dong=THEM_MA_BIEN_TINH")
    assert r_export.status_code == 200
    assert r_export.content[:2] == b"PK"

    # Trigger DB chặn UPDATE và DELETE trên bảng audit_log (FR-021, AC-15)
    with pytest.raises(DBAPIError):
        seeded_db.execute(
            text("UPDATE audit_log SET ket_qua = 'GIA_MAO' WHERE id = :id"),
            {"id": log_id},
        )
    seeded_db.rollback()

    with pytest.raises(DBAPIError):
        seeded_db.execute(
            text("DELETE FROM audit_log WHERE id = :id"),
            {"id": log_id},
        )
    seeded_db.rollback()


def test_catalog_management_loai_pt_nen_bien_ma_bien_tinh_ac25_ac53(
    authenticated_clients, seeded_db: Session
) -> None:
    admin = authenticated_clients["admin"]
    xa1 = authenticated_clients["xa_10105001"]

    # 1. Xã không được thêm danh mục -> 403
    r_forbidden = xa1.post(
        "/api/v1/danh-muc/loai-pt",
        json={"seri_chu": "Z98", "ten": "XE THỬ NGHIỆM"},
    )
    assert r_forbidden.status_code == 403

    # 2. Admin thêm LoaiPT mới, sửa khi chưa tham chiếu, xóa khi chưa tham chiếu
    r_add_lp = admin.post(
        "/api/v1/danh-muc/loai-pt",
        json={"seri_chu": "Z98", "ten": "XE THỬ NGHIỆM 1"},
    )
    assert r_add_lp.status_code == 201
    zz_id = r_add_lp.json()["id"]

    r_upd_lp = admin.put(
        f"/api/v1/danh-muc/loai-pt/{zz_id}",
        json={"ten": "XE THỬ NGHIỆM 2"},
    )
    assert r_upd_lp.status_code == 200
    assert r_upd_lp.json()["ten"] == "XE THỬ NGHIỆM 2"

    r_del_lp = admin.delete(f"/api/v1/danh-muc/loai-pt/{zz_id}")
    assert r_del_lp.status_code == 204

    # 3. Thêm LoaiPT và NenBien rồi tạo biển tham chiếu -> chặn xóa/đổi tên/màu, chỉ cho phép ngừng sử dụng (AC-25)
    r_lp_ref = admin.post(
        "/api/v1/danh-muc/loai-pt",
        json={"seri_chu": "Z99", "ten": "XE CHUYÊN DỤNG Z99"},
    )
    assert r_lp_ref.status_code == 201
    zy_id = r_lp_ref.json()["id"]

    r_nb_ref = admin.post(
        "/api/v1/danh-muc/nen-bien",
        json={"ten": "Nền biển đặc biệt", "mau_sac": "XANH LÁ"},
    )
    assert r_nb_ref.status_code == 201
    nb_id = r_nb_ref.json()["id"]

    # Xã tạo lô và thêm biển sử dụng SeriChu Z99 và nền biển XANH LÁ
    r_lo = xa1.post(
        "/api/v1/lo",
        json={"so_cong_van": "CV-CAT-01", "loai": "XA"},
    )
    assert r_lo.status_code == 201
    lo_id = r_lo.json()["id"]

    r_bien = xa1.post(
        f"/api/v1/lo/{lo_id}/bien",
        json={"bien_so": "29Z99-123.45", "mau_sac": "XANH LÁ"},
    )
    assert r_bien.status_code == 201

    # Chặn xóa LoaiPT đã được tham chiếu -> 409
    assert admin.delete(f"/api/v1/danh-muc/loai-pt/{zy_id}").status_code == 409
    # Chặn đổi tên LoaiPT đã được tham chiếu -> 409
    assert (
        admin.put(
            f"/api/v1/danh-muc/loai-pt/{zy_id}",
            json={"ten": "ĐỔI TÊN BỊ CHẶN"},
        ).status_code
        == 409
    )
    # Chặn xóa hoặc đổi màu NenBien đã được tham chiếu -> 409
    assert admin.delete(f"/api/v1/danh-muc/nen-bien/{nb_id}").status_code == 409
    assert (
        admin.put(
            f"/api/v1/danh-muc/nen-bien/{nb_id}",
            json={"mau_sac": "TÍM"},
        ).status_code
        == 409
    )

    # Cho phép ngừng sử dụng LoaiPT và NenBien -> 200, sau đó biển mới dùng mục đó bị từ chối (AC-25)
    r_deact_lp = admin.post(f"/api/v1/danh-muc/loai-pt/{zy_id}/ngung-dung")
    assert r_deact_lp.status_code == 200
    assert r_deact_lp.json()["dang_dung"] is False

    r_bien_deact = xa1.post(
        f"/api/v1/lo/{lo_id}/bien",
        json={"bien_so": "29Z99-123.46", "mau_sac": "TRẮNG"},
    )
    assert r_bien_deact.status_code == 400

    # 4. Quản lý danh mục ma_bien_tinh (AC-53)
    r_mbt = admin.post(
        "/api/v1/danh-muc/ma-bien-tinh",
        json={"ma_bien": "40", "tinh_ma": "01"},
    )
    assert r_mbt.status_code == 201
    mbt_id = r_mbt.json()["id"]

    r_mbt_deact = admin.post(f"/api/v1/danh-muc/ma-bien-tinh/{mbt_id}/ngung-dung")
    assert r_mbt_deact.status_code == 200
    assert r_mbt_deact.json()["dang_dung"] is False
