from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from biensoxe.models.bien import Bien
from biensoxe.models.tai_khoan import TaiKhoan
from biensoxe.security.session import CSRF_HEADER_NAME, SESSION_COOKIE_NAME, create_server_session
from conftest import _build_test_client


def _make_thread_client(test_engine, username: str):
    factory = sessionmaker(
        bind=test_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
    with factory() as db:
        tk = db.scalar(select(TaiKhoan).where(TaiKhoan.ten_dang_nhap == username))
        assert tk is not None
        raw_token, csrf_token = create_server_session(db, tai_khoan_id=tk.id, ip="127.0.0.1")
        db.commit()

    c = _build_test_client(test_engine)
    c.cookies.set(SESSION_COOKIE_NAME, raw_token)
    c.headers[CSRF_HEADER_NAME] = csrf_token
    return c


def test_concurrent_submit_same_plate_and_concurrent_create_same_so_cv_ac49(
    test_engine, authenticated_clients, seeded_db: Session
) -> None:
    """
    Kiểm chứng AC-49 (NFR-010):
    1. Hai xã cùng tỉnh (10105001 và 10105002) đồng thời gửi lô chứa cùng một biển số 30A-999.99
       -> đúng 1 lô thành công (200), 1 lô bị chặn trùng (409), và trong DB chỉ có đúng 1 bản ghi giữ chỗ.
    2. Hai request đồng thời tạo lô cùng Số công văn trong cùng đơn vị -> đúng 1 lô được tạo (201), 1 bị chặn (409).
    """
    xa1 = authenticated_clients["xa_10105001"]
    xa2 = authenticated_clients["xa_10105002"]

    # Chuẩn bị 2 lô ở trạng thái Khởi tạo tại 2 xã cùng tỉnh 01, cùng chứa biển 30A-999.99
    lo1 = xa1.post("/api/v1/lo", json={"loai": "XA", "so_cong_van": "CV-CONC-XA1"}).json()
    lo2 = xa2.post("/api/v1/lo", json={"loai": "XA", "so_cong_van": "CV-CONC-XA2"}).json()

    r_b1 = xa1.post(f"/api/v1/lo/{lo1['id']}/bien", json={"bien_so": "30A-999.99"})
    r_b2 = xa2.post(f"/api/v1/lo/{lo2['id']}/bien", json={"bien_so": "30A-999.99"})
    assert r_b1.status_code == 201
    assert r_b2.status_code == 201

    def _submit_lo(username: str, lo_id: int) -> int:
        client = _make_thread_client(test_engine, username)
        with client:
            resp = client.post(f"/api/v1/lo/{lo_id}/gui", json={"xac_nhan": True})
            return resp.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        f1 = pool.submit(_submit_lo, "10105001", lo1["id"])
        f2 = pool.submit(_submit_lo, "10105002", lo2["id"])
        statuses = sorted([f1.result(), f2.result()])

    assert statuses == [200, 409]

    seeded_db.expire_all()
    reserved_cnt = seeded_db.scalar(
        select(func.count(Bien.id)).where(
            Bien.tinh_ma == "01",
            Bien.bien_so_day_du == "30A-999.99",
            Bien.giu_cho.is_(True),
        )
    )
    assert reserved_cnt == 1

    # 2. Hai request đồng thời tạo lô cùng Số công văn trong cùng 1 xã -> đúng 1 thành công (201), 1 bị chặn (409)
    def _create_same_cv() -> int:
        client = _make_thread_client(test_engine, "10105001")
        with client:
            resp = client.post(
                "/api/v1/lo",
                json={"loai": "XA", "so_cong_van": "CV-DUP-CONC"},
            )
            return resp.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        c1 = pool.submit(_create_same_cv)
        c2 = pool.submit(_create_same_cv)
        cv_statuses = sorted([c1.result(), c2.result()])

    assert cv_statuses == [201, 409]
