from collections.abc import Generator
from datetime import datetime, timezone
import os

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

# Dùng tham số Argon2 nhanh hơn trong môi trường test để seed 3.356 tài khoản dưới 3 giây
os.environ.setdefault("ARGON2_TIME_COST", "1")
os.environ.setdefault("ARGON2_MEMORY_COST_KIB", "8192")

from biensoxe.cli import seed_database
from biensoxe.config import get_settings
from biensoxe.db import Base, ensure_local_postgres, get_db
from biensoxe.main import create_app
import biensoxe.models  # noqa: F401
from biensoxe.models.tai_khoan import TaiKhoan
from biensoxe.security.session import CSRF_HEADER_NAME, SESSION_COOKIE_NAME, create_server_session

os.environ["ARGON2_TIME_COST"] = "1"
os.environ["ARGON2_MEMORY_COST_KIB"] = "8192"
get_settings.cache_clear()


@pytest.fixture(scope="session")
def test_engine():
    ensure_local_postgres()
    settings = get_settings()
    engine = create_engine(settings.test_database_url, pool_pre_ping=True, future=True)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE OR REPLACE FUNCTION fn_prevent_audit_log_mutation()
                RETURNS trigger AS $$
                BEGIN
                    IF TG_OP = 'TRUNCATE' AND current_setting('biensoxe.allow_test_truncate', true) = '1' THEN
                        RETURN NULL;
                    END IF;
                    RAISE EXCEPTION 'audit_log là nhật ký bất biến, không được phép sửa hoặc xóa (FR-021)';
                END;
                $$ LANGUAGE plpgsql;

                DROP TRIGGER IF EXISTS trg_audit_log_no_update_delete ON audit_log;
                CREATE TRIGGER trg_audit_log_no_update_delete
                BEFORE UPDATE OR DELETE ON audit_log
                FOR EACH ROW EXECUTE FUNCTION fn_prevent_audit_log_mutation();

                DROP TRIGGER IF EXISTS trg_audit_log_no_truncate ON audit_log;
                CREATE TRIGGER trg_audit_log_no_truncate
                BEFORE TRUNCATE ON audit_log
                FOR EACH STATEMENT EXECUTE FUNCTION fn_prevent_audit_log_mutation();
                """
            )
        )
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(test_engine) -> Generator[Session, None, None]:
    factory = sessionmaker(bind=test_engine, autoflush=False, autocommit=False, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def seeded_db(db_session: Session) -> Session:
    seed_database(db_session)
    return db_session


def _build_test_client(test_engine) -> TestClient:
    factory = sessionmaker(bind=test_engine, autoflush=False, autocommit=False, expire_on_commit=False)
    app = create_app()

    def _override_get_db() -> Generator[Session, None, None]:
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    return TestClient(app)


@pytest.fixture()
def client(test_engine, seeded_db) -> Generator[TestClient, None, None]:
    with _build_test_client(test_engine) as c:
        yield c


@pytest.fixture()
def authenticated_clients(test_engine, seeded_db: Session) -> dict[str, TestClient]:
    """Tạo sẵn các TestClient đã đăng nhập và qua bước đổi mật khẩu / 2FA cho các vai trò."""
    accounts_map = {
        "admin": "ADMINS",
        "tinh_01": "01",
        "tinh_02": "02",
        "xa_10105001": "10105001",
        "xa_10105002": "10105002",
        "xa_22113001": "22113001",
        "xa_22701001": "22113001",
    }
    now = datetime.now(timezone.utc)
    clients: dict[str, TestClient] = {}

    for key, username in accounts_map.items():
        tk = seeded_db.scalar(select(TaiKhoan).where(TaiKhoan.ten_dang_nhap == username))
        assert tk is not None, f"Không tìm thấy tài khoản {username} trong DB đã seed"
        tk.bat_buoc_doi_mk = False
        tk.mk_doi_luc = now
        tk.so_lan_sai = 0
        tk.khoa_den = None
        tk.khoa_thu_cong = False
        if tk.vai_tro == "ADMIN":
            tk.totp_da_bat = True
        seeded_db.flush()

        raw_token, csrf_token = create_server_session(seeded_db, tai_khoan_id=tk.id, ip="127.0.0.1")
        seeded_db.commit()

        c = _build_test_client(test_engine)
        c.cookies.set(SESSION_COOKIE_NAME, raw_token)
        c.headers[CSRF_HEADER_NAME] = csrf_token
        clients[key] = c

    return clients
