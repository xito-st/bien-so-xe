from contextvars import ContextVar
from datetime import datetime, timezone
import json
import logging
import re
from typing import Any

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

SENSITIVE_KEYS = frozenset(
    {
        "password",
        "mat_khau",
        "mat_khau_hien_tai",
        "mat_khau_moi",
        "mat_khau_nhap_lai",
        "mat_khau_hash",
        "token",
        "session_token",
        "csrf_token",
        "totp_secret",
        "totp_secret_enc",
        "ma_totp",
        "ma_khoi_phuc",
        "secret",
        "authorization",
        "cookie",
        "admin_initial_password",
    }
)

_SECRET_PATTERN = re.compile(
    r"(?i)(mat_khau\w*|password\w*|token\w*|secret\w*)\s*([=:])\s*(['\"]?)([^'\",\s}&]+)\3"
)


def scrub_value(value: Any) -> Any:
    """Che mật khẩu, token và secret trong dict/list/chuỗi trước khi ghi log (FR-020, D-12)."""
    if isinstance(value, dict):
        return {
            k: ("***REDACTED***" if str(k).lower() in SENSITIVE_KEYS else scrub_value(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [scrub_value(item) for item in value]
    if isinstance(value, str):
        return _SECRET_PATTERN.sub(r"\1\2\3***REDACTED***\3", value)
    return value


class SecretScrubFilter(logging.Filter):
    """Bộ lọc logging đảm bảo không bao giờ ghi mật khẩu/token dạng rõ (FR-020, AC-14)."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = scrub_value(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = scrub_value(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(scrub_value(a) for a in record.args)
        if hasattr(record, "extra_data"):
            record.extra_data = scrub_value(getattr(record, "extra_data"))
        return True


class JsonLogFormatter(logging.Formatter):
    """Định dạng JSON có request_id (D-12)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "request_id": request_id_ctx.get(),
            "message": scrub_value(record.getMessage()),
        }
        if hasattr(record, "extra_data"):
            payload["data"] = scrub_value(getattr(record, "extra_data"))
        if record.exc_info:
            payload["exc_info"] = scrub_value(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger("biensoxe")
    logger.setLevel(level)
    logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.addFilter(SecretScrubFilter())
    handler.setFormatter(JsonLogFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger
