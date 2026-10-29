from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Cấu hình ứng dụng đọc từ biến môi trường / .env (NFR-015, D-11)."""

    model_config = SettingsConfigDict(
        env_file=(str(PROJECT_ROOT / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+psycopg://postgres@127.0.0.1:5432/biensoxe_dev",
        alias="DATABASE_URL",
    )
    test_database_url: str = Field(
        default="postgresql+psycopg://postgres@127.0.0.1:5432/biensoxe_test",
        alias="TEST_DATABASE_URL",
    )

    admin_initial_password: str = Field(
        default="AdminInit@2026!Secret",
        alias="ADMIN_INITIAL_PASSWORD",
    )
    totp_enc_key: str = Field(
        default="MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY=",
        alias="TOTP_ENC_KEY",
    )
    session_secret: str = Field(
        default="dev-session-secret-key-for-bien-so-xe-2026-local-only",
        alias="SESSION_SECRET",
    )
    cookie_secure: bool = Field(default=False, alias="COOKIE_SECURE")

    # Chính sách mật khẩu & khóa tài khoản (FR-013, FR-014, FR-022, NFR-015)
    password_min_length_user: int = Field(default=10, alias="PASSWORD_MIN_LENGTH_USER")
    password_min_length_admin: int = Field(default=12, alias="PASSWORD_MIN_LENGTH_ADMIN")
    password_history_count: int = Field(default=5, alias="PASSWORD_HISTORY_COUNT")
    password_expire_days: int = Field(default=90, alias="PASSWORD_EXPIRE_DAYS")
    password_warn_days: int = Field(default=7, alias="PASSWORD_WARN_DAYS")
    max_failed_login_attempts: int = Field(default=5, alias="MAX_FAILED_LOGIN_ATTEMPTS")
    lockout_duration_minutes: int = Field(default=30, alias="LOCKOUT_DURATION_MINUTES")
    session_idle_timeout_minutes: int = Field(
        default=30, alias="SESSION_IDLE_TIMEOUT_MINUTES"
    )

    # Giới hạn import & lô biển (FR-042, NFR-015)
    import_max_file_size_mb: int = Field(default=5, alias="IMPORT_MAX_FILE_SIZE_MB")
    import_max_rows: int = Field(default=5000, alias="IMPORT_MAX_ROWS")
    batch_max_plates: int = Field(default=5000, alias="BATCH_MAX_PLATES")

    # Tham số Argon2id (FR-020, D-04)
    argon2_time_cost: int = Field(default=2, alias="ARGON2_TIME_COST")
    argon2_memory_cost_kib: int = Field(default=19456, alias="ARGON2_MEMORY_COST_KIB")
    argon2_parallelism: int = Field(default=1, alias="ARGON2_PARALLELISM")

    # Giới hạn tần suất (FR-018)
    forgot_password_rate_limit_per_hour: int = Field(
        default=5, alias="FORGOT_PASSWORD_RATE_LIMIT_PER_HOUR"
    )

    @property
    def import_max_file_size_bytes(self) -> int:
        return self.import_max_file_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()

