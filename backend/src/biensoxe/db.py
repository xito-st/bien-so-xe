import atexit
from collections.abc import Generator
from contextlib import contextmanager
import socket
import subprocess
from typing import Any

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from biensoxe.config import PROJECT_ROOT, get_settings


class Base(DeclarativeBase):
    """Lớp cơ sở cho mọi SQLAlchemy model."""


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None
_started_local_pg: bool = False


def ensure_local_postgres() -> None:
    """Tự động khởi động PostgreSQL 17 portable cục bộ nếu cổng 5432 chưa mở."""
    try:
        with socket.create_connection(("127.0.0.1", 5432), timeout=0.5):
            return
    except PermissionError:
        # Bị chặn kết nối mạng bởi sandbox, không can thiệp vào tiến trình PostgreSQL đang chạy
        return
    except OSError:
        pass

    tools_dir = PROJECT_ROOT.parent / "_tools"
    pg_ctl = tools_dir / "pgsql" / "bin" / "pg_ctl.exe"
    pgdata = tools_dir / "pgdata17"
    if pg_ctl.exists() and pgdata.exists():
        status_proc = subprocess.run(
            [str(pg_ctl), "-D", str(pgdata), "status"],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if status_proc.returncode == 0:
            return
        subprocess.run(
            [
                str(pg_ctl),
                "-D",
                str(pgdata),
                "-l",
                str(tools_dir / "postgres17.log"),
                "-w",
                "start",
            ],
            check=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def get_engine(database_url: str | None = None) -> Engine:
    global _engine
    ensure_local_postgres()
    if database_url is not None:
        return create_engine(database_url, pool_pre_ping=True, future=True)
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=20,
            max_overflow=30,
            future=True,
        )
    return _engine


def get_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    global _SessionLocal
    if engine is not None:
        return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )
    return _SessionLocal


def get_db() -> Generator[Session, Any, None]:
    """Dependency cung cấp DB session cho FastAPI endpoint."""
    ensure_local_postgres()
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def transaction(db: Session) -> Generator[Session, Any, None]:
    """Helper quản lý giao dịch nguyên tử (NFR-010)."""
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
