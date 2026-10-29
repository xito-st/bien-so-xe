from datetime import datetime
import io
import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
import xlsxwriter

from biensoxe.api.deps import get_current_scope
from biensoxe.db import get_db
from biensoxe.models.audit import AuditLog
from biensoxe.repositories.scope import ScopeFilter

router = APIRouter(prefix="/api/v1/admin/audit-log", tags=["audit-log"])


def _query_audit_logs(
    db: Session,
    *,
    nguoi_dung: str | None = None,
    hanh_dong: str | None = None,
    doi_tuong: str | None = None,
    tu_ngay: datetime | None = None,
    den_ngay: datetime | None = None,
    limit: int = 200,
    offset: int = 0,
) -> list[AuditLog]:
    stmt = select(AuditLog)
    if nguoi_dung:
        stmt = stmt.where(AuditLog.nguoi_dung == nguoi_dung.strip())
    if hanh_dong:
        stmt = stmt.where(AuditLog.hanh_dong == hanh_dong.strip())
    if doi_tuong:
        stmt = stmt.where(AuditLog.doi_tuong.ilike(f"%{doi_tuong.strip()}%"))
    if tu_ngay:
        stmt = stmt.where(AuditLog.thoi_diem >= tu_ngay)
    if den_ngay:
        stmt = stmt.where(AuditLog.thoi_diem <= den_ngay)
    stmt = stmt.order_by(AuditLog.thoi_diem.desc(), AuditLog.id.desc()).limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


@router.get("")
def get_audit_logs(
    nguoi_dung: str | None = None,
    hanh_dong: str | None = None,
    doi_tuong: str | None = None,
    tu_ngay: datetime | None = None,
    den_ngay: datetime | None = None,
    limit: int = 200,
    offset: int = 0,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    if not scope.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ Admin được xem nhật ký thao tác (FR-021).",
        )
    logs = _query_audit_logs(
        db,
        nguoi_dung=nguoi_dung,
        hanh_dong=hanh_dong,
        doi_tuong=doi_tuong,
        tu_ngay=tu_ngay,
        den_ngay=den_ngay,
        limit=min(limit, 1000),
        offset=max(0, offset),
    )
    return {
        "items": [
            {
                "id": lg.id,
                "thoi_diem": lg.thoi_diem.isoformat(),
                "nguoi_dung": lg.nguoi_dung,
                "hanh_dong": lg.hanh_dong,
                "doi_tuong": lg.doi_tuong,
                "ket_qua": lg.ket_qua,
                "ip": lg.ip,
                "chi_tiet": lg.chi_tiet,
            }
            for lg in logs
        ]
    }


@router.get("/xuat")
def export_audit_logs_xlsx(
    nguoi_dung: str | None = None,
    hanh_dong: str | None = None,
    doi_tuong: str | None = None,
    tu_ngay: datetime | None = None,
    den_ngay: datetime | None = None,
    scope: ScopeFilter = Depends(get_current_scope),
    db: Session = Depends(get_db),
):
    if not scope.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ Admin được xuất nhật ký thao tác (FR-021).",
        )
    logs = _query_audit_logs(
        db,
        nguoi_dung=nguoi_dung,
        hanh_dong=hanh_dong,
        doi_tuong=doi_tuong,
        tu_ngay=tu_ngay,
        den_ngay=den_ngay,
        limit=10000,
        offset=0,
    )
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True, "constant_memory": True})
    ws = wb.add_worksheet("AuditLog")
    headers = ["ID", "THỜI ĐIỂM", "NGƯỜI THỰC HIỆN", "HÀNH ĐỘNG", "ĐỐI TƯỢNG", "KẾT QUẢ", "IP", "CHI TIẾT"]
    for col, h in enumerate(headers):
        ws.write(0, col, h)
    for row_idx, lg in enumerate(logs, start=1):
        ws.write(row_idx, 0, lg.id)
        ws.write(row_idx, 1, lg.thoi_diem.isoformat())
        ws.write(row_idx, 2, lg.nguoi_dung)
        ws.write(row_idx, 3, lg.hanh_dong)
        ws.write(row_idx, 4, lg.doi_tuong)
        ws.write(row_idx, 5, lg.ket_qua)
        ws.write(row_idx, 6, lg.ip or "")
        ws.write(row_idx, 7, json.dumps(lg.chi_tiet, ensure_ascii=False) if lg.chi_tiet else "")
    wb.close()
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="audit-log.xlsx"'},
    )
