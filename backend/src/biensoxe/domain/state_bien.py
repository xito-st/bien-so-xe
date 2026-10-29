from enum import StrEnum


class StateTransitionError(ValueError):
    """Lỗi chuyển trạng thái không hợp lệ ngoài sơ đồ (FR-046, FR-065, FR-071, AC-31)."""


class TinhTrangBien(StrEnum):
    """Trục 1: Tình trạng vòng đời/kho của biển (4.I)."""

    CHUA_DAT = "Chưa đặt"
    DA_DAT = "Đã đặt"
    TON_KHO_TINH = "Tồn kho tỉnh"
    TON_KHO_XA = "Tồn kho xã"
    DA_HUY = "Đã hủy"


class TrangThaiGiao(StrEnum):
    """Trục 2: Trạng thái giao cho người dân (4.I, FR-053, FR-054)."""

    CHUA_TRA = "Chưa trả"
    DA_TRA = "Đã trả"
    THU_HOI_VE_XA = "Thu hồi về xã"


ALLOWED_TINH_TRANG_TRANSITIONS: frozenset[tuple[TinhTrangBien, TinhTrangBien]] = frozenset(
    {
        (TinhTrangBien.CHUA_DAT, TinhTrangBien.DA_DAT),
        (TinhTrangBien.DA_DAT, TinhTrangBien.TON_KHO_TINH),
        (TinhTrangBien.TON_KHO_TINH, TinhTrangBien.TON_KHO_XA),
        (TinhTrangBien.DA_DAT, TinhTrangBien.DA_HUY),
        (TinhTrangBien.TON_KHO_TINH, TinhTrangBien.DA_HUY),
        (TinhTrangBien.TON_KHO_XA, TinhTrangBien.DA_HUY),
    }
)

ALLOWED_GIAO_TRANSITIONS: frozenset[tuple[TrangThaiGiao, TrangThaiGiao]] = frozenset(
    {
        (TrangThaiGiao.CHUA_TRA, TrangThaiGiao.DA_TRA),
        (TrangThaiGiao.DA_TRA, TrangThaiGiao.THU_HOI_VE_XA),
    }
)


def validate_bien_tinh_trang_transition(
    current: TinhTrangBien | str, target: TinhTrangBien | str
) -> None:
    cur = TinhTrangBien(current)
    tgt = TinhTrangBien(target)
    if (cur, tgt) not in ALLOWED_TINH_TRANG_TRANSITIONS:
        raise StateTransitionError(
            f"Không được phép chuyển tình trạng biển từ '{cur.value}' sang '{tgt.value}'."
        )


def validate_bien_giao_transition(
    current: TrangThaiGiao | str, target: TrangThaiGiao | str
) -> None:
    cur = TrangThaiGiao(current)
    tgt = TrangThaiGiao(target)
    if (cur, tgt) not in ALLOWED_GIAO_TRANSITIONS:
        raise StateTransitionError(
            f"Không được phép chuyển trạng thái giao từ '{cur.value}' sang '{tgt.value}'."
        )
