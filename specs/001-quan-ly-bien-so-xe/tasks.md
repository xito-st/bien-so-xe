# Tasks: Phần mềm quản lý đặt và cấp phát biển số xe (34 tỉnh/thành)

- **Spec:** [spec.md](./spec.md) · **Plan:** [plan.md](./plan.md)
- **Trạng thái:** Đã duyệt (2026-10-28) — Đang triển khai Pha 5
- **Ngày:** 2026-10-28
- Ký hiệu: `[ ]` chưa làm · `[x]` xong và đã kiểm chứng · `[P]` làm song song được

---

## Pha 0: Thiết lập môi trường & Hạ tầng nền tảng

- [x] **T001** [NFR-015] Cài đặt/cấu hình PostgreSQL 17 trên máy phát triển (bản Windows hoặc portable cục bộ), tạo database `biensoxe_dev` và `biensoxe_test` (encoding `UTF8`), tạo file `.env.example` và `.env` (đã nằm trong `.gitignore`).
  - **Đầu ra:** PostgreSQL chạy cục bộ, `bien-so-xe/.env.example`.
  - **Kiểm chứng:** Kết nối và chạy `SELECT version();` trên cả `biensoxe_dev` và `biensoxe_test` thành công.
- [x] **T002** [NFR-015, FR-020] Khởi tạo project backend Python bằng `uv` tại `backend/pyproject.toml`, cài đặt dependencies (`fastapi`, `uvicorn`, `sqlalchemy`, `psycopg[binary]`, `alembic`, `pydantic-settings`, `argon2-cffi`, `pyotp`, `cryptography`, `openpyxl`, `xlsxwriter`, `pytest`, `httpx`, `hypothesis`, `freezegun`), cấu hình `config.py` (NFR-015), `db.py` và logging JSON có bộ lọc che mật khẩu/token (D-12).
  - **Đầu ra:** `backend/pyproject.toml`, `backend/uv.lock`, `backend/src/biensoxe/{__init__.py,config.py,db.py,logging.py}`, `backend/tests/conftest.py`.
  - **Kiểm chứng:** `uv run pytest` chạy xanh test khói kiểm tra nạp cấu hình `Settings` và bộ lọc che mật khẩu trên log.
- [x] **T003** [P] [NFR-007, NFR-012] Khởi tạo project frontend React + TypeScript + Vite tại `frontend/`, cài đặt `react-router-dom`, `@tanstack/react-query`, `@tanstack/react-table`, `@tanstack/react-virtual`, thiết lập design tokens CSS, định dạng ngày giờ `dd/MM/yyyy HH:mm` (UTC+7) và cấu hình phục vụ file tĩnh từ FastAPI (`backend/src/biensoxe/main.py`).
  - **Đầu ra:** `frontend/package.json`, `frontend/package-lock.json`, `frontend/src/`, `backend/src/biensoxe/main.py`.
  - **Kiểm chứng:** `npm run build` trong `frontend/` thành công; `uv run pytest` kiểm tra `GET /api/v1/health` trả `200 OK` kèm security headers (NFR-008, NFR-009).

---

## Pha 1: US-1 (P1) — Danh mục đơn vị hành chính, Tự sinh tài khoản & Tài khoản phụ

- [x] **T004** [FR-001, FR-002, FR-003, FR-004, FR-033, FR-034, FR-038] Viết migration Alembic đầu tiên và SQLAlchemy models cho nhóm danh mục & tài khoản: `tinh` (có `loai_don_vi`), `xa_phuong` (có `loai_don_vi`, `stt`), `loai_pt`, `nen_bien`, `ma_bien_tinh`, `tai_khoan` (kèm CHECK ràng buộc vai trò/đơn vị theo FR-004), `lich_su_mat_khau`, `ma_khoi_phuc_2fa`, `session`, `yeu_cau_cap_lai_mk`, `audit_log` (kèm trigger chặn `UPDATE/DELETE/TRUNCATE` theo FR-021, NFR-011).
  - **Đầu ra:** `backend/src/biensoxe/models/{danh_muc.py,tai_khoan.py,audit.py}`, `backend/alembic/versions/0001_initial_schema.py`.
  - **Kiểm chứng:** `uv run alembic upgrade head` và `downgrade base` rồi `upgrade head` thành công trên DB test.
- [x] **T005** [FR-001, FR-002, FR-033, FR-034] Viết test integration (fail trước) cho lệnh `cli seed`: kiểm tra AC-1 (34 tỉnh/thành dùng "Thành phố/Tỉnh", không có "Tp"; 3.321 xã/phường/đặc khu đúng thứ tự và `loai_don_vi`), AC-2 (1 Admin `ADMINS` + 34 tỉnh + 3.321 xã, bắt buộc đổi mật khẩu lần đầu), AC-14 (mật khẩu lưu băm Argon2id, không có dạng rõ), AC-23 (86 `LoaiPT` STT 1–86 liên tục, 3 nền biển).
  - **Đầu ra:** `backend/tests/integration/test_seed.py`.
  - **Kiểm chứng:** Chạy `uv run pytest tests/integration/test_seed.py` báo fail do chưa có `cli seed`.
- [x] **T006** [FR-001, FR-002, FR-020, FR-033, FR-034] Triển khai `security/hashing.py` (Argon2id) và `cli.py seed` nạp 3 file CSV từ `data/` và khởi tạo idempotent 3.356 tài khoản (tận dụng pre-computed/parallel Argon2id cho mật khẩu mặc định với salt riêng mỗi tài khoản).
  - **Đầu ra:** `backend/data/*.csv`, `backend/src/biensoxe/security/hashing.py`, `backend/src/biensoxe/cli.py`.
  - **Kiểm chứng:** `uv run pytest tests/integration/test_seed.py` pass hoàn toàn (AC-1, AC-2, AC-14, AC-23).
- [x] **T007** [FR-003, FR-004, FR-023] Viết test integration (fail trước) cho `ScopeFilter` và API tạo/xem tài khoản phụ (`POST /api/v1/tai-khoan`, `GET /api/v1/tai-khoan`) theo AC-52: Admin tạo được cho tỉnh/xã bất kỳ; Tỉnh chỉ tạo được cho xã trực thuộc (tạo cho tỉnh hoặc xã tỉnh khác bị từ chối); Xã không có quyền; trùng tên đăng nhập bị từ chối; mật khẩu mặc định đúng theo vai trò, `bat_buoc_doi_mk=true`, có ghi `audit_log`.
  - **Đầu ra:** `backend/tests/integration/test_tai_khoan_phu.py`.
  - **Kiểm chứng:** Test fail đúng lý do (chưa có endpoint).
- [x] **T008** [FR-003, FR-004, FR-021, FR-023] Triển khai `repositories/scope.py` (`ScopeFilter`), `services/audit.py`, `services/tai_khoan.py` và router `api/tai_khoan.py`, `api/danh_muc.py` (đọc danh mục tỉnh, xã, loại PT, nền biển).
  - **Đầu ra:** `backend/src/biensoxe/repositories/scope.py`, `backend/src/biensoxe/services/{audit.py,tai_khoan.py}`, `backend/src/biensoxe/api/{tai_khoan.py,danh_muc.py}`.
  - **Kiểm chứng:** `uv run pytest tests/integration/test_tai_khoan_phu.py` pass (AC-52).

---

## Pha 2: US-2 (P1) — Xác thực, Chính sách mật khẩu, Đổi mật khẩu lần đầu, Khóa tự động & 2FA Admin

- [x] **T009** [FR-013] Viết unit test (fail trước) cho `domain/password_policy.py` theo AC-7: độ dài ≥10 (Admin ≥12), đủ 4 nhóm ký tự (hoa, thường, số, đặc biệt), không chứa tên đăng nhập, không trùng mật khẩu mặc định, không trùng 5 mật khẩu gần nhất, kiểm tra hết hạn 90 ngày và cảnh báo trước 7 ngày.
  - **Đầu ra:** `backend/tests/unit/test_password_policy.py`.
  - **Kiểm chứng:** Test fail do chưa triển khai `password_policy.py`.
- [x] **T010** [FR-013] Triển khai `domain/password_policy.py`.
  - **Đầu ra:** `backend/src/biensoxe/domain/password_policy.py`.
  - **Kiểm chứng:** `uv run pytest tests/unit/test_password_policy.py` pass (AC-7).
- [x] **T011** [FR-010, FR-011, FR-012, FR-013, FR-014, FR-019, FR-022] Viết test integration (fail trước) cho xác thực, phiên làm việc, đổi mật khẩu 4 bước, khóa tự động 30 phút và 2FA TOTP Admin (AC-3, AC-4, AC-5, AC-6, AC-8, AC-9 phần khóa tự động, AC-13, AC-16).
  - **Đầu ra:** `backend/tests/integration/test_auth.py`.
  - **Kiểm chứng:** Test fail do chưa có router `auth`.
- [x] **T012** [FR-010, FR-011, FR-012, FR-013, FR-014, FR-019, FR-020, FR-021, FR-022] Triển khai `security/{session.py,csrf.py,totp.py,ratelimit.py}`, `services/auth.py` và `api/auth.py` (cookie phiên + CSRF token, chặn mọi API nghiệp vụ khi `bat_buoc_doi_mk=true`, hết hạn mật khẩu >90 ngày hoặc Admin chưa bật TOTP; hết hạn phiên idle 30 phút).
  - **Đầu ra:** `backend/src/biensoxe/security/{session.py,csrf.py,totp.py,ratelimit.py}`, `backend/src/biensoxe/services/auth.py`, `backend/src/biensoxe/api/auth.py`.
  - **Kiểm chứng:** `uv run pytest tests/integration/test_auth.py` pass (AC-3..9, AC-13, AC-16).
- [x] **T013** [P] [FR-010, FR-011, FR-012, FR-019] Triển khai giao diện đăng nhập, đổi mật khẩu 4 bước, thiết lập/xác thực TOTP + hiển thị mã khôi phục cho Admin, cảnh báo mật khẩu sắp hết hạn và khung điều hướng theo vai trò.
  - **Đầu ra:** `frontend/src/features/auth/`, `frontend/src/components/Layout.tsx`.
  - **Kiểm chứng:** `npm run build` thành công, kiểm tra luồng đăng nhập & đổi mật khẩu.

---

## Pha 3: US-3 & US-4 (P1) — Phân tích biển số, Lập lô xã (Nhập tay & Import Excel), Kiểm tra trùng, Gửi & Đồng bộ

- [x] **T014** [FR-030, FR-031, FR-032, FR-034, FR-035, FR-038] Viết unit test + property-based test (`Hypothesis`) cho `domain/bien_so.py` theo AC-18, AC-19, AC-20, AC-21, AC-22, AC-53: tách `MaTinh`, `SeriChu` (kể cả `AA`, `A1`, `MĐ1`), chuẩn hóa `SeriSo` (`234.5` → `234.50`, `12.5` → `012.50`, từ chối `23.456`, từ chối `11A--234.56`), suy `LoaiPT`, `MauSac`, xác định cờ `ngoai_tinh`.
  - **Đầu ra:** `backend/tests/unit/test_bien_so.py`.
  - **Kiểm chứng:** Test fail do chưa có `domain/bien_so.py`.
- [x] **T015** [FR-030, FR-031, FR-032, FR-034, FR-035, FR-038] Triển khai `domain/bien_so.py`.
  - **Đầu ra:** `backend/src/biensoxe/domain/bien_so.py`.
  - **Kiểm chứng:** `uv run pytest tests/unit/test_bien_so.py` pass (AC-18..22, AC-53).
- [x] **T016** [FR-046, FR-065, FR-071, 4.I] Viết unit test (fail trước) cho 4 máy trạng thái trong `domain/`: `state_lo_xa.py` (J.1), `state_lo_dnm.py` (J.2), `state_lo_tinh.py` (J.3), `state_bien.py` (4.I, gồm `Thu hồi về xã` là trạng thái cuối), kiểm tra mọi cặp chuyển trạng thái hợp lệ và chặn mọi cặp ngoài sơ đồ (AC-31).
  - **Đầu ra:** `backend/tests/unit/test_state_machines.py`.
  - **Kiểm chứng:** Test fail do chưa có các module `state_*.py`.
- [x] **T017** [FR-046, FR-065, FR-071, 4.I] Triển khai `domain/{state_lo_xa.py,state_lo_dnm.py,state_lo_tinh.py,state_bien.py}`.
  - **Đầu ra:** `backend/src/biensoxe/domain/{state_lo_xa.py,state_lo_dnm.py,state_lo_tinh.py,state_bien.py}`.
  - **Kiểm chứng:** `uv run pytest tests/unit/test_state_machines.py` pass (AC-31).
- [x] **T018** [FR-036, FR-038, FR-040..FR-048, FR-062..FR-068, NFR-010] Viết migration Alembic số 2 và SQLAlchemy models cho `lo`, `lo_lich_su`, `bien` (có partial unique index `ux_bien_giu_cho` trên `(tinh_ma, bien_so_day_du) WHERE giu_cho`, cờ `ngoai_tinh`, `dat_lai_xac_nhan`), `ban_giao` (đủ `so_bien_ban`, `nguoi_nhan`, `chuc_vu`, `ngay_nhan`), `bien_lich_su`, `import_job`, `sync_job`.
  - **Đầu ra:** `backend/src/biensoxe/models/{lo.py,bien.py,jobs.py}`, `backend/alembic/versions/0002_lo_va_bien.py`.
  - **Kiểm chứng:** `uv run alembic upgrade head` thành công; kiểm tra các partial unique index trong PostgreSQL.
- [x] **T019** [FR-036, FR-038, FR-040..FR-046, FR-048, FR-090, FR-091] Viết test integration (fail trước) cho luồng lô xã: tạo/sửa/xóa lô và biển ở Khởi tạo, sinh Mã lô `{Số công văn}-{mã xã/phường}` ngay khi lưu (AC-26, AC-28, AC-30), kiểm tra tại chỗ `POST /bien/kiem-tra` (FR-090), tải mẫu & import `.xlsx` tất cả hoặc không + xuất báo cáo lỗi (AC-27), kiểm tra trùng trong lô / trong tỉnh / xác nhận đặt lại biển Đã trả hoặc Thu hồi về xã (AC-24), cảnh báo `ngoai_tinh` (AC-53), Gửi lô + đồng bộ + thử lại khi lỗi (AC-29) và lịch sử lô (AC-31).
  - **Đầu ra:** `backend/tests/integration/test_lo_xa.py`.
  - **Kiểm chứng:** Test fail do chưa có service/router lô xã và import.
- [x] **T020** [FR-036, FR-038, FR-040..FR-046, FR-048, FR-090, FR-091] Triển khai `services/{lo.py,bien.py,import_excel.py,sync.py}`, `workers/sync_worker.py` và router `api/{lo.py,bien.py,import_excel.py}`.
  - **Đầu ra:** `backend/src/biensoxe/services/{lo.py,bien.py,import_excel.py,sync.py}`, `backend/src/biensoxe/workers/sync_worker.py`, `backend/src/biensoxe/api/{lo.py,bien.py,import_excel.py}`.
  - **Kiểm chứng:** `uv run pytest tests/integration/test_lo_xa.py` pass (AC-24, AC-26..31, AC-53).
- [x] **T021** [P] [FR-040..FR-045, FR-048, FR-090, FR-091] Triển khai giao diện Xã/phường quản lý lô biển: danh sách lô, tạo/sửa lô, bảng biển 6 cột (virtualized), ô nhập tay kiểm tra tại chỗ hiển thị ngay `LoaiPT`, `MauSac`, `BienSoDayDu` và cảnh báo ngoại tỉnh, hộp thoại xác nhận đặt lại biển Đã trả/Thu hồi, import `.xlsx` + tải mẫu + tải báo cáo lỗi, nút Gửi lô (có hộp xác nhận FR-091), đồng bộ lại và xem lịch sử lô.
  - **Đầu ra:** `frontend/src/features/lo-xa/`.
  - **Kiểm chứng:** `npm run build` thành công.

---

## Pha 4: US-5, US-6 & US-10 (P1/P2) — Tỉnh duyệt lô xã, Cho phép điều chỉnh, Lô tỉnh & Lô đặt nhà máy

- [x] **T022** [FR-047, FR-049, FR-061..FR-065, FR-069, FR-071] Viết test integration (fail trước) cho:
  - Tỉnh duyệt lô xã từng lô hoặc hàng loạt (mỗi lô 1 transaction, AC-36), Từ chối kèm đánh dấu biển lỗi + tăng `so_lan_dat` khi gửi lại (AC-32);
  - Bật "Cho phép điều chỉnh" gỡ lô khỏi lô đặt nhà máy và đưa lô đặt nhà máy về Khởi tạo, cả xã và tỉnh đều sửa được, gửi lại / Hoàn tất điều chỉnh (AC-37);
  - Lô tỉnh: tạo, gửi duyệt, tự duyệt, tự từ chối, cho phép điều chỉnh, dùng chung không gian mã với lô đặt nhà máy (AC-38, AC-51);
  - Lô đặt nhà máy: chọn ≥1 lô xã/lô tỉnh Chấp nhận cùng tỉnh, bảng biển có cột `MÃ LÔ ĐẶT NHÀ MÁY` ở cuối, gửi duyệt, rút về, tự duyệt, hủy lô trả lô thành phần về Chấp nhận và giữ mã lô đã Hủy không cho dùng lại theo G-15 (AC-38, AC-39, AC-43).
  - **Đầu ra:** `backend/tests/integration/test_tinh_duyet_va_lo_dnm.py`.
  - **Kiểm chứng:** Test fail do chưa triển khai đầy đủ các hành động của tỉnh trên lô.
- [x] **T023** [FR-047, FR-049, FR-061..FR-065, FR-069, FR-071] Triển khai các nghiệp vụ tỉnh duyệt lô xã (đơn & hàng loạt), từ chối, cho phép điều chỉnh, lô tỉnh và lô đặt nhà máy trong `services/lo.py` và `api/lo.py`.
  - **Đầu ra:** Cập nhật `backend/src/biensoxe/services/lo.py`, `backend/src/biensoxe/api/lo.py`.
  - **Kiểm chứng:** `uv run pytest tests/integration/test_tinh_duyet_va_lo_dnm.py` pass (AC-32, AC-36..39, AC-43, AC-51).
- [x] **T024** [P] [FR-047, FR-049, FR-061..FR-065, FR-069, FR-071, FR-091] Triển khai giao diện Tỉnh/thành: danh sách lô xã trực thuộc (duyệt đơn/hàng loạt, từ chối + đánh dấu biển lỗi, bật/hoàn tất điều chỉnh), quản lý lô tỉnh, quản lý lô đặt nhà máy (chọn lô thành phần, bảng biển có cột `MÃ LÔ ĐẶT NHÀ MÁY`, gửi duyệt, tự duyệt, rút về, hủy).
  - **Đầu ra:** `frontend/src/features/lo-tinh/`, `frontend/src/features/lo-dnm/`.
  - **Kiểm chứng:** `npm run build` thành công.

---

## Pha 5: US-7, US-8 & US-13 (P2/P3) — Đặt thành công, Điều chỉnh sau đặt, Kho tỉnh, Import nhà máy, Chuyển xã, Trả/Thu hồi/Hủy biển

- [x] **T025** [FR-052, FR-053, FR-054, FR-066, FR-067, FR-068, FR-070, FR-072] Viết test integration (fail trước) cho:
  - Xác nhận Đặt thành công và Điều chỉnh sau Đặt thành công (thêm biển vào lô thành phần, sửa biển Đã đặt, bắt buộc xác nhận + lý do, chặn sửa biển đã nhập kho/chuyển xã, AC-40);
  - Nhập kho tỉnh cả lô hoặc từng biển (tiến độ n/m, AC-41) và import file `.xlsx` nhà máy trả về tất cả hoặc không + báo cáo lỗi (AC-54);
  - Chuyển xã từng phần bắt buộc đủ 4 trường (số biên bản, người nhận, chức vụ, ngày nhận ≤ hiện tại), lô tỉnh không chuyển xã (AC-42);
  - Xã xem biển đã nhận, trả biển cho dân (`Đã trả` + ngày giờ ≤ hiện tại, không lưu dữ liệu công dân, AC-34); cũng áp dụng trục giao cho biển của lô tỉnh đang `Tồn kho tỉnh` (G-6);
  - Xã thu hồi biển (`Đã trả` → `Thu hồi về xã` là trạng thái cuối, giải phóng `BienSoDayDu` để đặt lại có xác nhận) và xã/tỉnh hủy biển kèm lý do (AC-35, AC-44).
  - **Đầu ra:** `backend/tests/integration/test_kho_va_vong_doi_bien.py`.
  - **Kiểm chứng:** Test fail do chưa có `services/kho.py` và các endpoint kho/trả/thu hồi/hủy.
- [x] **T026** [FR-052, FR-053, FR-054, FR-066, FR-067, FR-068, FR-070, FR-072] Triển khai `services/kho.py`, mở rộng `services/{bien.py,import_excel.py}` và router `api/{kho.py,bien.py}`.
  - **Đầu ra:** `backend/src/biensoxe/services/kho.py`, `backend/src/biensoxe/api/kho.py`, cập nhật `bien.py`, `import_excel.py`.
  - **Kiểm chứng:** `uv run pytest tests/integration/test_kho_va_vong_doi_bien.py` pass (AC-34, AC-35, AC-40..42, AC-44, AC-54).
- [x] **T027** [P] [FR-052, FR-053, FR-054, FR-066, FR-067, FR-068, FR-070, FR-072, FR-091] Triển khai giao diện Kho tỉnh (điều chỉnh sau đặt, nhập kho chọn biển / import file nhà máy trả về, chuyển xã từng phần với 4 trường biên bản, trả/hủy biển lô tỉnh) và giao diện Xã quản lý biển đã nhận (trả biển từng biển/hàng loạt, thu hồi, hủy biển).
  - **Đầu ra:** `frontend/src/features/kho-tinh/`, `frontend/src/features/bien-xa/`.
  - **Kiểm chứng:** `npm run build` thành công.

---

## Pha 6: US-9, US-11, US-12, US-14 & US-15 (P2/P3) — Tra cứu, Quản trị Admin, Audit log, Danh mục & Báo cáo

- [x] **T028** [FR-015, FR-016, FR-017, FR-018, FR-021, FR-037, FR-038] Viết test integration (fail trước) cho chức năng quản trị của Admin:
  - Khóa thủ công (kèm lý do, hủy phiên ngay), mở khóa, đặt lại mật khẩu mặc định, hàng đợi quên mật khẩu có giới hạn tần suất (AC-9, AC-10, AC-11, AC-12);
  - Tra cứu và xuất file `audit_log`, đảm bảo không sửa/xóa được (AC-15);
  - Quản lý danh mục `LoaiPT`, `nen_bien`, `ma_bien_tinh` (thêm, sửa, ngừng sử dụng; chặn xóa/đổi mục đã được biển tham chiếu, AC-25, AC-53).
  - **Đầu ra:** `backend/tests/integration/test_admin_va_danh_muc.py`.
  - **Kiểm chứng:** Test fail do chưa triển khai đầy đủ endpoint Admin & quản lý danh mục.
- [x] **T029** [FR-015, FR-016, FR-017, FR-018, FR-021, FR-037, FR-038] Triển khai các endpoint quản trị tài khoản, quên mật khẩu, audit log (lọc + xuất `.xlsx`) và quản lý danh mục trong `services/{tai_khoan.py,audit.py,danh_muc.py}` và `api/{tai_khoan.py,audit.py,danh_muc.py}`, kèm lệnh `cli reset-admin` ghi audit log (FR-018).
  - **Đầu ra:** `backend/src/biensoxe/services/danh_muc.py`, `backend/src/biensoxe/api/audit.py`, cập nhật `tai_khoan.py`, `danh_muc.py`, `cli.py`.
  - **Kiểm chứng:** `uv run pytest tests/integration/test_admin_va_danh_muc.py` pass (AC-9..12, AC-15, AC-25).
- [x] **T030** [FR-023, FR-050, FR-051, FR-060, FR-080, FR-081, FR-082] Viết test integration (fail trước) cho Tra cứu (gợi ý từ ký tự thứ 2, lọc kết hợp theo Mã lô, `BienSoDayDu`, `SeriChu`, `DauSo`, `LoaiPT`, `MaTinh`, xã, trạng thái lô, tình trạng biển, `ngoai_tinh` đúng phạm vi quyền, AC-33) và 5 báo cáo R1–R5 + xuất `.xlsx` khớp số liệu tra cứu (AC-45).
  - **Đầu ra:** `backend/tests/integration/test_tra_cuu_va_bao_cao.py`.
  - **Kiểm chứng:** Test fail do chưa có `services/{tra_cuu.py,bao_cao.py}`.
- [x] **T031** [FR-023, FR-050, FR-051, FR-060, FR-080, FR-081, FR-082, NFR-012, NFR-016] Triển khai `services/{tra_cuu.py,bao_cao.py}` (dùng `xlsxwriter` `constant_memory` hỗ trợ Unicode tiếng Việt đầy đủ) và router `api/{tra_cuu.py,bao_cao.py}`.
  - **Đầu ra:** `backend/src/biensoxe/services/{tra_cuu.py,bao_cao.py}`, `backend/src/biensoxe/api/{tra_cuu.py,bao_cao.py}`.
  - **Kiểm chứng:** `uv run pytest tests/integration/test_tra_cuu_va_bao_cao.py` pass (AC-33, AC-45).
- [x] **T032** [P] [FR-015..018, FR-021, FR-037, FR-038, FR-050, FR-060, FR-080..082] Triển khai giao diện Tra cứu (gợi ý + lọc dần + xuất Excel cho mọi vai trò), giao diện Báo cáo R1–R5 + xuất Excel, và giao diện Admin (quản lý tài khoản, quên mật khẩu, audit log, danh mục `LoaiPT`/`nen_bien`/`ma_bien_tinh`).
  - **Đầu ra:** `frontend/src/features/{tra-cuu,bao-cao,admin}/`.
  - **Kiểm chứng:** `npm run build` thành công.

---

## Pha cuối: Kiểm thử Đồng thời, Bảo mật, Hiệu năng, Vận hành & Hoàn thiện

- [x] **T033** [FR-023, NFR-009, NFR-010, NFR-014] Viết và chạy bộ test Đồng thời (AC-49: 2 xã cùng tỉnh gửi đồng thời 1 biển → đúng 1 thành công; 2 lô cùng Số công văn đồng thời → đúng 1 được tạo) và ma trận Bảo mật phân quyền theo phạm vi (AC-17: Xã/Tỉnh/Admin truy cập ngoài phạm vi hoặc Admin gọi API ghi nghiệp vụ đều bị chặn 403/404; AC-14: không lộ mật khẩu trong DB/log).
  - **Đầu ra:** `backend/tests/security/test_scope_matrix.py`, `backend/tests/integration/test_concurrency.py`.
  - **Kiểm chứng:** `uv run pytest tests/security/ tests/integration/test_concurrency.py` pass (AC-14, AC-17, AC-49).
- [x] **T034** [NFR-001..004, NFR-011, NFR-016] Viết script benchmark/kiểm thử hiệu năng (`backend/tests/perf/`) và lệnh `cli create-partitions` cho `audit_log`; kiểm chứng thời gian truy vấn/import 5.000 dòng/duyệt 200 lô/xuất `.xlsx` (AC-47).
  - **Đầu ra:** `backend/tests/perf/test_performance.py`, cập nhật `backend/src/biensoxe/cli.py`.
  - **Kiểm chứng:** Chạy `uv run pytest tests/perf/test_performance.py` đạt ngưỡng thời gian.
- [x] **T035** [NFR-005, NFR-006, NFR-008] Tạo bộ công cụ vận hành trong `ops/`: script sao lưu/khôi phục `pg_dump` (`ops/backup.ps1`, `ops/restore-runbook.md`), cấu hình reverse proxy TLS mẫu (`ops/Caddyfile`), chạy thử sao lưu & khôi phục trên DB thử và ghi biên bản vào `ops/restore-log.md` (AC-48).
  - **Đầu ra:** `ops/{backup.ps1,restore-runbook.md,restore-log.md,Caddyfile}`.
  - **Kiểm chứng:** Chạy thử `backup.ps1` và khôi phục vào DB thử thành công, có `ops/restore-log.md` (AC-48).
- [x] **T036** [NFR-007, NFR-009, NFR-012, NFR-013, FR-090, FR-091] Chạy kiểm thử E2E giao diện (AC-46, AC-50), quét bảo mật (`bandit`, `npm audit`), cập nhật `README.md` (mục đích, kiến trúc, cài đặt, chạy, test) và đối chiếu toàn bộ AC-1..AC-54 vào bảng Kết quả kiểm chứng bên dưới.
  - **Đầu ra:** `README.md`, `frontend/e2e/`, bảng Kết quả kiểm chứng trong `tasks.md`.
  - **Kiểm chứng:** Toàn bộ test backend + frontend build + E2E pass.

---

## Kết quả kiểm chứng

| Tiêu chí | Yêu cầu | Kết quả | Bằng chứng |
|---|---|---|---|
| AC-1 | FR-001 | PASS | `tests/integration/test_seed.py` (34 tỉnh/thành, 3.321 xã/phường/đặc khu, chuẩn hóa "Thành phố", phân loại `Tỉnh`/`Thành phố`, `Xã`/`Phường`/`Đặc khu`) |
| AC-2 | FR-002, FR-003 | PASS | `tests/integration/test_seed.py` (1 `ADMINS` + 34 `TINH` + 3.321 `XA` = 3.356 tài khoản, `bat_buoc_doi_mk=true`) |
| AC-3 | FR-010, FR-011 | PASS | `tests/integration/test_auth.py::test_login_first_time_and_four_step_password_change_ac3_ac5_ac6` |
| AC-4 | FR-010 | PASS | `tests/integration/test_auth.py::test_login_invalid_credentials_and_auto_lock_ac4_ac9` (thông báo đồng nhất, không lộ tài khoản tồn tại) |
| AC-5 | FR-012 | PASS | `tests/integration/test_auth.py::test_login_first_time_and_four_step_password_change_ac3_ac5_ac6` |
| AC-6 | FR-012 | PASS | `tests/integration/test_auth.py::test_wrong_current_password_revokes_session_after_5_attempts_ac6` |
| AC-7 | FR-013 | PASS | `tests/unit/test_password_policy.py` (độ dài ≥10/12, 4 nhóm ký tự, không chứa username/mặc định, lịch sử 5 mật khẩu) |
| AC-8 | FR-013 | PASS | `tests/integration/test_auth.py::test_password_expiry_90_days_and_warning_7_days_ac8` |
| AC-9 | FR-014, FR-016 | PASS | `tests/integration/test_auth.py` (khóa tự động 5 lần sai / 30 phút) & `tests/integration/test_admin_va_danh_muc.py` (Admin mở khóa) |
| AC-10 | FR-015 | PASS | `tests/integration/test_admin_va_danh_muc.py::test_admin_lock_unlock_reset_password_forgot_queue_and_cli_reset_ac9_ac10_ac11_ac12` |
| AC-11 | FR-017 | PASS | `tests/integration/test_admin_va_danh_muc.py` (đặt lại mật khẩu mặc định, bật `bat_buoc_doi_mk`, hủy phiên) |
| AC-12 | FR-018 | PASS | `tests/integration/test_admin_va_danh_muc.py` (hàng đợi quên mật khẩu, duyệt/từ chối, `cli reset-admin`) |
| AC-13 | FR-019 | PASS | `tests/integration/test_auth.py::test_admin_totp_2fa_and_recovery_codes_ac13` |
| AC-14 | FR-020 | PASS | `tests/unit/test_config_and_logging.py` & `tests/security/test_scope_matrix.py` (băm Argon2id, scrubbing log) |
| AC-15 | FR-021 | PASS | `tests/integration/test_admin_va_danh_muc.py::test_audit_log_query_export_and_immutability_ac15` (trigger chặn UPDATE/DELETE/TRUNCATE) |
| AC-16 | FR-022 | PASS | `tests/integration/test_auth.py::test_session_idle_timeout_30_minutes_ac16` |
| AC-17 | FR-023, FR-004 | PASS | `tests/security/test_scope_matrix.py::test_scope_matrix_cross_unit_and_admin_readonly_ac17` |
| AC-18 | FR-030..032 | PASS | `tests/unit/test_bien_so.py` (tách `MaTinh`, `SeriChu` `A`/`AA`/`A1`/`MĐ1`, `SeriSo`, `DauSo`, suy `LoaiPT`) |
| AC-19 | FR-031, FR-032 | PASS | `tests/unit/test_bien_so.py` (chặn `SeriChu` không thuộc danh mục hoặc có `--`) |
| AC-20 | FR-031 | PASS | `tests/unit/test_bien_so.py` (chặn cấu trúc sai `23.456`, thiếu dấu `-` hoặc `.`) |
| AC-21 | FR-034 | PASS | `tests/unit/test_bien_so.py` (3 nền biển mặc định `TRẮNG`, `VÀNG`, `XANH`, chặn để trống) |
| AC-22 | FR-035, FR-042 | PASS | `tests/unit/test_bien_so.py` (`234.5` → `234.50`, `12.5` → `012.50`, property test Hypothesis) |
| AC-23 | FR-033 | PASS | `tests/integration/test_seed.py` (nạp đầy đủ 86 mục `LoaiPT` và 3 mục `nen_bien`) |
| AC-24 | FR-036 | PASS | `tests/integration/test_lo_xa.py` (chặn trùng trong lô/tỉnh, cho đặt lại biển `Đã hủy`, xác nhận đặt lại biển `Đã trả`/`Thu hồi về xã`) |
| AC-25 | FR-037, FR-033 | PASS | `tests/integration/test_admin_va_danh_muc.py::test_catalog_management_loai_pt_nen_bien_ma_bien_tinh_ac25_ac53` |
| AC-26 | FR-040, FR-041 | PASS | `tests/integration/test_lo_xa.py` & `frontend/src/features/lo-xa/LoXaPage.tsx` (bảng 6 cột chuẩn) |
| AC-27 | FR-042 | PASS | `tests/integration/test_lo_xa.py` (import `.xlsx` tất cả hoặc không, xuất báo cáo lỗi `.xlsx`, chặn `.xls`/macro) |
| AC-28 | FR-043 | PASS | `tests/integration/test_lo_xa.py` (chỉ sửa/xóa ở `Khởi tạo`, `Từ chối`, `Cho phép điều chỉnh`) |
| AC-29 | FR-044 | PASS | `tests/integration/test_lo_xa.py` (Gửi → `Đã gửi` → đồng bộ → `Chờ phê duyệt`, thử lại khi lỗi đồng bộ) |
| AC-30 | FR-045 | PASS | `tests/integration/test_lo_xa.py` (Mã lô `{Số công văn}-{mã xã/phường}` sinh ngay khi lưu, bất biến từ khi Gửi) |
| AC-31 | FR-046, FR-048 | PASS | `tests/unit/test_state_machines.py` & `tests/integration/test_lo_xa.py` (mọi chuyển trạng thái ngoài sơ đồ bị chặn, lưu `lo_lich_su`) |
| AC-32 | FR-047 | PASS | `tests/integration/test_tinh_duyet_va_lo_dnm.py` (Từ chối đánh dấu biển lỗi, gửi lại tăng `so_lan_dat`) |
| AC-33 | FR-050, FR-060 | PASS | `tests/integration/test_tra_cuu_va_bao_cao.py::test_tra_cuu_goi_y_combined_filters_scope_and_xlsx_export_ac33` |
| AC-34 | FR-052, FR-053 | PASS | `tests/integration/test_kho_va_vong_doi_bien.py::test_chuyen_xa_tra_bien_thu_hoi_and_huy_bien_ac34_ac35_ac42_ac44` |
| AC-35 | FR-054 | PASS | `tests/integration/test_kho_va_vong_doi_bien.py` (`Thu hồi về xã` là trạng thái cuối, giải phóng `BienSoDayDu`; hủy biển kèm lý do) |
| AC-36 | FR-061 | PASS | `tests/integration/test_tinh_duyet_va_lo_dnm.py` (duyệt hàng loạt mỗi lô 1 transaction độc lập) |
| AC-37 | FR-049 | PASS | `tests/integration/test_tinh_duyet_va_lo_dnm.py` (Cho phép điều chỉnh gỡ khỏi lô ĐNM, đưa lô ĐNM về `Khởi tạo`, Hoàn tất điều chỉnh) |
| AC-38 | FR-062..064 | PASS | `tests/integration/test_tinh_duyet_va_lo_dnm.py` (Lô đặt nhà máy gom lô xã/lô tỉnh `Chấp nhận`, bảng biển có cột `MÃ LÔ ĐẶT NHÀ MÁY`) |
| AC-39 | FR-065 | PASS | `tests/integration/test_tinh_duyet_va_lo_dnm.py` (Gửi duyệt, Rút về `Khởi tạo`, Tự duyệt `Chấp nhận`) |
| AC-40 | FR-066 | PASS | `tests/integration/test_kho_va_vong_doi_bien.py::test_dat_thanh_cong_post_order_adjustment_nhap_kho_and_factory_import_ac40_ac41_ac54` |
| AC-41 | FR-067 | PASS | `tests/integration/test_kho_va_vong_doi_bien.py` (nhập kho từng biển / cả lô, tiến độ n/m, chuyển `Đã nhập kho`) |
| AC-42 | FR-068 | PASS | `tests/integration/test_kho_va_vong_doi_bien.py` (chuyển xã từng phần bắt buộc đủ 4 trường biên bản, lô tỉnh không chuyển xã) |
| AC-43 | FR-069 | PASS | `tests/integration/test_tinh_duyet_va_lo_dnm.py` (Hủy lô ĐNM trả lô con về `Chấp nhận`, giữ mã lô đã hủy theo G-15) |
| AC-44 | FR-070 | PASS | `tests/integration/test_kho_va_vong_doi_bien.py` (Tỉnh hủy biển `Đã đặt` / `Tồn kho tỉnh` chưa trả kèm lý do, giải phóng số) |
| AC-45 | FR-080..082 | PASS | `tests/integration/test_tra_cuu_va_bao_cao.py::test_five_reports_r1_to_r5_and_xlsx_export_matching_counts_ac45` |
| AC-46 | FR-090, FR-091 | PASS | `frontend/src/components/ConfirmModal.tsx`, `frontend/src/features/lo-xa/LoXaPage.tsx`, `frontend/e2e/ui_smoke.spec.ts` |
| AC-47 | NFR-001..004, NFR-016 | PASS | `tests/perf/test_performance.py::test_audit_partitions_and_performance_thresholds_ac47_ac50` |
| AC-48 | NFR-006 | PASS | `tests/perf/test_performance.py::test_backup_and_restore_drill_ac48` & `ops/restore-log.md` |
| AC-49 | NFR-010 | PASS | `tests/integration/test_concurrency.py::test_concurrent_submit_same_plate_and_concurrent_create_same_so_cv_ac49` |
| AC-50 | NFR-007..009, NFR-012 | PASS | `tests/security/test_scope_matrix.py`, `tests/perf/test_performance.py` (`MĐ1`, `Đặc khu`), `npm run build` |
| AC-51 | FR-062, FR-071 | PASS | `tests/integration/test_tinh_duyet_va_lo_dnm.py` (vòng đời Lô tỉnh, dùng chung không gian mã với Lô ĐNM) |
| AC-52 | FR-003 | PASS | `tests/integration/test_tai_khoan_phu.py` (Admin/Tỉnh tạo tài khoản phụ theo phạm vi, Xã bị chặn 403) |
| AC-53 | FR-038 | PASS | `tests/unit/test_bien_so.py`, `tests/integration/test_lo_xa.py`, `tests/integration/test_admin_va_danh_muc.py` |
| AC-54 | FR-072 | PASS | `tests/integration/test_kho_va_vong_doi_bien.py` (import file `.xlsx` nhà máy trả về tất cả hoặc không + báo cáo lỗi) |

