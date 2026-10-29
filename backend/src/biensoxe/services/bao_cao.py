from datetime import datetime
import io

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session
import xlsxwriter

from biensoxe.models.bien import Bien
from biensoxe.models.danh_muc import LoaiPT, NenBien, Tinh, XaPhuong
from biensoxe.models.lo import Lo
from biensoxe.repositories.scope import ScopeFilter


def _apply_lo_scope_and_filters(
    stmt,
    scope: ScopeFilter,
    *,
    tinh_ma: str | None = None,
    xa_ma: str | None = None,
    tu_ngay: datetime | None = None,
    den_ngay: datetime | None = None,
):
    stmt = scope.filter_lo(stmt, Lo)
    if scope.is_tinh or scope.is_admin:
        stmt = stmt.where(
            or_(
                Lo.loai != "XA",
                Lo.trang_thai.notin_(("Khởi tạo", "Đã gửi")),
            )
        )
    if tinh_ma and tinh_ma.strip():
        stmt = stmt.where(Lo.tinh_ma == tinh_ma.strip().zfill(2))
    if xa_ma and xa_ma.strip():
        stmt = stmt.where(Lo.xa_ma == xa_ma.strip())
    if tu_ngay is not None:
        stmt = stmt.where(Lo.tao_luc >= tu_ngay)
    if den_ngay is not None:
        stmt = stmt.where(Lo.tao_luc <= den_ngay)
    return stmt


def _apply_bien_scope_and_filters(
    stmt,
    scope: ScopeFilter,
    *,
    tinh_ma: str | None = None,
    xa_ma: str | None = None,
    tu_ngay: datetime | None = None,
    den_ngay: datetime | None = None,
):
    stmt = scope.filter_bien(stmt, Bien)
    if scope.is_tinh or scope.is_admin:
        stmt = stmt.where(
            or_(
                Lo.loai != "XA",
                Lo.trang_thai.notin_(("Khởi tạo", "Đã gửi")),
            )
        )
    if tinh_ma and tinh_ma.strip():
        stmt = stmt.where(Bien.tinh_ma == tinh_ma.strip().zfill(2))
    if xa_ma and xa_ma.strip():
        stmt = stmt.where(Bien.xa_ma == xa_ma.strip())
    if tu_ngay is not None:
        stmt = stmt.where(Lo.tao_luc >= tu_ngay)
    if den_ngay is not None:
        stmt = stmt.where(Lo.tao_luc <= den_ngay)
    return stmt


def get_report_data(
    db: Session,
    scope: ScopeFilter,
    *,
    report_code: str,
    tinh_ma: str | None = None,
    xa_ma: str | None = None,
    tu_ngay: datetime | None = None,
    den_ngay: datetime | None = None,
) -> dict:
    """Tổng hợp báo cáo R1..R5 theo phạm vi quyền (FR-080, AC-45)."""
    code = (report_code or "").strip().upper()
    if code not in ("R1", "R2", "R3", "R4", "R5"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mã báo cáo không hợp lệ (chỉ hỗ trợ R1, R2, R3, R4, R5).",
        )

    tinh_map = {t.ma: t.ten for t in db.scalars(select(Tinh)).all()}
    xa_map = {x.ma: x.ten for x in db.scalars(select(XaPhuong)).all()}

    if code == "R1":
        lo_stmt = select(Lo.loai, Lo.trang_thai, func.count(Lo.id)).group_by(
            Lo.loai, Lo.trang_thai
        )
        lo_stmt = _apply_lo_scope_and_filters(
            lo_stmt,
            scope,
            tinh_ma=tinh_ma,
            xa_ma=xa_ma,
            tu_ngay=tu_ngay,
            den_ngay=den_ngay,
        ).order_by(Lo.loai.asc(), Lo.trang_thai.asc())
        lo_rows = db.execute(lo_stmt).all()

        bien_stmt = (
            select(Bien.tinh_trang, Bien.giao, func.count(Bien.id))
            .join(Lo, Lo.id == Bien.lo_id)
            .group_by(Bien.tinh_trang, Bien.giao)
        )
        bien_stmt = _apply_bien_scope_and_filters(
            bien_stmt,
            scope,
            tinh_ma=tinh_ma,
            xa_ma=xa_ma,
            tu_ngay=tu_ngay,
            den_ngay=den_ngay,
        ).order_by(Bien.tinh_trang.asc(), Bien.giao.asc())
        bien_rows = db.execute(bien_stmt).all()

        lo_theo_trang_thai = [
            {"loai": loai, "trang_thai": tt, "so_lo": int(cnt)}
            for loai, tt, cnt in lo_rows
        ]
        bien_theo_tinh_trang = [
            {"tinh_trang": tt, "giao": giao, "so_bien": int(cnt)}
            for tt, giao, cnt in bien_rows
        ]
        rows = [
            {
                "nhom": "LÔ",
                "phan_loai": item["loai"],
                "trang_thai": item["trang_thai"],
                "so_luong": item["so_lo"],
            }
            for item in lo_theo_trang_thai
        ] + [
            {
                "nhom": "BIỂN SỐ",
                "phan_loai": item["tinh_trang"],
                "trang_thai": item["giao"] or "—",
                "so_luong": item["so_bien"],
            }
            for item in bien_theo_tinh_trang
        ]
        return {
            "report": "R1",
            "title": "Báo cáo R1: Số lô và số biển theo trạng thái",
            "tong_so_lo": sum(x["so_lo"] for x in lo_theo_trang_thai),
            "tong_so_bien": sum(x["so_bien"] for x in bien_theo_tinh_trang),
            "lo_theo_trang_thai": lo_theo_trang_thai,
            "bien_theo_tinh_trang": bien_theo_tinh_trang,
            "rows": rows,
        }

    if code == "R2":
        stmt = (
            select(
                Bien.tinh_ma,
                Bien.xa_ma,
                LoaiPT.ten,
                Bien.seri_chu,
                Bien.tinh_trang,
                func.count(Bien.id),
            )
            .join(Lo, Lo.id == Bien.lo_id)
            .join(LoaiPT, LoaiPT.id == Bien.loai_pt_id)
            .where(Bien.tinh_trang.in_(("Tồn kho tỉnh", "Tồn kho xã")))
            .group_by(
                Bien.tinh_ma,
                Bien.xa_ma,
                LoaiPT.ten,
                Bien.seri_chu,
                Bien.tinh_trang,
            )
        )
        stmt = _apply_bien_scope_and_filters(
            stmt,
            scope,
            tinh_ma=tinh_ma,
            xa_ma=xa_ma,
            tu_ngay=tu_ngay,
            den_ngay=den_ngay,
        ).order_by(Bien.tinh_ma.asc(), Bien.xa_ma.asc(), Bien.seri_chu.asc())
        raw_rows = db.execute(stmt).all()

        rows = []
        ton_tinh = 0
        ton_xa = 0
        for tm, xm, lp_ten, sc, tt, cnt in raw_rows:
            c = int(cnt)
            if tt == "Tồn kho tỉnh":
                ton_tinh += c
            elif tt == "Tồn kho xã":
                ton_xa += c
            don_vi = xa_map.get(xm) if xm else tinh_map.get(tm, "")
            rows.append(
                {
                    "tinh_ma": tm,
                    "xa_ma": xm,
                    "don_vi": don_vi,
                    "loai_pt": lp_ten,
                    "seri_chu": sc,
                    "tinh_trang": tt,
                    "so_bien": c,
                }
            )
        return {
            "report": "R2",
            "title": "Báo cáo R2: Tồn kho theo tỉnh/xã/LoaiPT/SeriChu",
            "tong_ton_kho": ton_tinh + ton_xa,
            "ton_kho_tinh": ton_tinh,
            "ton_kho_xa": ton_xa,
            "rows": rows,
        }

    if code == "R3":
        lo_stmt = select(Lo.trang_thai, func.count(Lo.id)).group_by(Lo.trang_thai)
        lo_stmt = _apply_lo_scope_and_filters(
            lo_stmt,
            scope,
            tinh_ma=tinh_ma,
            xa_ma=xa_ma,
            tu_ngay=tu_ngay,
            den_ngay=den_ngay,
        )
        lo_counts = {tt: int(cnt) for tt, cnt in db.execute(lo_stmt).all()}

        bien_stmt = (
            select(Lo.trang_thai, func.count(Bien.id))
            .join(Lo, Lo.id == Bien.lo_id)
            .where(Bien.tinh_trang != "Đã hủy")
            .group_by(Lo.trang_thai)
        )
        bien_stmt = _apply_bien_scope_and_filters(
            bien_stmt,
            scope,
            tinh_ma=tinh_ma,
            xa_ma=xa_ma,
            tu_ngay=tu_ngay,
            den_ngay=den_ngay,
        )
        bien_by_lo_tt = {tt: int(cnt) for tt, cnt in db.execute(bien_stmt).all()}

        stages = [
            ("Chờ duyệt", ("Chờ phê duyệt",)),
            ("Đã duyệt", ("Chấp nhận",)),
            ("Đã đặt", ("Đặt thành công",)),
            ("Đã nhập kho", ("Đã nhập kho",)),
            ("Đã nhận", ("Đã nhận", "Đã chuyển Xã/phường")),
        ]
        rows = []
        for label, statuses in stages:
            so_lo = sum(lo_counts.get(s, 0) for s in statuses)
            so_bien = sum(bien_by_lo_tt.get(s, 0) for s in statuses)
            rows.append(
                {
                    "giai_doan": label,
                    "trang_thai_lo": ", ".join(statuses),
                    "so_lo": so_lo,
                    "so_bien": so_bien,
                }
            )
        return {
            "report": "R3",
            "title": "Báo cáo R3: Tiến độ đặt biển số",
            "cho_duyet": rows[0]["so_lo"],
            "da_duyet": rows[1]["so_lo"],
            "da_dat": rows[2]["so_lo"],
            "da_nhap_kho": rows[3]["so_lo"],
            "da_nhan": rows[4]["so_lo"],
            "rows": rows,
        }

    if code == "R4":
        stmt = (
            select(Bien.tinh_ma, Bien.xa_ma, Bien.giao, func.count(Bien.id))
            .join(Lo, Lo.id == Bien.lo_id)
            .where(Bien.giao.is_not(None))
            .group_by(Bien.tinh_ma, Bien.xa_ma, Bien.giao)
        )
        stmt = _apply_bien_scope_and_filters(
            stmt,
            scope,
            tinh_ma=tinh_ma,
            xa_ma=xa_ma,
            tu_ngay=tu_ngay,
            den_ngay=den_ngay,
        ).order_by(Bien.tinh_ma.asc(), Bien.xa_ma.asc())
        raw_rows = db.execute(stmt).all()

        grouped: dict[tuple[str, str | None], dict] = {}
        for tm, xm, giao, cnt in raw_rows:
            key = (tm, xm)
            if key not in grouped:
                don_vi = xa_map.get(xm) if xm else tinh_map.get(tm, "")
                grouped[key] = {
                    "tinh_ma": tm,
                    "xa_ma": xm,
                    "don_vi": don_vi,
                    "chua_tra": 0,
                    "da_tra": 0,
                    "thu_hoi_ve_xa": 0,
                    "tong_so": 0,
                }
            c = int(cnt)
            if giao == "Chưa trả":
                grouped[key]["chua_tra"] += c
            elif giao == "Đã trả":
                grouped[key]["da_tra"] += c
            elif giao == "Thu hồi về xã":
                grouped[key]["thu_hoi_ve_xa"] += c
            grouped[key]["tong_so"] += c

        rows = list(grouped.values())
        return {
            "report": "R4",
            "title": "Báo cáo R4: Biển chưa trả/đã trả/thu hồi về xã theo đơn vị",
            "tong_chua_tra": sum(r["chua_tra"] for r in rows),
            "tong_da_tra": sum(r["da_tra"] for r in rows),
            "tong_thu_hoi_ve_xa": sum(r["thu_hoi_ve_xa"] for r in rows),
            "tong_so": sum(r["tong_so"] for r in rows),
            "rows": rows,
        }

    # R5: Biển đã hủy / thu hồi kèm lý do
    stmt = (
        select(Bien, Lo, LoaiPT, NenBien)
        .join(Lo, Lo.id == Bien.lo_id)
        .join(LoaiPT, LoaiPT.id == Bien.loai_pt_id)
        .join(NenBien, NenBien.id == Bien.nen_bien_id)
        .where(
            or_(
                Bien.tinh_trang == "Đã hủy",
                Bien.giao == "Thu hồi về xã",
            )
        )
    )
    stmt = _apply_bien_scope_and_filters(
        stmt,
        scope,
        tinh_ma=tinh_ma,
        xa_ma=xa_ma,
        tu_ngay=tu_ngay,
        den_ngay=den_ngay,
    ).order_by(Bien.id.desc())
    raw_rows = db.execute(stmt).all()

    rows = []
    tong_da_huy = 0
    tong_thu_hoi = 0
    for bien, lo, lp, nb in raw_rows:
        if bien.tinh_trang == "Đã hủy":
            tong_da_huy += 1
            ly_do = bien.ly_do_huy or ""
        else:
            tong_thu_hoi += 1
            ly_do = bien.ly_do_thu_hoi or ""
        don_vi = xa_map.get(bien.xa_ma) if bien.xa_ma else tinh_map.get(bien.tinh_ma, "")
        rows.append(
            {
                "id": bien.id,
                "ma_lo": lo.ma_lo,
                "tinh_ma": bien.tinh_ma,
                "xa_ma": bien.xa_ma,
                "don_vi": don_vi,
                "bien_so_day_du": bien.bien_so_day_du,
                "loai_pt": lp.ten,
                "mau_sac": nb.mau_sac,
                "tinh_trang": bien.tinh_trang,
                "giao": bien.giao,
                "ly_do": ly_do,
            }
        )
    return {
        "report": "R5",
        "title": "Báo cáo R5: Biển đã hủy/thu hồi kèm lý do",
        "tong_da_huy": tong_da_huy,
        "tong_thu_hoi_ve_xa": tong_thu_hoi,
        "tong_so": len(rows),
        "rows": rows,
    }


def export_report_xlsx(
    db: Session,
    scope: ScopeFilter,
    *,
    report_code: str,
    tinh_ma: str | None = None,
    xa_ma: str | None = None,
    tu_ngay: datetime | None = None,
    den_ngay: datetime | None = None,
) -> bytes:
    """Xuất báo cáo R1..R5 ra file .xlsx theo đúng bộ lọc và phạm vi quyền (FR-081, AC-45)."""
    data = get_report_data(
        db,
        scope,
        report_code=report_code,
        tinh_ma=tinh_ma,
        xa_ma=xa_ma,
        tu_ngay=tu_ngay,
        den_ngay=den_ngay,
    )
    code = data["report"]
    rows = data["rows"]

    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True, "constant_memory": True})
    ws = wb.add_worksheet(code)

    if code == "R1":
        headers = ["STT", "NHÓM", "PHÂN LOẠI", "TRẠNG THÁI", "SỐ LƯỢNG"]
        keys = ["nhom", "phan_loai", "trang_thai", "so_luong"]
    elif code == "R2":
        headers = ["STT", "MÃ TỈNH", "MÃ XÃ", "ĐƠN VỊ", "LOẠI PHƯƠNG TIỆN", "SERI CHỮ", "TÌNH TRẠNG", "SỐ BIỂN"]
        keys = ["tinh_ma", "xa_ma", "don_vi", "loai_pt", "seri_chu", "tinh_trang", "so_bien"]
    elif code == "R3":
        headers = ["STT", "GIAI ĐOẠN", "TRẠNG THÁI LÔ", "SỐ LÔ", "SỐ BIỂN"]
        keys = ["giai_doan", "trang_thai_lo", "so_lo", "so_bien"]
    elif code == "R4":
        headers = ["STT", "MÃ TỈNH", "MÃ XÃ", "ĐƠN VỊ", "CHƯA TRẢ", "ĐÃ TRẢ", "THU HỒI VỀ XÃ", "TỔNG SỐ"]
        keys = ["tinh_ma", "xa_ma", "don_vi", "chua_tra", "da_tra", "thu_hoi_ve_xa", "tong_so"]
    else:
        headers = ["STT", "MÃ LÔ", "ĐƠN VỊ", "BIỂN SỐ ĐẦY ĐỦ", "LOẠI PHƯƠNG TIỆN", "MÀU SẮC", "TÌNH TRẠNG", "TRẠNG THÁI GIAO", "LÝ DO"]
        keys = ["ma_lo", "don_vi", "bien_so_day_du", "loai_pt", "mau_sac", "tinh_trang", "giao", "ly_do"]

    for col, h in enumerate(headers):
        ws.write(0, col, h)

    for idx, row in enumerate(rows, start=1):
        ws.write(idx, 0, idx)
        for col_offset, k in enumerate(keys, start=1):
            val = row.get(k)
            ws.write(idx, col_offset, "" if val is None else val)

    wb.close()
    buf.seek(0)
    return buf.getvalue()

