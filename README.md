# Phần mềm Quản lý Đặt và Cấp phát Biển số xe (34 Tỉnh/Thành)

Hệ thống nội bộ quản lý vòng đời đặt, phê duyệt, nhập kho nhà máy, bàn giao về xã/phường và cấp phát/thu hồi/hủy biển số xe cơ giới trên phạm vi **34 tỉnh/thành** và **3.321 xã/phường/đặc khu** (theo đặc tả `specs/001-quan-ly-bien-so-xe/`).

---

## 1. Kiến trúc & Công nghệ

- **Backend (`backend/`):** Python 3.12+, FastAPI, SQLAlchemy 2.0, Alembic, `psycopg` v3, `argon2-cffi`, `pyotp`, `cryptography`, `openpyxl`, `xlsxwriter` (`constant_memory=True`), `structlog` (JSON scrubbing chống lộ bí mật).
- **Cơ sở dữ liệu:** PostgreSQL 17 (`UTF8`, `timestamptz` UTC, hiển thị `UTC+7`), partial unique index giữ chỗ nguyên tử `ux_bien_giu_cho` trên `(tinh_ma, bien_so_day_du) WHERE giu_cho`, trigger bất biến `audit_log` và phân vùng lưu trữ ≥ 24 tháng.
- **Frontend (`frontend/`):** React + TypeScript + Vite, `@tanstack/react-query`, `@tanstack/react-virtual` (bảng ảo hóa 5.000 dòng), build trực tiếp vào `backend/static/` để phục vụ cùng nguồn gốc (same-origin) với cookie phiên `HttpOnly` + `X-CSRF-Token`.
- **Vận hành (`ops/`):** Script sao lưu/kiểm tra toàn vẹn `ops/backup.ps1`, quy trình khôi phục `ops/restore-runbook.md`, nhật ký diễn tập `ops/restore-log.md`, cấu hình mẫu Reverse Proxy TLS ≥ 1.2 `ops/Caddyfile`.

---

## 2. Cấu trúc Thư mục

```text
bien-so-xe/
├── backend/
│   ├── alembic/                # Migrations 0001 & 0002 (schema, partial indexes, triggers)
│   ├── data/                   # Danh mục CSV chuẩn (34 tỉnh, 3.321 xã, 86 LoaiPT, 3 nền biển)
│   ├── src/biensoxe/
│   │   ├── api/                # REST API /api/v1 (auth, tai_khoan, danh_muc, audit, lo, bien, import_excel, kho, tra_cuu, bao_cao)
│   │   ├── domain/             # Logic thuần: bien_so, password_policy, 4 máy trạng thái (lo_xa, lo_tinh, lo_dnm, bien)
│   │   ├── models/             # SQLAlchemy 2.0 ORM models
│   │   ├── repositories/       # ScopeFilter phân quyền phạm vi dữ liệu tập trung
│   │   ├── security/           # Argon2id, session cookie, CSRF, TOTP 2FA, rate limiter
│   │   ├── services/           # Nghiệp vụ transactional
│   │   ├── workers/            # Đồng bộ lô xã -> tỉnh có thử lại (exponential backoff)
│   │   ├── cli.py              # CLI: seed, reset-admin, create-partitions
│   │   └── main.py             # FastAPI app + CSP/Security headers + SPA static mount
│   └── tests/                  # Unit, Property-based (Hypothesis), Integration, Security, Concurrency, Perf tests
├── frontend/
│   ├── src/                    # Giao diện tiếng Việt theo vai trò (ADMIN, TINH, XA)
│   └── e2e/                    # Kịch bản kiểm thử giao diện E2E
├── ops/                        # Công cụ sao lưu pg_dump, runbook khôi phục, Caddyfile
└── specs/001-quan-ly-bien-so-xe/
    ├── spec.md                 # Đặc tả yêu cầu (FR-001..091, NFR-001..016, AC-1..54)
    ├── plan.md                 # Kế hoạch kiến trúc & kỹ thuật
    └── tasks.md                # Danh sách tác vụ & Bảng kết quả kiểm chứng
```

---

## 3. Cài đặt & Khởi chạy

### 3.1 Cấu hình biến môi trường
Sao chép `.env.example` thành `.env` và cập nhật các khóa bí mật:
```powershell
Copy-Item .env.example .env
```

### 3.2 Chạy Migration & Khởi tạo dữ liệu (34 tỉnh, 3.321 xã, 3.356 tài khoản)
```powershell
.\backend\.venv\Scripts\alembic.exe -c .\backend\alembic.ini upgrade head
.\backend\.venv\Scripts\python.exe -m biensoxe.cli seed
.\backend\.venv\Scripts\python.exe -m biensoxe.cli create-partitions
```

### 3.3 Build Giao diện Frontend & Khởi chạy Máy chủ
```powershell
npm.cmd --prefix .\frontend run build
.\backend\.venv\Scripts\uvicorn.exe biensoxe.main:app --host 127.0.0.1 --port 8000
```

---

## 4. Kiểm thử (Testing)

Chạy toàn bộ bộ kiểm thử tự động (Unit, Property-based, Integration, Security Matrix, Concurrency, Performance):
```powershell
.\backend\.venv\Scripts\pytest.exe .\backend\tests -q
```

---

## 5. Vận hành & Sao lưu

- **Sao lưu hằng ngày & kiểm tra toàn vẹn:**
  ```powershell
  powershell -ExecutionPolicy Bypass -File .\ops\backup.ps1 -Database biensoxe_dev
  ```
- **Khôi phục tài khoản Admin khi mất 2FA/mật khẩu (FR-018):**
  ```powershell
  .\backend\.venv\Scripts\python.exe -m biensoxe.cli reset-admin
  ```
