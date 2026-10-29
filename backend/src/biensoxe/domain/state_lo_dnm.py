from enum import StrEnum

from biensoxe.domain.state_bien import StateTransitionError


class TrangThaiLoDNM(StrEnum):
    """Vòng đời lô đặt nhà máy theo sơ đồ 4.J.2 (FR-065, FR-069)."""

    KHOI_TAO = "Khởi tạo"
    CHO_PHE_DUYET = "Chờ phê duyệt"
    CHAP_NHAN = "Chấp nhận"
    DAT_THANH_CONG = "Đặt thành công"
    DA_NHAP_KHO = "Đã nhập kho"
    DA_CHUYEN_XA = "Đã chuyển Xã/phường"
    HUY = "Hủy"


ALLOWED_LO_DNM_TRANSITIONS: frozenset[tuple[TrangThaiLoDNM, TrangThaiLoDNM]] = frozenset(
    {
        (TrangThaiLoDNM.KHOI_TAO, TrangThaiLoDNM.CHO_PHE_DUYET),
        (TrangThaiLoDNM.CHO_PHE_DUYET, TrangThaiLoDNM.KHOI_TAO),
        (TrangThaiLoDNM.CHO_PHE_DUYET, TrangThaiLoDNM.CHAP_NHAN),
        (TrangThaiLoDNM.CHAP_NHAN, TrangThaiLoDNM.KHOI_TAO),
        (TrangThaiLoDNM.CHAP_NHAN, TrangThaiLoDNM.DAT_THANH_CONG),
        (TrangThaiLoDNM.DAT_THANH_CONG, TrangThaiLoDNM.DA_NHAP_KHO),
        (TrangThaiLoDNM.DA_NHAP_KHO, TrangThaiLoDNM.DA_CHUYEN_XA),
        (TrangThaiLoDNM.KHOI_TAO, TrangThaiLoDNM.HUY),
        (TrangThaiLoDNM.CHO_PHE_DUYET, TrangThaiLoDNM.HUY),
        (TrangThaiLoDNM.CHAP_NHAN, TrangThaiLoDNM.HUY),
    }
)


def validate_lo_dnm_transition(
    current: TrangThaiLoDNM | str, target: TrangThaiLoDNM | str
) -> None:
    cur = TrangThaiLoDNM(current)
    tgt = TrangThaiLoDNM(target)
    if (cur, tgt) not in ALLOWED_LO_DNM_TRANSITIONS:
        raise StateTransitionError(
            f"Không được phép chuyển trạng thái lô đặt nhà máy từ '{cur.value}' sang '{tgt.value}' (FR-065)."
        )
