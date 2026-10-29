import pytest

from biensoxe.domain.state_bien import (
     StateTransitionError,
    TrangThaiGiao,
    TinhTrangBien,
    validate_bien_giao_transition,
    validate_bien_tinh_trang_transition,
)
from biensoxe.domain.state_lo_dnm import (
    TrangThaiLoDNM,
    validate_lo_dnm_transition,
)
from biensoxe.domain.state_lo_tinh import (
    TrangThaiLoTinh,
    validate_lo_tinh_transition,
)
from biensoxe.domain.state_lo_xa import (
    TrangThaiLoXa,
    validate_lo_xa_transition,
)


def test_lo_xa_state_machine_ac31():
    """Kiểm chứng sơ đồ J.1 (FR-046, AC-31): chỉ cho phép các chuyển trạng thái trong sơ đồ."""
    allowed = {
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
    for s_from in TrangThaiLoXa:
        for s_to in TrangThaiLoXa:
            if (s_from, s_to) in allowed:
                validate_lo_xa_transition(s_from, s_to)
            else:
                with pytest.raises(StateTransitionError):
                    validate_lo_xa_transition(s_from, s_to)


def test_lo_dnm_state_machine_j2():
    """Kiểm chứng sơ đồ J.2 (FR-065, FR-069): vòng đời lô đặt nhà máy."""
    allowed = {
        (TrangThaiLoDNM.KHOI_TAO, TrangThaiLoDNM.CHO_PHE_DUYET),
        (TrangThaiLoDNM.CHO_PHE_DUYET, TrangThaiLoDNM.KHOI_TAO),
        (TrangThaiLoDNM.CHO_PHE_DUYET, TrangThaiLoDNM.CHAP_NHAN),
        (TrangThaiLoDNM.CHAP_NHAN, TrangThaiLoDNM.KHOI_TAO),  # khi lô thành phần bật điều chỉnh (FR-049/FR-071)
        (TrangThaiLoDNM.CHAP_NHAN, TrangThaiLoDNM.DAT_THANH_CONG),
        (TrangThaiLoDNM.DAT_THANH_CONG, TrangThaiLoDNM.DA_NHAP_KHO),
        (TrangThaiLoDNM.DA_NHAP_KHO, TrangThaiLoDNM.DA_CHUYEN_XA),
        (TrangThaiLoDNM.KHOI_TAO, TrangThaiLoDNM.HUY),
        (TrangThaiLoDNM.CHO_PHE_DUYET, TrangThaiLoDNM.HUY),
        (TrangThaiLoDNM.CHAP_NHAN, TrangThaiLoDNM.HUY),
    }
    for s_from in TrangThaiLoDNM:
        for s_to in TrangThaiLoDNM:
            if (s_from, s_to) in allowed:
                validate_lo_dnm_transition(s_from, s_to)
            else:
                with pytest.raises(StateTransitionError):
                    validate_lo_dnm_transition(s_from, s_to)


def test_lo_tinh_state_machine_j3():
    """Kiểm chứng sơ đồ J.3 (FR-062, FR-071): vòng đời lô tỉnh."""
    allowed = {
        (TrangThaiLoTinh.KHOI_TAO, TrangThaiLoTinh.CHO_PHE_DUYET),
        (TrangThaiLoTinh.CHO_PHE_DUYET, TrangThaiLoTinh.CHAP_NHAN),
        (TrangThaiLoTinh.CHO_PHE_DUYET, TrangThaiLoTinh.TU_CHOI),
        (TrangThaiLoTinh.TU_CHOI, TrangThaiLoTinh.CHO_PHE_DUYET),
        (TrangThaiLoTinh.CHAP_NHAN, TrangThaiLoTinh.CHO_PHEP_DIEU_CHINH),
        (TrangThaiLoTinh.CHO_PHEP_DIEU_CHINH, TrangThaiLoTinh.CHO_PHE_DUYET),
        (TrangThaiLoTinh.CHAP_NHAN, TrangThaiLoTinh.DAT_THANH_CONG),
        (TrangThaiLoTinh.DAT_THANH_CONG, TrangThaiLoTinh.DA_NHAP_KHO),
    }
    for s_from in TrangThaiLoTinh:
        for s_to in TrangThaiLoTinh:
            if (s_from, s_to) in allowed:
                validate_lo_tinh_transition(s_from, s_to)
            else:
                with pytest.raises(StateTransitionError):
                    validate_lo_tinh_transition(s_from, s_to)


def test_bien_two_axes_state_machine_4i():
    """Kiểm chứng 2 trục trạng thái biển (4.I, FR-053, FR-054, FR-070): Thu hồi về xã là trạng thái cuối."""
    allowed_tinh_trang = {
        (TinhTrangBien.CHUA_DAT, TinhTrangBien.DA_DAT),
        (TinhTrangBien.DA_DAT, TinhTrangBien.TON_KHO_TINH),
        (TinhTrangBien.TON_KHO_TINH, TinhTrangBien.TON_KHO_XA),
        (TinhTrangBien.DA_DAT, TinhTrangBien.DA_HUY),
        (TinhTrangBien.TON_KHO_TINH, TinhTrangBien.DA_HUY),
        (TinhTrangBien.TON_KHO_XA, TinhTrangBien.DA_HUY),
    }
    for s_from in TinhTrangBien:
        for s_to in TinhTrangBien:
            if (s_from, s_to) in allowed_tinh_trang:
                validate_bien_tinh_trang_transition(s_from, s_to)
            else:
                with pytest.raises(StateTransitionError):
                    validate_bien_tinh_trang_transition(s_from, s_to)

    allowed_giao = {
        (TrangThaiGiao.CHUA_TRA, TrangThaiGiao.DA_TRA),
        (TrangThaiGiao.DA_TRA, TrangThaiGiao.THU_HOI_VE_XA),
    }
    for g_from in TrangThaiGiao:
        for g_to in TrangThaiGiao:
            if (g_from, g_to) in allowed_giao:
                validate_bien_giao_transition(g_from, g_to)
            else:
                with pytest.raises(StateTransitionError):
                    validate_bien_giao_transition(g_from, g_to)

