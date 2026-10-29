from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from biensoxe.domain.bien_so import BienSoValidationError
from biensoxe.models.bien import BanGiao, Bien, BienLichSu
from biensoxe.models.lo import Lo, LoLichSu
from biensoxe.repositories.scope import ScopeFilter
from biensoxe.services.audit import write_audit_log
from biensoxe.services.bien import (
    check_plate_duplicates,
    resequence_lo_stt,
    resolve_plate_metadata,
    serialize_bien,
)
from biensoxe.services.lo import serialize_lo

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def sync_dnm_and_children_completion_states(
    db: Session,
    dnm_lo: Lo,
    *,
    nguoi: str,
    now: datetime | None = None,
) -> None:
    """
    Cập nhật tự động trạng thái hoàn tất Nhập kho / Đã nhận / Đã chuyển Xã/phường
    cho lô đặt nhà máy và các lô thành phần (FR-067, FR-068, AC-41, AC-42).
    """
    current = now or datetime.now(timezone.utc)
    children = db.scalars(select(Lo).where(Lo.lo_cha_id == dnm_lo.id)).all()
    if not children:
        return

    all_dnm_stocked = True
    has_xa_child = False
    all_xa_received = True

    for child in children:
        active_plates = db.scalars(
            select(Bien).where(Bien.lo_id == child.id, Bien.tinh_trang != "Đã hủy")
        ).all()

        if active_plates:
            child_all_stocked = all(
                p.tinh_trang in ("Tồn kho tỉnh", "Tồn kho xã") for p in active_plates
            )
            child_all_xa = all(p.tinh_trang == "Tồn kho xã" for p in active_plates)
        else:
            child_all_stocked = True
            child_all_xa = True

        if not child_all_stocked:
            all_dnm_stocked = False

        if child.loai == "TINH":
            if child.trang_thai == "Đặt thành công" and child_all_stocked:
                child.trang_thai = "Đã nhập kho"
                db.add(
                    LoLichSu(
                        lo_id=child.id,
                        tu="Đặt thành công",
                        den="Đã nhập kho",
                        nguoi=nguoi,
                        luc=current,
                        ly_do="Toàn bộ biển số của lô tỉnh đã nhập kho/hủy",
                    )
                )
        elif child.loai == "XA":
            has_xa_child = True
            if child.trang_thai == "Đặt thành công" and child_all_xa:
                child.trang_thai = "Đã nhận"
                db.add(
                    LoLichSu(
                        lo_id=child.id,
                        tu="Đặt thành công",
                        den="Đã nhận",
                        nguoi=nguoi,
                        luc=current,
                        ly_do="Xã/phường đã nhận đủ biển số của lô",
                    )
                )
            if child.trang_thai != "Đã nhận":
                all_xa_received = False

    if dnm_lo.trang_thai == "Đặt thành công" and all_dnm_stocked:
        dnm_lo.trang_thai = "Đã nhập kho"
        db.add(
            LoLichSu(
                lo_id=dnm_lo.id,
                tu="Đặt thành công",
                den="Đã nhập kho",
                nguoi=nguoi,
                luc=current,
                ly_do="Toàn bộ biển số của lô đặt nhà máy đã nhập kho tỉnh",
            )
        )

    if (
        dnm_lo.trang_thai == "Đã nhập kho"
        and has_xa_child
        and all_xa_received
    ):
        dnm_lo.trang_thai = "Đã chuyển Xã/phường"
        db.add(
            LoLichSu(
                lo_id=dnm_lo.id,
                tu="Đã nhập kho",
                den="Đã chuyển Xã/phường",
                nguoi=nguoi,
                luc=current,
                ly_do="Toàn bộ lô xã thành phần đã nhận đủ biển số",
            )
        )


def mark_dnm_dat_thanh_cong(
    db: Session,
    scope: ScopeFilter,
    *,
    lo_id: int,
    xac_nhan: bool = True,
    ip: str | None = None,
) -> dict:
    """Xác nhận lô đặt nhà máy 'Đặt thành công' (FR-066, AC-40)."""
    scope.require_non_admin_for_mutation()
    if not xac_nhan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng xác nhận trước khi chuyển sang Đặt thành công (FR-091).",
        )
    lo = db.get(Lo, lo_id)
    if lo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô.")
    if not (scope.is_tinh and scope.tinh_ma == lo.tinh_ma):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền.")
    if lo.loai != "DAT_NHA_MAY" or lo.trang_thai != "Chấp nhận":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chỉ xác nhận 'Đặt thành công' cho lô đặt nhà máy đang ở trạng thái 'Chấp nhận'.",
        )

    children = db.scalars(select(Lo).where(Lo.lo_cha_id == lo.id)).all()
    if not children:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lô đặt nhà máy không có lô thành phần nào.",
        )

    now = datetime.now(timezone.utc)
    lo.trang_thai = "Đặt thành công"
    db.add(
        LoLichSu(
            lo_id=lo.id,
            tu="Chấp nhận",
            den="Đặt thành công",
            nguoi=scope.ten_dang_nhap,
            luc=now,
            ly_do=None,
        )
    )

    for child in children:
        old_c = child.trang_thai
        child.trang_thai = "Đặt thành công"
        db.add(
            LoLichSu(
                lo_id=child.id,
                tu=old_c,
                den="Đặt thành công",
                nguoi=scope.ten_dang_nhap,
                luc=now,
                ly_do=f"Đặt thành công theo lô đặt nhà máy {lo.ma_lo}",
            )
        )
        plates = db.scalars(
            select(Bien).where(Bien.lo_id == child.id, Bien.tinh_trang != "Đã hủy")
        ).all()
        for p in plates:
            old_p = p.tinh_trang
            p.tinh_trang = "Đã đặt"
            p.giu_cho = True
            db.add(
                BienLichSu(
                    bien_id=p.id,
                    su_kien="DAT_NHA_MAY_THANH_CONG",
                    tu=old_p,
                    den="Đã đặt",
                    ly_do=None,
                    nguoi=scope.ten_dang_nhap,
                    luc=now,
                )
            )

    write_audit_log(
        db,
        nguoi_dung=scope.ten_dang_nhap,
        hanh_dong="DAT_THANH_CONG_LO_DNM",
        doi_tuong=lo.ma_lo,
        ket_qua="THANH_CONG",
        ip=ip,
        chi_tiet={"lo_id": lo.id, "so_lo_con": len(children)},
    )
    db.commit()
    return serialize_lo(db, lo)


def adjust_after_dat_thanh_cong(
    db: Session,
    scope: ScopeFilter,
    *,
    dnm_lo_id: int,
    hanh_dong: str,  # 'THEM_BIEN' | 'SUA_BIEN'
    ly_do: str,
    xac_nhan: bool = False,
    lo_con_id: int | None = None,
    bien_id: int | None = None,
    bien_so: str | None = None,
    nen_bien: str | None = None,
    nen_bien_id: int | None = None,
    ghi_chu: str | None = None,
    dat_lai_xac_nhan: bool = False,
    ip: str | None = None,
) -> dict | JSONResponse:
    """
    Điều chỉnh biển số sau khi lô đặt nhà máy đã 'Đặt thành công' (FR-066, G-18, AC-40):
    - Giữ nguyên trạng thái lô đặt nhà máy là 'Đặt thành công'
    - Bắt buộc xac_nhan=True và lý do bắt buộc
    - Cho phép thêm biển mới vào lô con được chọn (vào thẳng 'Đã đặt', giu_cho=True)
    - Cho phép sửa biển đang ở 'Đã đặt'; chặn sửa biển đã 'Tồn kho tỉnh', 'Tồn kho xã' hoặc 'Đã hủy'
    """
    scope.require_non_admin_for_mutation()
    if not xac_nhan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bắt buộc xác nhận thao tác điều chỉnh sau Đặt thành công (FR-066, AC-40).",
        )
    reason = (ly_do or "").strip()
    if not reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bắt buộc nhập lý do điều chỉnh sau Đặt thành công (FR-066, AC-40).",
        )

    dnm_lo = db.get(Lo, dnm_lo_id)
    if dnm_lo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô.")
    if not (scope.is_tinh and scope.tinh_ma == dnm_lo.tinh_ma):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền.")
    if dnm_lo.loai != "DAT_NHA_MAY" or dnm_lo.trang_thai != "Đặt thành công":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chỉ điều chỉnh sau đặt cho lô đặt nhà máy đang ở trạng thái 'Đặt thành công'.",
        )

    action = (hanh_dong or "").strip().upper()
    now = datetime.now(timezone.utc)

    if action == "THEM_BIEN":
        if lo_con_id is None or not bien_so:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cần chọn lô thành phần (lo_con_id) và nhập biển số cần thêm.",
            )
        child_lo = db.get(Lo, lo_con_id)
        if child_lo is None or child_lo.lo_cha_id != dnm_lo.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lô thành phần không thuộc lô đặt nhà máy này.",
            )
        try:
            meta = resolve_plate_metadata(
                db, bien_so, dnm_lo.tinh_ma, nen_bien=nen_bien, nen_bien_id=nen_bien_id
            )
        except BienSoValidationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        parsed = meta["parsed"]
        dup = check_plate_duplicates(
            db,
            lo_id=child_lo.id,
            tinh_ma=dnm_lo.tinh_ma,
            bien_so_day_du=parsed.bien_so_day_du,
        )
        if dup["blocked"]:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=dup["reason"])
        if dup["requires_reorder_confirm"] and not dat_lai_xac_nhan:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "detail": f"Biển số '{parsed.bien_so_day_du}' cần xác nhận đặt lại.",
                    "yeu_cau_xac_nhan_dat_lai": True,
                    "thong_tin_dat_lai": dup["reorder_info"],
                },
            )

        max_stt = (
            db.scalar(
                select(func.coalesce(func.max(Bien.stt), 0)).where(Bien.lo_id == child_lo.id)
            )
            or 0
        )
        new_b = Bien(
            lo_id=child_lo.id,
            stt=max_stt + 1,
            bien_so_day_du=parsed.bien_so_day_du,
            ma_tinh_bien=parsed.ma_tinh,
            seri_chu=parsed.seri_chu,
            seri_so=parsed.seri_so,
            dau_so=parsed.dau_so,
            loai_pt_id=meta["loai_pt"].id,
            nen_bien_id=meta["nen_bien"].id,
            ghi_chu=(ghi_chu or "").strip() or None,
            tinh_ma=child_lo.tinh_ma,
            xa_ma=child_lo.xa_ma,
            tinh_trang="Đã đặt",
            giao=None,
            dat_lai_xac_nhan=bool(dup["requires_reorder_confirm"] and dat_lai_xac_nhan),
            ngoai_tinh=meta["ngoai_tinh"],
            loi_ly_do=None,
            giu_cho=True,
        )
        db.add(new_b)
        db.flush()

        db.add(
            BienLichSu(
                bien_id=new_b.id,
                su_kien="THEM_SAU_DAT_THANH_CONG",
                tu=None,
                den="Đã đặt",
                ly_do=reason,
                nguoi=scope.ten_dang_nhap,
                luc=now,
            )
        )
        db.add(
            LoLichSu(
                lo_id=dnm_lo.id,
                tu="Đặt thành công",
                den="Đặt thành công",
                nguoi=scope.ten_dang_nhap,
                luc=now,
                ly_do=f"Thêm biển {new_b.bien_so_day_du} vào lô {child_lo.ma_lo}: {reason}",
            )
        )
        write_audit_log(
            db,
            nguoi_dung=scope.ten_dang_nhap,
            hanh_dong="DIEU_CHINH_SAU_DAT_THEM_BIEN",
            doi_tuong=new_b.bien_so_day_du,
            ket_qua="THANH_CONG",
            ip=ip,
            chi_tiet={"dnm_lo_id": dnm_lo.id, "lo_con_id": child_lo.id, "ly_do": reason},
        )
        db.commit()
        return serialize_bien(db, new_b)

    elif action == "SUA_BIEN":
        if bien_id is None or not bien_so:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cần truyền bien_id và bien_so mới khi sửa biển sau đặt.",
            )
        b = db.get(Bien, bien_id)
        if b is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy biển số.")
        child_lo = db.get(Lo, b.lo_id)
        if child_lo is None or child_lo.lo_cha_id != dnm_lo.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Biển số không thuộc lô đặt nhà máy này.",
            )
        if b.tinh_trang != "Đã đặt":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Biển số đang ở tình trạng '{b.tinh_trang}', không được phép sửa (chỉ sửa được biển đang 'Đã đặt') (FR-066, AC-40).",
            )

        eff_nen_id = (
            nen_bien_id
            if (nen_bien is None and nen_bien_id is not None)
            else (b.nen_bien_id if nen_bien is None else None)
        )
        try:
            meta = resolve_plate_metadata(
                db, bien_so, dnm_lo.tinh_ma, nen_bien=nen_bien, nen_bien_id=eff_nen_id
            )
        except BienSoValidationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        parsed = meta["parsed"]
        dup = check_plate_duplicates(
            db,
            lo_id=child_lo.id,
            tinh_ma=dnm_lo.tinh_ma,
            bien_so_day_du=parsed.bien_so_day_du,
            exclude_bien_id=b.id,
        )
        if dup["blocked"]:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=dup["reason"])
        if dup["requires_reorder_confirm"] and not dat_lai_xac_nhan:
            return JSONResponse(
                status_code=status.HTTP_409_CONFLICT,
                content={
                    "detail": f"Biển số '{parsed.bien_so_day_du}' cần xác nhận đặt lại.",
                    "yeu_cau_xac_nhan_dat_lai": True,
                    "thong_tin_dat_lai": dup["reorder_info"],
                },
            )

        old_code = b.bien_so_day_du
        b.bien_so_day_du = parsed.bien_so_day_du
        b.ma_tinh_bien = parsed.ma_tinh
        b.seri_chu = parsed.seri_chu
        b.seri_so = parsed.seri_so
        b.dau_so = parsed.dau_so
        b.loai_pt_id = meta["loai_pt"].id
        b.nen_bien_id = meta["nen_bien"].id
        if ghi_chu is not None:
            b.ghi_chu = ghi_chu.strip() or None
        b.ngoai_tinh = meta["ngoai_tinh"]
        b.dat_lai_xac_nhan = bool(dup["requires_reorder_confirm"] and dat_lai_xac_nhan)

        db.add(
            BienLichSu(
                bien_id=b.id,
                su_kien="SUA_SAU_DAT_THANH_CONG",
                tu=old_code,
                den=b.bien_so_day_du,
                ly_do=reason,
                nguoi=scope.ten_dang_nhap,
                luc=now,
            )
        )
        db.add(
            LoLichSu(
                lo_id=dnm_lo.id,
                tu="Đặt thành công",
                den="Đặt thành công",
                nguoi=scope.ten_dang_nhap,
                luc=now,
                ly_do=f"Sửa biển {old_code} -> {b.bien_so_day_du}: {reason}",
            )
        )
        write_audit_log(
            db,
            nguoi_dung=scope.ten_dang_nhap,
            hanh_dong="DIEU_CHINH_SAU_DAT_SUA_BIEN",
            doi_tuong=b.bien_so_day_du,
            ket_qua="THANH_CONG",
            ip=ip,
            chi_tiet={"bien_id": b.id, "tu": old_code, "den": b.bien_so_day_du, "ly_do": reason},
        )
        db.commit()
        return serialize_bien(db, b)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Hành động điều chỉnh sau đặt không hợp lệ (chỉ hỗ trợ THEM_BIEN hoặc SUA_BIEN).",
    )


def nhap_kho_tinh(
    db: Session,
    scope: ScopeFilter,
    *,
    lo_id: int,
    ca_lo: bool = False,
    bien_ids: list[int] | None = None,
    ip: str | None = None,
) -> dict:
    """Nhập kho tỉnh theo cả lô hoặc chọn từng biển (FR-067, AC-41)."""
    scope.require_non_admin_for_mutation()
    lo = db.get(Lo, lo_id)
    if lo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô.")
    if not (scope.is_tinh and scope.tinh_ma == lo.tinh_ma):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền nhập kho.")

    if lo.loai == "DAT_NHA_MAY":
        dnm_lo = lo
        child_ids = list(db.scalars(select(Lo.id).where(Lo.lo_cha_id == dnm_lo.id)).all())
    elif lo.lo_cha_id is not None:
        dnm_lo = db.get(Lo, lo.lo_cha_id)
        assert dnm_lo is not None
        child_ids = [lo.id]
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chỉ nhập kho cho lô đặt nhà máy đã Đặt thành công.",
        )

    if dnm_lo.trang_thai != "Đặt thành công":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Lô đặt nhà máy đang ở trạng thái '{dnm_lo.trang_thai}', cần ở 'Đặt thành công' để nhập kho.",
        )

    if ca_lo:
        targets = list(
            db.scalars(
                select(Bien).where(
                    Bien.lo_id.in_(child_ids),
                    Bien.tinh_trang == "Đã đặt",
                )
            ).all()
        )
    else:
        req_ids = list(dict.fromkeys(bien_ids or []))
        if not req_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vui lòng chọn ít nhất 1 biển số hoặc chọn nhập kho cả lô.",
            )
        targets = list(
            db.scalars(
                select(Bien).where(
                    Bien.id.in_(req_ids),
                    Bien.lo_id.in_(child_ids),
                )
            ).all()
        )
        if len(targets) != len(req_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Có biển số không thuộc lô đặt nhà máy này.",
            )
        for t in targets:
            if t.tinh_trang != "Đã đặt":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Biển số '{t.bien_so_day_du}' đang ở tình trạng '{t.tinh_trang}', không thể nhập kho.",
                )

    if not targets:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không có biển số nào đang ở trạng thái 'Đã đặt' để nhập kho.",
        )

    now = datetime.now(timezone.utc)
    for b in targets:
        b.tinh_trang = "Tồn kho tỉnh"
        b.ngay_nhap_kho = now
        if b.xa_ma is None:
            b.giao = "Chưa trả"
        db.add(
            BienLichSu(
                bien_id=b.id,
                su_kien="NHAP_KHO_TINH",
                tu="Đã đặt",
                den="Tồn kho tỉnh",
                ly_do=None,
                nguoi=scope.ten_dang_nhap,
                luc=now,
            )
        )

    db.flush()
    sync_dnm_and_children_completion_states(db, dnm_lo, nguoi=scope.ten_dang_nhap, now=now)

    write_audit_log(
        db,
        nguoi_dung=scope.ten_dang_nhap,
        hanh_dong="NHAP_KHO_TINH",
        doi_tuong=dnm_lo.ma_lo,
        ket_qua="THANH_CONG",
        ip=ip,
        chi_tiet={"so_luong_nhap": len(targets), "trang_thai_dnm": dnm_lo.trang_thai},
    )
    db.commit()
    return serialize_lo(db, dnm_lo)


def chuyen_bien_cho_xa(
    db: Session,
    scope: ScopeFilter,
    *,
    lo_id: int,
    bien_ids: list[int],
    so_bien_ban: str,
    nguoi_nhan: str,
    chuc_vu: str,
    ngay_nhan: date,
    xac_nhan: bool = True,
    lo_xa_id: int | None = None,
    ip: str | None = None,
) -> dict:
    """
    Chuyển biển số đang 'Tồn kho tỉnh' về 'Tồn kho xã' từng phần kèm 4 trường biên bản bàn giao (FR-068, AC-42).
    """
    scope.require_non_admin_for_mutation()
    if not xac_nhan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng xác nhận trước khi chuyển biển cho xã/phường (FR-091).",
        )

    sbb = (so_bien_ban or "").strip()
    nn = (nguoi_nhan or "").strip()
    cv = (chuc_vu or "").strip()
    if not sbb or not nn or not cv or ngay_nhan is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bắt buộc nhập đủ 4 thông tin: số biên bản nhận, người nhận, chức vụ và ngày nhận (FR-068, AC-42).",
        )

    today_vn = datetime.now(VN_TZ).date()
    if ngay_nhan > today_vn:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ngày nhận không được lớn hơn ngày hiện tại (FR-068, AC-42).",
        )

    target_lo_id = lo_xa_id if lo_xa_id is not None else lo_id
    lo = db.get(Lo, target_lo_id)
    if lo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô.")
    if not (scope.is_tinh and scope.tinh_ma == lo.tinh_ma):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền chuyển kho.")

    if lo.loai == "TINH":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Biển số của lô tỉnh không chuyển cho xã/phường (FR-068, G-6).",
        )
    if lo.loai != "XA":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng chọn một lô xã thành phần để bàn giao biển số.",
        )

    req_ids = list(dict.fromkeys(bien_ids or []))
    if not req_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng chọn ít nhất 1 biển số đang ở Tồn kho tỉnh để chuyển cho xã.",
        )

    plates = list(
        db.scalars(
            select(Bien).where(Bien.id.in_(req_ids), Bien.lo_id == lo.id)
        ).all()
    )
    if len(plates) != len(req_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Có biển số không thuộc lô xã được chọn.",
        )
    for p in plates:
        if p.tinh_trang != "Tồn kho tỉnh":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Biển số '{p.bien_so_day_du}' đang ở tình trạng '{p.tinh_trang}', chỉ chuyển được biển đang ở 'Tồn kho tỉnh'.",
            )

    now = datetime.now(timezone.utc)
    bg = BanGiao(
        lo_xa_id=lo.id,
        so_bien_ban=sbb,
        nguoi_nhan=nn,
        chuc_vu=cv,
        ngay_nhan=ngay_nhan,
        tao_boi=scope.ten_dang_nhap,
        tao_luc=now,
    )
    db.add(bg)
    db.flush()

    for p in plates:
        p.tinh_trang = "Tồn kho xã"
        p.giao = "Chưa trả"
        p.ban_giao_id = bg.id
        db.add(
            BienLichSu(
                bien_id=p.id,
                su_kien="CHUYEN_KHO_XA",
                tu="Tồn kho tỉnh",
                den="Tồn kho xã",
                ly_do=f"Biên bản {sbb} - Người nhận: {nn} ({cv})",
                nguoi=scope.ten_dang_nhap,
                luc=now,
            )
        )

    db.flush()
    if lo.lo_cha_id is not None:
        parent_dnm = db.get(Lo, lo.lo_cha_id)
        if parent_dnm is not None:
            sync_dnm_and_children_completion_states(
                db, parent_dnm, nguoi=scope.ten_dang_nhap, now=now
            )

    write_audit_log(
        db,
        nguoi_dung=scope.ten_dang_nhap,
        hanh_dong="CHUYEN_BIEN_CHO_XA",
        doi_tuong=lo.ma_lo,
        ket_qua="THANH_CONG",
        ip=ip,
        chi_tiet={
            "ban_giao_id": bg.id,
            "so_bien_ban": sbb,
            "nguoi_nhan": nn,
            "chuc_vu": cv,
            "ngay_nhan": ngay_nhan.isoformat(),
            "so_luong_bien": len(plates),
        },
    )
    db.commit()
    return {
        "ban_giao": {
            "id": bg.id,
            "lo_xa_id": bg.lo_xa_id,
            "so_bien_ban": bg.so_bien_ban,
            "nguoi_nhan": bg.nguoi_nhan,
            "chuc_vu": bg.chuc_vu,
            "ngay_nhan": bg.ngay_nhan.isoformat(),
        },
        "lo_xa": serialize_lo(db, lo),
    }


def list_bien_da_nhan(
    db: Session,
    scope: ScopeFilter,
    *,
    lo_id: int | None = None,
    giao: str | None = None,
) -> list[dict]:
    """Xem danh sách biển đã nhận về Tồn kho xã kèm thông tin biên bản bàn giao (FR-052)."""
    stmt = select(Bien).where(Bien.tinh_trang == "Tồn kho xã")
    stmt = scope.filter_bien(stmt, Bien)
    if lo_id is not None:
        stmt = stmt.where(Bien.lo_id == lo_id)
    if giao:
        stmt = stmt.where(Bien.giao == giao.strip())
    stmt = stmt.order_by(Bien.id.desc())
    plates = db.scalars(stmt).all()

    bg_ids = {p.ban_giao_id for p in plates if p.ban_giao_id is not None}
    bg_map = (
        {
            b.id: b
            for b in db.scalars(select(BanGiao).where(BanGiao.id.in_(bg_ids))).all()
        }
        if bg_ids
        else {}
    )

    result = []
    for p in plates:
        d = serialize_bien(db, p)
        bg = bg_map.get(p.ban_giao_id) if p.ban_giao_id else None
        d["so_bien_ban"] = bg.so_bien_ban if bg else None
        d["nguoi_nhan"] = bg.nguoi_nhan if bg else None
        d["chuc_vu"] = bg.chuc_vu if bg else None
        d["ngay_nhan"] = bg.ngay_nhan.isoformat() if bg else None
        result.append(d)
    return result


def tra_bien_cho_dan(
    db: Session,
    scope: ScopeFilter,
    *,
    bien_ids: list[int],
    ngay_gio_tra: datetime | None = None,
    ip: str | None = None,
) -> dict:
    """
    Trả biển số cho người dân (từng biển hoặc hàng loạt), không lưu dữ liệu công dân,
    chặn ngày giờ trả trong tương lai, và giải phóng cờ giữ chỗ để cho phép đặt lại có xác nhận (FR-053, G-6, AC-34).
    """
    scope.require_non_admin_for_mutation()
    clean_ids = list(dict.fromkeys(bien_ids or []))
    if not clean_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng chọn ít nhất 1 biển số để đánh dấu Đã trả.",
        )

    now = datetime.now(timezone.utc)
    ts = ngay_gio_tra or now
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    if ts > now + timedelta(seconds=5):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ngày giờ trả không được lớn hơn thời điểm hiện tại (FR-053, AC-34).",
        )

    plates = list(db.scalars(select(Bien).where(Bien.id.in_(clean_ids))).all())
    if len(plates) != len(clean_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy biển số.")

    for p in plates:
        scope.ensure_can_access_record(tinh_ma=p.tinh_ma, xa_ma=p.xa_ma)
        if p.xa_ma is not None:
            if not (scope.is_xa and scope.xa_ma == p.xa_ma):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Chỉ xã/phường quản lý mới được trả biển thuộc tồn kho xã.",
                )
            if p.tinh_trang != "Tồn kho xã" or p.giao != "Chưa trả":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Biển số '{p.bien_so_day_du}' không ở trạng thái 'Tồn kho xã / Chưa trả' (hiện tại: {p.tinh_trang} / {p.giao}).",
                )
        else:
            # Biển của lô tỉnh đang Tồn kho tỉnh (G-6)
            if not (scope.is_tinh and scope.tinh_ma == p.tinh_ma):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Chỉ tài khoản tỉnh mới được trả biển của lô tỉnh.",
                )
            if p.tinh_trang != "Tồn kho tỉnh" or p.giao != "Chưa trả":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Biển số lô tỉnh '{p.bien_so_day_du}' không ở trạng thái 'Tồn kho tỉnh / Chưa trả'.",
                )

        p.giao = "Đã trả"
        p.ngay_gio_tra = ts
        p.giu_cho = False
        db.add(
            BienLichSu(
                bien_id=p.id,
                su_kien="TRA_BIEN_CHO_DAN",
                tu="Chưa trả",
                den="Đã trả",
                ly_do=None,
                nguoi=scope.ten_dang_nhap,
                luc=now,
            )
        )

    write_audit_log(
        db,
        nguoi_dung=scope.ten_dang_nhap,
        hanh_dong="TRA_BIEN_CHO_DAN",
        doi_tuong=",".join(p.bien_so_day_du for p in plates[:5]),
        ket_qua="THANH_CONG",
        ip=ip,
        chi_tiet={
            "so_luong": len(plates),
            "bien_ids": clean_ids,
            "ngay_gio_tra": ts.isoformat(),
        },
    )
    db.commit()
    return {
        "so_luong_da_tra": len(plates),
        "items": [serialize_bien(db, p) for p in plates],
    }


def thu_hoi_bien(
    db: Session,
    scope: ScopeFilter,
    *,
    bien_id: int,
    ly_do: str,
    xac_nhan: bool = True,
    ip: str | None = None,
) -> dict:
    """
    Thu hồi biển đã trả về xã/tỉnh ('Đã trả' -> 'Thu hồi về xã'):
    trạng thái cuối trên trục giao, không trả/hủy tiếp được, giải phóng số để đặt lại có xác nhận (FR-054, G-17, AC-35).
    """
    scope.require_non_admin_for_mutation()
    if not xac_nhan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng xác nhận trước khi thu hồi biển số (FR-091).",
        )
    reason = (ly_do or "").strip()
    if not reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bắt buộc nhập lý do thu hồi biển số (FR-054, AC-35).",
        )

    p = db.get(Bien, bien_id)
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy biển số.")
    scope.ensure_can_access_record(tinh_ma=p.tinh_ma, xa_ma=p.xa_ma)

    if p.xa_ma is not None and not (scope.is_xa and scope.xa_ma == p.xa_ma):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ xã sở hữu mới được thu hồi biển này.")
    if p.xa_ma is None and not (scope.is_tinh and scope.tinh_ma == p.tinh_ma):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ tỉnh sở hữu mới được thu hồi biển lô tỉnh.")

    if p.giao != "Đã trả":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Chỉ thu hồi được biển đang ở trạng thái 'Đã trả' (hiện tại: '{p.giao}') (FR-054, AC-35).",
        )

    now = datetime.now(timezone.utc)
    p.giao = "Thu hồi về xã"
    p.ly_do_thu_hoi = reason
    p.giu_cho = False

    db.add(
        BienLichSu(
            bien_id=p.id,
            su_kien="THU_HOI_BIEN",
            tu="Đã trả",
            den="Thu hồi về xã",
            ly_do=reason,
            nguoi=scope.ten_dang_nhap,
            luc=now,
        )
    )
    write_audit_log(
        db,
        nguoi_dung=scope.ten_dang_nhap,
        hanh_dong="THU_HOI_BIEN",
        doi_tuong=p.bien_so_day_du,
        ket_qua="THANH_CONG",
        ip=ip,
        chi_tiet={"bien_id": p.id, "ly_do": reason},
    )
    db.commit()
    return serialize_bien(db, p)


def huy_bien(
    db: Session,
    scope: ScopeFilter,
    *,
    bien_id: int,
    ly_do: str,
    xac_nhan: bool = True,
    ip: str | None = None,
) -> dict:
    """
    Hủy biển số kèm lý do bắt buộc, giải phóng BienSoDayDu cho lần đặt khác (FR-054, FR-070, AC-35, AC-44):
    - Tỉnh hủy được biển đang 'Đã đặt' hoặc 'Tồn kho tỉnh' (chưa trả).
    - Xã hủy được biển đang 'Tồn kho xã' và 'Chưa trả'.
    """
    scope.require_non_admin_for_mutation()
    if not xac_nhan:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Vui lòng xác nhận trước khi hủy biển số (FR-091).",
        )
    reason = (ly_do or "").strip()
    if not reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bắt buộc nhập lý do hủy biển số (FR-054, FR-070).",
        )

    p = db.get(Bien, bien_id)
    if p is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy biển số.")
    scope.ensure_can_access_record(tinh_ma=p.tinh_ma, xa_ma=p.xa_ma)

    if p.tinh_trang == "Đã hủy":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Biển số đã ở trạng thái Đã hủy.")
    if p.giao in ("Đã trả", "Thu hồi về xã"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Biển số đã ở trạng thái '{p.giao}', không được phép hủy (FR-054, AC-35).",
        )

    if scope.is_xa:
        if p.xa_ma != scope.xa_ma or p.tinh_trang != "Tồn kho xã" or p.giao != "Chưa trả":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Xã/phường chỉ được hủy biển đang ở 'Tồn kho xã' và 'Chưa trả' (FR-054).",
            )
    elif scope.is_tinh:
        if p.tinh_ma != scope.tinh_ma or p.tinh_trang not in ("Đã đặt", "Tồn kho tỉnh"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Tỉnh chỉ được hủy biển đang ở 'Đã đặt' hoặc 'Tồn kho tỉnh' chưa trả (FR-070).",
            )

    now = datetime.now(timezone.utc)
    old_st = p.tinh_trang
    p.tinh_trang = "Đã hủy"
    p.giao = None
    p.ly_do_huy = reason
    p.giu_cho = False

    db.add(
        BienLichSu(
            bien_id=p.id,
            su_kien="HUY_BIEN",
            tu=old_st,
            den="Đã hủy",
            ly_do=reason,
            nguoi=scope.ten_dang_nhap,
            luc=now,
        )
    )
    db.flush()

    lo = db.get(Lo, p.lo_id)
    if lo is not None and lo.lo_cha_id is not None:
        parent_dnm = db.get(Lo, lo.lo_cha_id)
        if parent_dnm is not None:
            sync_dnm_and_children_completion_states(
                db, parent_dnm, nguoi=scope.ten_dang_nhap, now=now
            )

    write_audit_log(
        db,
        nguoi_dung=scope.ten_dang_nhap,
        hanh_dong="HUY_BIEN",
        doi_tuong=p.bien_so_day_du,
        ket_qua="THANH_CONG",
        ip=ip,
        chi_tiet={"bien_id": p.id, "tu": old_st, "ly_do": reason},
    )
    db.commit()
    return serialize_bien(db, p)

