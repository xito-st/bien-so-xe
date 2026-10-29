from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from biensoxe.models.jobs import SyncJob
from biensoxe.models.lo import Lo, LoLichSu
from biensoxe.repositories.scope import ScopeFilter
from biensoxe.services.audit import write_audit_log


def create_or_run_sync_job(
    db: Session,
    lo: Lo,
    *,
    nguoi: str,
    simulate_error: bool = False,
) -> SyncJob:
    """
    Tạo hoặc cập nhật trạng thái đồng bộ của lô xã lên tỉnh (FR-044, AC-29).
    Khi đồng bộ thành công, lô chuyển từ 'Đã gửi' sang 'Chờ phê duyệt'.
    Khi lỗi đồng bộ, lô giữ nguyên ở 'Đã gửi'.
    """
    now = datetime.now(timezone.utc)
    job = db.scalar(select(SyncJob).where(SyncJob.lo_id == lo.id))
    if job is None:
        job = SyncJob(
            lo_id=lo.id,
            trang_thai="LOI_DONG_BO" if simulate_error else "DA_DONG_BO",
            lan_thu=1,
            lan_tiep_theo_luc=now + timedelta(seconds=30) if simulate_error else now,
            loi_cuoi="Lỗi kết nối đồng bộ tạm thời" if simulate_error else None,
            tao_luc=now,
        )
        db.add(job)
    else:
        job.lan_thu += 1
        if simulate_error:
            job.trang_thai = "LOI_DONG_BO"
            job.lan_tiep_theo_luc = now + timedelta(seconds=30 * (2 ** min(job.lan_thu, 5)))
            job.loi_cuoi = "Lỗi kết nối đồng bộ tạm thời"
        else:
            job.trang_thai = "DA_DONG_BO"
            job.lan_tiep_theo_luc = now
            job.loi_cuoi = None

    if not simulate_error and lo.trang_thai == "Đã gửi":
        lo.trang_thai = "Chờ phê duyệt"
        db.add(
            LoLichSu(
                lo_id=lo.id,
                tu="Đã gửi",
                den="Chờ phê duyệt",
                nguoi=nguoi,
                luc=now,
                ly_do="Đồng bộ lên tỉnh/thành thành công",
            )
        )
    db.flush()
    return job


def get_sync_status(db: Session, lo_id: int) -> str:
    job = db.scalar(select(SyncJob).where(SyncJob.lo_id == lo_id))
    if job is None:
        return "CHUA_GUI"
    return job.trang_thai


def retry_sync_lo(
    db: Session,
    scope: ScopeFilter,
    *,
    lo_id: int,
    ip: str | None = None,
) -> SyncJob:
    """Thử đồng bộ lại lô xã theo cơ chế idempotent, không tạo bản ghi trùng (FR-044, AC-29)."""
    scope.require_non_admin_for_mutation()
    lo = db.get(Lo, lo_id)
    if lo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy lô.")
    scope.ensure_can_access_record(tinh_ma=lo.tinh_ma, xa_ma=lo.xa_ma)

    job = create_or_run_sync_job(db, lo, nguoi=scope.ten_dang_nhap, simulate_error=False)
    write_audit_log(
        db,
        nguoi_dung=scope.ten_dang_nhap,
        hanh_dong="DONG_BO_LAI_LO",
        doi_tuong=lo.ma_lo,
        ket_qua="THANH_CONG",
        ip=ip,
        chi_tiet={"lo_id": lo.id, "lan_thu": job.lan_thu, "trang_thai": lo.trang_thai},
    )
    db.commit()
    return job
