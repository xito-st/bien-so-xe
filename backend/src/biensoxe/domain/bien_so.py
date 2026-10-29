from collections.abc import Mapping, Set
from dataclasses import dataclass
import re
import unicodedata


class BienSoValidationError(ValueError):
    """Lỗi cấu trúc hoặc danh mục biển số không hợp lệ (FR-030..035)."""


@dataclass(frozen=True)
class ParsedBienSo:
    ma_tinh: str
    seri_chu: str
    seri_so: str
    dau_so: str
    bien_so_day_du: str
    loai_pt: str
    nen_bien: str
    mau_sac: str
    ngoai_tinh: bool = False
    canh_bao_ngoai_tinh: str | None = None


_BIEN_SO_RE = re.compile(r"^(\d{2})([A-ZĐ0-9]{1,3})-(\d{1,3})\.(\d{1,2})$")


def normalize_raw_bien_so(raw: str) -> str:
    if not isinstance(raw, str):
        raise BienSoValidationError("Biển số phải là chuỗi văn bản.")
    text = unicodedata.normalize("NFC", raw).strip().upper()
    return text


def parse_and_validate_bien_so(
    raw_bien_so: str,
    nen_bien: str,
    active_loai_pt: Mapping[str, str],
    active_nen_bien: Mapping[str, str],
    allowed_ma_bien_tinh: Set[str] | None = None,
) -> ParsedBienSo:
    """
    Phân tích, chuẩn hóa và kiểm tra hợp lệ biển số theo FR-030..035, FR-038 (AC-18..22, AC-53).
    """
    cleaned = normalize_raw_bien_so(raw_bien_so)
    if not cleaned:
        raise BienSoValidationError("Biển số không được để trống.")

    match = _BIEN_SO_RE.match(cleaned)
    if not match:
        raise BienSoValidationError(
            f"Biển số '{raw_bien_so}' không đúng cấu trúc D1D2<SeriChu>-DDD.DD (FR-030, FR-035)."
        )

    ma_tinh, seri_chu, phan_nguyen, phan_thap_phan = match.groups()

    if seri_chu not in active_loai_pt:
        raise BienSoValidationError(
            f"SeriChu '{seri_chu}' không tồn tại hoặc đã ngừng sử dụng trong danh mục LoaiPT (FR-031)."
        )
    loai_pt = active_loai_pt[seri_chu]

    nen_bien_clean = unicodedata.normalize("NFC", nen_bien or "").strip()
    if not nen_bien_clean:
        raise BienSoValidationError("Bắt buộc phải chọn nền biển (FR-034).")
    if nen_bien_clean not in active_nen_bien:
        raise BienSoValidationError(
            f"Nền biển '{nen_bien_clean}' không hợp lệ hoặc đã ngừng sử dụng (FR-034)."
        )
    mau_sac = active_nen_bien[nen_bien_clean]

    # Chuẩn hóa SeriSo (FR-035): đệm 0 bên trái phần nguyên (<3 chữ số) và đệm 0 bên phải phần thập phân (1 chữ số)
    dau_so = phan_nguyen.zfill(3)
    duoi_so = phan_thap_phan.ljust(2, "0")
    seri_so = f"{dau_so}.{duoi_so}"
    bien_so_day_du = f"{ma_tinh}{seri_chu}-{seri_so}"

    ngoai_tinh = False
    canh_bao_ngoai_tinh: str | None = None
    if allowed_ma_bien_tinh and ma_tinh not in allowed_ma_bien_tinh:
        ngoai_tinh = True
        canh_bao_ngoai_tinh = (
            f"Mã biển '{ma_tinh}' không thuộc danh mục mã biển của tỉnh đang quản lý (FR-038)."
        )

    return ParsedBienSo(
        ma_tinh=ma_tinh,
        seri_chu=seri_chu,
        seri_so=seri_so,
        dau_so=dau_so,
        bien_so_day_du=bien_so_day_du,
        loai_pt=loai_pt,
        nen_bien=nen_bien_clean,
        mau_sac=mau_sac,
        ngoai_tinh=ngoai_tinh,
        canh_bao_ngoai_tinh=canh_bao_ngoai_tinh,
    )

