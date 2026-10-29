from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from biensoxe.config import get_settings
from biensoxe.db import transaction
from biensoxe.domain.password_policy import (
    DEFAULT_PASSWORDS,
    check_password_expiration,
    validate_new_password,
)
from biensoxe.models.tai_khoan import (
    LichSuMatKhau,
    PhienDangNhap,
    TaiKhoan,
    YeuCauCapLaiMK,
)
from biensoxe.security.hashing import (
    hash_password,
    verify_dummy_password,
    verify_password,
)
from biensoxe.security.ratelimit import is_forgot_password_rate_limited
from biensoxe.security.session import (
    create_server_session,
    revoke_all_user_sessions,
    revoke_session,
)
from biensoxe.security.totp import (
    build_totp_provisioning_uri,
    decrypt_totp_secret,
    encrypt_totp_secret,
    generate_recovery_codes,
    generate_totp_secret,
    verify_and_consume_recovery_code,
    verify_totp_code,
)
from biensoxe.services.audit import log_audit

GENERIC_LOGIN_ERROR = "Tên đăng nhập hoặc mật khẩu không đúng."


def _register_failed_attempt(
    db: Session, user: TaiKhoan, now: datetime, ip: str | None, hanh_dong: str = "DANG_NHAP"
) -> None:
    settings = get_settings()
    user.so_lan_sai = (user.so_lan_sai or 0) + 1
    locked = False
    if user.so_lan_sai >= settings.max_failed_login_attempts:
        user.khoa_den = now + timedelta(minutes=settings.lockout_duration_minutes)
        locked = True
    log_audit(
        db,
        nguoi_dung=user.ten_dang_nhap,
        hanh_dong=hanh_dong,
        doi_tuong=user.ten_dang_nhap,
        ket_qua="THAT_BAI",
        ip=ip,
        chi_tiet={"so_lan_sai": user.so_lan_sai, "bi_khoa_tam": locked},
        thoi_diem=now,
    )


def authenticate_user(
    db: Session,
    *,
    ten_dang_nhap: str,
    mat_khau: str,
    ma_totp: str | None = None,
    ip: str | None = None,
    now: datetime | None = None,
) -> dict:
    """Xác thực đăng nhập theo FR-010, FR-011, FR-013, FR-014, FR-019 (AC-3, AC-4, AC-8, AC-9, AC-10, AC-13)."""
    current = now or datetime.now(timezone.utc)
    username = (ten_dang_nhap or "").strip()

    user = db.scalar(
        select(TaiKhoan).where(TaiKhoan.ten_dang_nhap == username).with_for_update()
    )
    if user is None:
        verify_dummy_password(mat_khau or "")
        log_audit(
            db,
            nguoi_dung=username or "UNKNOWN",
            hanh_dong="DANG_NHAP",
            doi_tuong=username or "UNKNOWN",
            ket_qua="THAT_BAI",
            ip=ip,
            chi_tiet={"ly_do": "khong_ton_tai"},
            thoi_diem=current,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=GENERIC_LOGIN_ERROR,
        )

    # Kiểm tra khóa thủ công (FR-015)
    if user.khoa_thu_cong:
        log_audit(
            db,
            nguoi_dung=user.ten_dang_nhap,
            hanh_dong="DANG_NHAP",
            doi_tuong=user.ten_dang_nhap,
            ket_qua="BI_CHAN_KHOA_THU_CONG",
            ip=ip,
            thoi_diem=current,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đang bị khóa. Vui lòng liên hệ quản trị viên.",
        )

    # Kiểm tra khóa tự động 30 phút (FR-014)
    if user.khoa_den is not None:
        khoa_den = user.khoa_den
        if khoa_den.tzinfo is None:
            khoa_den = khoa_den.replace(tzinfo=timezone.utc)
        if current < khoa_den:
            log_audit(
                db,
                nguoi_dung=user.ten_dang_nhap,
                hanh_dong="DANG_NHAP",
                doi_tuong=user.ten_dang_nhap,
                ket_qua="BI_CHAN_KHOA_TAM",
                ip=ip,
                thoi_diem=current,
            )
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tài khoản đang bị khóa tạm thời do nhập sai quá số lần quy định.",
            )
        else:
            # Hết hạn khóa tạm -> tự mở (FR-014)
            user.khoa_den = None
            user.so_lan_sai = 0

    # Kiểm tra mật khẩu
    if not verify_password(mat_khau or "", user.mat_khau_hash):
        _register_failed_attempt(db, user, current, ip)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=GENERIC_LOGIN_ERROR,
        )

    # Kiểm tra 2FA cho Admin đã bật TOTP (FR-019, AC-13)
    if user.vai_tro == "ADMIN" and user.totp_da_bat and user.totp_secret_enc:
        if not ma_totp:
            # Chưa nhập mã: chỉ yêu cầu nhập, không tính vào bộ đếm khóa (FR-014)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Yêu cầu mã xác thực 2 lớp (TOTP hoặc mã khôi phục).",
            )
        secret = decrypt_totp_secret(user.totp_secret_enc)
        totp_ok = verify_totp_code(secret, ma_totp, for_time=current)
        if not totp_ok:
            totp_ok = verify_and_consume_recovery_code(
                db, user.id, ma_totp, now=current
            )
        if not totp_ok:
            _register_failed_attempt(db, user, current, ip, hanh_dong="XAC_THUC_2FA")
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Mã xác thực 2 lớp không hợp lệ.",
            )

    # Đăng nhập thành công -> đặt lại bộ đếm sai (FR-014)
    user.so_lan_sai = 0
    user.khoa_den = None

    # Kiểm tra hết hạn 90 ngày (FR-013, AC-8)
    settings = get_settings()
    exp_status = check_password_expiration(
        user.mk_doi_luc,
        now=current,
        expire_days=settings.password_expire_days,
        warn_days=settings.password_warn_days,
    )
    if exp_status.is_expired:
        user.bat_buoc_doi_mk = True

    raw_token, csrf_token = create_server_session(
        db, user.id, ip=ip, now=current
    )
    log_audit(
        db,
        nguoi_dung=user.ten_dang_nhap,
        hanh_dong="DANG_NHAP",
        doi_tuong=user.ten_dang_nhap,
        ket_qua="THANH_CONG",
        ip=ip,
        thoi_diem=current,
    )
    db.commit()

    return {
        "session_token": raw_token,
        "csrf_token": csrf_token,
        "user": {
            "id": user.id,
            "ten_dang_nhap": user.ten_dang_nhap,
            "vai_tro": user.vai_tro,
            "tinh_ma": user.tinh_ma,
            "xa_ma": user.xa_ma,
            "bat_buoc_doi_mk": user.bat_buoc_doi_mk,
            "yeu_cau_thiet_lap_2fa": user.vai_tro == "ADMIN" and not user.totp_da_bat,
            "canh_bao_het_han_mk": exp_status.should_warn,
            "so_ngay_con_lai_mk": exp_status.days_remaining,
        },
    }


def change_password_four_steps(
    db: Session,
    *,
    session_obj: PhienDangNhap,
    mat_khau_hien_tai: str,
    mat_khau_moi: str,
    mat_khau_nhap_lai: str,
    ip: str | None = None,
    now: datetime | None = None,
) -> dict:
    """
    Luồng đổi mật khẩu 4 bước theo FR-012, FR-013 (AC-5, AC-6, AC-7):
    (1) Kiểm tra mật khẩu hiện tại (sai 5 lần liên tiếp -> hủy phiên + khóa tạm 30 phút).
    (2) Kiểm tra mật khẩu mới theo chính sách FR-013.
    (3) Kiểm tra nhập lại mật khẩu mới khớp bước 2.
    (4) Cập nhật mật khẩu, lưu lịch sử 5 bản gần nhất, hủy mọi phiên đang hoạt động.
    """
    current = now or datetime.now(timezone.utc)
    settings = get_settings()

    with transaction(db):
        user = db.scalar(
            select(TaiKhoan).where(TaiKhoan.id == session_obj.tai_khoan_id).with_for_update()
        )
        sess = db.scalar(
            select(PhienDangNhap)
            .where(PhienDangNhap.token_hash == session_obj.token_hash)
            .with_for_update()
        )
        if user is None or sess is None or sess.huy_luc is not None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Phiên không hợp lệ.")

        # Bước 1: Kiểm tra mật khẩu hiện tại
        if not verify_password(mat_khau_hien_tai or "", user.mat_khau_hash):
            sess.so_lan_sai_doi_mk = (sess.so_lan_sai_doi_mk or 0) + 1
            user.so_lan_sai = (user.so_lan_sai or 0) + 1
            if (
                sess.so_lan_sai_doi_mk >= settings.max_failed_login_attempts
                or user.so_lan_sai >= settings.max_failed_login_attempts
            ):
                user.khoa_den = current + timedelta(minutes=settings.lockout_duration_minutes)
                revoke_all_user_sessions(db, user.id, now=current)
                log_audit(
                    db,
                    nguoi_dung=user.ten_dang_nhap,
                    hanh_dong="DOI_MAT_KHAU",
                    doi_tuong=user.ten_dang_nhap,
                    ket_qua="KHOA_DO_NHAP_SAI_5_LAN",
                    ip=ip,
                    thoi_diem=current,
                )
                return {
                    "ok": False,
                    "locked": True,
                    "status_code": status.HTTP_403_FORBIDDEN,
                    "detail": "Nhập sai mật khẩu hiện tại 5 lần liên tiếp. Phiên đã bị hủy và tài khoản bị khóa tạm 30 phút.",
                }

            log_audit(
                db,
                nguoi_dung=user.ten_dang_nhap,
                hanh_dong="DOI_MAT_KHAU",
                doi_tuong=user.ten_dang_nhap,
                ket_qua="THAT_BAI",
                ip=ip,
                chi_tiet={"buoc": 1, "so_lan_sai": sess.so_lan_sai_doi_mk},
                thoi_diem=current,
            )
            return {
                "ok": False,
                "locked": False,
                "status_code": status.HTTP_400_BAD_REQUEST,
                "detail": "Mật khẩu hiện tại không đúng. Vui lòng nhập lại từ bước 1.",
            }

        # Bước 3: Kiểm tra mật khẩu mới và nhập lại khớp nhau
        if mat_khau_moi != mat_khau_nhap_lai:
            return {
                "ok": False,
                "locked": False,
                "status_code": status.HTTP_400_BAD_REQUEST,
                "detail": "Mật khẩu mới và mật khẩu nhập lại không khớp. Vui lòng thực hiện lại từ bước 1.",
            }

        # Bước 2: Kiểm tra chính sách mật khẩu mới & 5 mật khẩu gần nhất (FR-013)
        recent_histories = db.scalars(
            select(LichSuMatKhau)
            .where(LichSuMatKhau.tai_khoan_id == user.id)
            .order_by(LichSuMatKhau.tao_luc.desc(), LichSuMatKhau.id.desc())
            .limit(settings.password_history_count)
        ).all()
        matches_history = verify_password(mat_khau_moi, user.mat_khau_hash) or any(
            verify_password(mat_khau_moi, h.hash) for h in recent_histories
        )

        validation = validate_new_password(
            mat_khau_moi,
            username=user.ten_dang_nhap,
            is_admin=(user.vai_tro == "ADMIN"),
            min_len_user=settings.password_min_length_user,
            min_len_admin=settings.password_min_length_admin,
            forbidden_passwords=(*DEFAULT_PASSWORDS, settings.admin_initial_password),
            matches_recent_history=matches_history,
        )
        if not validation.is_valid:
            return {
                "ok": False,
                "locked": False,
                "status_code": status.HTTP_400_BAD_REQUEST,
                "detail": " ".join(validation.errors),
            }

        # Bước 4: Hợp lệ -> Lưu lịch sử, cập nhật mật khẩu, hủy phiên (AC-6)
        db.add(
            LichSuMatKhau(
                tai_khoan_id=user.id,
                hash=user.mat_khau_hash,
                tao_luc=current,
            )
        )
        db.flush()

        # Giữ tối đa N bản lịch sử gần nhất
        all_hist_ids = db.scalars(
            select(LichSuMatKhau.id)
            .where(LichSuMatKhau.tai_khoan_id == user.id)
            .order_by(LichSuMatKhau.tao_luc.desc(), LichSuMatKhau.id.desc())
        ).all()
        if len(all_hist_ids) > settings.password_history_count:
            ids_to_delete = all_hist_ids[settings.password_history_count :]
            db.execute(delete(LichSuMatKhau).where(LichSuMatKhau.id.in_(ids_to_delete)))

        user.mat_khau_hash = hash_password(mat_khau_moi)
        user.bat_buoc_doi_mk = False
        user.mk_doi_luc = current
        user.so_lan_sai = 0
        user.khoa_den = None

        revoke_all_user_sessions(db, user.id, now=current)
        log_audit(
            db,
            nguoi_dung=user.ten_dang_nhap,
            hanh_dong="DOI_MAT_KHAU",
            doi_tuong=user.ten_dang_nhap,
            ket_qua="THANH_CONG",
            ip=ip,
            thoi_diem=current,
        )
        return {
            "ok": True,
            "locked": False,
            "status_code": status.HTTP_200_OK,
            "detail": "Đổi mật khẩu thành công. Vui lòng đăng nhập lại.",
        }


def setup_admin_totp(
    db: Session, *, user: TaiKhoan, ip: str | None = None, now: datetime | None = None
) -> dict:
    """Khởi tạo bí mật TOTP cho Admin (FR-019, AC-13)."""
    if user.vai_tro != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ tài khoản Admin mới thiết lập xác thực 2 lớp.",
        )
    current = now or datetime.now(timezone.utc)
    secret = generate_totp_secret()
    with transaction(db):
        tk = db.scalar(select(TaiKhoan).where(TaiKhoan.id == user.id).with_for_update())
        assert tk is not None
        tk.totp_secret_enc = encrypt_totp_secret(secret)
        tk.totp_da_bat = False
        log_audit(
            db,
            nguoi_dung=tk.ten_dang_nhap,
            hanh_dong="KHOI_TAO_2FA",
            doi_tuong=tk.ten_dang_nhap,
            ket_qua="THANH_CONG",
            ip=ip,
            thoi_diem=current,
        )
    return {
        "secret": secret,
        "provisioning_uri": build_totp_provisioning_uri(secret, user.ten_dang_nhap),
    }


def confirm_admin_totp(
    db: Session,
    *,
    user: TaiKhoan,
    ma_totp: str,
    ip: str | None = None,
    now: datetime | None = None,
) -> dict:
    """Xác nhận mã TOTP lần đầu và cấp 8 mã khôi phục dùng một lần cho Admin (FR-019, AC-13)."""
    if user.vai_tro != "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền.")
    current = now or datetime.now(timezone.utc)
    with transaction(db):
        tk = db.scalar(select(TaiKhoan).where(TaiKhoan.id == user.id).with_for_update())
        if tk is None or not tk.totp_secret_enc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chưa khởi tạo thiết lập 2FA.",
            )
        secret = decrypt_totp_secret(tk.totp_secret_enc)
        if not verify_totp_code(secret, ma_totp, for_time=current):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mã TOTP xác nhận không đúng.",
            )
        tk.totp_da_bat = True
        recovery_codes = generate_recovery_codes(db, tk.id, count=8, now=current)
        log_audit(
            db,
            nguoi_dung=tk.ten_dang_nhap,
            hanh_dong="BAT_2FA",
            doi_tuong=tk.ten_dang_nhap,
            ket_qua="THANH_CONG",
            ip=ip,
            thoi_diem=current,
        )
    return {
        "totp_da_bat": True,
        "ma_khoi_phuc": recovery_codes,
    }


def submit_forgot_password_request(
    db: Session,
    *,
    ten_dang_nhap: str,
    lien_he: str,
    ip: str | None = None,
    now: datetime | None = None,
) -> dict:
    """Gửi yêu cầu cấp lại mật khẩu, phản hồi trung tính và giới hạn tần suất (FR-018, AC-12)."""
    current = now or datetime.now(timezone.utc)
    username = (ten_dang_nhap or "").strip()
    contact = (lien_he or "").strip()
    if not username or not contact:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng nhập đầy đủ tên đăng nhập và thông tin liên hệ.",
        )

    if is_forgot_password_rate_limited(db, username, ip, now=current):
        log_audit(
            db,
            nguoi_dung=username,
            hanh_dong="YEU_CAU_QUEN_MAT_KHAU",
            doi_tuong=username,
            ket_qua="BI_CHAN_TAN_SUAT",
            ip=ip,
            thoi_diem=current,
        )
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Bạn đã gửi quá nhiều yêu cầu. Vui lòng thử lại sau.",
        )

    req = YeuCauCapLaiMK(
        ten_dang_nhap=username,
        lien_he=contact,
        trang_thai="CHO_XU_LY",
        tao_luc=current,
        ip=ip or "127.0.0.1",
    )
    db.add(req)
    log_audit(
        db,
        nguoi_dung=username,
        hanh_dong="YEU_CAU_QUEN_MAT_KHAU",
        doi_tuong=username,
        ket_qua="THANH_CONG",
        ip=ip,
        thoi_diem=current,
    )
    db.commit()

    return {
        "detail": "Yêu cầu đã được ghi nhận. Quản trị viên sẽ xác minh và xử lý theo quy định."
    }


def logout_user(
    db: Session, *, raw_token: str | None, user: TaiKhoan | None, ip: str | None = None
) -> None:
    with transaction(db):
        revoke_session(db, raw_token)
        if user is not None:
            log_audit(
                db,
                nguoi_dung=user.ten_dang_nhap,
                hanh_dong="DANG_XUAT",
                doi_tuong=user.ten_dang_nhap,
                ket_qua="THANH_CONG",
                ip=ip,
            )
