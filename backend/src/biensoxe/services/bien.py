from datetime import datetime, timezone

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from biensoxe.domain.bien_so import (
    BienSoValidationError,
    normalize_raw_bien_so,
    parse_and_validate_bien_so,
)
from biensoxe.models.bien import Bien, BienLichSu
from biensoxe.models.danh_muc import LoaiPT, MaBienTinh, NenBien, Tinh, XaPhuong
from biensoxe.models.lo import Lo
from biensoxe.repositories.scope import ScopeFilter
from biensoxe.services.audit import write_audit_log

DEFAULT_NEN_BIEN_TEN = "Nền màu TRẮNG, chữ và số màu ĐEN"


def get_active_province_codes(db: Session, tinh_ma: str) -> set[str]:
    codes = db.scalars(
        select(MaBienTinh.ma_bien).where(
            MaBienTinh.tinh_ma == tinh_ma,
            MaBienTinh.dang_dung.is_(True),
        )
    ).all()
    return set(codes)


def resolve_plate_metadata(
    db: Session,
    raw_plate: str,
    tinh_ma: str,
    *,
    nen_bien: str | None = None,
    nen_bien_id: int | None = None,
) -> dict:
    """Phân tách chuỗi biển số, đối chiếu danh mục LoaiPT, NenBien và kiểm tra mã biển tỉnh (FR-030..038)."""
    loai_pt_objs = db.scalars(select(LoaiPT).where(LoaiPT.dang_dung.is_(True))).all()
    active_loai_pt = {lp.seri_chu: lp.ten for lp in loai_pt_objs}
    lp_by_seri = {lp.seri_chu: lp for lp in loai_pt_objs}

    nen_bien_objs = db.scalars(select(NenBien).where(NenBien.dang_dung.is_(True))).all()
    active_nen_bien = {nb.ten: nb.mau_sac for nb in nen_bien_objs}
    nb_by_ten = {nb.ten: nb for nb in nen_bien_objs}
    nb_by_mau = {nb.mau_sac.upper(): nb for nb in nen_bien_objs}
    nb_by_id = {nb.id: nb for nb in nen_bien_objs}

    resolved_nen_ten = DEFAULT_NEN_BIEN_TEN
    if nen_bien_id is not None:
        nb_obj = nb_by_id.get(nen_bien_id)
        if nb_obj is None:
            raise BienSoValidationError("Nền biển được chọn không tồn tại hoặc đã ngừng sử dụng (FR-034).")
        resolved_nen_ten = nb_obj.ten
    elif nen_bien is not None:
        nb_clean = nen_bien.strip()
        if not nb_clean:
            resolved_nen_ten = ""
        elif nb_clean in nb_by_ten:
            resolved_nen_ten = nb_clean
        elif nb_clean.upper() in nb_by_mau:
            resolved_nen_ten = nb_by_mau[nb_clean.upper()].ten
        else:
            resolved_nen_ten = nb_clean

    prov_codes = get_active_province_codes(db, tinh_ma)
    parsed = parse_and_validate_bien_so(
        raw_bien_so=raw_plate,
        nen_bien=resolved_nen_ten,
        active_loai_pt=active_loai_pt,
        active_nen_bien=active_nen_bien,
        allowed_ma_bien_tinh=prov_codes,
    )

    return {
        "parsed": parsed,
        "loai_pt": lp_by_seri[parsed.seri_chu],
        "nen_bien": nb_by_ten[parsed.nen_bien],
        "ngoai_tinh": parsed.ngoai_tinh,
    }


def check_plate_duplicates(
    db: Session,
    *,
    lo_id: int | None,
    tinh_ma: str,
    bien_so_day_du: str,
    exclude_bien_id: int | None = None,
) -> dict:
    """
    Kiểm tra trùng biển số ở 4 trường hợp (FR-036 a/b/c/d, G-17, AC-24):
    a) Trùng trong cùng lô (tinh_trang != 'Đã hủy') -> chặn
    b) Trùng với biển đang giữ chỗ (giu_cho = True) ở lô khác trong cùng tỉnh -> chặn
    c) Biển ở lô khác đã 'Đã hủy' -> cho phép đặt lại không cần xác nhận
    d) Biển ở lô khác đã 'Đã trả' hoặc 'Thu hồi về xã' -> yêu cầu xác nhận đặt lại
    """
    if lo_id is not None:
        stmt_same = select(Bien).where(
            Bien.lo_id == lo_id,
            Bien.bien_so_day_du == bien_so_day_du,
            Bien.tinh_trang != "Đã hủy",
        )
        if exclude_bien_id is not None:
            stmt_same = stmt_same.where(Bien.id != exclude_bien_id)
        same_in_lo = db.scalar(stmt_same)
        if same_in_lo is not None:
            return {
                "blocked": True,
                "reason": f"Biển số '{bien_so_day_du}' bị trùng trong cùng lô (STT {same_in_lo.stt}).",
                "requires_reorder_confirm": False,
                "reorder_info": None,
            }

    stmt_active = select(Bien).where(
        Bien.tinh_ma == tinh_ma,
        Bien.bien_so_day_du == bien_so_day_du,
        Bien.giu_cho.is_(True),
    )
    if lo_id is not None:
        stmt_active = stmt_active.where(Bien.lo_id != lo_id)
    if exclude_bien_id is not None:
        stmt_active = stmt_active.where(Bien.id != exclude_bien_id)
    active_other = db.scalar(stmt_active)
    if active_other is not None:
        other_lo = db.get(Lo, active_other.lo_id)
        ma_lo_khac = other_lo.ma_lo if other_lo else str(active_other.lo_id)
        return {
            "blocked": True,
            "reason": f"Biển số '{bien_so_day_du}' đang hoạt động ở lô khác trong tỉnh ({ma_lo_khac}).",
            "requires_reorder_confirm": False,
            "reorder_info": None,
        }

    stmt_returned = (
        select(Bien)
        .where(
            Bien.tinh_ma == tinh_ma,
            Bien.bien_so_day_du == bien_so_day_du,
            Bien.giao.in_(("Đã trả", "Thu hồi về xã")),
        )
        .order_by(Bien.id.desc())
    )
    if exclude_bien_id is not None:
        stmt_returned = stmt_returned.where(Bien.id != exclude_bien_id)
    returned_prev = db.scalar(stmt_returned)
    if returned_prev is not None:
        prev_lo = db.get(Lo, returned_prev.lo_id)
        return {
            "blocked": False,
            "reason": None,
            "requires_reorder_confirm": True,
            "reorder_info": {
                "bien_id_cu": returned_prev.id,
                "ma_lo_cu": prev_lo.ma_lo if prev_lo else None,
                "giao_cu": returned_prev.giao,
                "ngay_gio_tra": (
                    returned_prev.ngay_gio_tra.isoformat()
                    if returned_prev.ngay_gio_tra
                    else None
                ),
            },
        }

    return {
        "blocked": False,
        "reason": None,
        "requires_reorder_confirm": False,
        "reorder_info": None,
    }


def inspect_plate_inline(
    db: Session,
    scope: ScopeFilter,
    *,
    lo_id: int | None,
    bien_so: str,
    nen_bien: str | None = None,
    nen_bien_id: int | None = None,
    exclude_bien_id: int | None = None,
) -> dict:
    """API kiểm tra tại chỗ POST /api/v1/bien/kiem-tra (FR-090)."""
    tinh_ma = scope.tinh_ma
    if lo_id is not None:
        lo = db.get(Lo, lo_id)
        if lo is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô.")
        scope.ensure_can_access_record(tinh_ma=lo.tinh_ma, xa_ma=lo.xa_ma)
        tinh_ma = lo.tinh_ma
    if not tinh_ma:
        tinh_ma = "01"

    try:
        meta = resolve_plate_metadata(
            db, bien_so, tinh_ma, nen_bien=nen_bien, nen_bien_id=nen_bien_id
        )
    except BienSoValidationError as exc:
        return {
            "hop_le": False,
            "loi": str(exc),
            "bien_so_day_du": None,
            "ma_tinh_bien": None,
            "seri_chu": None,
            "seri_so": None,
            "dau_so": None,
            "loai_pt_id": None,
            "loai_pt_ten": None,
            "nen_bien_id": None,
            "nen_bien_ten": None,
            "mau_sac": None,
            "ngoai_tinh": False,
            "yeu_cau_xac_nhan_dat_lai": False,
            "thong_tin_dat_lai": None,
        }

    parsed = meta["parsed"]
    loai_pt = meta["loai_pt"]
    nen_bien_obj = meta["nen_bien"]
    dup = check_plate_duplicates(
        db,
        lo_id=lo_id,
        tinh_ma=tinh_ma,
        bien_so_day_du=parsed.bien_so_day_du,
        exclude_bien_id=exclude_bien_id,
    )
    if dup["blocked"]:
        return {
            "hop_le": False,
            "loi": dup["reason"],
            "bien_so_day_du": parsed.bien_so_day_du,
            "ma_tinh_bien": parsed.ma_tinh,
            "seri_chu": parsed.seri_chu,
            "seri_so": parsed.seri_so,
            "dau_so": parsed.dau_so,
            "loai_pt_id": loai_pt.id,
            "loai_pt_ten": loai_pt.ten,
            "nen_bien_id": nen_bien_obj.id,
            "nen_bien_ten": nen_bien_obj.ten,
            "mau_sac": nen_bien_obj.mau_sac,
            "ngoai_tinh": meta["ngoai_tinh"],
            "yeu_cau_xac_nhan_dat_lai": False,
            "thong_tin_dat_lai": None,
        }

    return {
        "hop_le": True,
        "loi": None,
        "bien_so_day_du": parsed.bien_so_day_du,
        "ma_tinh_bien": parsed.ma_tinh,
        "seri_chu": parsed.seri_chu,
        "seri_so": parsed.seri_so,
        "dau_so": parsed.dau_so,
        "loai_pt_id": loai_pt.id,
        "loai_pt_ten": loai_pt.ten,
        "nen_bien_id": nen_bien_obj.id,
        "nen_bien_ten": nen_bien_obj.ten,
        "mau_sac": nen_bien_obj.mau_sac,
        "ngoai_tinh": meta["ngoai_tinh"],
        "yeu_cau_xac_nhan_dat_lai": dup["requires_reorder_confirm"],
        "thong_tin_dat_lai": dup["reorder_info"],
    }


def ensure_lo_editable_for_plates(lo: Lo, scope: ScopeFilter) -> None:
    """Kiểm tra lô có đang mở cho phép thêm/sửa/xóa biển hay không (FR-043, FR-049, FR-071)."""
    scope.require_non_admin_for_mutation()
    if lo.loai == "XA":
        if lo.trang_thai in ("Khởi tạo", "Từ chối"):
            if not (scope.is_xa and scope.xa_ma == lo.xa_ma):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Chỉ xã/phường sở hữu lô mới được sửa khi ở trạng thái Khởi tạo hoặc Từ chối.",
                )
        elif lo.trang_thai == "Cho phép điều chỉnh":
            if not (
                (scope.is_xa and scope.xa_ma == lo.xa_ma)
                or (scope.is_tinh and scope.tinh_ma == lo.tinh_ma)
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Không có quyền điều chỉnh lô này.",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Lô đang ở trạng thái '{lo.trang_thai}', không được phép thêm/sửa/xóa biển số.",
            )
    elif lo.loai == "TINH":
        if not (scope.is_tinh and scope.tinh_ma == lo.tinh_ma):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chỉ tài khoản tỉnh sở hữu lô mới được sửa lô tỉnh.",
            )
        if lo.trang_thai not in ("Khởi tạo", "Từ chối", "Cho phép điều chỉnh"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Lô tỉnh đang ở trạng thái '{lo.trang_thai}', không được phép thêm/sửa/xóa biển số.",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Không thêm trực tiếp biển rời vào lô đặt nhà máy khi chưa Đặt thành công.",
        )


def resequence_lo_stt(db: Session, lo_id: int) -> None:
    """Đánh lại số thứ tự 1..N liên tục cho danh sách biển trong lô (AC-26)."""
    plates = db.scalars(
        select(Bien).where(Bien.lo_id == lo_id).order_by(Bien.stt.asc(), Bien.id.asc())
    ).all()
    for idx, p in enumerate(plates, start=1):
        if p.stt != idx:
            p.stt = idx
    db.flush()


def serialize_bien(
    db: Session,
    b: Bien,
    *,
    lo_map: dict[int, Lo] | None = None,
    loai_pt_map: dict[int, LoaiPT] | None = None,
    nen_bien_map: dict[int, NenBien] | None = None,
    tinh_map: dict[str, Tinh] | None = None,
    xa_map: dict[str, XaPhuong] | None = None,
    parent_lo_map: dict[int, Lo] | None = None,
) -> dict:
    lo = lo_map.get(b.lo_id) if lo_map else db.get(Lo, b.lo_id)
    lp = loai_pt_map.get(b.loai_pt_id) if loai_pt_map else db.get(LoaiPT, b.loai_pt_id)
    nb = nen_bien_map.get(b.nen_bien_id) if nen_bien_map else db.get(NenBien, b.nen_bien_id)

    tinh_code = b.tinh_ma or (lo.tinh_ma if lo else None)
    xa_code = b.xa_ma or (lo.xa_ma if lo else None)

    tinh = (tinh_map.get(tinh_code) if tinh_map else db.get(Tinh, tinh_code)) if tinh_code else None
    xa = (xa_map.get(xa_code) if xa_map else db.get(XaPhuong, xa_code)) if xa_code else None

    ma_lo_dat_nha_may = None
    if lo and lo.lo_cha_id:
        parent = (
            parent_lo_map.get(lo.lo_cha_id)
            if parent_lo_map
            else db.get(Lo, lo.lo_cha_id)
        )
        if parent:
            ma_lo_dat_nha_may = parent.ma_lo

    don_vi_name = xa.ten if xa else (tinh.ten if tinh else "")
    loai_pt_name = lp.ten if lp else ""

    return {
        "id": b.id,
        "lo_id": b.lo_id,
        "ma_lo": lo.ma_lo if lo else None,
        "loai_lo": lo.loai if lo else None,
        "trang_thai_lo": lo.trang_thai if lo else None,
        "ma_lo_dat_nha_may": ma_lo_dat_nha_may,
        "stt": b.stt,
        "bien_so_day_du": b.bien_so_day_du,
        "ma_tinh_bien": b.ma_tinh_bien,
        "seri_chu": b.seri_chu,
        "seri_so": b.seri_so,
        "dau_so": b.dau_so,
        "loai_pt_id": b.loai_pt_id,
        "loai_pt_ten": loai_pt_name,
        "loai_pt": loai_pt_name,
        "nen_bien_id": b.nen_bien_id,
        "nen_bien_ten": nb.ten if nb else None,
        "mau_sac": nb.mau_sac if nb else None,
        "ghi_chu": b.ghi_chu,
        "tinh_ma": tinh_code,
        "tinh_ten": tinh.ten if tinh else None,
        "xa_ma": xa_code,
        "xa_ten": xa.ten if xa else None,
        "don_vi_ten": don_vi_name,
        "don_vi": don_vi_name,
        "tinh_trang": b.tinh_trang,
        "giao": b.giao,
        "ngay_gio_tra": b.ngay_gio_tra.isoformat() if b.ngay_gio_tra else None,
        "ban_giao_id": b.ban_giao_id,
        "ngay_nhap_kho": b.ngay_nhap_kho.isoformat() if b.ngay_nhap_kho else None,
        "ly_do_huy": b.ly_do_huy,
        "ly_do_thu_hoi": b.ly_do_thu_hoi,
        "dat_lai_xac_nhan": b.dat_lai_xac_nhan,
        "ngoai_tinh": b.ngoai_tinh,
        "loi_ly_do": b.loi_ly_do,
        "giu_cho": b.giu_cho,
    }


def list_plates_in_lo(db: Session, scope: ScopeFilter, *, lo_id: int) -> list[dict]:
    lo = db.get(Lo, lo_id)
    if lo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô.")
    scope.ensure_can_access_record(tinh_ma=lo.tinh_ma, xa_ma=lo.xa_ma)

    if lo.loai == "DAT_NHA_MAY":
        child_los = db.scalars(select(Lo).where(Lo.lo_cha_id == lo.id).order_by(Lo.id.asc())).all()
        child_ids = [c.id for c in child_los]
        if not child_ids:
            return []
        plates = db.scalars(
            select(Bien)
            .where(Bien.lo_id.in_(child_ids))
            .order_by(Bien.lo_id.asc(), Bien.stt.asc(), Bien.id.asc())
        ).all()
        lo_map = {c.id: c for c in child_los}
        parent_map = {lo.id: lo}
    else:
        plates = db.scalars(
            select(Bien).where(Bien.lo_id == lo.id).order_by(Bien.stt.asc(), Bien.id.asc())
        ).all()
        lo_map = {lo.id: lo}
        parent_map = {}
        if lo.lo_cha_id:
            parent_lo = db.get(Lo, lo.lo_cha_id)
            if parent_lo:
                parent_map[parent_lo.id] = parent_lo

    lp_map = {lp.id: lp for lp in db.scalars(select(LoaiPT)).all()}
    nb_map = {nb.id: nb for nb in db.scalars(select(NenBien)).all()}
    tinh_map = {t.ma: t for t in db.scalars(select(Tinh)).all()}
    xa_ids = {p.xa_ma for p in plates if p.xa_ma}
    if lo.xa_ma:
        xa_ids.add(lo.xa_ma)
    for c in lo_map.values():
        if c.xa_ma:
            xa_ids.add(c.xa_ma)
    xa_map = (
        {x.ma: x for x in db.scalars(select(XaPhuong).where(XaPhuong.ma.in_(xa_ids))).all()}
        if xa_ids
        else {}
    )

    result = []
    for idx, p in enumerate(plates, start=1):
        d = serialize_bien(
            db,
            p,
            lo_map=lo_map,
            loai_pt_map=lp_map,
            nen_bien_map=nb_map,
            tinh_map=tinh_map,
            xa_map=xa_map,
            parent_lo_map=parent_map,
        )
        if lo.loai == "DAT_NHA_MAY":
            d["stt"] = idx
        result.append(d)
    return result


def add_plate_to_lo(
    db: Session,
    scope: ScopeFilter,
    *,
    lo_id: int,
    bien_so: str,
    nen_bien: str | None = None,
    nen_bien_id: int | None = None,
    ghi_chu: str | None = None,
    dat_lai_xac_nhan: bool = False,
    ip: str | None = None,
) -> dict | JSONResponse:
    lo = db.get(Lo, lo_id)
    if lo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô.")
    scope.ensure_can_access_record(tinh_ma=lo.tinh_ma, xa_ma=lo.xa_ma)
    ensure_lo_editable_for_plates(lo, scope)

    try:
        meta = resolve_plate_metadata(
            db, bien_so, lo.tinh_ma, nen_bien=nen_bien, nen_bien_id=nen_bien_id
        )
    except BienSoValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    parsed = meta["parsed"]
    dup = check_plate_duplicates(
        db,
        lo_id=lo.id,
        tinh_ma=lo.tinh_ma,
        bien_so_day_du=parsed.bien_so_day_du,
    )
    if dup["blocked"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=dup["reason"])

    if dup["requires_reorder_confirm"] and not dat_lai_xac_nhan:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": (
                    f"Biển số '{parsed.bien_so_day_du}' đã ở trạng thái "
                    f"'{dup['reorder_info']['giao_cu']}'. Vui lòng xác nhận đặt lại (FR-036)."
                ),
                "yeu_cau_xac_nhan_dat_lai": True,
                "thong_tin_dat_lai": dup["reorder_info"],
            },
        )

    max_stt = (
        db.scalar(select(func.coalesce(func.max(Bien.stt), 0)).where(Bien.lo_id == lo.id)) or 0
    )
    should_reserve = lo.trang_thai == "Cho phép điều chỉnh"
    now = datetime.now(timezone.utc)

    bien = Bien(
        lo_id=lo.id,
        stt=max_stt + 1,
        bien_so_day_du=parsed.bien_so_day_du,
        ma_tinh_bien=parsed.ma_tinh,
        seri_chu=parsed.seri_chu,
        seri_so=parsed.seri_so,
        dau_so=parsed.dau_so,
        loai_pt_id=meta["loai_pt"].id,
        nen_bien_id=meta["nen_bien"].id,
        ghi_chu=(ghi_chu or "").strip() or None,
        tinh_ma=lo.tinh_ma,
        xa_ma=lo.xa_ma,
        tinh_trang="Chưa đặt",
        giao=None,
        dat_lai_xac_nhan=bool(dup["requires_reorder_confirm"] and dat_lai_xac_nhan),
        ngoai_tinh=meta["ngoai_tinh"],
        loi_ly_do=None,
        giu_cho=should_reserve,
    )
    db.add(bien)
    db.flush()

    db.add(
        BienLichSu(
            bien_id=bien.id,
            su_kien="TAO_BIEN",
            tu=None,
            den="Chưa đặt",
            ly_do=None,
            nguoi=scope.ten_dang_nhap,
            luc=now,
        )
    )
    write_audit_log(
        db,
        nguoi_dung=scope.ten_dang_nhap,
        hanh_dong="THEM_BIEN",
        doi_tuong=bien.bien_so_day_du,
        ket_qua="THANH_CONG",
        ip=ip,
        chi_tiet={
            "lo_id": lo.id,
            "ma_lo": lo.ma_lo,
            "ngoai_tinh": bien.ngoai_tinh,
            "dat_lai_xac_nhan": bien.dat_lai_xac_nhan,
        },
    )
    db.commit()
    return serialize_bien(db, bien)


def update_plate_in_lo(
    db: Session,
    scope: ScopeFilter,
    *,
    bien_id: int,
    bien_so: str,
    nen_bien: str | None = None,
    nen_bien_id: int | None = None,
    ghi_chu: str | None = None,
    dat_lai_xac_nhan: bool = False,
    ip: str | None = None,
) -> dict | JSONResponse:
    bien = db.get(Bien, bien_id)
    if bien is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy biển số."
        )
    lo = db.get(Lo, bien.lo_id)
    assert lo is not None
    scope.ensure_can_access_record(tinh_ma=lo.tinh_ma, xa_ma=lo.xa_ma)
    ensure_lo_editable_for_plates(lo, scope)

    eff_nen_id = nen_bien_id if (nen_bien is None and nen_bien_id is not None) else (bien.nen_bien_id if nen_bien is None else None)
    try:
        meta = resolve_plate_metadata(
            db, bien_so, lo.tinh_ma, nen_bien=nen_bien, nen_bien_id=eff_nen_id
        )
    except BienSoValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    parsed = meta["parsed"]
    dup = check_plate_duplicates(
        db,
        lo_id=lo.id,
        tinh_ma=lo.tinh_ma,
        bien_so_day_du=parsed.bien_so_day_du,
        exclude_bien_id=bien.id,
    )
    if dup["blocked"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=dup["reason"])

    if dup["requires_reorder_confirm"] and not dat_lai_xac_nhan:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": (
                    f"Biển số '{parsed.bien_so_day_du}' đã ở trạng thái "
                    f"'{dup['reorder_info']['giao_cu']}'. Vui lòng xác nhận đặt lại (FR-036)."
                ),
                "yeu_cau_xac_nhan_dat_lai": True,
                "thong_tin_dat_lai": dup["reorder_info"],
            },
        )

    old_plate = bien.bien_so_day_du
    bien.bien_so_day_du = parsed.bien_so_day_du
    bien.ma_tinh_bien = parsed.ma_tinh
    bien.seri_chu = parsed.seri_chu
    bien.seri_so = parsed.seri_so
    bien.dau_so = parsed.dau_so
    bien.loai_pt_id = meta["loai_pt"].id
    bien.nen_bien_id = meta["nen_bien"].id
    bien.ghi_chu = (ghi_chu or "").strip() or None
    bien.ngoai_tinh = meta["ngoai_tinh"]
    bien.dat_lai_xac_nhan = bool(dup["requires_reorder_confirm"] and dat_lai_xac_nhan)
    bien.loi_ly_do = None

    write_audit_log(
        db,
        nguoi_dung=scope.ten_dang_nhap,
        hanh_dong="SUA_BIEN",
        doi_tuong=bien.bien_so_day_du,
        ket_qua="THANH_CONG",
        ip=ip,
        chi_tiet={"bien_id": bien.id, "tu": old_plate, "den": bien.bien_so_day_du},
    )
    db.commit()
    return serialize_bien(db, bien)


def delete_plate_in_lo(
    db: Session,
    scope: ScopeFilter,
    *,
    bien_id: int,
    ip: str | None = None,
) -> None:
    bien = db.get(Bien, bien_id)
    if bien is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy biển số."
        )
    lo = db.get(Lo, bien.lo_id)
    assert lo is not None
    scope.ensure_can_access_record(tinh_ma=lo.tinh_ma, xa_ma=lo.xa_ma)
    ensure_lo_editable_for_plates(lo, scope)

    plate_code = bien.bien_so_day_du
    lo_id = lo.id
    db.delete(bien)
    db.flush()
    resequence_lo_stt(db, lo_id)

    write_audit_log(
        db,
        nguoi_dung=scope.ten_dang_nhap,
        hanh_dong="XOA_BIEN",
        doi_tuong=plate_code,
        ket_qua="THANH_CONG",
        ip=ip,
        chi_tiet={"lo_id": lo_id, "ma_lo": lo.ma_lo},
    )
    db.commit()
