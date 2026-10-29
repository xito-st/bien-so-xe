from sqlalchemy import func, select

from biensoxe.cli import seed_database
from biensoxe.config import get_settings
from biensoxe.models.danh_muc import LoaiPT, NenBien, Tinh, XaPhuong
from biensoxe.models.tai_khoan import TaiKhoan
from biensoxe.security.hashing import verify_password


def test_seed_danh_muc_and_tai_khoan(db_session):
    """Kiểm chứng AC-1, AC-2, AC-14, AC-23 cho lệnh seed khởi tạo hệ thống."""
    seed_database(db_session)
    # Chạy lần 2 phải idempotent
    seed_database(db_session)

    # AC-1: 34 tỉnh/thành, tiền tố Thành phố/Tỉnh, không chứa "Tp"
    tinh_list = db_session.scalars(select(Tinh).order_by(Tinh.stt)).all()
    assert len(tinh_list) == 34
    for t in tinh_list:
        assert "Tp" not in t.ten
        assert t.loai_don_vi in ("Tỉnh", "Thành phố")
        assert t.ten.startswith(t.loai_don_vi)

    # AC-1: 3.321 xã/phường/đặc khu (2.621 xã, 687 phường, 13 đặc khu), giữ nguyên thứ tự STT
    xa_list = db_session.scalars(select(XaPhuong).order_by(XaPhuong.stt)).all()
    assert len(xa_list) == 3321
    assert [x.stt for x in xa_list] == list(range(1, 3322))
    counts_by_type = dict(
        db_session.execute(
            select(XaPhuong.loai_don_vi, func.count()).group_by(XaPhuong.loai_don_vi)
        ).all()
    )
    assert counts_by_type == {"Xã": 2621, "Phường": 687, "Đặc khu": 13}

    # AC-23: 86 LoaiPT, STT 1..86 liên tục; XL, Y1, YM, Z1, ZY -> 82..86; 3 nền biển
    loai_pt_list = db_session.scalars(select(LoaiPT).order_by(LoaiPT.stt)).all()
    assert len(loai_pt_list) == 86
    assert [lp.stt for lp in loai_pt_list] == list(range(1, 87))
    tail_map = {lp.seri_chu: lp.stt for lp in loai_pt_list[-5:]}
    assert tail_map == {"XL": 82, "Y1": 83, "YM": 84, "Z1": 85, "ZY": 86}

    nen_bien_list = db_session.scalars(select(NenBien).order_by(NenBien.stt)).all()
    assert len(nen_bien_list) == 3
    assert [nb.mau_sac for nb in nen_bien_list] == ["VÀNG", "TRẮNG", "XANH"]

    # AC-2: 1 Admin + 34 tỉnh + 3.321 xã = 3.356 tài khoản
    tk_list = db_session.scalars(select(TaiKhoan)).all()
    assert len(tk_list) == 1 + 34 + 3321

    admin = db_session.scalar(select(TaiKhoan).where(TaiKhoan.ten_dang_nhap == "ADMINS"))
    assert admin is not None
    assert admin.vai_tro == "ADMIN"
    assert admin.bat_buoc_doi_mk is True
    assert verify_password(get_settings().admin_initial_password, admin.mat_khau_hash)

    tinh_01 = db_session.scalar(select(TaiKhoan).where(TaiKhoan.ten_dang_nhap == "01"))
    assert tinh_01 is not None
    assert tinh_01.vai_tro == "TINH"
    assert tinh_01.tinh_ma == "01"
    assert tinh_01.bat_buoc_doi_mk is True
    assert verify_password("Abc@!321", tinh_01.mat_khau_hash)

    xa_sample = db_session.scalar(select(TaiKhoan).where(TaiKhoan.ten_dang_nhap == "10105001"))
    assert xa_sample is not None
    assert xa_sample.vai_tro == "XA"
    assert xa_sample.tinh_ma == "01"
    assert xa_sample.xa_ma == "10105001"
    assert xa_sample.bat_buoc_doi_mk is True
    assert verify_password("Abc@321", xa_sample.mat_khau_hash)

    # Kiểm tra cả 13 đặc khu đều có tài khoản như xã/phường
    dac_khu_mas = [x.ma for x in xa_list if x.loai_don_vi == "Đặc khu"]
    assert len(dac_khu_mas) == 13
    dac_khu_tks = db_session.scalars(
        select(TaiKhoan).where(TaiKhoan.ten_dang_nhap.in_(dac_khu_mas))
    ).all()
    assert len(dac_khu_tks) == 13

    # AC-14: Không có mật khẩu dạng rõ trong DB, mọi bản ghi dùng Argon2id với salt riêng
    hashes = [tk.mat_khau_hash for tk in tk_list]
    assert all(h.startswith("$argon2id$") for h in hashes)
    assert all("Abc@321" not in h and "Abc@!321" not in h for h in hashes)
    assert len(set(hashes)) == len(hashes)
