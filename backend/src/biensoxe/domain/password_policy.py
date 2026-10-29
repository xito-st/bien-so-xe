from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
import re

DEFAULT_PASSWORDS = ("Abc@!321", "Abc@321")


@dataclass(frozen=True)
class PasswordValidationResult:
    is_valid: bool
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PasswordExpirationStatus:
    is_expired: bool
    should_warn: bool
    days_remaining: int


def validate_new_password(
    new_password: str,
    username: str,
    is_admin: bool = False,
    min_len_user: int = 10,
    min_len_admin: int = 12,
    forbidden_passwords: Iterable[str] = (),
    matches_recent_history: bool = False,
) -> PasswordValidationResult:
    """Kiểm tra chính sách mật khẩu mới theo FR-013 (AC-7)."""
    errors: list[str] = []
    min_len = min_len_admin if is_admin else min_len_user

    if len(new_password) < min_len:
        errors.append(f"Mật khẩu mới phải có độ dài tối thiểu {min_len} ký tự.")

    if not any(ch.isupper() for ch in new_password):
        errors.append("Mật khẩu mới phải có ít nhất 1 chữ cái viết hoa.")
    if not any(ch.islower() for ch in new_password):
        errors.append("Mật khẩu mới phải có ít nhất 1 chữ cái viết thường.")
    if not any(ch.isdigit() for ch in new_password):
        errors.append("Mật khẩu mới phải có ít nhất 1 chữ số.")
    if not re.search(r"[^\w\s]", new_password):
        errors.append("Mật khẩu mới phải có ít nhất 1 ký tự đặc biệt.")

    if username and username.lower() in new_password.lower():
        errors.append("Mật khẩu mới không được chứa tên đăng nhập.")

    all_defaults = set(DEFAULT_PASSWORDS) | set(forbidden_passwords)
    if new_password in all_defaults:
        errors.append("Mật khẩu mới không được trùng với mật khẩu mặc định.")

    if matches_recent_history:
        errors.append("Mật khẩu mới không được trùng với 5 mật khẩu gần nhất.")

    return PasswordValidationResult(is_valid=len(errors) == 0, errors=errors)


def check_password_expiration(
    password_changed_at: datetime,
    now: datetime | None = None,
    expire_days: int = 90,
    warn_days: int = 7,
) -> PasswordExpirationStatus:
    """Kiểm tra thời hạn mật khẩu 90 ngày và cảnh báo từ 7 ngày trước (FR-013, AC-8)."""
    current = now or datetime.now(timezone.utc)
    if password_changed_at.tzinfo is None:
        password_changed_at = password_changed_at.replace(tzinfo=timezone.utc)
    elapsed_days = (current - password_changed_at).days
    days_remaining = expire_days - elapsed_days
    is_expired = days_remaining <= 0
    should_warn = (not is_expired) and (days_remaining <= warn_days)
    return PasswordExpirationStatus(
        is_expired=is_expired,
        should_warn=should_warn,
        days_remaining=max(0, days_remaining),
    )

