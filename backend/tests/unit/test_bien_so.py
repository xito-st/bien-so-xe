from hypothesis import given, strategies as st
import pytest

from biensoxe.domain.bien_so import BienSoValidationError, parse_and_validate_bien_so

SAMPLE_LOAI_PT = {
    "A": "Ô TÔ",
    "AA": "MÔ TÔ",
    "A1": "MÔ TÔ",
    "B2": "MÔ TÔ",
    "F1": "MÔ TÔ",
    "Z1": "MÔ TÔ",
    "MĐ1": "XE MÁY ĐIỆN",
    "RM": "Ô TÔ RƠ MÓC",
}

SAMPLE_NEN_BIEN = {
    "Nền màu VÀNG, chữ và số màu ĐEN": "VÀNG",
    "Nền màu TRẮNG, chữ và số màu ĐEN": "TRẮNG",
    "Nền màu XANH, chữ và số màu TRẮNG": "XANH",
}


def test_parse_valid_plates_ac18_ac19_ac21():
    """Kiểm chứng AC-18, AC-19, AC-21."""
    r1 = parse_and_validate_bien_so(
        raw_bien_so="11A-234.56",
        nen_bien="Nền màu TRẮNG, chữ và số màu ĐEN",
        active_loai_pt=SAMPLE_LOAI_PT,
        active_nen_bien=SAMPLE_NEN_BIEN,
    )
    assert r1.ma_tinh == "11"
    assert r1.seri_chu == "A"
    assert r1.seri_so == "234.56"
    assert r1.dau_so == "234"
    assert r1.bien_so_day_du == "11A-234.56"
    assert r1.loai_pt == "Ô TÔ"
    assert r1.mau_sac == "TRẮNG"

    r2 = parse_and_validate_bien_so(
        raw_bien_so="11AA-234.56",
        nen_bien="Nền màu VÀNG, chữ và số màu ĐEN",
        active_loai_pt=SAMPLE_LOAI_PT,
        active_nen_bien=SAMPLE_NEN_BIEN,
    )
    assert r2.seri_chu == "AA"
    assert r2.bien_so_day_du == "11AA-234.56"
    assert r2.loai_pt == "MÔ TÔ"
    assert r2.mau_sac == "VÀNG"

    r3 = parse_and_validate_bien_so(
        raw_bien_so="11MĐ1-234.56",
        nen_bien="Nền màu XANH, chữ và số màu TRẮNG",
        active_loai_pt=SAMPLE_LOAI_PT,
        active_nen_bien=SAMPLE_NEN_BIEN,
    )
    assert r3.seri_chu == "MĐ1"
    assert r3.bien_so_day_du == "11MĐ1-234.56"
    assert r3.loai_pt == "XE MÁY ĐIỆN"
    assert r3.mau_sac == "XANH"

    r4 = parse_and_validate_bien_so(
        raw_bien_so="11A1-234.56",
        nen_bien="Nền màu TRẮNG, chữ và số màu ĐEN",
        active_loai_pt=SAMPLE_LOAI_PT,
        active_nen_bien=SAMPLE_NEN_BIEN,
    )
    assert r4.seri_chu == "A1"
    assert r4.loai_pt == "MÔ TÔ"


def test_parse_invalid_plates_ac20_ac21():
    """Kiểm chứng AC-20, AC-21: SeriChu không có trong danh mục, dấu '-' kép, thiếu nền biển."""
    with pytest.raises(BienSoValidationError) as exc1:
        parse_and_validate_bien_so(
            raw_bien_so="11QQ-234.56",
            nen_bien="Nền màu TRẮNG, chữ và số màu ĐEN",
            active_loai_pt=SAMPLE_LOAI_PT,
            active_nen_bien=SAMPLE_NEN_BIEN,
        )
    assert "SeriChu" in str(exc1.value) or "danh mục" in str(exc1.value)

    with pytest.raises(BienSoValidationError):
        parse_and_validate_bien_so(
            raw_bien_so="11A--234.56",
            nen_bien="Nền màu TRẮNG, chữ và số màu ĐEN",
            active_loai_pt=SAMPLE_LOAI_PT,
            active_nen_bien=SAMPLE_NEN_BIEN,
        )

    with pytest.raises(BienSoValidationError):
        parse_and_validate_bien_so(
            raw_bien_so="11A-234.56",
            nen_bien="",
            active_loai_pt=SAMPLE_LOAI_PT,
            active_nen_bien=SAMPLE_NEN_BIEN,
        )


def test_normalize_seri_so_ac22():
    """Kiểm chứng AC-22 (FR-035): chuẩn hóa SeriSo bị Excel cắt số 0."""
    p1 = parse_and_validate_bien_so(
        raw_bien_so="11A-234.5",
        nen_bien="Nền màu TRẮNG, chữ và số màu ĐEN",
        active_loai_pt=SAMPLE_LOAI_PT,
        active_nen_bien=SAMPLE_NEN_BIEN,
    )
    assert p1.seri_so == "234.50"
    assert p1.bien_so_day_du == "11A-234.50"

    p2 = parse_and_validate_bien_so(
        raw_bien_so="11A-12.5",
        nen_bien="Nền màu TRẮNG, chữ và số màu ĐEN",
        active_loai_pt=SAMPLE_LOAI_PT,
        active_nen_bien=SAMPLE_NEN_BIEN,
    )
    assert p2.seri_so == "012.50"
    assert p2.dau_so == "012"
    assert p2.bien_so_day_du == "11A-012.50"

    with pytest.raises(BienSoValidationError):
        parse_and_validate_bien_so(
            raw_bien_so="11A-23.456",
            nen_bien="Nền màu TRẮNG, chữ và số màu ĐEN",
            active_loai_pt=SAMPLE_LOAI_PT,
            active_nen_bien=SAMPLE_NEN_BIEN,
        )


def test_ngoai_tinh_warning_ac53():
    """Kiểm chứng AC-53 (FR-038): cảnh báo và gắn cờ ngoại tỉnh khi tỉnh đã khai báo mã biển."""
    # Tỉnh chưa khai báo mã biển -> không cảnh báo
    p_unconfigured = parse_and_validate_bien_so(
        raw_bien_so="29A-123.45",
        nen_bien="Nền màu TRẮNG, chữ và số màu ĐEN",
        active_loai_pt=SAMPLE_LOAI_PT,
        active_nen_bien=SAMPLE_NEN_BIEN,
        allowed_ma_bien_tinh=set(),
    )
    assert p_unconfigured.ngoai_tinh is False
    assert p_unconfigured.canh_bao_ngoai_tinh is None

    # Tỉnh khai báo {"11"}, nhập 29A-123.45 -> ngoai_tinh=True + có cảnh báo
    p_foreign = parse_and_validate_bien_so(
        raw_bien_so="29A-123.45",
        nen_bien="Nền màu TRẮNG, chữ và số màu ĐEN",
        active_loai_pt=SAMPLE_LOAI_PT,
        active_nen_bien=SAMPLE_NEN_BIEN,
        allowed_ma_bien_tinh={"11"},
    )
    assert p_foreign.ngoai_tinh is True
    assert p_foreign.canh_bao_ngoai_tinh is not None

    # Tỉnh khai báo {"11"}, nhập 11A-123.45 -> ngoai_tinh=False
    p_local = parse_and_validate_bien_so(
        raw_bien_so="11A-123.45",
        nen_bien="Nền màu TRẮNG, chữ và số màu ĐEN",
        active_loai_pt=SAMPLE_LOAI_PT,
        active_nen_bien=SAMPLE_NEN_BIEN,
        allowed_ma_bien_tinh={"11"},
    )
    assert p_local.ngoai_tinh is False
    assert p_local.canh_bao_ngoai_tinh is None


@given(
    ma_tinh=st.integers(min_value=1, max_value=99).map(lambda n: f"{n:02d}"),
    seri_chu=st.sampled_from(list(SAMPLE_LOAI_PT.keys())),
    phan_nguyen=st.integers(min_value=0, max_value=999),
    phan_thap_phan=st.integers(min_value=0, max_value=99),
)
def test_property_parse_idempotent(ma_tinh, seri_chu, phan_nguyen, phan_thap_phan):
    raw = f" {ma_tinh}{seri_chu.lower()}-{phan_nguyen}.{phan_thap_phan:02d} "
    first = parse_and_validate_bien_so(
        raw_bien_so=raw,
        nen_bien="Nền màu TRẮNG, chữ và số màu ĐEN",
        active_loai_pt=SAMPLE_LOAI_PT,
        active_nen_bien=SAMPLE_NEN_BIEN,
    )
    second = parse_and_validate_bien_so(
        raw_bien_so=first.bien_so_day_du,
        nen_bien="Nền màu TRẮNG, chữ và số màu ĐEN",
        active_loai_pt=SAMPLE_LOAI_PT,
        active_nen_bien=SAMPLE_NEN_BIEN,
    )
    assert first == second
