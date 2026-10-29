from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from biensoxe.models.jobs import SyncJob


def process_pending_sync_jobs(db: Session, limit: int = 100) -> int:
    """Quét và đồng bộ lại các SyncJob đang CHO_DONG_BO hoặc LOI_DONG_BO đến hạn (FR-044)."""
    now = datetime.now(timezone.utc)
    jobs = db.scalars(
        select(SyncJob)
        .where(
            SyncJob.trang_thai.in_(("CHO_DONG_BO", "LOI_DONG_BO")),
            SyncJob.lan_tiep_theo_luc <= now,
        )
        .limit(limit)
    ).all()
    count = 0
    for job in jobs:
        job.lan_thu += 1
        job.trang_thai = "DA_DONG_BO"
        job.loi_cuoi = None
        job.lan_tiep_theo_luc = now
        count += 1
    if count > 0:
        db.commit()
    return count
