from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from biensoxe.models.bien import Bien
from biensoxe.models.danh_muc import Tinh, XaPhuong
from biensoxe.models.lo import Lo, LoLichSu
from biensoxe.repositories.scope import ScopeFilter
from biensoxe.services.audit import write_audit_log
from biensoxe.services.bien import check_plate_duplicates
from biensoxe.services.sync import create_or_run_sync_job, get_sync_status


def serialize_lo(db: Session, lo: Lo) -> dict:
    tinh = db.get(Tinh, lo.tinh_ma)
    xa = db.get(XaPhuong, lo.xa_ma) if lo.xa_ma else None
    parent = db.get(Lo, lo.lo_cha_id) if lo.lo_cha_id else None

    if lo.loai == "DAT_NHA_MAY":
        child_los = db.scalars(select(Lo).where(Lo.lo_cha_id == lo.id).order_by(Lo.id.asc())).all()
        child_ids = [c.id for c in child_los]
        if child_ids:
            total_bien = (
                db.scalar(
                    select(func.count(Bien.id)).where(
                        Bien.lo_id.in_(child_ids),
                        Bien.tinh_trang != "Đã hủy",
                    )
                )
                or 0
            )
            nhap_kho_count = (
                db.scalar(
                    select(func.count(Bien.id)).where(
                        Bien.lo_id.in_(child_ids),
                        Bien.tinh_trang.in_(("Tồn kho tỉnh", "Tồn kho xã")),
                    )
                )
                or 0
            )
            ngoai_tinh_count = (
                db.scalar(
                    select(func.count(Bien.id)).where(
                        Bien.lo_id.in_(child_ids),
                        Bien.ngoai_tinh.is_(True),
                        Bien.tinh_trang != "Đã hủy",
                    )
                )
                or 0
            )
        else:
            total_bien = 0
            nhap_kho_count = 0
            ngoai_tinh_count = 0
        lo_con_summary = [
            {
                "id": c.id,
                "ma_lo": c.ma_lo,
                "loai": c.loai,
                "xa_ma": c.xa_ma,
                "trang_thai": c.trang_thai,
            }
            for c in child_los
        ]
    else:
        total_bien = (
            db.scalar(
                select(func.count(Bien.id)).where(
                    Bien.lo_id == lo.id,
                    Bien.tinh_trang != "Đã hủy",
                )
            )
            or 0
        )
        nhap_kho_count = (
            db.scalar(
                select(func.count(Bien.id)).where(
                    Bien.lo_id == lo.id,
                    Bien.tinh_trang.in_(("Tồn kho tỉnh", "Tồn kho xã")),
                )
            )
            or 0
        )
        ngoai_tinh_count = (
            db.scalar(
                select(func.count(Bien.id)).where(
                    Bien.lo_id == lo.id,
                    Bien.ngoai_tinh.is_(True),
                    Bien.tinh_trang != "Đã hủy",
                )
            )
            or 0
        )
        lo_con_summary = []

    sync_status = get_sync_status(db, lo.id) if lo.loai == "XA" else "KHONG_AP_DUNG"

    return {
        "id": lo.id,
        "loai": lo.loai,
        "tinh_ma": lo.tinh_ma,
        "tinh_ten": tinh.ten if tinh else None,
        "xa_ma": lo.xa_ma,
        "xa_ten": xa.ten if xa else None,
        "don_vi_ten": xa.ten if xa else (tinh.ten if tinh else None),
        "don_vi": xa.ten if xa else (tinh.ten if tinh else None),
        "so_cong_van": lo.so_cong_van,
        "ma_lo": lo.ma_lo,
        "trang_thai": lo.trang_thai,
        "lo_cha_id": lo.lo_cha_id,
        "ma_lo_dat_nha_may": parent.ma_lo if parent else None,
        "so_lan_dat": lo.so_lan_dat,
        "ghi_chu": lo.ghi_chu,
        "ly_do": lo.ly_do,
        "tao_boi": lo.tao_boi,
        "tao_luc": lo.tao_luc.isoformat() if lo.tao_luc else None,
        "so_luong_bien": total_bien,
        "so_luong_nhap_kho": nhap_kho_count,
        "so_luong_ngoai_tinh": ngoai_tinh_count,
        "trang_thai_dong_bo": sync_status,
        "lo_con": lo_con_summary,
    }


def _validate_so_cong_van(raw_cv: str) -> tuple[str, str]:
    cv = (raw_cv or "").strip()
    if not cv or len(cv) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Số công văn bắt buộc và có độ dài tối đa 50 ký tự (FR-041).",
        )
    return cv, cv.upper()


def _check_unique_so_cv(
    db: Session,
    *,
    loai: str,
    tinh_ma: str,
    xa_ma: str | None,
    so_cv_chuan: str,
    exclude_lo_id: int | None = None,
) -> None:
    if loai == "XA":
        stmt = select(Lo).where(
            Lo.loai == "XA",
            Lo.xa_ma == xa_ma,
            Lo.so_cv_chuan == so_cv_chuan,
        )
        if exclude_lo_id is not None:
            stmt = stmt.where(Lo.id != exclude_lo_id)
        existing = db.scalar(stmt)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Số công văn '{existing.so_cong_van}' đã tồn tại ở xã/phường này (Mã lô: {existing.ma_lo}).",
            )
    else:
        stmt = select(Lo).where(
            Lo.loai.in_(("TINH", "DAT_NHA_MAY")),
            Lo.tinh_ma == tinh_ma,
            Lo.so_cv_chuan == so_cv_chuan,
        )
        if exclude_lo_id is not None:
            stmt = stmt.where(Lo.id != exclude_lo_id)
        existing = db.scalar(stmt)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Số công văn '{existing.so_cong_van}' đã được sử dụng trong không gian mã của tỉnh (Mã lô: {existing.ma_lo}).",
            )


def _validate_and_attach_children_for_dnm(
    db: Session,
    *,
    dnm_lo: Lo,
    lo_con_ids: list[int],
) -> None:
    clean_ids = list(dict.fromkeys(lo_con_ids or []))
    if not clean_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lô đặt nhà máy phải chọn ít nhất 1 lô xã hoặc lô tỉnh ở trạng thái 'Chấp nhận' (FR-063).",
        )

    old_children = db.scalars(select(Lo).where(Lo.lo_cha_id == dnm_lo.id)).all()
    for oc in old_children:
        if oc.id not in clean_ids:
            oc.lo_cha_id = None

    for cid in clean_ids:
        child = db.get(Lo, cid)
        if child is None or child.tinh_ma != dnm_lo.tinh_ma:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy lô thành phần ID={cid} thuộc cùng tỉnh.",
            )
        if child.loai not in ("XA", "TINH"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chỉ được gom lô xã hoặc lô tỉnh vào lô đặt nhà máy.",
            )
        if child.trang_thai != "Chấp nhận":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Lô '{child.ma_lo}' đang ở trạng thái '{child.trang_thai}', chỉ được chọn lô ở trạng thái 'Chấp nhận'.",
            )
        if child.lo_cha_id is not None and child.lo_cha_id != dnm_lo.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Lô '{child.ma_lo}' đã thuộc một lô đặt nhà máy khác.",
            )
        plate_cnt = (
            db.scalar(
                select(func.count(Bien.id)).where(
                    Bien.lo_id == child.id,
                    Bien.tinh_trang != "Đã hủy",
                )
            )
            or 0
        )
        if plate_cnt == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Lô '{child.ma_lo}' không có biển số hợp lệ nào.",
            )
        child.lo_cha_id = dnm_lo.id


def create_lo(
    db: Session,
    scope: ScopeFilter,
    *,
    loai: str,
    so_cong_van: str,
    ghi_chu: str | None = None,
    lo_con_ids: list[int] | None = None,
    ip: str | None = None,
) -> dict:
    """Tạo lô mới (XA, TINH, DAT_NHA_MAY) và sinh Mã lô ngay khi lưu (FR-040..045, FR-062..064, AC-30, AC-38, AC-51)."""
    scope.require_non_admin_for_mutation()
    loai_norm = (loai or "XA").strip().upper()
    if loai_norm not in ("XA", "TINH", "DAT_NHA_MAY"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Loại lô không hợp lệ.")

    cv, cv_chuan = _validate_so_cong_van(so_cong_van)

    if loai_norm == "XA":
        if not scope.is_xa or not scope.xa_ma or not scope.tinh_ma:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chỉ tài khoản xã/phường mới được tạo lô xã.",
            )
        tinh_ma = scope.tinh_ma
        xa_ma = scope.xa_ma
        ma_lo = f"{cv}-{xa_ma}"
    else:
        if not scope.is_tinh or not scope.tinh_ma:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chỉ tài khoản tỉnh/thành mới được tạo lô tỉnh hoặc lô đặt nhà máy.",
            )
        tinh_ma = scope.tinh_ma
        xa_ma = None
        ma_lo = f"{cv}-{tinh_ma}"

    _check_unique_so_cv(
        db,
        loai=loai_norm,
        tinh_ma=tinh_ma,
        xa_ma=xa_ma,
        so_cv_chuan=cv_chuan,
    )

    now = datetime.now(timezone.utc)
    lo = Lo(
        loai=loai_norm,
        tinh_ma=tinh_ma,
        xa_ma=xa_ma,
        so_cong_van=cv,
        so_cv_chuan=cv_chuan,
        ma_lo=ma_lo,
        trang_thai="Khởi tạo",
        lo_cha_id=None,
        so_lan_dat=1,
        ghi_chu=(ghi_chu or "").strip() or None,
        ly_do=None,
        tao_boi=scope.ten_dang_nhap,
        tao_luc=now,
    )
    db.add(lo)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Số công văn / Mã lô đã tồn tại.",
        ) from exc

    if loai_norm == "DAT_NHA_MAY":
        _validate_and_attach_children_for_dnm(db, dnm_lo=lo, lo_con_ids=lo_con_ids or [])

    db.add(
        LoLichSu(
            lo_id=lo.id,
            tu=None,
            den="Khởi tạo",
            nguoi=scope.ten_dang_nhap,
            luc=now,
            ly_do=None,
        )
    )
    write_audit_log(
        db,
        nguoi_dung=scope.ten_dang_nhap,
        hanh_dong=f"TAO_LO_{loai_norm}",
        doi_tuong=lo.ma_lo,
        ket_qua="THANH_CONG",
        ip=ip,
        chi_tiet={"lo_id": lo.id, "loai": lo.loai, "lo_con_ids": lo_con_ids},
    )
    db.commit()
    return serialize_lo(db, lo)


def list_lo(
    db: Session,
    scope: ScopeFilter,
    *,
    loai: str | None = None,
    trang_thai: str | None = None,
    tinh_ma: str | None = None,
    xa_ma: str | None = None,
    chua_gan_dnm: bool = False,
) -> list[dict]:
    stmt = select(Lo)
    stmt = scope.filter_lo(stmt, Lo)
    if loai:
        stmt = stmt.where(Lo.loai == loai.strip().upper())
    if trang_thai:
        stmt = stmt.where(Lo.trang_thai == trang_thai.strip())
    if tinh_ma:
        stmt = stmt.where(Lo.tinh_ma == tinh_ma.strip())
    if xa_ma:
        stmt = stmt.where(Lo.xa_ma == xa_ma.strip())
    if chua_gan_dnm:
        stmt = stmt.where(Lo.lo_cha_id.is_(None))
    stmt = stmt.order_by(Lo.id.desc())
    items = db.scalars(stmt).all()
    return [serialize_lo(db, item) for item in items]


def get_lo_detail(db: Session, scope: ScopeFilter, *, lo_id: int) -> dict:
    lo = db.get(Lo, lo_id)
    if lo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô.")
    scope.ensure_can_access_record(tinh_ma=lo.tinh_ma, xa_ma=lo.xa_ma)
    return serialize_lo(db, lo)


def update_lo(
    db: Session,
    scope: ScopeFilter,
    *,
    lo_id: int,
    so_cong_van: str | None = None,
    ghi_chu: str | None = None,
    lo_con_ids: list[int] | None = None,
    ip: str | None = None,
) -> dict:
    scope.require_non_admin_for_mutation()
    lo = db.get(Lo, lo_id)
    if lo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô.")
    scope.ensure_can_access_record(tinh_ma=lo.tinh_ma, xa_ma=lo.xa_ma)

    if lo.loai == "XA" and not (scope.is_xa and scope.xa_ma == lo.xa_ma):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền sửa lô này.")
    if lo.loai in ("TINH", "DAT_NHA_MAY") and not (scope.is_tinh and scope.tinh_ma == lo.tinh_ma):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền sửa lô này.")

    if lo.trang_thai != "Khởi tạo":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Chỉ được phép sửa thông tin lô khi đang ở trạng thái 'Khởi tạo' (hiện tại: '{lo.trang_thai}').",
        )

    if so_cong_van is not None:
        cv, cv_chuan = _validate_so_cong_van(so_cong_van)
        _check_unique_so_cv(
            db,
            loai=lo.loai,
            tinh_ma=lo.tinh_ma,
            xa_ma=lo.xa_ma,
            so_cv_chuan=cv_chuan,
            exclude_lo_id=lo.id,
        )
        lo.so_cong_van = cv
        lo.so_cv_chuan = cv_chuan
        unit_code = lo.xa_ma if lo.loai == "XA" else lo.tinh_ma
        lo.ma_lo = f"{cv}-{unit_code}"

    if ghi_chu is not None:
        lo.ghi_chu = ghi_chu.strip() or None

    if lo.loai == "DAT_NHA_MAY" and lo_con_ids is not None:
        _validate_and_attach_children_for_dnm(db, dnm_lo=lo, lo_con_ids=lo_con_ids)

    write_audit_log(
        db,
        nguoi_dung=scope.ten_dang_nhap,
        hanh_dong="SUA_LO",
        doi_tuong=lo.ma_lo,
        ket_qua="THANH_CONG",
        ip=ip,
        chi_tiet={"lo_id": lo.id},
    )
    db.commit()
    return serialize_lo(db, lo)


def delete_lo(
    db: Session,
    scope: ScopeFilter,
    *,
    lo_id: int,
    ip: str | None = None,
) -> None:
    scope.require_non_admin_for_mutation()
    lo = db.get(Lo, lo_id)
    if lo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô.")
    scope.ensure_can_access_record(tinh_ma=lo.tinh_ma, xa_ma=lo.xa_ma)

    if lo.loai == "XA" and not (scope.is_xa and scope.xa_ma == lo.xa_ma):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền xóa lô xã này.")
    if lo.loai in ("TINH", "DAT_NHA_MAY") and not (scope.is_tinh and scope.tinh_ma == lo.tinh_ma):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền xóa lô tỉnh này.")

    if lo.trang_thai != "Khởi tạo":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Chỉ được xóa lô khi ở trạng thái 'Khởi tạo' (hiện tại: '{lo.trang_thai}').",
        )
    if lo.loai == "DAT_NHA_MAY":
        for child in db.scalars(select(Lo).where(Lo.lo_cha_id == lo.id)).all():
            child.lo_cha_id = None

    ma_lo = lo.ma_lo
    db.delete(lo)
    write_audit_log(
        db,
        nguoi_dung=scope.ten_dang_nhap,
        hanh_dong="XOA_LO",
        doi_tuong=ma_lo,
        ket_qua="THANH_CONG",
        ip=ip,
        chi_tiet={"lo_id": lo_id},
    )
    db.commit()


def _reserve_plates_for_lo_submission(db: Session, lo: Lo) -> int:
    plates = db.scalars(
        select(Bien)
        .where(Bien.lo_id == lo.id, Bien.tinh_trang != "Đã hủy")
        .order_by(Bien.stt.asc(), Bien.id.asc())
    ).all()
    if not plates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lô phải có ít nhất 1 biển số hợp lệ trước khi gửi (FR-043, AC-28).",
        )
    for p in plates:
        dup = check_plate_duplicates(
            db,
            lo_id=lo.id,
            tinh_ma=lo.tinh_ma,
            bien_so_day_du=p.bien_so_day_du,
            exclude_bien_id=p.id,
        )
        if dup["blocked"]:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=dup["reason"])
        p.giu_cho = True
        p.loi_ly_do = None
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Có biển số trong lô vừa được giữ chỗ bởi một lô khác trong cùng tỉnh.",
        ) from exc
    return len(plates)


def submit_lo(
    db: Session,
    scope: ScopeFilter,
    *,
    lo_id: int,
    xac_nhan: bool = False,
    gia_lap_loi_dong_bo: bool = False,
    ip: str | None = None,
) -> dict:
    """
    Gửi lô theo sơ đồ 4.J.1..4.J.3 (FR-044, FR-062, FR-065, FR-091):
    - Lô xã: Khởi tạo / Từ chối / Cho phép điều chỉnh -> Đã gửi -> (nếu đồng bộ thành công) Chờ phê duyệt.
    - Lô tỉnh: Khởi tạo / Từ chối / Cho phép điều chỉnh -> Chờ phê duyệt.
    - Lô đặt nhà máy: Khởi tạo -> Chờ phê duyệt.
    """
    scope.require_non_admin_for_mutation()
    if not xac_nhan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng xác nhận trước khi gửi lô (FR-091).",
        )

    lo = db.get(Lo, lo_id)
    if lo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô.")
    scope.ensure_can_access_record(tinh_ma=lo.tinh_ma, xa_ma=lo.xa_ma)

    now = datetime.now(timezone.utc)
    old_state = lo.trang_thai

    if lo.loai == "XA":
        if old_state in ("Khởi tạo", "Từ chối"):
            if not (scope.is_xa and scope.xa_ma == lo.xa_ma):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ xã sở hữu mới được gửi lô.")
        elif old_state == "Cho phép điều chỉnh":
            if not (
                (scope.is_xa and scope.xa_ma == lo.xa_ma)
                or (scope.is_tinh and scope.tinh_ma == lo.tinh_ma)
            ):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền gửi lại lô này.")
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Lô xã đang ở trạng thái '{old_state}', không thể gửi.",
            )

        _reserve_plates_for_lo_submission(db, lo)

        if old_state == "Từ chối":
            lo.so_lan_dat += 1
            lo.ly_do = None

        lo.trang_thai = "Đã gửi"
        db.add(
            LoLichSu(
                lo_id=lo.id,
                tu=old_state,
                den="Đã gửi",
                nguoi=scope.ten_dang_nhap,
                luc=now,
                ly_do=None,
            )
        )
        create_or_run_sync_job(
            db, lo, nguoi=scope.ten_dang_nhap, simulate_error=gia_lap_loi_dong_bo
        )

    elif lo.loai == "TINH":
        if not (scope.is_tinh and scope.tinh_ma == lo.tinh_ma):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ tỉnh sở hữu mới được gửi duyệt lô tỉnh.")
        if old_state not in ("Khởi tạo", "Từ chối", "Cho phép điều chỉnh"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Lô tỉnh đang ở trạng thái '{old_state}', không thể gửi duyệt.",
            )
        _reserve_plates_for_lo_submission(db, lo)

        if old_state == "Từ chối":
            lo.so_lan_dat += 1
            lo.ly_do = None

        lo.trang_thai = "Chờ phê duyệt"
        db.add(
            LoLichSu(
                lo_id=lo.id,
                tu=old_state,
                den="Chờ phê duyệt",
                nguoi=scope.ten_dang_nhap,
                luc=now,
                ly_do=None,
            )
        )

    elif lo.loai == "DAT_NHA_MAY":
        if not (scope.is_tinh and scope.tinh_ma == lo.tinh_ma):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền.")
        if old_state != "Khởi tạo":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Lô đặt nhà máy đang ở trạng thái '{old_state}', không thể gửi duyệt.",
            )
        child_count = (
            db.scalar(select(func.count(Lo.id)).where(Lo.lo_cha_id == lo.id)) or 0
        )
        if child_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lô đặt nhà máy phải có ít nhất 1 lô thành phần trước khi gửi duyệt (FR-063).",
            )
        lo.trang_thai = "Chờ phê duyệt"
        db.add(
            LoLichSu(
                lo_id=lo.id,
                tu=old_state,
                den="Chờ phê duyệt",
                nguoi=scope.ten_dang_nhap,
                luc=now,
                ly_do=None,
            )
        )

    write_audit_log(
        db,
        nguoi_dung=scope.ten_dang_nhap,
        hanh_dong="GUI_LO",
        doi_tuong=lo.ma_lo,
        ket_qua="THANH_CONG",
        ip=ip,
        chi_tiet={"lo_id": lo.id, "tu": old_state, "den": lo.trang_thai},
    )
    db.commit()
    return serialize_lo(db, lo)


def _approve_single_lo_in_tx(db: Session, scope: ScopeFilter, lo: Lo, ip: str | None) -> None:
    if not (scope.is_tinh and scope.tinh_ma == lo.tinh_ma):
        raise ValueError("Chỉ tài khoản tỉnh quản lý địa bàn mới có quyền duyệt lô.")

    if lo.trang_thai != "Chờ phê duyệt":
        raise ValueError(
            f"Lô '{lo.ma_lo}' đang ở trạng thái '{lo.trang_thai}', cần ở 'Chờ phê duyệt' để duyệt."
        )

    if lo.loai in ("XA", "TINH"):
        plate_cnt = (
            db.scalar(
                select(func.count(Bien.id)).where(
                    Bien.lo_id == lo.id, Bien.tinh_trang != "Đã hủy"
                )
            )
            or 0
        )
        if plate_cnt == 0:
            raise ValueError(f"Lô '{lo.ma_lo}' không có biển số hợp lệ nào.")
    else:
        child_cnt = (
            db.scalar(select(func.count(Lo.id)).where(Lo.lo_cha_id == lo.id)) or 0
        )
        if child_cnt == 0:
            raise ValueError(f"Lô đặt nhà máy '{lo.ma_lo}' không có lô thành phần nào.")

    now = datetime.now(timezone.utc)
    old_st = lo.trang_thai
    lo.trang_thai = "Chấp nhận"
    db.add(
        LoLichSu(
            lo_id=lo.id,
            tu=old_st,
            den="Chấp nhận",
            nguoi=scope.ten_dang_nhap,
            luc=now,
            ly_do=None,
        )
    )
    write_audit_log(
        db,
        nguoi_dung=scope.ten_dang_nhap,
        hanh_dong="DUYET_LO",
        doi_tuong=lo.ma_lo,
        ket_qua="THANH_CONG",
        ip=ip,
        chi_tiet={"lo_id": lo.id, "tu": old_st, "den": "Chấp nhận"},
    )


def approve_lo(
    db: Session,
    scope: ScopeFilter,
    *,
    lo_id: int,
    xac_nhan: bool = True,
    ip: str | None = None,
) -> dict:
    scope.require_non_admin_for_mutation()
    if not scope.is_tinh:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ tài khoản cấp Tỉnh/Thành mới có quyền phê duyệt lô.",
        )
    if not xac_nhan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng xác nhận trước khi duyệt lô (FR-091).",
        )
    lo = db.get(Lo, lo_id)
    if lo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô.")
    scope.ensure_can_access_record(tinh_ma=lo.tinh_ma, xa_ma=None)

    try:
        _approve_single_lo_in_tx(db, scope, lo, ip)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    db.commit()
    return serialize_lo(db, lo)


def approve_lo_bulk(
    db: Session,
    scope: ScopeFilter,
    *,
    lo_ids: list[int],
    xac_nhan: bool = True,
    ip: str | None = None,
) -> dict:
    """Duyệt hàng loạt theo nguyên tắc mỗi lô một giao dịch độc lập (FR-061, AC-36)."""
    scope.require_non_admin_for_mutation()
    if not scope.is_tinh:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ tài khoản tỉnh mới có quyền duyệt lô hàng loạt.",
        )
    if not xac_nhan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng xác nhận trước khi duyệt hàng loạt (FR-091).",
        )

    thanh_cong: list[dict] = []
    that_bai: list[dict] = []

    for lid in dict.fromkeys(lo_ids or []):
        try:
            with db.begin_nested():
                lo = db.get(Lo, lid)
                if lo is None or lo.tinh_ma != scope.tinh_ma:
                    raise ValueError(f"Không tìm thấy lô ID={lid} thuộc tỉnh quản lý.")
                _approve_single_lo_in_tx(db, scope, lo, ip)
            db.commit()
            thanh_cong.append({"lo_id": lid, "ma_lo": lo.ma_lo, "trang_thai": "Chấp nhận"})
        except Exception as exc:
            that_bai.append({"lo_id": lid, "ly_do": str(exc)})

    return {
        "so_luong_thanh_cong": len(thanh_cong),
        "so_luong_that_bai": len(that_bai),
        "thanh_cong": thanh_cong,
        "that_bai": that_bai,
    }


def reject_lo(
    db: Session,
    scope: ScopeFilter,
    *,
    lo_id: int,
    ly_do: str,
    bien_loi: list[dict] | None = None,
    xac_nhan: bool = True,
    ip: str | None = None,
) -> dict:
    """Từ chối lô xã/lô tỉnh đang ở 'Chờ phê duyệt' sang 'Từ chối', đánh dấu biển lỗi để sửa và gửi lại (FR-047, FR-071, AC-32)."""
    scope.require_non_admin_for_mutation()
    if not xac_nhan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng xác nhận trước khi từ chối lô (FR-091).",
        )
    reason = (ly_do or "").strip()
    if not reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bắt buộc nhập lý do từ chối lô (FR-047).",
        )

    lo = db.get(Lo, lo_id)
    if lo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô.")
    if not (scope.is_tinh and scope.tinh_ma == lo.tinh_ma):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ tài khoản tỉnh quản lý mới được từ chối lô.",
        )

    if lo.loai not in ("XA", "TINH") or lo.trang_thai != "Chờ phê duyệt":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Lô đang ở trạng thái '{lo.trang_thai}', cần ở 'Chờ phê duyệt' để từ chối.",
        )

    error_map: dict[int, str] = {}
    for item in bien_loi or []:
        bid = item.get("bien_id")
        err_text = (item.get("ly_do") or "").strip() or reason
        if bid is not None:
            error_map[int(bid)] = err_text

    plates = db.scalars(select(Bien).where(Bien.lo_id == lo.id)).all()
    for p in plates:
        p.giu_cho = False
        p.loi_ly_do = error_map.get(p.id)

    now = datetime.now(timezone.utc)
    old_st = lo.trang_thai
    lo.ly_do = reason
    lo.trang_thai = "Từ chối"

    db.add(
        LoLichSu(
            lo_id=lo.id,
            tu=old_st,
            den="Từ chối",
            nguoi=scope.ten_dang_nhap,
            luc=now,
            ly_do=reason,
        )
    )
    write_audit_log(
        db,
        nguoi_dung=scope.ten_dang_nhap,
        hanh_dong="TU_CHOI_LO",
        doi_tuong=lo.ma_lo,
        ket_qua="THANH_CONG",
        ip=ip,
        chi_tiet={
            "lo_id": lo.id,
            "ly_do": reason,
            "so_bien_danh_dau_loi": len(error_map),
        },
    )
    db.commit()
    return serialize_lo(db, lo)


def enable_adjustment_lo(
    db: Session,
    scope: ScopeFilter,
    *,
    lo_id: int,
    ly_do: str | None = None,
    ip: str | None = None,
) -> dict:
    """
    Bật 'Cho phép điều chỉnh' cho lô xã hoặc lô tỉnh đang 'Chấp nhận'.
    Nếu lô đã nằm trong lô đặt nhà máy chưa Đặt thành công -> tự gỡ ra và đưa lô đặt nhà máy về Khởi tạo (FR-049, FR-069, AC-37).
    """
    scope.require_non_admin_for_mutation()
    lo = db.get(Lo, lo_id)
    if lo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô.")
    if not (scope.is_tinh and scope.tinh_ma == lo.tinh_ma):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ tài khoản tỉnh mới được bật Cho phép điều chỉnh.",
        )
    if lo.loai not in ("XA", "TINH") or lo.trang_thai != "Chấp nhận":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chỉ bật 'Cho phép điều chỉnh' cho lô xã hoặc lô tỉnh đang ở trạng thái 'Chấp nhận'.",
        )

    now = datetime.now(timezone.utc)
    detached_dnm_ma: str | None = None

    if lo.lo_cha_id is not None:
        parent_dnm = db.get(Lo, lo.lo_cha_id)
        if parent_dnm is not None:
            if parent_dnm.trang_thai in ("Đặt thành công", "Hủy"):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Lô đặt nhà máy '{parent_dnm.ma_lo}' đã ở trạng thái '{parent_dnm.trang_thai}', không được bật Cho phép điều chỉnh (FR-049).",
                )
            detached_dnm_ma = parent_dnm.ma_lo
            lo.lo_cha_id = None
            if parent_dnm.trang_thai in ("Chờ phê duyệt", "Chấp nhận"):
                old_dnm_st = parent_dnm.trang_thai
                parent_dnm.trang_thai = "Khởi tạo"
                db.add(
                    LoLichSu(
                        lo_id=parent_dnm.id,
                        tu=old_dnm_st,
                        den="Khởi tạo",
                        nguoi=scope.ten_dang_nhap,
                        luc=now,
                        ly_do=f"Tự động đưa về Khởi tạo do lô thành phần '{lo.ma_lo}' bật Cho phép điều chỉnh",
                    )
                )

    lo.trang_thai = "Cho phép điều chỉnh"
    db.add(
        LoLichSu(
            lo_id=lo.id,
            tu="Chấp nhận",
            den="Cho phép điều chỉnh",
            nguoi=scope.ten_dang_nhap,
            luc=now,
            ly_do=(ly_do or "").strip() or None,
        )
    )
    write_audit_log(
        db,
        nguoi_dung=scope.ten_dang_nhap,
        hanh_dong="CHO_PHEP_DIEU_CHINH_LO",
        doi_tuong=lo.ma_lo,
        ket_qua="THANH_CONG",
        ip=ip,
        chi_tiet={"lo_id": lo.id, "go_khoi_lo_dnm": detached_dnm_ma},
    )
    db.commit()
    return serialize_lo(db, lo)


def complete_adjustment_lo(
    db: Session,
    scope: ScopeFilter,
    *,
    lo_id: int,
    ip: str | None = None,
) -> dict:
    """Tỉnh bấm 'Hoàn tất điều chỉnh' đưa lô từ 'Cho phép điều chỉnh' sang 'Chờ phê duyệt' (FR-049, FR-071, AC-37)."""
    scope.require_non_admin_for_mutation()
    lo = db.get(Lo, lo_id)
    if lo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô.")
    if not (scope.is_tinh and scope.tinh_ma == lo.tinh_ma):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ tài khoản tỉnh mới được Hoàn tất điều chỉnh.",
        )
    if lo.trang_thai != "Cho phép điều chỉnh":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Lô đang ở trạng thái '{lo.trang_thai}', không ở trạng thái 'Cho phép điều chỉnh'.",
        )

    _reserve_plates_for_lo_submission(db, lo)
    now = datetime.now(timezone.utc)
    lo.trang_thai = "Chờ phê duyệt"
    db.add(
        LoLichSu(
            lo_id=lo.id,
            tu="Cho phép điều chỉnh",
            den="Chờ phê duyệt",
            nguoi=scope.ten_dang_nhap,
            luc=now,
            ly_do="Hoàn tất điều chỉnh tại tỉnh",
        )
    )
    write_audit_log(
        db,
        nguoi_dung=scope.ten_dang_nhap,
        hanh_dong="HOAN_TAT_DIEU_CHINH_LO",
        doi_tuong=lo.ma_lo,
        ket_qua="THANH_CONG",
        ip=ip,
        chi_tiet={"lo_id": lo.id},
    )
    db.commit()
    return serialize_lo(db, lo)


def withdraw_dnm_lo(
    db: Session,
    scope: ScopeFilter,
    *,
    lo_id: int,
    ly_do: str | None = None,
    ip: str | None = None,
) -> dict:
    """Rút lô đặt nhà máy từ Chờ phê duyệt / Chấp nhận về Khởi tạo để thêm/bớt lô thành phần (FR-065, AC-38)."""
    scope.require_non_admin_for_mutation()
    lo = db.get(Lo, lo_id)
    if lo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô.")
    if not (scope.is_tinh and scope.tinh_ma == lo.tinh_ma):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền.")
    if lo.loai != "DAT_NHA_MAY" or lo.trang_thai not in ("Chờ phê duyệt", "Chấp nhận"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chỉ rút về Khởi tạo đối với lô đặt nhà máy đang ở 'Chờ phê duyệt' hoặc 'Chấp nhận'.",
        )

    now = datetime.now(timezone.utc)
    old_st = lo.trang_thai
    lo.trang_thai = "Khởi tạo"
    db.add(
        LoLichSu(
            lo_id=lo.id,
            tu=old_st,
            den="Khởi tạo",
            nguoi=scope.ten_dang_nhap,
            luc=now,
            ly_do=(ly_do or "").strip() or "Rút về để điều chỉnh danh sách lô thành phần",
        )
    )
    write_audit_log(
        db,
        nguoi_dung=scope.ten_dang_nhap,
        hanh_dong="RUT_VE_LO_DNM",
        doi_tuong=lo.ma_lo,
        ket_qua="THANH_CONG",
        ip=ip,
        chi_tiet={"lo_id": lo.id, "tu": old_st},
    )
    db.commit()
    return serialize_lo(db, lo)


def cancel_dnm_lo(
    db: Session,
    scope: ScopeFilter,
    *,
    lo_id: int,
    ly_do: str,
    xac_nhan: bool = True,
    ip: str | None = None,
) -> dict:
    """
    Hủy lô đặt nhà máy khi chưa Đặt thành công: trả các lô thành phần về trạng thái Chấp nhận (lo_cha_id = NULL)
    và giữ nguyên bản ghi lô đặt nhà máy ở trạng thái Hủy (không cho dùng lại Số công văn theo G-15) (FR-065, AC-39, AC-43).
    """
    scope.require_non_admin_for_mutation()
    if not xac_nhan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng xác nhận trước khi hủy lô đặt nhà máy (FR-091).",
        )
    reason = (ly_do or "").strip()
    if not reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bắt buộc nhập lý do hủy lô đặt nhà máy.",
        )

    lo = db.get(Lo, lo_id)
    if lo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô.")
    if not (scope.is_tinh and scope.tinh_ma == lo.tinh_ma):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền.")
    if lo.loai != "DAT_NHA_MAY" or lo.trang_thai not in ("Khởi tạo", "Chờ phê duyệt", "Chấp nhận"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Lô đặt nhà máy đang ở trạng thái '{lo.trang_thai}', không được phép hủy (FR-065, AC-39).",
        )

    children = db.scalars(select(Lo).where(Lo.lo_cha_id == lo.id)).all()
    released_codes = [c.ma_lo for c in children]
    for c in children:
        c.lo_cha_id = None

    now = datetime.now(timezone.utc)
    old_st = lo.trang_thai
    lo.trang_thai = "Hủy"
    lo.ly_do = reason
    db.add(
        LoLichSu(
            lo_id=lo.id,
            tu=old_st,
            den="Hủy",
            nguoi=scope.ten_dang_nhap,
            luc=now,
            ly_do=reason,
        )
    )
    write_audit_log(
        db,
        nguoi_dung=scope.ten_dang_nhap,
        hanh_dong="HUY_LO_DNM",
        doi_tuong=lo.ma_lo,
        ket_qua="THANH_CONG",
        ip=ip,
        chi_tiet={"lo_id": lo.id, "ly_do": reason, "lo_con_tra_ve": released_codes},
    )
    db.commit()
    return serialize_lo(db, lo)


def list_lo_history(db: Session, scope: ScopeFilter, *, lo_id: int) -> list[dict]:
    lo = db.get(Lo, lo_id)
    if lo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô.")
    scope.ensure_can_access_record(tinh_ma=lo.tinh_ma, xa_ma=lo.xa_ma)
    rows = db.scalars(
        select(LoLichSu)
        .where(LoLichSu.lo_id == lo.id)
        .order_by(LoLichSu.luc.asc(), LoLichSu.id.asc())
    ).all()
    return [
        {
            "id": r.id,
            "lo_id": r.lo_id,
            "tu": r.tu,
            "den": r.den,
            "nguoi": r.nguoi,
            "luc": r.luc.isoformat(),
            "ly_do": r.ly_do,
        }
        for r in rows
    ]
