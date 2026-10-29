from datetime import datetime, timedelta, timezone
import io
import uuid
import zipfile

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse
import openpyxl
from sqlalchemy import func, select
from sqlalchemy.orm import Session
import xlsxwriter

from biensoxe.domain.bien_so import BienSoValidationError, normalize_raw_bien_so
from biensoxe.models.bien import Bien, BienLichSu
from biensoxe.models.jobs import ImportJob
from biensoxe.models.lo import Lo
from biensoxe.repositories.scope import ScopeFilter
from biensoxe.services.audit import write_audit_log
from biensoxe.services.bien import (
    check_plate_duplicates,
    ensure_lo_editable_for_plates,
    resolve_plate_metadata,
)

MAX_XLSX_BYTES = 5 * 1024 * 1024
MAX_IMPORT_ROWS = 5000


def _validate_and_read_xlsx_rows(file_bytes: bytes, filename: str) -> list[tuple[int, str, str]]:
    """
    Kiểm tra an toàn tệp .xlsx (kích thước <= 5MB, từ chối macro vbaProject.bin,
    đọc bằng openpyxl read_only=True, data_only=True, tối đa 5.000 dòng) (FR-042, NFR-009).
    Trả về danh sách (excel_row_number, raw_plate, note).
    """
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Chỉ chấp nhận tệp định dạng .xlsx.",
        )
    if len(file_bytes) > MAX_XLSX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dung lượng tệp vượt quá giới hạn tối đa 5MB.",
        )
    try:
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as zf:
            names = set(zf.namelist())
            if any(name.endswith("vbaProject.bin") for name in names):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Từ chối tệp Excel có chứa macro (vbaProject.bin).",
                )
            if "xl/workbook.xml" not in names:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Tệp .xlsx không đúng cấu trúc chuẩn.",
                )
    except zipfile.BadZipFile as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tệp tải lên không phải là tệp .xlsx hợp lệ.",
        ) from exc

    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
    try:
        ws = wb.active
        if ws is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tệp Excel không có trang tính nào.",
            )
        rows_out: list[tuple[int, str, str]] = []
        for idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
            if idx == 1:
                continue  # Bỏ qua dòng tiêu đề
            if not row or all(cell is None or str(cell).strip() == "" for cell in row):
                continue
            raw_plate = str(row[0]).strip() if len(row) > 0 and row[0] is not None else ""
            note = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""
            rows_out.append((idx, raw_plate, note))
            if len(rows_out) > MAX_IMPORT_ROWS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Số dòng dữ liệu vượt quá giới hạn tối đa {MAX_IMPORT_ROWS} dòng/lần.",
                )
    finally:
        wb.close()

    if not rows_out:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tệp Excel không có dữ liệu biển số nào.",
        )
    return rows_out


def generate_lo_bien_template_xlsx() -> bytes:
    """Sinh tệp mẫu .xlsx nhập danh sách biển số (FR-042)."""
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True, "constant_memory": True})
    ws = wb.add_worksheet("MauNhapBienSo")
    header_fmt = wb.add_format({"bold": True, "bg_color": "#D9E1F2", "border": 1})
    ws.write(0, 0, "BIỂN SỐ ĐẦY ĐỦ", header_fmt)
    ws.write(0, 1, "GHI CHÚ", header_fmt)
    ws.set_column(0, 0, 24)
    ws.set_column(1, 1, 36)
    wb.close()
    buf.seek(0)
    return buf.getvalue()


def import_plates_to_lo_xlsx(
    db: Session,
    scope: ScopeFilter,
    *,
    lo_id: int,
    file_bytes: bytes,
    filename: str,
    dat_lai_xac_nhan_all: bool = False,
    ip: str | None = None,
) -> dict | JSONResponse:
    """
    Nhập hàng loạt biển số từ tệp .xlsx theo nguyên tắc tất cả hoặc không (FR-042, AC-27).
    """
    lo = db.get(Lo, lo_id)
    if lo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô.")
    scope.ensure_can_access_record(tinh_ma=lo.tinh_ma, xa_ma=lo.xa_ma)
    ensure_lo_editable_for_plates(lo, scope)

    raw_rows = _validate_and_read_xlsx_rows(file_bytes, filename)
    errors: list[dict] = []
    reorder_warnings: list[dict] = []
    prepared_items: list[dict] = []
    seen_in_file: dict[str, int] = {}

    for excel_row, raw_plate, note in raw_rows:
        if not raw_plate:
            errors.append(
                {
                    "dong": excel_row,
                    "bien_so": "",
                    "ly_do": "Cột BIỂN SỐ ĐẦY ĐỦ bị để trống.",
                }
            )
            continue

        try:
            meta = resolve_plate_metadata(db, raw_plate, lo.tinh_ma)
        except BienSoValidationError as exc:
            errors.append(
                {
                    "dong": excel_row,
                    "bien_so": raw_plate,
                    "ly_do": str(exc),
                }
            )
            continue

        parsed = meta["parsed"]
        full_plate = parsed.bien_so_day_du

        if full_plate in seen_in_file:
            first_row = seen_in_file[full_plate]
            errors.append(
                {
                    "dong": excel_row,
                    "bien_so": full_plate,
                    "ly_do": f"Trùng biển số '{full_plate}' ngay trong tệp import (trùng với dòng {first_row}).",
                }
            )
            continue
        seen_in_file[full_plate] = excel_row

        dup = check_plate_duplicates(
            db,
            lo_id=lo.id,
            tinh_ma=lo.tinh_ma,
            bien_so_day_du=full_plate,
        )
        if dup["blocked"]:
            errors.append(
                {
                    "dong": excel_row,
                    "bien_so": full_plate,
                    "ly_do": dup["reason"],
                }
            )
            continue

        if dup["requires_reorder_confirm"]:
            reorder_warnings.append(
                {
                    "dong": excel_row,
                    "bien_so": full_plate,
                    "thong_tin_dat_lai": dup["reorder_info"],
                }
            )

        prepared_items.append(
            {
                "dong": excel_row,
                "parsed": parsed,
                "loai_pt_id": meta["loai_pt"].id,
                "nen_bien_id": meta["nen_bien"].id,
                "ngoai_tinh": meta["ngoai_tinh"],
                "ghi_chu": note or None,
                "requires_reorder": dup["requires_reorder_confirm"],
            }
        )

    now = datetime.now(timezone.utc)
    job_id = uuid.uuid4().hex

    if errors:
        job = ImportJob(
            id=job_id,
            tai_khoan_id=scope.user_id,
            lo_id=lo.id,
            loai_import="TAO_BIEN",
            trang_thai="LOI",
            loi=errors,
            dong_hop_le=None,
            trung_da_tra=reorder_warnings or None,
            het_han_luc=now + timedelta(hours=2),
        )
        db.add(job)
        write_audit_log(
            db,
            nguoi_dung=scope.ten_dang_nhap,
            hanh_dong="IMPORT_BIEN_XLSX",
            doi_tuong=lo.ma_lo,
            ket_qua="THAT_BAI",
            ip=ip,
            chi_tiet={"so_dong_loi": len(errors), "import_job_id": job_id},
        )
        db.commit()
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "detail": f"Phát hiện {len(errors)} dòng lỗi. Không có biển số nào được lưu (nguyên tắc tất cả hoặc không).",
                "errors": errors,
                "import_job_id": job_id,
            },
        )

    if reorder_warnings and not dat_lai_xac_nhan_all:
        job = ImportJob(
            id=job_id,
            tai_khoan_id=scope.user_id,
            lo_id=lo.id,
            loai_import="TAO_BIEN",
            trang_thai="CHO_XAC_NHAN",
            loi=None,
            dong_hop_le=[
                {
                    "bien_so": item["parsed"].bien_so_day_du,
                    "ghi_chu": item["ghi_chu"],
                }
                for item in prepared_items
            ],
            trung_da_tra=reorder_warnings,
            het_han_luc=now + timedelta(hours=2),
        )
        db.add(job)
        db.commit()
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "detail": "Tệp có chứa biển số đã trả hoặc thu hồi về xã, cần xác nhận đặt lại.",
                "yeu_cau_xac_nhan_dat_lai": True,
                "trung_da_tra": reorder_warnings,
                "import_job_id": job_id,
            },
        )

    max_stt = (
        db.scalar(select(func.coalesce(func.max(Bien.stt), 0)).where(Bien.lo_id == lo.id)) or 0
    )
    should_reserve = lo.trang_thai == "Cho phép điều chỉnh"

    for offset, item in enumerate(prepared_items, start=1):
        parsed = item["parsed"]
        b = Bien(
            lo_id=lo.id,
            stt=max_stt + offset,
            bien_so_day_du=parsed.bien_so_day_du,
            ma_tinh_bien=parsed.ma_tinh,
            seri_chu=parsed.seri_chu,
            seri_so=parsed.seri_so,
            dau_so=parsed.dau_so,
            loai_pt_id=item["loai_pt_id"],
            nen_bien_id=item["nen_bien_id"],
            ghi_chu=item["ghi_chu"],
            tinh_ma=lo.tinh_ma,
            xa_ma=lo.xa_ma,
            tinh_trang="Chưa đặt",
            giao=None,
            dat_lai_xac_nhan=bool(item["requires_reorder"]),
            ngoai_tinh=item["ngoai_tinh"],
            loi_ly_do=None,
            giu_cho=should_reserve,
        )
        db.add(b)
        db.flush()
        db.add(
            BienLichSu(
                bien_id=b.id,
                su_kien="IMPORT_BIEN",
                tu=None,
                den="Chưa đặt",
                ly_do=None,
                nguoi=scope.ten_dang_nhap,
                luc=now,
            )
        )

    job = ImportJob(
        id=job_id,
        tai_khoan_id=scope.user_id,
        lo_id=lo.id,
        loai_import="TAO_BIEN",
        trang_thai="THANH_CONG",
        loi=None,
        dong_hop_le=None,
        trung_da_tra=None,
        het_han_luc=now + timedelta(hours=2),
    )
    db.add(job)
    write_audit_log(
        db,
        nguoi_dung=scope.ten_dang_nhap,
        hanh_dong="IMPORT_BIEN_XLSX",
        doi_tuong=lo.ma_lo,
        ket_qua="THANH_CONG",
        ip=ip,
        chi_tiet={"so_luong_them": len(prepared_items), "import_job_id": job_id},
    )
    db.commit()
    return {
        "so_luong_them": len(prepared_items),
        "import_job_id": job_id,
    }


def import_factory_return_xlsx(
    db: Session,
    scope: ScopeFilter,
    *,
    lo_id: int,
    file_bytes: bytes,
    filename: str,
    ip: str | None = None,
) -> dict | JSONResponse:
    """
    Nhập kho tỉnh bằng tệp .xlsx danh sách biển nhà máy trả về theo nguyên tắc tất cả hoặc không (FR-072, AC-54).
    """
    scope.require_non_admin_for_mutation()
    lo = db.get(Lo, lo_id)
    if lo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô.")
    if not (scope.is_tinh and scope.tinh_ma == lo.tinh_ma):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ tài khoản tỉnh sở hữu lô mới được nhập kho.",
        )
    if lo.loai != "DAT_NHA_MAY" or lo.trang_thai != "Đặt thành công":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Chỉ được nhập kho đối với lô đặt nhà máy đang ở trạng thái 'Đặt thành công'.",
        )

    raw_rows = _validate_and_read_xlsx_rows(file_bytes, filename)
    child_ids = list(
        db.scalars(select(Lo.id).where(Lo.lo_cha_id == lo.id)).all()
    )
    plates_in_dnm = {
        b.bien_so_day_du: b
        for b in db.scalars(select(Bien).where(Bien.lo_id.in_(child_ids))).all()
    }

    errors: list[dict] = []
    matched_plates: list[Bien] = []
    seen_in_file: dict[str, int] = {}

    for excel_row, raw_plate, _note in raw_rows:
        norm = normalize_raw_bien_so(raw_plate)
        if not norm:
            errors.append(
                {
                    "dong": excel_row,
                    "bien_so": "",
                    "ly_do": "Cột BIỂN SỐ ĐẦY ĐỦ bị để trống.",
                }
            )
            continue
        try:
            meta = resolve_plate_metadata(db, raw_plate, lo.tinh_ma)
            norm = meta["parsed"].bien_so_day_du
        except BienSoValidationError:
            pass
        if norm in seen_in_file:
            errors.append(
                {
                    "dong": excel_row,
                    "bien_so": norm,
                    "ly_do": f"Biển số '{norm}' bị trùng lặp trong tệp import (dòng {seen_in_file[norm]}).",
                }
            )
            continue
        seen_in_file[norm] = excel_row

        target_bien = plates_in_dnm.get(norm)
        if target_bien is None:
            errors.append(
                {
                    "dong": excel_row,
                    "bien_so": norm,
                    "ly_do": f"Biển số '{norm}' không thuộc lô đặt nhà máy '{lo.ma_lo}'.",
                }
            )
            continue
        if target_bien.tinh_trang != "Đã đặt":
            errors.append(
                {
                    "dong": excel_row,
                    "bien_so": norm,
                    "ly_do": f"Biển số '{norm}' đang ở tình trạng '{target_bien.tinh_trang}' (chỉ nhập kho biển đang 'Đã đặt').",
                }
            )
            continue
        matched_plates.append(target_bien)

    now = datetime.now(timezone.utc)
    job_id = uuid.uuid4().hex

    if errors:
        job = ImportJob(
            id=job_id,
            tai_khoan_id=scope.user_id,
            lo_id=lo.id,
            loai_import="NHAP_KHO",
            trang_thai="LOI",
            loi=errors,
            dong_hop_le=None,
            trung_da_tra=None,
            het_han_luc=now + timedelta(hours=2),
        )
        db.add(job)
        write_audit_log(
            db,
            nguoi_dung=scope.ten_dang_nhap,
            hanh_dong="IMPORT_NHAP_KHO_XLSX",
            doi_tuong=lo.ma_lo,
            ket_qua="THAT_BAI",
            ip=ip,
            chi_tiet={"so_dong_loi": len(errors), "import_job_id": job_id},
        )
        db.commit()
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "detail": f"Phát hiện {len(errors)} dòng lỗi. Không có biển số nào được nhập kho (nguyên tắc tất cả hoặc không).",
                "errors": errors,
                "import_job_id": job_id,
            },
        )

    for b in matched_plates:
        old_st = b.tinh_trang
        b.tinh_trang = "Tồn kho tỉnh"
        b.ngay_nhap_kho = now
        if b.xa_ma is None:
            # Biển của lô tỉnh khi nhập kho tỉnh sẵn sàng giao trực tiếp (G-6)
            b.giao = "Chưa trả"
        db.add(
            BienLichSu(
                bien_id=b.id,
                su_kien="NHAP_KHO_TINH_IMPORT",
                tu=old_st,
                den="Tồn kho tỉnh",
                ly_do=None,
                nguoi=scope.ten_dang_nhap,
                luc=now,
            )
        )

    db.flush()
    from biensoxe.services.kho import sync_dnm_and_children_completion_states

    sync_dnm_and_children_completion_states(db, lo, nguoi=scope.ten_dang_nhap, now=now)

    job = ImportJob(
        id=job_id,
        tai_khoan_id=scope.user_id,
        lo_id=lo.id,
        loai_import="NHAP_KHO",
        trang_thai="THANH_CONG",
        loi=None,
        dong_hop_le=None,
        trung_da_tra=None,
        het_han_luc=now + timedelta(hours=2),
    )
    db.add(job)
    write_audit_log(
        db,
        nguoi_dung=scope.ten_dang_nhap,
        hanh_dong="IMPORT_NHAP_KHO_XLSX",
        doi_tuong=lo.ma_lo,
        ket_qua="THANH_CONG",
        ip=ip,
        chi_tiet={
            "so_luong_nhap_kho": len(matched_plates),
            "import_job_id": job_id,
            "trang_thai_lo": lo.trang_thai,
        },
    )
    db.commit()
    return {
        "so_luong_nhap_kho": len(matched_plates),
        "import_job_id": job_id,
        "trang_thai_lo": lo.trang_thai,
    }


def export_import_job_error_xlsx(db: Session, scope: ScopeFilter, *, job_id: str) -> bytes:
    """Xuất tệp .xlsx báo cáo các dòng lỗi của một phiên import (FR-042, FR-072, AC-27, AC-54)."""
    job = db.get(ImportJob, job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy phiên import hoặc phiên đã hết hạn.",
        )
    lo = db.get(Lo, job.lo_id)
    if lo is not None:
        scope.ensure_can_access_record(tinh_ma=lo.tinh_ma, xa_ma=lo.xa_ma)

    errors = job.loi or []
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True, "constant_memory": True})
    ws = wb.add_worksheet("BaoCaoLoiImport")
    header_fmt = wb.add_format({"bold": True, "bg_color": "#F8CBAD", "border": 1})
    ws.write(0, 0, "DÒNG", header_fmt)
    ws.write(0, 1, "BIỂN SỐ", header_fmt)
    ws.write(0, 2, "LÝ DO LỖI", header_fmt)
    ws.set_column(0, 0, 10)
    ws.set_column(1, 1, 24)
    ws.set_column(2, 2, 60)

    for row_idx, err in enumerate(errors, start=1):
        ws.write(row_idx, 0, err.get("dong", ""))
        ws.write(row_idx, 1, err.get("bien_so", ""))
        ws.write(row_idx, 2, err.get("ly_do", ""))

    wb.close()
    buf.seek(0)
    return buf.getvalue()
