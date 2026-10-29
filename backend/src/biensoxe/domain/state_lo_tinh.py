from enum import StrEnum

from biensoxe.domain.state_bien import StateTransitionError


class TrangThaiLoTinh(StrEnum):
    """Vòng đời lô tỉnh theo sơ đồ 4.J.3 (FR-062, FR-071)."""

    KHOI_TAO = "Khởi tạo"
    CHO_PHE_DUYET = "Chờ phê duyệt"
    CHAP_NHAN = "Chấp nhận"
    TU_CHOI = "Từ chối"
    CHO_PHEP_DIEU_CHINH = "Cho phép điều chỉnh"
    DAT_THANH_CONG = "Đặt thành công"
    DA_NHAP_KHO = "Đã nhập kho"


ALLOWED_LO_TINH_TRANSITIONS: frozenset[tuple[TrangThaiLoTinh, TrangThaiLoTinh]] = frozenset(
    {
        (TrangThaiLoTinh.KHOI_TAO, TrangThaiLoTinh.CHO_PHE_DUYET),
        (TrangThaiLoTinh.CHO_PHE_DUYET, TrangThaiLoTinh.CHAP_NHAN),
        (TrangThaiLoTinh.CHO_PHE_DUYET, TrangThaiLoTinh.TU_CHOI),
        (TrangThaiLoTinh.TU_CHOI, TrangThaiLoTinh.CHO_PHE_DUYET),
        (TrangThaiLoTinh.CHAP_NHAN, TrangThaiLoTinh.CHO_PHEP_DIEU_CHINH),
        (TrangThaiLoTinh.CHO_PHEP_DIEU_CHINH, TrangThaiLoTinh.CHO_PHE_DUYET),
        (TrangThaiLoTinh.CHAP_NHAN, TrangThaiLoTinh.DAT_THANH_CONG),
        (TrangThaiLoTinh.DAT_THANH_CONG, TrangThaiLoTinh.DA_NHAP_KHO),
    }
)

EDITABLE_LO_TINH_STATES: frozenset[TrangThaiLoTinh] = frozenset(
    {
        TrangThaiLoTinh.KHOI_TAO,
        TrangThaiLoTinh.TU_CHOI,
        TrangThaiLoTinh.CHO_PHEP_DIEU_CHINH,
    }
)


def validate_lo_tinh_transition(
    current: TrangThaiLoTinh | str, target: TrangThaiLoTinh | str
) -> None:
    cur = TrangThaiLoTinh(current)
    tgt = TrangThaiLoTinh(target)
    if (cur, tgt) not in ALLOWED_LO_TINH_TRANSITIONS:
        raise StateTransitionError(
            f"Không được phép chuyển trạng thái lô tỉnh từ '{cur.value}' sang '{tgt.value}' (FR-071)."
        )
