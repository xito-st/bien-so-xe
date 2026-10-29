from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status


@dataclass(frozen=True)
class ScopeFilter:
    """
    Bộ lọc phân quyền phạm vi dữ liệu tập trung (FR-023, FR-004, AC-17).
    - XA: chỉ thấy dữ liệu của xã/phường mình (`xa_ma`).
    - TINH: thấy dữ liệu của tỉnh mình và toàn bộ xã/phường trực thuộc (`tinh_ma`).
    - ADMIN: xem toàn hệ thống (chỉ đọc đối với lô/biển theo FR-023, FR-082).
    Đối tượng ngoài phạm vi trả 404 để không lộ sự tồn tại.
    """

    user_id: int
    ten_dang_nhap: str
    vai_tro: str  # 'ADMIN' | 'TINH' | 'XA'
    tinh_ma: str | None
    xa_ma: str | None

    @property
    def is_admin(self) -> bool:
        return self.vai_tro == "ADMIN"

    @property
    def is_tinh(self) -> bool:
        return self.vai_tro == "TINH"

    @property
    def is_xa(self) -> bool:
        return self.vai_tro == "XA"

    def apply_to_query(self, stmt: Any, model: Any) -> Any:
        """Áp dụng điều kiện lọc phạm vi lên câu truy vấn SQLAlchemy."""
        if self.is_admin:
            return stmt
        if self.is_tinh:
            return stmt.where(model.tinh_ma == self.tinh_ma)
        if self.is_xa:
            return stmt.where(model.tinh_ma == self.tinh_ma, model.xa_ma == self.xa_ma)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Vai trò không hợp lệ.")

    def ensure_in_scope(self, tinh_ma: str | None, xa_ma: str | None = None) -> None:
        """Kiểm tra đối tượng có thuộc phạm vi quyền không; ngoài phạm vi trả 404 (plan §1)."""
        if self.is_admin:
            return
        if self.is_tinh:
            if tinh_ma != self.tinh_ma:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Không tìm thấy dữ liệu trong phạm vi quản lý.",
                )
            return
        if self.is_xa:
            if tinh_ma != self.tinh_ma or xa_ma != self.xa_ma:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Không tìm thấy dữ liệu trong phạm vi quản lý.",
                )
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Không có quyền truy cập.")

    def ensure_not_admin_for_operational_write(self) -> None:
        """Admin chỉ có quyền tra cứu/báo cáo chỉ đọc đối với lô và biển (FR-023, FR-082)."""
        if self.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tài khoản Admin chỉ có quyền tra cứu và xem báo cáo (chế độ chỉ đọc).",
            )

    filter_lo = apply_to_query
    filter_bien = apply_to_query
    ensure_can_access_record = ensure_in_scope
    require_non_admin_for_mutation = ensure_not_admin_for_operational_write
