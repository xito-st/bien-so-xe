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


def _friendly_lo_type(loai: str) -> str:
    if loai == "DAT_NHA_MAY":
        return "Lô Đặt nhà máy"
    if loai == "TINH":
        return "Lô Tỉnh"
    if loai == "XA":
        return "Lô Xã/Phường"
    return loai


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
        # Tiến độ chuẩn của lô theo quy trình vòng đời:
        # Khởi tạo -> Đã gửi -> Chờ phê duyệt -> Chấp nhận -> Đặt thành công -> Đã nhập kho -> Đã chuyển Xã/phường -> Đã nhận -> Từ chối / Hủy
        LO_PROGRESS_ORDER = {
            "Khởi tạo": 1,
            "Đã gửi": 2,
            "Chờ phê duyệt": 3,
            "Chấp nhận": 4,
            "Đặt thành công": 5,
            "Đã nhập kho": 6,
            "Đã chuyển Xã/phường": 7,
            "Đã nhận": 8,
            "Từ chối": 9,
            "Hủy": 10,
        }

        # Tiến độ chuẩn của biển số theo trạng thái kho & cấp phát:
        BIEN_PROGRESS_ORDER = {
            "Tồn kho tỉnh": 1,
            "Tồn kho xã": 2,
            "Chưa trả": 3,
            "Đã trả": 4,
            "Thu hồi về xã": 5,
            "Đã hủy": 6,
        }

        lo_stmt = (
            select(
                Lo.tinh_ma,
                Lo.xa_ma,
                Lo.loai,
                Lo.trang_thai,
                func.count(Lo.id),
            )
            .group_by(Lo.tinh_ma, Lo.xa_ma, Lo.loai, Lo.trang_thai)
        )
        lo_stmt = _apply_lo_scope_and_filters(
            lo_stmt,
            scope,
            tinh_ma=tinh_ma,
            xa_ma=xa_ma,
            tu_ngay=tu_ngay,
            den_ngay=den_ngay,
        )
        lo_raw_rows = db.execute(lo_stmt).all()

        bien_stmt = (
            select(
                Bien.tinh_ma,
                Bien.xa_ma,
                Bien.tinh_trang,
                Bien.giao,
                func.count(Bien.id),
            )
            .join(Lo, Lo.id == Bien.lo_id)
            .group_by(Bien.tinh_ma, Bien.xa_ma, Bien.tinh_trang, Bien.giao)
        )
        bien_stmt = _apply_bien_scope_and_filters(
            bien_stmt,
            scope,
            tinh_ma=tinh_ma,
            xa_ma=xa_ma,
            tu_ngay=tu_ngay,
            den_ngay=den_ngay,
        )
        bien_raw_rows = db.execute(bien_stmt).all()

        bang_lo = []
        for tm, xm, loai, tt, cnt in lo_raw_rows:
            don_vi = (
                xa_map.get(xm, f"Xã/Phường {xm}")
                if xm
                else (f"{tinh_map.get(tm, tm)} (Cấp tỉnh)" if tm else "Cơ quan Quản lý")
            )
            bang_lo.append(
                {
                    "tinh_ma": tm,
                    "xa_ma": xm,
                    "don_vi": don_vi,
                    "loai": loai,
                    "loai_hien_thi": _friendly_lo_type(loai),
                    "trang_thai": tt,
                    "so_luong": int(cnt),
                    "thu_tu_tien_do": LO_PROGRESS_ORDER.get(tt, 99),
                }
            )
        # Sắp xếp theo đơn vị rồi theo thứ tự tiến độ chuẩn của lô
        bang_lo.sort(key=lambda x: (x["don_vi"], x["thu_tu_tien_do"], x["loai"]))

        bang_bien = []
        for tm, xm, tt, giao, cnt in bien_raw_rows:
            don_vi = (
                xa_map.get(xm, f"Xã/Phường {xm}")
                if xm
                else (f"{tinh_map.get(tm, tm)} (Cấp tỉnh)" if tm else "Cơ quan Quản lý")
            )
            giao_str = giao if giao else "Chưa bàn giao"
            bien_order = BIEN_PROGRESS_ORDER.get(giao, BIEN_PROGRESS_ORDER.get(tt, 99))
            bang_bien.append(
                {
                    "tinh_ma": tm,
                    "xa_ma": xm,
                    "don_vi": don_vi,
                    "tinh_trang": tt,
                    "giao": giao_str,
                    "so_luong": int(cnt),
                    "thu_tu_tien_do": bien_order,
                }
            )
        # Sắp xếp theo đơn vị rồi theo thứ tự tiến độ chuẩn của biển số
        bang_bien.sort(key=lambda x: (x["don_vi"], x["thu_tu_tien_do"], x["tinh_trang"]))

        # Giữ lo_theo_trang_thai & bien_theo_tinh_trang để tương thích thẻ KPI
        lo_theo_trang_thai = [
            {"loai": item["loai"], "trang_thai": item["trang_thai"], "so_lo": item["so_luong"]}
            for item in bang_lo
        ]
        bien_theo_tinh_trang = [
            {"tinh_trang": item["tinh_trang"], "giao": item["giao"], "so_bien": item["so_luong"]}
            for item in bang_bien
        ]

        rows = [
            {
                "don_vi": item["don_vi"],
                "nhom": "LÔ",
                "phan_loai": item["loai_hien_thi"],
                "phan_loai_ma": item["loai"],
                "trang_thai": item["trang_thai"],
                "so_luong": item["so_luong"],
            }
            for item in bang_lo
        ] + [
            {
                "don_vi": item["don_vi"],
                "nhom": "BIỂN SỐ",
                "phan_loai": item["tinh_trang"],
                "phan_loai_ma": item["tinh_trang"],
                "trang_thai": item["giao"],
                "so_luong": item["so_luong"],
            }
            for item in bang_bien
        ]
        return {
            "report": "R1",
            "title": "Báo cáo R1: Tiến độ Lô và Tình trạng Biển số theo Đơn vị",
            "tong_so_lo": sum(x["so_luong"] for x in bang_lo),
            "tong_so_bien": sum(x["so_luong"] for x in bang_bien),
            "lo_theo_trang_thai": lo_theo_trang_thai,
            "bien_theo_tinh_trang": bien_theo_tinh_trang,
            "bang_lo": bang_lo,
            "bang_bien": bang_bien,
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
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    ws = wb.add_worksheet(code)

    header_fmt = wb.add_format({
        "bold": True,
        "bg_color": "#1B365D",
        "font_color": "#FFFFFF",
        "border": 1,
        "align": "center",
        "valign": "vcenter",
    })
    cell_fmt = wb.add_format({"border": 1, "valign": "vcenter"})
    cell_center = wb.add_format({"border": 1, "align": "center", "valign": "vcenter"})
    cell_num = wb.add_format({"border": 1, "num_format": "#,##0", "align": "right", "valign": "vcenter"})

    if code == "R1":
        headers = ["STT", "ĐƠN VỊ", "NHÓM", "PHÂN LOẠI", "TRẠNG THÁI TIẾN ĐỘ", "SỐ LƯỢNG"]
        keys = ["don_vi", "nhom", "phan_loai", "trang_thai", "so_luong"]
        col_widths = [8, 30, 14, 24, 26, 16]
        alignments = ["center", "left", "center", "left", "left", "right"]
    elif code == "R2":
        headers = ["STT", "MÃ TỈNH", "MÃ XÃ", "ĐƠN VỊ", "LOẠI PHƯƠNG TIỆN", "SERI CHỮ", "TÌNH TRẠNG", "SỐ BIỂN"]
        keys = ["tinh_ma", "xa_ma", "don_vi", "loai_pt", "seri_chu", "tinh_trang", "so_bien"]
        col_widths = [8, 12, 14, 28, 20, 12, 18, 16]
        alignments = ["center", "center", "center", "left", "left", "center", "left", "right"]
    elif code == "R3":
        headers = ["STT", "GIAI ĐOẠN", "TRẠNG THÁI LÔ", "SỐ LÔ", "SỐ BIỂN"]
        keys = ["giai_doan", "trang_thai_lo", "so_lo", "so_bien"]
        col_widths = [8, 20, 36, 16, 16]
        alignments = ["center", "left", "left", "right", "right"]
    elif code == "R4":
        headers = ["STT", "MÃ TỈNH", "MÃ XÃ", "ĐƠN VỊ", "CHƯA TRẢ", "ĐÃ TRẢ", "THU HỒI VỀ XÃ", "TỔNG SỐ"]
        keys = ["tinh_ma", "xa_ma", "don_vi", "chua_tra", "da_tra", "thu_hoi_ve_xa", "tong_so"]
        col_widths = [8, 12, 14, 28, 16, 16, 16, 16]
        alignments = ["center", "center", "center", "left", "right", "right", "right", "right"]
    else:
        headers = ["STT", "MÃ LÔ", "ĐƠN VỊ", "BIỂN SỐ ĐẦY ĐỦ", "LOẠI PHƯƠNG TIỆN", "MÀU SẮC", "TÌNH TRẠNG", "TRẠNG THÁI GIAO", "LÝ DO"]
        keys = ["ma_lo", "don_vi", "bien_so_day_du", "loai_pt", "mau_sac", "tinh_trang", "giao", "ly_do"]
        col_widths = [8, 24, 28, 18, 18, 12, 16, 18, 36]
        alignments = ["center", "left", "left", "center", "left", "center", "left", "left", "left"]

    # Đặt chiều cao dòng tiêu đề & độ rộng các cột
    ws.set_row(0, 26)
    for col_idx, width in enumerate(col_widths):
        ws.set_column(col_idx, col_idx, width)

    for col, h in enumerate(headers):
        ws.write(0, col, h, header_fmt)

    for idx, row in enumerate(rows, start=1):
        ws.set_row(idx, 20)
        ws.write(idx, 0, idx, cell_center)
        for col_offset, k in enumerate(keys, start=1):
            val = row.get(k)
            align = alignments[col_offset] if col_offset < len(alignments) else "left"
            if align == "right" and isinstance(val, (int, float)):
                ws.write_number(idx, col_offset, val, cell_num)
            elif align == "center":
                ws.write(idx, col_offset, "" if val is None else str(val), cell_center)
            else:
                ws.write(idx, col_offset, "" if val is None else str(val), cell_fmt)

    wb.close()
    buf.seek(0)
    return buf.getvalue()


def get_report_drilldown_plates(
    db: Session,
    scope: ScopeFilter,
    *,
    tinh_ma: str | None = None,
    xa_ma: str | None = None,
    is_cap_tinh: bool = False,
    loai_lo: str | None = None,
    trang_thai_lo: str | None = None,
    tinh_trang: str | None = None,
    giao: str | None = None,
    loai_pt: str | None = None,
    seri_chu: str | None = None,
    tu_ngay: datetime | None = None,
    den_ngay: datetime | None = None,
    q: str | None = None,
    limit: int = 500,
) -> list[dict]:
    """Truy vấn danh sách biển số chi tiết phục vụ tương tác trực tiếp (drill-down) trên bảng thống kê."""
    tinh_map = {t.ma: t.ten for t in db.scalars(select(Tinh)).all()}
    xa_map = {x.ma: x.ten for x in db.scalars(select(XaPhuong)).all()}

    stmt = (
        select(Bien, Lo, LoaiPT, NenBien)
        .join(Lo, Lo.id == Bien.lo_id)
        .join(LoaiPT, LoaiPT.id == Bien.loai_pt_id)
        .join(NenBien, NenBien.id == Bien.nen_bien_id)
    )
    stmt = _apply_bien_scope_and_filters(
        stmt,
        scope,
        tu_ngay=tu_ngay,
        den_ngay=den_ngay,
    )

    if q and q.strip():
        q_up = q.strip().upper()
        stmt = stmt.where(
            or_(
                Bien.bien_so_day_du.ilike(f"%{q_up}%"),
                Lo.ma_lo.ilike(f"%{q_up}%"),
                Bien.seri_chu.ilike(f"{q_up}%"),
                LoaiPT.ten.ilike(f"%{q_up}%"),
            )
        )

    if xa_ma and xa_ma.strip():
        stmt = stmt.where(Bien.xa_ma == xa_ma.strip())
    elif is_cap_tinh and tinh_ma and tinh_ma.strip():
        # Cấp tỉnh (không thuộc xã nào)
        stmt = stmt.where(Bien.tinh_ma == tinh_ma.strip().zfill(2), Bien.xa_ma.is_(None))
    elif tinh_ma and tinh_ma.strip():
        stmt = stmt.where(Bien.tinh_ma == tinh_ma.strip().zfill(2))

    if loai_lo and loai_lo.strip():
        ll = loai_lo.strip().upper()
        if ll == "DAT_NHA_MAY":
            dnm_sub = select(Lo.id).where(Lo.loai == "DAT_NHA_MAY")
            if trang_thai_lo and trang_thai_lo.strip():
                dnm_sub = dnm_sub.where(Lo.trang_thai == trang_thai_lo.strip())
            stmt = stmt.where(or_(Lo.loai == "DAT_NHA_MAY", Lo.lo_cha_id.in_(dnm_sub)))
        elif ll in ("XA", "TINH"):
            stmt = stmt.where(Lo.loai == ll)
            if trang_thai_lo and trang_thai_lo.strip():
                stmt = stmt.where(Lo.trang_thai == trang_thai_lo.strip())
    elif trang_thai_lo and trang_thai_lo.strip():
        stmt = stmt.where(Lo.trang_thai == trang_thai_lo.strip())

    if tinh_trang and tinh_trang.strip():
        stmt = stmt.where(Bien.tinh_trang == tinh_trang.strip())

    if giao and giao.strip():
        g = giao.strip()
        if g in ("Chưa giao", "Chưa trả", "Chưa bàn giao", "Chưa giao / Lưu kho"):
            stmt = stmt.where(or_(Bien.giao == "Chưa trả", Bien.giao == g, Bien.giao.is_(None)))
        else:
            stmt = stmt.where(Bien.giao == g)

    if loai_pt and loai_pt.strip():
        stmt = stmt.where(LoaiPT.ten.ilike(f"%{loai_pt.strip()}%"))

    if seri_chu and seri_chu.strip():
        stmt = stmt.where(Bien.seri_chu == seri_chu.strip().upper())

    stmt = stmt.order_by(Bien.stt.asc(), Bien.id.asc()).limit(limit)
    rows = db.execute(stmt).all()

    # Thu thập parent_ids để tìm mã lô ĐNM
    parent_ids = {lo.lo_cha_id for bien, lo, lp, nb in rows if lo.lo_cha_id}
    parent_map = {}
    if parent_ids:
        parent_los = db.scalars(select(Lo).where(Lo.id.in_(parent_ids))).all()
        parent_map = {p.id: p.ma_lo for p in parent_los}

    results = []
    for bien, lo, lp, nb in rows:
        don_vi = (
            xa_map.get(bien.xa_ma)
            if bien.xa_ma
            else f"{tinh_map.get(bien.tinh_ma, bien.tinh_ma)} (Cấp tỉnh)"
        )
        ma_lo_dnm = (
            parent_map.get(lo.lo_cha_id)
            if lo.lo_cha_id
            else (lo.ma_lo if lo.loai == "DAT_NHA_MAY" else None)
        )
        results.append(
            {
                "id": bien.id,
                "ma_lo": lo.ma_lo,
                "ma_lo_dnm": ma_lo_dnm,
                "loai_lo": lo.loai,
                "loai_lo_hien_thi": _friendly_lo_type(lo.loai),
                "trang_thai_lo": lo.trang_thai,
                "tinh_ma": bien.tinh_ma,
                "xa_ma": bien.xa_ma,
                "don_vi": don_vi,
                "bien_so_day_du": bien.bien_so_day_du,
                "seri_chu": bien.seri_chu,
                "dau_so": bien.dau_so,
                "loai_pt": lp.ten,
                "mau_sac": nb.mau_sac,
                "tinh_trang": bien.tinh_trang,
                "giao": bien.giao or "Chưa trả",
                "tao_luc": (
                    lo.tao_luc.strftime("%d/%m/%Y %H:%M")
                    if hasattr(lo, "tao_luc") and lo.tao_luc
                    else "—"
                ),
            }
        )
    return results


def export_drilldown_plates_xlsx(
    db: Session,
    scope: ScopeFilter,
    *,
    tinh_ma: str | None = None,
    xa_ma: str | None = None,
    is_cap_tinh: bool = False,
    loai_lo: str | None = None,
    trang_thai_lo: str | None = None,
    tinh_trang: str | None = None,
    giao: str | None = None,
    loai_pt: str | None = None,
    seri_chu: str | None = None,
    tu_ngay: datetime | None = None,
    den_ngay: datetime | None = None,
    q: str | None = None,
    limit: int = 5000,
) -> bytes:
    """Xuất danh sách biển số chi tiết (drill-down) ra file .xlsx chuyên nghiệp."""
    plates = get_report_drilldown_plates(
        db,
        scope,
        tinh_ma=tinh_ma,
        xa_ma=xa_ma,
        is_cap_tinh=is_cap_tinh,
        loai_lo=loai_lo,
        trang_thai_lo=trang_thai_lo,
        tinh_trang=tinh_trang,
        giao=giao,
        loai_pt=loai_pt,
        seri_chu=seri_chu,
        tu_ngay=tu_ngay,
        den_ngay=den_ngay,
        q=q,
        limit=limit,
    )

    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    ws = wb.add_worksheet("ChiTietBienSo")

    header_fmt = wb.add_format({
        "bold": True,
        "bg_color": "#1B365D",
        "font_color": "#FFFFFF",
        "border": 1,
        "align": "center",
        "valign": "vcenter",
    })
    cell_fmt = wb.add_format({"border": 1, "valign": "vcenter"})
    cell_center = wb.add_format({"border": 1, "align": "center", "valign": "vcenter"})
    cell_bold_center = wb.add_format({"border": 1, "bold": True, "align": "center", "valign": "vcenter"})

    headers = [
        "STT",
        "MÃ LÔ",
        "MÃ LÔ ĐNM",
        "ĐƠN VỊ",
        "BIỂN SỐ ĐẦY ĐỦ",
        "LOẠI PHƯƠNG TIỆN",
        "MÀU SẮC",
        "TÌNH TRẠNG KHO",
        "TRẠNG THÁI GIAO",
        "NGÀY TẠO",
    ]
    keys = [
        "ma_lo",
        "ma_lo_dnm",
        "don_vi",
        "bien_so_day_du",
        "loai_pt",
        "mau_sac",
        "tinh_trang",
        "giao",
        "tao_luc",
    ]
    col_widths = [8, 22, 22, 28, 18, 26, 14, 18, 18, 20]
    alignments = ["center", "center", "center", "left", "center", "left", "center", "center", "center", "center"]

    ws.set_row(0, 26)
    for col_idx, width in enumerate(col_widths):
        ws.set_column(col_idx, col_idx, width)

    for col, h in enumerate(headers):
        ws.write(0, col, h, header_fmt)

    for idx, p in enumerate(plates, start=1):
        ws.set_row(idx, 20)
        ws.write(idx, 0, idx, cell_center)
        for col_offset, k in enumerate(keys, start=1):
            val = p.get(k)
            val_str = "" if val is None else str(val)
            align = alignments[col_offset]
            if k == "bien_so_day_du":
                ws.write(idx, col_offset, val_str, cell_bold_center)
            elif align == "center":
                ws.write(idx, col_offset, val_str, cell_center)
            else:
                ws.write(idx, col_offset, val_str, cell_fmt)

    wb.close()
    buf.seek(0)
    return buf.getvalue()

