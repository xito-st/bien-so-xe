from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
import pyotp
from sqlalchemy import delete, select

from biensoxe.main import create_app
from biensoxe.models.tai_khoan import LichSuMatKhau, PhienDangNhap, TaiKhoan
from biensoxe.security.hashing import hash_password


def _make_fresh_user(
    db_session,
    *,
    ten_dang_nhap: str,
    vai_tro: str,
    mat_khau: str,
    tinh_ma: str | None = None,
    xa_ma: str | None = None,
    bat_buoc_doi_mk: bool = True,
) -> TaiKhoan:
    existing = db_session.scalar(select(TaiKhoan).where(TaiKhoan.ten_dang_nhap == ten_dang_nhap))
    now = datetime.now(timezone.utc)
    if existing is None:
        tk = TaiKhoan(
            ten_dang_nhap=ten_dang_nhap,
            vai_tro=vai_tro,
            tinh_ma=tinh_ma,
            xa_ma=xa_ma,
            mat_khau_hash=hash_password(mat_khau),
            bat_buoc_doi_mk=bat_buoc_doi_mk,
            mk_doi_luc=now,
            so_lan_sai=0,
            khoa_den=None,
            khoa_thu_cong=False,
            totp_da_bat=False,
            tao_boi="TEST",
            tao_luc=now,
        )
        db_session.add(tk)
    else:
        tk = existing
        tk.mat_khau_hash = hash_password(mat_khau)
        tk.bat_buoc_doi_mk = bat_buoc_doi_mk
        tk.mk_doi_luc = now
        tk.so_lan_sai = 0
        tk.khoa_den = None
        tk.khoa_thu_cong = False
        tk.totp_da_bat = False
        tk.totp_secret_enc = None
        db_session.execute(delete(LichSuMatKhau).where(LichSuMatKhau.tai_khoan_id == tk.id))
    db_session.commit()
    return tk


def test_login_generic_error_and_first_login_force_change_ac3_ac4_ac6(client: TestClient, seeded_db):
    """Kiểm chứng AC-3, AC-4, AC-6: lỗi chung chung, bắt buộc đổi MK lần đầu, hủy phiên sau khi đổi."""
    # AC-4: Tên đăng nhập không tồn tại vs mật khẩu sai trả thông báo giống hệt nhau
    r_nonexist = client.post(
        "/api/v1/auth/login",
        json={"ten_dang_nhap": "KHONG_TON_TAI_999", "mat_khau": "WrongPass123!"},
    )
    r_wrongpw = client.post(
        "/api/v1/auth/login",
        json={"ten_dang_nhap": "10105001", "mat_khau": "WrongPass123!"},
    )
    assert r_nonexist.status_code == 401
    assert r_wrongpw.status_code == 401
    assert r_nonexist.json()["detail"] == r_wrongpw.json()["detail"]

    # Reset so_lan_sai sau thử nghiệm sai
    _make_fresh_user(
        seeded_db,
        ten_dang_nhap="10105001",
        vai_tro="XA",
        mat_khau="Abc@321",
        tinh_ma="01",
        xa_ma="10105001",
        bat_buoc_doi_mk=True,
    )

    # AC-3: Đăng nhập lần đầu bằng mật khẩu mặc định -> bị chặn truy cập các API nghiệp vụ
    r_login = client.post(
        "/api/v1/auth/login",
        json={"ten_dang_nhap": "10105001", "mat_khau": "Abc@321"},
    )
    assert r_login.status_code == 200
    assert r_login.json()["user"]["bat_buoc_doi_mk"] is True

    r_blocked = client.get("/api/v1/danh-muc/tinh")
    assert r_blocked.status_code == 403

    # AC-6: Đổi mật khẩu 4 bước hợp lệ -> phiên bị hủy, mật khẩu cũ hết tác dụng
    r_change = client.post(
        "/api/v1/auth/doi-mat-khau",
        json={
            "mat_khau_hien_tai": "Abc@321",
            "mat_khau_moi": "XaMoiHopLe@2026",
            "mat_khau_nhap_lai": "XaMoiHopLe@2026",
        },
    )
    assert r_change.status_code == 200
    assert r_change.json()["ok"] is True

    # Phiên cũ không còn dùng được
    assert client.get("/api/v1/auth/me").status_code == 401

    # Mật khẩu cũ không đăng nhập được nữa
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"ten_dang_nhap": "10105001", "mat_khau": "Abc@321"},
        ).status_code
        == 401
    )

    # Đăng nhập bằng mật khẩu mới -> vào được hệ thống
    r_new_login = client.post(
        "/api/v1/auth/login",
        json={"ten_dang_nhap": "10105001", "mat_khau": "XaMoiHopLe@2026"},
    )
    assert r_new_login.status_code == 200
    assert r_new_login.json()["user"]["bat_buoc_doi_mk"] is False
    assert client.get("/api/v1/danh-muc/tinh").status_code == 200


def test_change_password_mismatch_and_5_wrong_current_locks_ac5(client: TestClient, seeded_db):
    """Kiểm chứng AC-5 (FR-012): nhập lại không khớp báo lỗi; sai mật khẩu hiện tại 5 lần hủy phiên + khóa 30 phút."""
    _make_fresh_user(
        seeded_db,
        ten_dang_nhap="10105002",
        vai_tro="XA",
        mat_khau="Abc@321",
        tinh_ma="01",
        xa_ma="10105002",
        bat_buoc_doi_mk=True,
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"ten_dang_nhap": "10105002", "mat_khau": "Abc@321"},
        ).status_code
        == 200
    )

    # Mật khẩu mới và nhập lại không khớp
    r_mismatch = client.post(
        "/api/v1/auth/doi-mat-khau",
        json={
            "mat_khau_hien_tai": "Abc@321",
            "mat_khau_moi": "ValidPass@123",
            "mat_khau_nhap_lai": "ValidPass@999",
        },
    )
    assert r_mismatch.status_code == 400

    # Sai mật khẩu hiện tại 5 lần liên tiếp -> lần thứ 5 khóa và hủy phiên
    for i in range(1, 5):
        r_wrong = client.post(
            "/api/v1/auth/doi-mat-khau",
            json={
                "mat_khau_hien_tai": f"SaiMatKhau{i}",
                "mat_khau_moi": "ValidPass@123",
                "mat_khau_nhap_lai": "ValidPass@123",
            },
        )
        assert r_wrong.status_code == 400

    r_fifth = client.post(
        "/api/v1/auth/doi-mat-khau",
        json={
            "mat_khau_hien_tai": "SaiMatKhau5",
            "mat_khau_moi": "ValidPass@123",
            "mat_khau_nhap_lai": "ValidPass@123",
        },
    )
    assert r_fifth.status_code == 403
    assert r_fifth.json()["locked"] is True

    # Phiên đã bị hủy & thử đăng nhập đúng mật khẩu cũng bị từ chối trong 30 phút
    assert client.get("/api/v1/auth/me").status_code == 401
    r_locked_login = client.post(
        "/api/v1/auth/login",
        json={"ten_dang_nhap": "10105002", "mat_khau": "Abc@321"},
    )
    assert r_locked_login.status_code == 403


def test_auto_lockout_and_90_day_expiry_and_idle_timeout_ac8_ac9_ac16(
    client: TestClient, seeded_db
):
    """Kiểm chứng AC-8 (hết hạn 90 ngày), AC-9 (khóa tự động sau 5 lần sai), AC-16 (phiên idle 30 phút)."""
    user = _make_fresh_user(
        seeded_db,
        ten_dang_nhap="10101003",
        vai_tro="XA",
        mat_khau="MatKhauCu@123",
        tinh_ma="01",
        xa_ma="10101003",
        bat_buoc_doi_mk=False,
    )

    # AC-9: 5 lần đăng nhập sai liên tiếp -> lần 6 nhập đúng vẫn bị từ chối
    for _ in range(5):
        r = client.post(
            "/api/v1/auth/login",
            json={"ten_dang_nhap": "10101003", "mat_khau": "SaiMatKhau!"},
        )
        assert r.status_code == 401

    r_sixth = client.post(
        "/api/v1/auth/login",
        json={"ten_dang_nhap": "10101003", "mat_khau": "MatKhauCu@123"},
    )
    assert r_sixth.status_code == 403

    # Giả lập hết 30 phút khóa tạm -> đăng nhập được lại
    seeded_db.refresh(user)
    user.khoa_den = datetime.now(timezone.utc) - timedelta(seconds=10)
    seeded_db.commit()

    r_after_lock = client.post(
        "/api/v1/auth/login",
        json={"ten_dang_nhap": "10101003", "mat_khau": "MatKhauCu@123"},
    )
    assert r_after_lock.status_code == 200

    # AC-16: Giả lập phiên không hoạt động > 30 phút -> thao tác tiếp yêu cầu đăng nhập lại (401)
    sess = seeded_db.scalar(
        select(PhienDangNhap)
        .where(PhienDangNhap.tai_khoan_id == user.id, PhienDangNhap.huy_luc.is_(None))
        .order_by(PhienDangNhap.tao_luc.desc())
    )
    assert sess is not None
    sess.hoat_dong_luc = datetime.now(timezone.utc) - timedelta(minutes=31)
    seeded_db.commit()

    assert client.get("/api/v1/danh-muc/tinh").status_code == 401

    # AC-8: Giả lập mật khẩu đã dùng 90 ngày -> khi đăng nhập bị buộc đổi trước khi vào hệ thống
    seeded_db.refresh(user)
    user.mk_doi_luc = datetime.now(timezone.utc) - timedelta(days=91)
    seeded_db.commit()

    r_exp_login = client.post(
        "/api/v1/auth/login",
        json={"ten_dang_nhap": "10101003", "mat_khau": "MatKhauCu@123"},
    )
    assert r_exp_login.status_code == 200
    assert r_exp_login.json()["user"]["bat_buoc_doi_mk"] is True
    assert client.get("/api/v1/danh-muc/tinh").status_code == 403


def test_admin_2fa_setup_recovery_and_lockout_ac13(client: TestClient, seeded_db):
    """Kiểm chứng AC-13 (FR-019): Admin đổi MK lần đầu -> bắt buộc thiết lập 2FA -> cấp 8 mã khôi phục -> đăng nhập cần TOTP."""
    _make_fresh_user(
        seeded_db,
        ten_dang_nhap="ADMINS",
        vai_tro="ADMIN",
        mat_khau="AdminInit@2026!Secret",
        bat_buoc_doi_mk=True,
    )

    # 1. Đăng nhập lần đầu & đổi mật khẩu
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"ten_dang_nhap": "ADMINS", "mat_khau": "AdminInit@2026!Secret"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/auth/doi-mat-khau",
            json={
                "mat_khau_hien_tai": "AdminInit@2026!Secret",
                "mat_khau_moi": "QuanTriVien#2026!",
                "mat_khau_nhap_lai": "QuanTriVien#2026!",
            },
        ).status_code
        == 200
    )

    # 2. Đăng nhập lại sau khi đổi mật khẩu -> chưa bật 2FA nên bị chặn gọi API quản trị
    r_login2 = client.post(
        "/api/v1/auth/login",
        json={"ten_dang_nhap": "ADMINS", "mat_khau": "QuanTriVien#2026!"},
    )
    assert r_login2.status_code == 200
    assert r_login2.json()["user"]["yeu_cau_thiet_lap_2fa"] is True
    assert client.get("/api/v1/admin/tai-khoan").status_code == 403

    # 3. Khởi tạo và xác nhận 2FA -> nhận 8 mã khôi phục
    r_setup = client.post("/api/v1/auth/totp/thiet-lap")
    assert r_setup.status_code == 200
    secret = r_setup.json()["secret"]
    totp_code = pyotp.TOTP(secret).now()

    r_confirm = client.post("/api/v1/auth/totp/xac-nhan", json={"ma_totp": totp_code})
    assert r_confirm.status_code == 200
    recovery_codes = r_confirm.json()["ma_khoi_phuc"]
    assert len(recovery_codes) >= 8

    # Giờ gọi được API quản trị
    assert client.get("/api/v1/admin/tai-khoan").status_code == 200

    # 4. Đăng xuất rồi đăng nhập lại thiếu mã TOTP -> bị từ chối (401)
    client.post("/api/v1/auth/logout")
    r_no_totp = client.post(
        "/api/v1/auth/login",
        json={"ten_dang_nhap": "ADMINS", "mat_khau": "QuanTriVien#2026!"},
    )
    assert r_no_totp.status_code == 401

    # 5. Đăng nhập bằng mã TOTP hợp lệ -> thành công
    r_with_totp = client.post(
        "/api/v1/auth/login",
        json={
            "ten_dang_nhap": "ADMINS",
            "mat_khau": "QuanTriVien#2026!",
            "ma_totp": pyotp.TOTP(secret).now(),
        },
    )
    assert r_with_totp.status_code == 200
    client.post("/api/v1/auth/logout")

    # 6. Đăng nhập bằng mã khôi phục dùng 1 lần -> lần 1 thành công, dùng lại mã đó lần 2 thất bại
    one_code = recovery_codes[0]
    r_rec1 = client.post(
        "/api/v1/auth/login",
        json={
            "ten_dang_nhap": "ADMINS",
            "mat_khau": "QuanTriVien#2026!",
            "ma_totp": one_code,
        },
    )
    assert r_rec1.status_code == 200
    client.post("/api/v1/auth/logout")

    r_rec2 = client.post(
        "/api/v1/auth/login",
        json={
            "ten_dang_nhap": "ADMINS",
            "mat_khau": "QuanTriVien#2026!",
            "ma_totp": one_code,
        },
    )
    assert r_rec2.status_code == 401
