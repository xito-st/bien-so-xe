from concurrent.futures import ThreadPoolExecutor
import os

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from biensoxe.config import get_settings


def get_password_hasher() -> PasswordHasher:
    settings = get_settings()
    return PasswordHasher(
        time_cost=settings.argon2_time_cost,
        memory_cost=settings.argon2_memory_cost_kib,
        parallelism=settings.argon2_parallelism,
    )


_DUMMY_HASH: str | None = None


def hash_password(plain_password: str) -> str:
    """Băm mật khẩu một chiều bằng Argon2id với salt ngẫu nhiên riêng biệt (FR-020, D-04)."""
    return get_password_hasher().hash(plain_password)


def hash_passwords_batch(passwords: list[str]) -> list[str]:
    """Băm song song nhiều mật khẩu (giải phóng GIL trong argon2-cffi) để tăng tốc seed (R-2)."""
    hasher = get_password_hasher()
    workers = min(32, (os.cpu_count() or 4) * 2)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(hasher.hash, passwords))


def verify_password(plain_password: str, password_hash: str) -> bool:
    """Kiểm tra mật khẩu khớp với băm Argon2id."""
    try:
        return get_password_hasher().verify(password_hash, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def verify_dummy_password(plain_password: str) -> None:
    """So khớp băm giả khi tên đăng nhập không tồn tại để chống dò tên đăng nhập qua timing (FR-010, AC-4)."""
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password("DummyPasswordForTimingProtection@2026!")
    verify_password(plain_password, _DUMMY_HASH)
