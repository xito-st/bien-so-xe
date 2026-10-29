from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from biensoxe.cli import DEFAULT_TINH_PASSWORD, DEFAULT_XA_PASSWORD
from biensoxe.db import transaction
from biensoxe.models.danh_muc import Tinh, XaPhuong
from biensoxe.models.tai_khoan import TaiKhoan, YeuCauCapLaiMK
from biensoxe.repositories.scope import ScopeFilter
from biensoxe.security.hashing import hash_password
from biensoxe.security.session import revoke_all_user_sessions
from biensoxe.services.audit import log_audit


def list_tai_khoan(
    db: Session,
    scope: ScopeFilter,
    *,
    vai_tro: str | None = None,
    tinh_ma: str | None = None,
    xa_ma: str | None = None,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[TaiKhoan]:
    if scope.is_xa:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản xã/phường không có quyền quản lý danh sách tài khoản.",
        )
    stmt = select(TaiKhoan)
    if scope.is_tinh:
        stmt = stmt.where(TaiKhoan.tinh_ma == scope.tinh_ma)
    if vai_tro:
        stmt = stmt.where(TaiKhoan.vai_tro == vai_tro)
    if tinh_ma:
        scope.ensure_in_scope(tinh_ma)
        stmt = stmt.where(TaiKhoan.tinh_ma == tinh_ma)
    if xa_ma:
        stmt = stmt.where(TaiKhoan.xa_ma == xa_ma)
    if q:
        stmt = stmt.where(TaiKhoan.ten_dang_nhap.ilike(f"%{q.strip()}%"))
    stmt = stmt.order_by(TaiKhoan.id.asc()).limit(min(limit, 500)).offset(max(0, offset))
    return list(db.scalars(stmt).all())


def create_supplementary_account(
    db: Session,
    scope: ScopeFilter,
    *,
    ten_dang_nhap: str,
    vai_tro: str,
    tinh_ma: str | None,
    xa_ma: str | None = None,
    ip: str | None = None,
    now: datetime | None = None,
) -> TaiKhoan:
    """Tạo tài khoản phụ cho đơn vị theo FR-003 (AC-52)."""
    if scope.is_xa:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Xã/phường không có chức năng tạo tài khoản.",
        )

    username = (ten_dang_nhap or "").strip()
    if not username or len(username) > 64:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tên đăng nhập không hợp lệ (1–64 ký tự).",
        )

    role = (vai_tro or "").strip().upper()
    if role not in ("TINH", "XA"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chỉ được tạo tài khoản phụ cho vai trò TINH hoặc XA.",
        )

    if scope.is_tinh:
        if role != "XA":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tỉnh/thành chỉ được tạo tài khoản phụ cho xã/phường trực thuộc.",
            )
        if tinh_ma and tinh_ma != scope.tinh_ma:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Không được tạo tài khoản cho xã/phường thuộc tỉnh khác.",
            )
        tinh_ma = scope.tinh_ma

    current = now or datetime.now(timezone.utc)

    with transaction(db):
        existing = db.scalar(select(TaiKhoan).where(TaiKhoan.ten_dang_nhap == username))
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Tên đăng nhập '{username}' đã tồn tại.",
            )

        if role == "TINH":
            if not tinh_ma:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Phải chọn tỉnh/thành cho tài khoản cấp tỉnh.",
                )
            tinh_obj = db.scalar(select(Tinh).where(Tinh.ma == tinh_ma))
            if tinh_obj is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Không tìm thấy tỉnh/thành.",
                )
            xa_ma = None
            default_pw = DEFAULT_TINH_PASSWORD
        else:
            if not xa_ma:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Phải chọn xã/phường cho tài khoản cấp xã.",
                )
            xa_obj = db.scalar(select(XaPhuong).where(XaPhuong.ma == xa_ma))
            if xa_obj is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Không tìm thấy xã/phường.",
                )
            if scope.is_tinh and xa_obj.tinh_ma != scope.tinh_ma:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Xã/phường không thuộc tỉnh của bạn.",
                )
            if tinh_ma and tinh_ma != xa_obj.tinh_ma:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Xã/phường không khớp với mã tỉnh đã chọn.",
                )
            tinh_ma = xa_obj.tinh_ma
            default_pw = DEFAULT_XA_PASSWORD

        tk = TaiKhoan(
            ten_dang_nhap=username,
            vai_tro=role,
            tinh_ma=tinh_ma,
            xa_ma=xa_ma,
            mat_khau_hash=hash_password(default_pw),
            bat_buoc_doi_mk=True,
            mk_doi_luc=current,
            so_lan_sai=0,
            khoa_den=None,
            khoa_thu_cong=False,
            totp_da_bat=False,
            tao_boi=scope.ten_dang_nhap,
            tao_luc=current,
        )
        db.add(tk)
        db.flush()

        log_audit(
            db,
            nguoi_dung=scope.ten_dang_nhap,
            hanh_dong="TAO_TAI_KHOAN",
            doi_tuong=username,
            ket_qua="THANH_CONG",
            ip=ip,
            chi_tiet={"vai_tro": role, "tinh_ma": tinh_ma, "xa_ma": xa_ma},
            thoi_diem=current,
        )
        return tk


def lock_account_manually(
    db: Session,
    scope: ScopeFilter,
    *,
    tai_khoan_id: int,
    ly_do: str,
    ip: str | None = None,
    now: datetime | None = None,
) -> TaiKhoan:
    """Admin khóa thủ công tài khoản tỉnh/xã kèm lý do, hủy mọi phiên ngay (FR-015, AC-10)."""
    if not scope.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ Admin được khóa tài khoản.")
    reason = (ly_do or "").strip()
    if not reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bắt buộc phải nhập lý do khóa tài khoản (FR-015).",
        )
    current = now or datetime.now(timezone.utc)
    with transaction(db):
        tk = db.scalar(select(TaiKhoan).where(TaiKhoan.id == tai_khoan_id).with_for_update())
        if tk is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài khoản.")
        if tk.vai_tro == "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Không được khóa tài khoản Admin.",
            )
        tk.khoa_thu_cong = True
        tk.ly_do_khoa = reason
        revoke_all_user_sessions(db, tk.id, now=current)
        log_audit(
            db,
            nguoi_dung=scope.ten_dang_nhap,
            hanh_dong="KHOA_TAI_KHOAN",
            doi_tuong=tk.ten_dang_nhap,
            ket_qua="THANH_CONG",
            ip=ip,
            chi_tiet={"ly_do": reason},
            thoi_diem=current,
        )
        return tk


def unlock_account(
    db: Session,
    scope: ScopeFilter,
    *,
    tai_khoan_id: int,
    ip: str | None = None,
    now: datetime | None = None,
) -> TaiKhoan:
    """Admin mở khóa tài khoản (cả tự động và thủ công), đặt lại bộ đếm sai (FR-016, AC-9)."""
    if not scope.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ Admin được mở khóa tài khoản.")
    current = now or datetime.now(timezone.utc)
    with transaction(db):
        tk = db.scalar(select(TaiKhoan).where(TaiKhoan.id == tai_khoan_id).with_for_update())
        if tk is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài khoản.")
        tk.khoa_thu_cong = False
        tk.ly_do_khoa = None
        tk.khoa_den = None
        tk.so_lan_sai = 0
        log_audit(
            db,
            nguoi_dung=scope.ten_dang_nhap,
            hanh_dong="MO_KHOA_TAI_KHOAN",
            doi_tuong=tk.ten_dang_nhap,
            ket_qua="THANH_CONG",
            ip=ip,
            thoi_diem=current,
        )
        return tk


def reset_account_password(
    db: Session,
    scope: ScopeFilter,
    *,
    tai_khoan_id: int,
    ip: str | None = None,
    now: datetime | None = None,
) -> TaiKhoan:
    """Admin đặt lại mật khẩu mặc định cho tài khoản tỉnh/xã, buộc đổi lần đầu và hủy phiên (FR-017, AC-11)."""
    if not scope.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ Admin được đặt lại mật khẩu.",
        )
    current = now or datetime.now(timezone.utc)
    with transaction(db):
        tk = db.scalar(select(TaiKhoan).where(TaiKhoan.id == tai_khoan_id).with_for_update())
        if tk is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tài khoản.")
        if tk.vai_tro == "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Khôi phục mật khẩu Admin phải thực hiện qua quy trình vận hành CLI (FR-018).",
            )
        default_pw = DEFAULT_TINH_PASSWORD if tk.vai_tro == "TINH" else DEFAULT_XA_PASSWORD
        tk.mat_khau_hash = hash_password(default_pw)
        tk.bat_buoc_doi_mk = True
        tk.mk_doi_luc = current
        tk.so_lan_sai = 0
        tk.khoa_den = None
        revoke_all_user_sessions(db, tk.id, now=current)
        log_audit(
            db,
            nguoi_dung=scope.ten_dang_nhap,
            hanh_dong="DAT_LAI_MAT_KHAU",
            doi_tuong=tk.ten_dang_nhap,
            ket_qua="THANH_CONG",
            ip=ip,
            thoi_diem=current,
        )
        return tk


def list_forgot_password_requests(
    db: Session,
    scope: ScopeFilter,
    *,
    trang_thai: str | None = None,
) -> list[YeuCauCapLaiMK]:
    if not scope.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ Admin được xem.")
    stmt = select(YeuCauCapLaiMK)
    if trang_thai:
        stmt = stmt.where(YeuCauCapLaiMK.trang_thai == trang_thai)
    stmt = stmt.order_by(YeuCauCapLaiMK.tao_luc.desc(), YeuCauCapLaiMK.id.desc())
    return list(db.scalars(stmt).all())


def process_forgot_password_request(
    db: Session,
    scope: ScopeFilter,
    *,
    req_id: int,
    hanh_dong: str,
    ly_do_tu_choi: str | None = None,
    ip: str | None = None,
    now: datetime | None = None,
) -> YeuCauCapLaiMK:
    """Admin xử lý yêu cầu quên mật khẩu: đặt lại về mặc định hoặc từ chối kèm lý do (FR-018, AC-12)."""
    if not scope.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ Admin được xử lý.")
    action = (hanh_dong or "").strip().upper()
    if action not in ("DAT_LAI", "TU_CHOI"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hành động phải là DAT_LAI hoặc TU_CHOI.",
        )
    current = now or datetime.now(timezone.utc)
    with transaction(db):
        req = db.scalar(
            select(YeuCauCapLaiMK).where(YeuCauCapLaiMK.id == req_id).with_for_update()
        )
        if req is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy yêu cầu.")
        if req.trang_thai != "CHO_XU_LY":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Yêu cầu này đã được xử lý trước đó.",
            )

        if action == "TU_CHOI":
            reason = (ly_do_tu_choi or "").strip()
            if not reason:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Bắt buộc nhập lý do khi từ chối yêu cầu quên mật khẩu.",
                )
            req.trang_thai = "TU_CHOI"
            req.ly_do_tu_choi = reason
            req.xu_ly_boi = scope.ten_dang_nhap
            req.xu_ly_luc = current
            log_audit(
                db,
                nguoi_dung=scope.ten_dang_nhap,
                hanh_dong="TU_CHOI_YEU_CAU_QUEN_MK",
                doi_tuong=req.ten_dang_nhap,
                ket_qua="THANH_CONG",
                ip=ip,
                chi_tiet={"req_id": req.id, "ly_do": reason},
                thoi_diem=current,
            )
            return req

        # DAT_LAI
        tk = db.scalar(
            select(TaiKhoan)
            .where(TaiKhoan.ten_dang_nhap == req.ten_dang_nhap)
            .with_for_update()
        )
        if tk is None or tk.vai_tro == "ADMIN":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tài khoản không tồn tại hoặc không hỗ trợ đặt lại qua hàng đợi.",
            )
        default_pw = DEFAULT_TINH_PASSWORD if tk.vai_tro == "TINH" else DEFAULT_XA_PASSWORD
        tk.mat_khau_hash = hash_password(default_pw)
        tk.bat_buoc_doi_mk = True
        tk.mk_doi_luc = current
        tk.so_lan_sai = 0
        tk.khoa_den = None
        revoke_all_user_sessions(db, tk.id, now=current)

        req.trang_thai = "DA_DAT_LAI"
        req.xu_ly_boi = scope.ten_dang_nhap
        req.xu_ly_luc = current
        log_audit(
            db,
            nguoi_dung=scope.ten_dang_nhap,
            hanh_dong="DUYET_YEU_CAU_QUEN_MK",
            doi_tuong=tk.ten_dang_nhap,
            ket_qua="THANH_CONG",
            ip=ip,
            chi_tiet={"req_id": req.id},
            thoi_diem=current,
        )
        return req

