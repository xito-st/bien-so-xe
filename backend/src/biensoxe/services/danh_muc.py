import re
import unicodedata

from fastapi import HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from biensoxe.db import transaction
from biensoxe.models.bien import Bien
from biensoxe.models.danh_muc import LoaiPT, MaBienTinh, NenBien, Tinh, XaPhuong
from biensoxe.repositories.scope import ScopeFilter
from biensoxe.services.audit import log_audit

_SERI_CHU_RE = re.compile(r"^[A-ZĐ0-9]{1,3}$")
_MA_BIEN_RE = re.compile(r"^\d{2}$")


def list_tinh(db: Session) -> list[Tinh]:
    return list(db.scalars(select(Tinh).order_by(Tinh.stt.asc())).all())


def list_xa_phuong(
    db: Session, scope: ScopeFilter, tinh_ma: str | None = None
) -> list[XaPhuong]:
    stmt = select(XaPhuong)
    if scope.is_xa:
        stmt = stmt.where(XaPhuong.ma == scope.xa_ma)
    elif scope.is_tinh:
        stmt = stmt.where(XaPhuong.tinh_ma == scope.tinh_ma)
    elif tinh_ma:
        stmt = stmt.where(XaPhuong.tinh_ma == tinh_ma)
    stmt = stmt.order_by(XaPhuong.stt.asc())
    return list(db.scalars(stmt).all())


def list_loai_pt(db: Session, include_inactive: bool = False) -> list[LoaiPT]:
    stmt = select(LoaiPT)
    if not include_inactive:
        stmt = stmt.where(LoaiPT.dang_dung.is_(True))
    stmt = stmt.order_by(LoaiPT.stt.asc())
    return list(db.scalars(stmt).all())


def list_nen_bien(db: Session, include_inactive: bool = False) -> list[NenBien]:
    stmt = select(NenBien)
    if not include_inactive:
        stmt = stmt.where(NenBien.dang_dung.is_(True))
    stmt = stmt.order_by(NenBien.stt.asc())
    return list(db.scalars(stmt).all())


def list_ma_bien_tinh(
    db: Session, tinh_ma: str | None = None, include_inactive: bool = False
) -> list[MaBienTinh]:
    stmt = select(MaBienTinh)
    if tinh_ma:
        stmt = stmt.where(MaBienTinh.tinh_ma == tinh_ma)
    if not include_inactive:
        stmt = stmt.where(MaBienTinh.dang_dung.is_(True))
    stmt = stmt.order_by(MaBienTinh.tinh_ma.asc(), MaBienTinh.ma_bien.asc())
    return list(db.scalars(stmt).all())


def create_loai_pt(
    db: Session,
    scope: ScopeFilter,
    *,
    seri_chu: str,
    ten: str,
    ip: str | None = None,
) -> LoaiPT:
    if not scope.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ Admin được quản lý danh mục.")
    sc = unicodedata.normalize("NFC", (seri_chu or "").strip()).upper()
    ten_clean = unicodedata.normalize("NFC", (ten or "").strip()).upper()
    if not _SERI_CHU_RE.match(sc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SeriChu phải gồm 1–3 ký tự (A–Z, Đ, chữ số) và không chứa dấu '-' (FR-031).",
        )
    if not ten_clean:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tên loại phương tiện không được trống.")

    with transaction(db):
        if db.scalar(select(LoaiPT).where(LoaiPT.seri_chu == sc)) is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"SeriChu '{sc}' đã tồn tại trong danh mục (FR-037).",
            )
        max_stt = db.scalar(select(func.max(LoaiPT.stt))) or 0
        item = LoaiPT(stt=max_stt + 1, seri_chu=sc, ten=ten_clean, dang_dung=True)
        db.add(item)
        db.flush()
        log_audit(
            db,
            nguoi_dung=scope.ten_dang_nhap,
            hanh_dong="THEM_LOAI_PT",
            doi_tuong=sc,
            ket_qua="THANH_CONG",
            ip=ip,
            chi_tiet={"id": item.id, "seri_chu": sc, "ten": ten_clean},
        )
        return item


def update_loai_pt(
    db: Session,
    scope: ScopeFilter,
    *,
    loai_pt_id: int,
    ten: str | None = None,
    dang_dung: bool | None = None,
    ip: str | None = None,
) -> LoaiPT:
    """Sửa hoặc ngừng sử dụng LoaiPT; chặn đổi tên nếu đã được biển tham chiếu (FR-037, AC-25)."""
    if not scope.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ Admin được quản lý danh mục.")
    with transaction(db):
        item = db.scalar(select(LoaiPT).where(LoaiPT.id == loai_pt_id).with_for_update())
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy mục LoaiPT.")

        if ten is not None:
            ten_clean = unicodedata.normalize("NFC", ten.strip()).upper()
            if not ten_clean:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tên LoaiPT không hợp lệ.")
            if ten_clean != item.ten:
                ref_count = (
                    db.scalar(
                        select(func.count()).select_from(Bien).where(Bien.loai_pt_id == item.id)
                    )
                    or 0
                )
                if ref_count > 0:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Mục LoaiPT đã được biển tham chiếu, không được đổi LoaiPT mà chỉ được ngừng sử dụng (FR-037).",
                    )
                item.ten = ten_clean

        if dang_dung is not None:
            item.dang_dung = bool(dang_dung)

        log_audit(
            db,
            nguoi_dung=scope.ten_dang_nhap,
            hanh_dong="CAP_NHAT_LOAI_PT",
            doi_tuong=item.seri_chu,
            ket_qua="THANH_CONG",
            ip=ip,
            chi_tiet={"id": item.id, "ten": item.ten, "dang_dung": item.dang_dung},
        )
        return item


def delete_loai_pt(
    db: Session, scope: ScopeFilter, *, loai_pt_id: int, ip: str | None = None
) -> None:
    if not scope.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ Admin được quản lý danh mục.")
    with transaction(db):
        item = db.scalar(select(LoaiPT).where(LoaiPT.id == loai_pt_id).with_for_update())
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy mục LoaiPT.")
        ref_count = (
            db.scalar(select(func.count()).select_from(Bien).where(Bien.loai_pt_id == item.id))
            or 0
        )
        if ref_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Mục LoaiPT đã được biển tham chiếu, không được xóa mà chỉ được ngừng sử dụng (FR-037).",
            )
        seri = item.seri_chu
        db.execute(delete(LoaiPT).where(LoaiPT.id == item.id))
        log_audit(
            db,
            nguoi_dung=scope.ten_dang_nhap,
            hanh_dong="XOA_LOAI_PT",
            doi_tuong=seri,
            ket_qua="THANH_CONG",
            ip=ip,
        )


def create_nen_bien(
    db: Session,
    scope: ScopeFilter,
    *,
    ten: str,
    mau_sac: str,
    ip: str | None = None,
) -> NenBien:
    if not scope.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ Admin được quản lý danh mục.")
    ten_clean = unicodedata.normalize("NFC", (ten or "").strip())
    mau_clean = unicodedata.normalize("NFC", (mau_sac or "").strip()).upper()
    if not ten_clean or not mau_clean:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Thiếu tên nền biển hoặc màu sắc.")
    with transaction(db):
        if db.scalar(select(NenBien).where(NenBien.ten == ten_clean)) is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tên nền biển đã tồn tại.")
        max_stt = db.scalar(select(func.max(NenBien.stt))) or 0
        item = NenBien(stt=max_stt + 1, ten=ten_clean, mau_sac=mau_clean, dang_dung=True)
        db.add(item)
        db.flush()
        log_audit(
            db,
            nguoi_dung=scope.ten_dang_nhap,
            hanh_dong="THEM_NEN_BIEN",
            doi_tuong=ten_clean,
            ket_qua="THANH_CONG",
            ip=ip,
            chi_tiet={"id": item.id, "mau_sac": mau_clean},
        )
        return item


def update_nen_bien(
    db: Session,
    scope: ScopeFilter,
    *,
    nen_bien_id: int,
    ten: str | None = None,
    mau_sac: str | None = None,
    dang_dung: bool | None = None,
    ip: str | None = None,
) -> NenBien:
    if not scope.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ Admin được quản lý danh mục.")
    with transaction(db):
        item = db.scalar(select(NenBien).where(NenBien.id == nen_bien_id).with_for_update())
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nền biển.")
        ref_count = (
            db.scalar(select(func.count()).select_from(Bien).where(Bien.nen_bien_id == item.id))
            or 0
        )
        if mau_sac is not None:
            mau_clean = unicodedata.normalize("NFC", mau_sac.strip()).upper()
            if mau_clean != item.mau_sac and ref_count > 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Nền biển đã được tham chiếu, không được đổi MauSac (FR-037).",
                )
            item.mau_sac = mau_clean
        if ten is not None:
            ten_clean = unicodedata.normalize("NFC", ten.strip())
            if ten_clean != item.ten and ref_count > 0:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Nền biển đã được tham chiếu, không được đổi tên (FR-037).",
                )
            item.ten = ten_clean
        if dang_dung is not None:
            item.dang_dung = bool(dang_dung)
        log_audit(
            db,
            nguoi_dung=scope.ten_dang_nhap,
            hanh_dong="CAP_NHAT_NEN_BIEN",
            doi_tuong=item.ten,
            ket_qua="THANH_CONG",
            ip=ip,
            chi_tiet={"id": item.id, "mau_sac": item.mau_sac, "dang_dung": item.dang_dung},
        )
        return item


def delete_nen_bien(
    db: Session, scope: ScopeFilter, *, nen_bien_id: int, ip: str | None = None
) -> None:
    if not scope.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ Admin được quản lý danh mục.")
    with transaction(db):
        item = db.scalar(select(NenBien).where(NenBien.id == nen_bien_id).with_for_update())
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy nền biển.")
        ref_count = (
            db.scalar(select(func.count()).select_from(Bien).where(Bien.nen_bien_id == item.id))
            or 0
        )
        if ref_count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Nền biển đã được biển tham chiếu, không được xóa mà chỉ được ngừng sử dụng (FR-037).",
            )
        ten = item.ten
        db.execute(delete(NenBien).where(NenBien.id == item.id))
        log_audit(
            db,
            nguoi_dung=scope.ten_dang_nhap,
            hanh_dong="XOA_NEN_BIEN",
            doi_tuong=ten,
            ket_qua="THANH_CONG",
            ip=ip,
        )


def create_ma_bien_tinh(
    db: Session,
    scope: ScopeFilter,
    *,
    ma_bien: str,
    tinh_ma: str,
    ip: str | None = None,
) -> MaBienTinh:
    """Admin khai báo mã biển D1D2 -> tỉnh/thành (FR-038, AC-53)."""
    if not scope.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ Admin được quản lý danh mục.")
    mb = (ma_bien or "").strip()
    tm = (tinh_ma or "").strip().zfill(2)
    if not _MA_BIEN_RE.match(mb):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mã biển phải gồm đúng 2 chữ số.")
    with transaction(db):
        if db.scalar(select(Tinh).where(Tinh.ma == tm)) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy tỉnh/thành.")
        existing = db.scalar(
            select(MaBienTinh).where(MaBienTinh.ma_bien == mb, MaBienTinh.tinh_ma == tm)
        )
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Mã biển đã được khai báo cho tỉnh này.")
        item = MaBienTinh(ma_bien=mb, tinh_ma=tm, dang_dung=True)
        db.add(item)
        db.flush()
        log_audit(
            db,
            nguoi_dung=scope.ten_dang_nhap,
            hanh_dong="THEM_MA_BIEN_TINH",
            doi_tuong=f"{mb}->{tm}",
            ket_qua="THANH_CONG",
            ip=ip,
        )
        return item


def update_ma_bien_tinh(
    db: Session,
    scope: ScopeFilter,
    *,
    item_id: int,
    ma_bien: str | None = None,
    dang_dung: bool | None = None,
    ip: str | None = None,
) -> MaBienTinh:
    if not scope.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Chỉ Admin được quản lý danh mục.")
    with transaction(db):
        item = db.scalar(select(MaBienTinh).where(MaBienTinh.id == item_id).with_for_update())
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Không tìm thấy khai báo mã biển.")
        if ma_bien is not None:
            mb = ma_bien.strip()
            if not _MA_BIEN_RE.match(mb):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mã biển phải gồm 2 chữ số.")
            item.ma_bien = mb
        if dang_dung is not None:
            item.dang_dung = bool(dang_dung)
        log_audit(
            db,
            nguoi_dung=scope.ten_dang_nhap,
            hanh_dong="CAP_NHAT_MA_BIEN_TINH",
            doi_tuong=f"{item.ma_bien}->{item.tinh_ma}",
            ket_qua="THANH_CONG",
            ip=ip,
            chi_tiet={"dang_dung": item.dang_dung},
        )
        return item

