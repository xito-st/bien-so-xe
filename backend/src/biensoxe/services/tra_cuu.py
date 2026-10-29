import io

from sqlalchemy import case, or_, select
from sqlalchemy.orm import Session
import xlsxwriter

from biensoxe.models.bien import Bien
from biensoxe.models.danh_muc import LoaiPT, NenBien, Tinh, XaPhuong
from biensoxe.models.lo import Lo
from biensoxe.repositories.scope import ScopeFilter


def _apply_visibility_scope(stmt, scope: ScopeFilter):
    stmt = scope.filter_bien(stmt, Bien)
    if scope.is_tinh or scope.is_admin:
        # Tỉnh và Admin chỉ thấy lô xã sau khi đã đồng bộ lên tỉnh (FR-044, FR-045)
        stmt = stmt.where(
            or_(
                Lo.loai != "XA",
                Lo.trang_thai.notin_(("Khởi tạo", "Đã gửi")),
            )
        )
    return stmt


def suggest_tra_cuu(
    db: Session,
    scope: ScopeFilter,
    *,
    q: str | None = None,
    limit: int = 20,
) -> list[dict]:
    """Gợi ý tra cứu từ ký tự thứ 2 trở đi trong phạm vi quyền (FR-050, FR-060, AC-33)."""
    q_clean = (q or "").strip()
    if len(q_clean) < 2:
        return []

    q_upper = q_clean.upper()
    stmt = (
        select(Bien, Lo, LoaiPT, NenBien)
        .join(Lo, Lo.id == Bien.lo_id)
        .join(LoaiPT, LoaiPT.id == Bien.loai_pt_id)
        .join(NenBien, NenBien.id == Bien.nen_bien_id)
    )
    stmt = _apply_visibility_scope(stmt, scope)
    stmt = stmt.where(
        or_(
            Bien.bien_so_day_du.ilike(f"%{q_upper}%"),
            Lo.ma_lo.ilike(f"%{q_upper}%"),
            Bien.seri_chu.ilike(f"{q_upper}%"),
            Bien.dau_so.ilike(f"{q_upper}%"),
            Bien.ma_tinh_bien.ilike(f"{q_upper}%"),
            LoaiPT.ten.ilike(f"%{q_upper}%"),
        )
    )
    stmt = stmt.order_by(
        case((Bien.tinh_trang != "Đã hủy", 0), else_=1),
        Bien.bien_so_day_du.asc(),
        Bien.id.desc(),
    ).limit(min(max(limit, 1), 50))

    rows = db.execute(stmt).all()
    results: list[dict] = []
    for bien, lo, loai_pt, nen_bien in rows:
        results.append(
            {
                "id": bien.id,
                "bien_so_day_du": bien.bien_so_day_du,
                "ma_lo": lo.ma_lo,
                "seri_chu": bien.seri_chu,
                "dau_so": bien.dau_so,
                "loai_pt": loai_pt.ten,
                "mau_sac": nen_bien.mau_sac,
                "ma_tinh_bien": bien.ma_tinh_bien,
                "tinh_trang": bien.tinh_trang,
                "giao": bien.giao,
                "ngoai_tinh": bien.ngoai_tinh,
            }
        )
    return results


def search_bien(
    db: Session,
    scope: ScopeFilter,
    *,
    q: str | None = None,
    ma_lo: str | None = None,
    bien_so: str | None = None,
    seri_chu: str | None = None,
    dau_so: str | None = None,
    loai_pt_id: int | None = None,
    loai_pt: str | None = None,
    ma_tinh_bien: str | None = None,
    tinh_ma: str | None = None,
    xa_ma: str | None = None,
    trang_thai_lo: str | None = None,
    tinh_trang: str | None = None,
    giao: str | None = None,
    ngoai_tinh: bool | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[dict]:
    """Tra cứu và lọc kết hợp nhiều tiêu chí theo phạm vi quyền (FR-050, FR-060, FR-082, AC-33)."""
    stmt = (
        select(Bien, Lo, LoaiPT, NenBien)
        .join(Lo, Lo.id == Bien.lo_id)
        .join(LoaiPT, LoaiPT.id == Bien.loai_pt_id)
        .join(NenBien, NenBien.id == Bien.nen_bien_id)
    )
    stmt = _apply_visibility_scope(stmt, scope)

    if q and q.strip():
        q_up = q.strip().upper()
        stmt = stmt.where(
            or_(
                Bien.bien_so_day_du.ilike(f"%{q_up}%"),
                Lo.ma_lo.ilike(f"%{q_up}%"),
                Bien.seri_chu.ilike(f"{q_up}%"),
                Bien.dau_so.ilike(f"{q_up}%"),
                LoaiPT.ten.ilike(f"%{q_up}%"),
            )
        )
    if ma_lo and ma_lo.strip():
        ml = ma_lo.strip()
        parent_ids = select(Lo.id).where(
            Lo.loai == "DAT_NHA_MAY",
            Lo.ma_lo.ilike(f"%{ml}%"),
        )
        stmt = stmt.where(
            or_(
                Lo.ma_lo.ilike(f"%{ml}%"),
                Lo.lo_cha_id.in_(parent_ids),
            )
        )
    if bien_so and bien_so.strip():
        bs = bien_so.strip().upper()
        stmt = stmt.where(Bien.bien_so_day_du.ilike(f"%{bs}%"))
    if seri_chu and seri_chu.strip():
        sc = seri_chu.strip().upper()
        stmt = stmt.where(Bien.seri_chu == sc)
    if dau_so and dau_so.strip():
        ds = dau_so.strip()
        stmt = stmt.where(Bien.dau_so == ds)
    if loai_pt_id is not None:
        stmt = stmt.where(Bien.loai_pt_id == loai_pt_id)
    if loai_pt and loai_pt.strip():
        lp_q = loai_pt.strip().upper()
        stmt = stmt.where(
            or_(
                LoaiPT.seri_chu == lp_q,
                LoaiPT.ten.ilike(f"%{lp_q}%"),
            )
        )
    if ma_tinh_bien and ma_tinh_bien.strip():
        mt = ma_tinh_bien.strip().zfill(2)
        stmt = stmt.where(Bien.ma_tinh_bien == mt)
    if tinh_ma and tinh_ma.strip():
        tm = tinh_ma.strip().zfill(2)
        stmt = stmt.where(Bien.tinh_ma == tm)
    if xa_ma and xa_ma.strip():
        xm = xa_ma.strip()
        stmt = stmt.where(Bien.xa_ma == xm)
    if trang_thai_lo and trang_thai_lo.strip():
        stmt = stmt.where(Lo.trang_thai == trang_thai_lo.strip())
    if tinh_trang and tinh_trang.strip():
        stmt = stmt.where(Bien.tinh_trang == tinh_trang.strip())
    if giao and giao.strip():
        stmt = stmt.where(Bien.giao == giao.strip())
    if ngoai_tinh is not None:
        stmt = stmt.where(Bien.ngoai_tinh.is_(bool(ngoai_tinh)))

    # Đưa bản ghi đang còn hiệu lực lên trước khi có nhiều bản ghi trùng BienSoDayDu (R-4)
    stmt = (
        stmt.order_by(
            case((Bien.tinh_trang != "Đã hủy", 0), else_=1),
            case((Bien.giu_cho.is_(True), 0), else_=1),
            Bien.id.desc(),
        )
        .limit(min(max(limit, 1), 10000))
        .offset(max(offset, 0))
    )

    rows = db.execute(stmt).all()
    if not rows:
        return []

    tinh_map = {t.ma: t.ten for t in db.scalars(select(Tinh)).all()}
    xa_ids = {b.xa_ma for b, _, _, _ in rows if b.xa_ma}
    xa_map = (
        {
            x.ma: x.ten
            for x in db.scalars(select(XaPhuong).where(XaPhuong.ma.in_(xa_ids))).all()
        }
        if xa_ids
        else {}
    )
    parent_ids_set = {lo.lo_cha_id for _, lo, _, _ in rows if lo.lo_cha_id}
    parent_map = (
        {
            p.id: p.ma_lo
            for p in db.scalars(select(Lo).where(Lo.id.in_(parent_ids_set))).all()
        }
        if parent_ids_set
        else {}
    )

    items: list[dict] = []
    for idx, (bien, lo, loai_pt_obj, nen_bien_obj) in enumerate(rows, start=1):
        don_vi = xa_map.get(bien.xa_ma) if bien.xa_ma else tinh_map.get(bien.tinh_ma, "")
        items.append(
            {
                "id": bien.id,
                "stt": idx,
                "lo_id": lo.id,
                "ma_lo": lo.ma_lo,
                "ma_lo_dat_nha_may": parent_map.get(lo.lo_cha_id) if lo.lo_cha_id else None,
                "loai_lo": lo.loai,
                "trang_thai_lo": lo.trang_thai,
                "tinh_ma": bien.tinh_ma,
                "xa_ma": bien.xa_ma,
                "don_vi": don_vi,
                "bien_so_day_du": bien.bien_so_day_du,
                "ma_tinh_bien": bien.ma_tinh_bien,
                "seri_chu": bien.seri_chu,
                "seri_so": bien.seri_so,
                "dau_so": bien.dau_so,
                "loai_pt_id": bien.loai_pt_id,
                "loai_pt": loai_pt_obj.ten,
                "nen_bien_id": bien.nen_bien_id,
                "nen_bien": nen_bien_obj.ten,
                "mau_sac": nen_bien_obj.mau_sac,
                "tinh_trang": bien.tinh_trang,
                "giao": bien.giao,
                "ngoai_tinh": bien.ngoai_tinh,
                "giu_cho": bien.giu_cho,
                "ghi_chu": bien.ghi_chu,
                "ly_do_huy": bien.ly_do_huy,
                "ly_do_thu_hoi": bien.ly_do_thu_hoi,
            }
        )
    return items


def export_search_bien_xlsx(
    db: Session,
    scope: ScopeFilter,
    **filters,
) -> bytes:
    """Xuất danh sách tra cứu biển số ra file .xlsx theo đúng bộ lọc và phạm vi quyền (FR-081, NFR-016)."""
    filters.setdefault("limit", 10000)
    filters.setdefault("offset", 0)
    items = search_bien(db, scope, **filters)

    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True, "constant_memory": True})
    ws = wb.add_worksheet("TraCuuBienSo")
    headers = [
        "STT",
        "MÃ LÔ",
        "ĐƠN VỊ",
        "LOẠI PHƯƠNG TIỆN",
        "MÀU SẮC",
        "BIỂN SỐ ĐẦY ĐỦ",
        "MÃ LÔ ĐẶT NHÀ MÁY",
        "TRẠNG THÁI LÔ",
        "TÌNH TRẠNG BIỂN",
        "TRẠNG THÁI GIAO",
        "NGOẠI TỈNH",
        "GHI CHÚ",
    ]
    for col, h in enumerate(headers):
        ws.write(0, col, h)
    for row_idx, item in enumerate(items, start=1):
        ws.write(row_idx, 0, row_idx)
        ws.write(row_idx, 1, item["ma_lo"])
        ws.write(row_idx, 2, item["don_vi"] or "")
        ws.write(row_idx, 3, item["loai_pt"])
        ws.write(row_idx, 4, item["mau_sac"])
        ws.write(row_idx, 5, item["bien_so_day_du"])
        ws.write(row_idx, 6, item["ma_lo_dat_nha_may"] or "")
        ws.write(row_idx, 7, item["trang_thai_lo"])
        ws.write(row_idx, 8, item["tinh_trang"])
        ws.write(row_idx, 9, item["giao"] or "")
        ws.write(row_idx, 10, "Có" if item["ngoai_tinh"] else "Không")
        ws.write(row_idx, 11, item["ghi_chu"] or "")
    wb.close()
    buf.seek(0)
    return buf.getvalue()
