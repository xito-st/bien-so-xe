import io
import json
import logging

from fastapi.testclient import TestClient

from biensoxe.config import Settings
from biensoxe.logging import JsonLogFormatter, SecretScrubFilter, request_id_ctx, scrub_value
from biensoxe.main import create_app


def test_settings_load_defaults_and_overrides(monkeypatch):
    monkeypatch.setenv("IMPORT_MAX_FILE_SIZE_MB", "10")
    monkeypatch.setenv("MAX_FAILED_LOGIN_ATTEMPTS", "7")
    s = Settings(_env_file=None)
    assert s.import_max_file_size_mb == 10
    assert s.import_max_file_size_bytes == 10 * 1024 * 1024
    assert s.max_failed_login_attempts == 7
    assert s.password_min_length_user == 10
    assert s.password_min_length_admin == 12


def test_secret_scrubbing_in_logs():
    data = {
        "ten_dang_nhap": "ADMINS",
        "mat_khau": "Abc@!321",
        "nested": {"password": "SecretPassword123!", "safe": "ok"},
    }
    scrubbed = scrub_value(data)
    assert scrubbed["mat_khau"] == "***REDACTED***"
    assert scrubbed["nested"]["password"] == "***REDACTED***"
    assert scrubbed["nested"]["safe"] == "ok"

    stream = io.StringIO()
    logger = logging.getLogger("test_scrub")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    handler = logging.StreamHandler(stream)
    handler.addFilter(SecretScrubFilter())
    handler.setFormatter(JsonLogFormatter())
    logger.addHandler(handler)

    token = request_id_ctx.set("req-123")
    try:
        logger.info("Đăng nhập thất bại với mat_khau=Abc@!321 và token=xyz987")
    finally:
        request_id_ctx.reset(token)

    output = stream.getvalue().strip()
    assert "Abc@!321" not in output
    assert "xyz987" not in output
    parsed = json.loads(output)
    assert parsed["request_id"] == "req-123"
    assert "***REDACTED***" in parsed["message"]


def test_health_and_security_headers():
    client = TestClient(create_app())
    resp = client.get("/api/v1/health", headers={"X-Request-ID": "test-req-001"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.headers["X-Request-ID"] == "test-req-001"
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'self'" in resp.headers["Content-Security-Policy"]
