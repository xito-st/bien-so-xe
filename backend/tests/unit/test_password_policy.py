from datetime import datetime, timedelta, timezone

from biensoxe.domain.password_policy import (
    check_password_expiration,
    validate_new_password,
)


def test_password_policy_length_and_complexity():
    """Kiểm chứng AC-7 (FR-013): độ dài tối thiểu 10 (Admin 12) và đủ 4 nhóm ký tự."""
    # Quá ngắn (< 10 ký tự)
    res = validate_new_password("abc123", username="10105001", is_admin=False)
    assert not res.is_valid
    assert any("10 ký tự" in err for err in res.errors)

    # Admin cần tối thiểu 12 ký tự
    res_admin_short = validate_new_password("GoodPass@12", username="ADMINS", is_admin=True)
    assert not res_admin_short.is_valid
    assert any("12 ký tự" in err for err in res_admin_short.errors)

    # Thiếu chữ hoa / chữ thường / số / ký tự đặc biệt
    assert not validate_new_password("alllowercase@123", username="01", is_admin=False).is_valid
    assert not validate_new_password("ALLUPPERCASE@123", username="01", is_admin=False).is_valid
    assert not validate_new_password("NoDigitsHere@!", username="01", is_admin=False).is_valid
    assert not validate_new_password("NoSpecialChar123", username="01", is_admin=False).is_valid

    # Hợp lệ cho tỉnh/xã (10+ ký tự) và Admin (12+ ký tự)
    assert validate_new_password("HopLe@1234", username="10105001", is_admin=False).is_valid
    assert validate_new_password("AdminHopLe@123", username="ADMINS", is_admin=True).is_valid


def test_password_policy_username_default_and_history():
    """Kiểm chứng AC-7 (FR-013): không chứa tên đăng nhập, không trùng mặc định, không trùng 5 mật khẩu gần nhất."""
    # Chứa tên đăng nhập (không phân biệt hoa/thường)
    res_user = validate_new_password("Mk_10105001@A", username="10105001", is_admin=False)
    assert not res_user.is_valid
    assert any("tên đăng nhập" in err.lower() for err in res_user.errors)

    res_admin = validate_new_password("MyAdmins@2026!", username="ADMINS", is_admin=True)
    assert not res_admin.is_valid

    # Trùng mật khẩu mặc định
    res_default = validate_new_password(
        "Abc@!321Extra",
        username="01",
        is_admin=False,
        forbidden_passwords=["Abc@!321Extra"],
    )
    assert not res_default.is_valid
    assert any("mặc định" in err.lower() for err in res_default.errors)

    # Trùng 1 trong 5 mật khẩu gần nhất
    res_hist = validate_new_password(
        "ValidNewPass@99",
        username="01",
        is_admin=False,
         matches_recent_history=True,
    )
    assert not res_hist.is_valid
    assert any("5 mật khẩu gần nhất" in err for err in res_hist.errors)


def test_password_expiration_and_warning():
    """Kiểm chứng AC-8 (FR-013): hết hạn sau 90 ngày, cảnh báo từ 7 ngày trước."""
    now = datetime(2026, 10, 28, 12, 0, tzinfo=timezone.utc)

    # Mới đổi 10 ngày trước -> chưa hết hạn, chưa cảnh báo
    status_ok = check_password_expiration(now - timedelta(days=10), now=now)
    assert not status_ok.is_expired
    assert not status_ok.should_warn

    # Đã dùng 85 ngày (còn 5 ngày <= 7 ngày) -> cảnh báo
    status_warn = check_password_expiration(now - timedelta(days=85), now=now)
    assert not status_warn.is_expired
    assert status_warn.should_warn
    assert status_warn.days_remaining == 5

    # Đã dùng 90 ngày -> hết hạn
    status_exp = check_password_expiration(now - timedelta(days=90), now=now)
    assert status_exp.is_expired

