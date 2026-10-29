from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from biensoxe.config import get_settings
from biensoxe.models.tai_khoan import YeuCauCapLaiMK


def is_forgot_password_rate_limited(
    db: Session,
    ten_dang_nhap: str,
    ip: str | None,
    now: datetime | None = None,
) -> bool:
    """Giới hạn tần suất gửi yêu cầu quên mật khẩu theo tên đăng nhập và IP (FR-018, AC-12)."""
    current = now or datetime.now(timezone.utc)
    window_start = current - timedelta(hours=1)
    limit = get_settings().forgot_password_rate_limit_per_hour

    count_by_user = db.scalar(
        select(func.count())
        .select_from(YeuCauCapLaiMK)
        .where(
            YeuCauCapLaiMK.ten_dang_nhap == ten_dang_nhap,
            YeuCauCapLaiMK.tao_luc >= window_start,
        )
    )
    if (count_by_user or 0) >= limit:
        return True

    if ip:
        count_by_ip = db.scalar(
            select(func.count())
            .select_from(YeuCauCapLaiMK)
            .where(
                YeuCauCapLaiMK.ip == ip,
                YeuCauCapLaiMK.tao_luc >= window_start,
            )
        )
        if (count_by_ip or 0) >= limit * 2:
            return True

    return False
