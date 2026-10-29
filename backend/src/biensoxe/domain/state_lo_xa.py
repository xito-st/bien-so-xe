from enum import StrEnum

from biensoxe.domain.state_bien import StateTransitionError


class TrangThaiLoXa(StrEnum):
    """8 trạng thái vòng đời lô xã theo sơ đồ 4.J.1 (FR-046)."""

    KHOI_TAO = "Khởi tạo"
    DA_GUI = "Đã gửi"
    CHO_PHE_DUYET = "Chờ phê duyệt"
    CHAP_NHAN = "Chấp nhận"
    TU_CHOI = "Từ chối"
    CHO_PHEP_DIEU_CHINH = "Cho phép điều chỉnh"
    DAT_THANH_CONG = "Đặt thành công"
    DA_NHAN = "Đã nhận"


ALLOWED_LO_XA_TRANSITIONS: frozenset[tuple[TrangThaiLoXa, TrangThaiLoXa]] = frozenset(
    {
        (TrangThaiLoXa.KHOI_TAO, TrangThaiLoXa.DA_GUI),
        (TrangThaiLoXa.DA_GUI, TrangThaiLoXa.DA_GUI),
        (TrangThaiLoXa.DA_GUI, TrangThaiLoXa.CHO_PHE_DUYET),
        (TrangThaiLoXa.CHO_PHE_DUYET, TrangThaiLoXa.CHAP_NHAN),
        (TrangThaiLoXa.CHO_PHE_DUYET, TrangThaiLoXa.TU_CHOI),
        (TrangThaiLoXa.TU_CHOI, TrangThaiLoXa.DA_GUI),
        (TrangThaiLoXa.CHAP_NHAN, TrangThaiLoXa.CHO_PHEP_DIEU_CHINH),
        (TrangThaiLoXa.CHO_PHEP_DIEU_CHINH, TrangThaiLoXa.DA_GUI),
        (TrangThaiLoXa.CHO_PHEP_DIEU_CHINH, TrangThaiLoXa.CHO_PHE_DUYET),
        (TrangThaiLoXa.CHAP_NHAN, TrangThaiLoXa.DAT_THANH_CONG),
        (TrangThaiLoXa.DAT_THANH_CONG, TrangThaiLoXa.DA_NHAN),
    }
)

EDITABLE_LO_XA_STATES: frozenset[TrangThaiLoXa] = frozenset(
    {
        TrangThaiLoXa.KHOI_TAO,
        TrangThaiLoXa.TU_CHOI,
        TrangThaiLoXa.CHO_PHEP_DIEU_CHINH,
    }
)


def validate_lo_xa_transition(current: TrangThaiLoXa | str, target: TrangThaiLoXa | str) -> None:
    cur = TrangThaiLoXa(current)
    tgt = TrangThaiLoXa(target)
    if (cur, tgt) not in ALLOWED_LO_XA_TRANSITIONS:
        raise StateTransitionError(
            f"Không được phép chuyển trạng thái lô xã từ '{cur.value}' sang '{tgt.value}' (FR-046)."
        )

