# Plan: Phần mềm quản lý đặt và cấp phát biển số xe

- **Spec:** [spec.md](./spec.md)
- **Trạng thái:** Đã duyệt (2026-10-28)
- **Ngày:** 2026-10-21 (cập nhật & duyệt: 2026-10-28)

## 1. Tóm tắt hướng tiếp cận

Ứng dụng web **một khối (modular monolith)**: backend **Python + FastAPI**, CSDL **PostgreSQL** (nguồn sự thật duy nhất),
frontend **React + TypeScript (Vite)** được build ra file tĩnh và phục vụ cùng origin với API.

Ba ý tưởng thiết kế quyết định toàn bộ plan:

1. **Máy trạng thái tường minh trong `domain/`** (lô xã, lô tỉnh, lô đặt nhà máy, biển): mọi chuyển trạng thái đi qua
   một hàm duy nhất, trong một transaction, có khóa dòng, tự ghi lịch sử và audit log (FR-046, FR-048, NFR-010).
2. **Tính duy nhất của biển do chính PostgreSQL bảo đảm** bằng *partial unique index* trên cờ `giu_cho` (xem §5.3), không
   dựa vào kiểm tra ở tầng ứng dụng, nên an toàn khi hai người thao tác đồng thời (NFR-010, AC-49).
3. **Phân quyền theo phạm vi dữ liệu ở một chỗ**: mọi truy vấn đi qua `ScopeFilter(user)`; ngoài phạm vi trả `404`
   (FR-023, FR-004, AC-17).

"Đồng bộ" xã → tỉnh (G-3) là thao tác trong cùng một CSDL, được chạy bằng hàng đợi việc trong DB có thử lại, để vẫn có
trạng thái *Đã gửi* khi lỗi (FR-044).

## 2. Bối cảnh kỹ thuật hiện có

| Hạng mục | Kết quả kiểm tra (2026-10-21) |
|---|---|
| Repo `bien-so-xe` | Chỉ có `.editorconfig`, `.gitignore` (đã loại `.env`, `.venv`, `node_modules`), `README.md` placeholder; chưa có commit/code |
| Rule workspace | Python dùng `uv` + venv theo dự án; Node dùng lockfile; Conventional Commits; không hardcode secret, dùng `.env`; mỗi dự án có `README.md` |
| `_templates/python`, `_templates/web` | Chỉ có khung tối giản (`conftest.py`, `main.py`, `tests/`; html/css/js trơn). Dùng lại quy ước `pytest`; không có gì khác đáng tái dùng |
| Công cụ trên máy | Python 3.13.5, uv 0.13.0, Node 22.14.0, npm 11.2.0, git 2.55 **có**; **Docker và PostgreSQL (`psql`) KHÔNG có** |
| Dữ liệu danh mục | 3 CSV UTF-8 trong [data/](./data/): đơn vị hành chính (3.321 xã), loại phương tiện (86), nền biển (3) |

> [!WARNING]
> Máy chưa có PostgreSQL lẫn Docker. Plan này cần một trong hai để chạy và kiểm thử (xem câu hỏi mở Q-1, §9).

## 3. Công nghệ & quyết định

| # | Quyết định | Lý do | Phương án đã loại | Phục vụ |
|---|---|---|---|---|
| D-01 | **PostgreSQL ≥ 16** | Cần partial unique index, transaction + `FOR UPDATE`, `SKIP LOCKED`, partition, index `*_pattern_ops` cho gợi ý theo tiền tố | SQLite (không đủ đồng thời); MySQL (partial index kém) | FR-036, NFR-001, NFR-010 |
| D-02 | **FastAPI + Pydantic v2**, Python 3.13, quản lý bằng `uv` | Theo rule workspace; kiểu rõ ràng; OpenAPI tự sinh làm hợp đồng cho frontend | Django (bạn đã chọn FastAPI; admin mặc định không hợp phân quyền theo phạm vi) | mọi FR |
| D-03 | **SQLAlchemy 2.x (sync) + psycopg 3 + Alembic** | Kiểm soát SQL/index chính xác; migration có phiên bản. Sync + threadpool đủ cho 1.000 phiên, đơn giản hơn async | async SQLAlchemy (phức tạp, lợi ích thấp ở quy mô này) | NFR-001, NFR-004, NFR-010 |
| D-04 | **argon2-cffi** (Argon2id, `m=19MiB,t=2,p=1` theo OWASP), salt riêng mỗi tài khoản | Thuật toán dành riêng cho mật khẩu | bcrypt (giới hạn 72 byte); SHA-x (cấm) | FR-020 |
| D-05 | **Phiên phía server** lưu trong bảng `session`; cookie `__Host-sid` (`HttpOnly; Secure; SameSite=Strict`), chỉ chứa token ngẫu nhiên (lưu băm SHA-256); CSRF bằng header `X-CSRF-Token` (double submit) | Hủy phiên tức thì khi khóa/đặt lại (FR-015, FR-017); hết hạn idle 30 phút | JWT (khó hủy tức thì) | FR-015, FR-017, FR-022, NFR-008, NFR-009 |
| D-06 | **pyotp** cho TOTP; bí mật TOTP mã hóa **Fernet** bằng khóa từ biến môi trường; mã khôi phục lưu băm | Chuẩn RFC 6238 | SMS/email OTP (ngoài phạm vi) | FR-019 |
| D-07 | **openpyxl (read_only, data_only)** để đọc import; **xlsxwriter (constant_memory)** để xuất và tạo file mẫu | Đọc theo luồng, bỏ công thức lấy giá trị; ghi nhanh cho 100.000 dòng | pandas (nặng, tự suy kiểu cột làm hỏng `BIỂN SỐ`) | FR-042, FR-081, NFR-002, NFR-016 |
| D-08 | **Frontend: React 19 + TypeScript + Vite + React Router + TanStack Query + TanStack Table (virtualized)**; CSS thuần với design tokens, không Tailwind | Bảng lớn, gợi ý, nhiều form kiểm tra tại chỗ; kiểu TS sinh từ OpenAPI | Server-rendered (khó làm gợi ý/kiểm tra tại chỗ mượt) | FR-050, FR-090, NFR-007, NFR-012 |
| D-09 | **Phục vụ frontend build bằng chính FastAPI** (cùng origin); TLS kết thúc ở reverse proxy (Caddy/nginx/IIS) | Không cần CORS, cookie `Strict` hoạt động, ít thành phần vận hành | SPA + API khác origin (thêm CORS/CSRF phức tạp) | NFR-008, NFR-009 |
| D-10 | **Hàng đợi đồng bộ trong DB** (`sync_job`, `SELECT … FOR UPDATE SKIP LOCKED`), worker là luồng nền trong cùng ứng dụng; thử lại lũy tiến | Không thêm broker; vẫn giữ *Đã gửi* khi lỗi | Celery/Redis (thừa); đồng bộ cứng trong request (mất ý nghĩa trạng thái *Đã gửi*) | FR-044, G-3 |
| D-11 | **Cấu hình bằng biến môi trường + `pydantic-settings`**; mọi ngưỡng ở NFR-015 là một khóa cấu hình (đổi + khởi động lại, không build lại) | Đúng "không cần phát hành lại" | Bảng cấu hình sửa trên giao diện (thêm quyền/audit, ngoài spec) | NFR-015 |
| D-12 | **Logging JSON có `request_id`**, bộ lọc che mật khẩu/token | Không lộ secret | print/log tự do | FR-020 |
| D-13 | **Kiểm thử:** `pytest` + `httpx`, `Hypothesis` cho bộ phân tích biển số, `Playwright` cho E2E (3 trình duyệt), `Locust` cho tải | Phủ AC theo §7 | k6 (chưa cài; Locust cài qua `uv`) | AC-47, AC-50 |

## 4. Kiến trúc & cấu trúc mã

```text
bien-so-xe/
├── README.md                      # mục đích, cài đặt, chạy, test (rule workspace)
├── backend/
│   ├── pyproject.toml, uv.lock
│   ├── alembic/versions/          # migration
│   ├── src/biensoxe/
│   │   ├── config.py              # Settings (NFR-015)
│   │   ├── db.py                  # engine, session, tx helper
│   │   ├── domain/                # THUẦN Python, không I/O: dễ test
│   │   │   ├── bien_so.py         # parse/chuẩn hóa/validate biển (FR-030..035)
│   │   │   ├── state_lo_xa.py     # bảng chuyển trạng thái J.1
│   │   │   ├── state_lo_tinh.py   # J.3
│   │   │   ├── state_lo_dnm.py    # J.2 (đặt nhà máy)
│   │   │   ├── state_bien.py      # tình trạng + giao (4.I)
│   │   │   └── password_policy.py # FR-013
│   │   ├── models/                # SQLAlchemy models (§5)
│   │   ├── repositories/          # truy vấn, luôn nhận ScopeFilter
│   │   ├── services/              # auth, lo, bien, kho, bao_cao, import_excel, audit, sync
│   │   ├── security/              # hashing, session, csrf, totp, ratelimit
│   │   ├── api/                   # routers /api/v1, dependencies (current_user, require_role)
│   │   ├── workers/sync_worker.py # D-10
│   │   ├── cli.py                 # seed, create-partitions, backup-check
│   │   └── main.py                # app factory, security headers, static SPA
│   ├── data/                      # 3 CSV danh mục dùng cho seed (copy từ specs/.../data)
│   └── tests/{unit,integration,security,perf}/
├── frontend/
│   ├── package.json, package-lock.json
│   └── src/{api,components,features,routes,styles}/
└── ops/                           # backup.ps1/.sh, restore-runbook.md, caddy/nginx mẫu, compose.yaml (tùy chọn)
```

Luồng một thao tác nghiệp vụ (ví dụ *Gửi lô*): `router` → `service` mở 1 transaction → khóa dòng `lo` (`FOR UPDATE`) →
`domain.state_*` kiểm tra hợp lệ → cập nhật biển/lô → ghi `lo_lich_su` + `audit_log` → commit → đẩy `sync_job`.
Không có logic nghiệp vụ trong router hay frontend; frontend chỉ hiển thị kết quả kiểm tra từ API (FR-090).

## 5. Mô hình dữ liệu

### 5.1 Danh mục & tài khoản (FR-001..004, FR-010..021, FR-033, FR-034, FR-037, FR-038)

| Bảng | Trường chính | Ràng buộc |
|---|---|---|
| `tinh` | `ma` char(2) PK, `ten`, `loai_don_vi` ('Tỉnh'/'Thành phố'), `stt` | 34 dòng, nạp từ CSV; suy `loai_don_vi` từ tiền tố tên (FR-001) |
| `xa_phuong` | `ma` char(8) PK, `ten`, `loai_don_vi` ('Xã'/'Phường'/'Đặc khu'), `tinh_ma` FK, `stt` | 3.321 dòng; giữ thứ tự `stt`; suy `loai_don_vi` từ tiền tố tên (FR-001) |
| `tai_khoan` | `id`, `ten_dang_nhap` unique, `vai_tro` (ADMIN/TINH/XA), `tinh_ma`, `xa_ma`, `mat_khau_hash`, `bat_buoc_doi_mk`, `mk_doi_luc`, `so_lan_sai`, `khoa_den`, `khoa_thu_cong`, `ly_do_khoa`, `totp_secret_enc`, `totp_da_bat`, `tao_boi` | CHECK: ADMIN không có đơn vị; TINH có `tinh_ma`; XA có `xa_ma` và `tinh_ma` khớp danh mục (FR-004); một đơn vị có thể có nhiều tài khoản (1 tự sinh + các tài khoản phụ theo FR-003) |
| `lich_su_mat_khau` | `tai_khoan_id`, `hash`, `tao_luc` | giữ 5 bản gần nhất (FR-013) |
| `ma_khoi_phuc_2fa` | `tai_khoan_id`, `hash`, `dung_luc` | ≥ 8 mã/lần cấp (FR-019) |
| `session` | `token_hash` PK, `tai_khoan_id`, `tao_luc`, `hoat_dong_luc`, `huy_luc`, `ip` | hết hạn idle 30 phút (FR-022) |
| `yeu_cau_cap_lai_mk` | `id`, `ten_dang_nhap`, `lien_he`, `trang_thai`, `xu_ly_boi`, `ly_do_tu_choi`, `tao_luc`, `ip` | giới hạn tần suất theo IP + tên (FR-018) |
| `loai_pt` | `id`, `stt`, `seri_chu` unique, `ten`, `dang_dung` | 86 dòng; không xóa/đổi nếu đã tham chiếu, chỉ `dang_dung=false` (FR-037) |
| `nen_bien` | `id`, `ten` unique, `mau_sac`, `dang_dung` | 3 dòng; `mau_sac` lấy từ danh mục, không nhập tay (FR-034) |
| `ma_bien_tinh` | `id`, `ma_bien` char(2), `tinh_ma` FK, `dang_dung` | `UNIQUE(ma_bien, tinh_ma)`; ban đầu rỗng; Admin quản lý để cảnh báo cờ `ngoai_tinh` (FR-038, G-16) |
| `audit_log` | `id`, `thoi_diem`, `nguoi_dung`, `hanh_dong`, `doi_tuong`, `ket_qua`, `ip`, `chi_tiet jsonb` | **chỉ INSERT**; partition theo tháng; xem §8 |

Seed (`cli seed`): 1 Admin (`ADMINS`, mật khẩu từ biến môi trường `ADMIN_INITIAL_PASSWORD`, không có trong repo; G-10), 34 tỉnh
(`Abc@!321`), 3.321 xã (`Abc@321`); mọi tài khoản `bat_buoc_doi_mk = true` (FR-002, FR-011). Seed idempotent, băm Argon2 chạy
song song nhiều tiến trình để xong trong vài phút.

### 5.2 Lô, biển (FR-038, FR-040..049, FR-052..054, FR-062..072, 4.I)

Dùng **một bảng `lo`** cho cả ba loại (cùng cấu trúc: công văn, mã, trạng thái, lịch sử) với cột `loai`:

| Bảng | Trường chính | Ràng buộc then chốt |
|---|---|---|
| `lo` | `id`, `loai` (XA/TINH/DAT_NHA_MAY), `tinh_ma`, `xa_ma` (null nếu không phải lô xã), `so_cong_van`, `so_cv_chuan` (trim + casefold), `ma_lo`, `trang_thai`, `lo_cha_id` (lô đặt nhà máy chứa nó), `so_lan_dat`, `ghi_chu`, `ly_do`, `tao_boi`, `tao_luc` | `UNIQUE(ma_lo)`; **`UNIQUE(xa_ma, so_cv_chuan) WHERE loai='XA'`**; **`UNIQUE(tinh_ma, so_cv_chuan) WHERE loai IN ('TINH','DAT_NHA_MAY')`** (không gian mã chung, kể cả lô đã *Hủy* không dùng lại mã theo G-15; FR-064, G-2); FK phức hợp `(lo_cha_id, tinh_ma) → lo(id, tinh_ma)` để lô thành phần luôn cùng tỉnh (FR-063); CHECK `trang_thai` thuộc tập hợp hợp lệ theo `loai`; `so_cong_van` dài 1-50 |
| `lo_lich_su` | `lo_id`, `tu`, `den`, `nguoi`, `luc`, `ly_do` | mỗi chuyển hợp lệ hoặc điều chỉnh sau đặt đúng 1 dòng (FR-048, FR-066, AC-31) |
| `bien` | `id`, `lo_id`, `stt`, `bien_so_day_du`, `ma_tinh_bien`, `seri_chu`, `seri_so`, `dau_so`, `loai_pt_id`, `nen_bien_id`, `ghi_chu`, `tinh_ma`, `xa_ma` (null nếu của tỉnh), `tinh_trang`, `giao` (`CHUA_TRA`/`DA_TRA`/`THU_HOI_VE_XA`), `ngay_gio_tra`, `ban_giao_id`, `ngay_nhap_kho`, `ly_do_huy`, `dat_lai_xac_nhan`, **`ngoai_tinh` boolean**, `loi_ly_do`, **`giu_cho` boolean** | xem 5.3; `giao` chỉ khác null khi `tinh_trang = TON_KHO_XA`, hoặc `TON_KHO_TINH` của lô loại TINH (G-6); `UNIQUE(lo_id, bien_so_day_du) WHERE tinh_trang <> 'DA_HUY'` (FR-036a) |
| `ban_giao` | `id`, `lo_xa_id`, `so_bien_ban`, `nguoi_nhan`, `chuc_vu`, `ngay_nhan` date, `tao_boi`, `tao_luc` | mỗi lần chuyển từng phần = 1 biên bản, bắt buộc đủ 4 trường biên bản/người nhận/chức vụ/ngày nhận (FR-068); `ngay_nhan ≤ hôm nay` |
| `bien_lich_su` | `bien_id`, `su_kien`, `tu`, `den`, `ly_do`, `nguoi`, `luc` | trả/thu hồi/hủy/nhập kho/chuyển xã/điều chỉnh sau đặt (FR-054, FR-066) |
| `import_job` | `id`, `tai_khoan_id`, `lo_id`, `loai_import` (TAO_BIEN/NHA_MAY), `trang_thai`, `loi jsonb`, `dong_hop_le jsonb`, `trung_da_tra jsonb`, `het_han_luc` | giữ tạm khi import cần xác nhận đặt lại (FR-036d) hoặc để tải báo cáo lỗi (FR-042, FR-072); dọn sau 15 phút |
| `sync_job` | `lo_id`, `lan_thu`, `lan_tiep_theo_luc`, `loi_cuoi` | FR-044; cảnh báo xã khi `Đã gửi` > 24 giờ (truy vấn) |

Chỉ mục phục vụ NFR-001 (5.000.000 biển): `bien(bien_so_day_du varchar_pattern_ops)`, `bien(tinh_ma, bien_so_day_du varchar_pattern_ops)`,
`bien(xa_ma, bien_so_day_du varchar_pattern_ops)`, `bien(lo_id)`, `bien(tinh_ma, seri_chu)`, `bien(tinh_ma, dau_so)`,
`bien(tinh_ma, tinh_trang)`, `bien(tinh_ma, ngoai_tinh)`, `bien(xa_ma, giao)`; gợi ý bằng tiền tố (`LIKE 'q%'`) và phân trang **keyset**. Chưa partition `bien`
(5 triệu dòng chưa cần); đo ở AC-47 rồi mới quyết (xem R-3).

### 5.3 Cờ `giu_cho` và tính duy nhất (FR-036, FR-054, FR-066, NFR-010)

`CREATE UNIQUE INDEX ux_bien_giu_cho ON bien (tinh_ma, bien_so_day_du) WHERE giu_cho;`

`giu_cho = true` nghĩa là biển *đang đặt hoặc trong kho* (đang "chiếm" số). Vòng đời cờ do `services/bien.py` đặt trong cùng transaction với chuyển trạng thái:

| Sự kiện | `giu_cho` của biển trong lô |
|---|---|
| Lưu biển vào lô Khởi tạo/Từ chối (hoặc biển thêm mới khi *Cho phép điều chỉnh*) | `false` (chỉ **cảnh báo** trùng, FR-036) |
| **Gửi** (xã) / **Gửi duyệt** (tỉnh) / **Hoàn tất điều chỉnh** | `true` cho mọi biển chưa hủy; vi phạm unique → **chặn**, trả danh sách biển trùng; **cả lô thất bại nguyên tử** (AC-24, AC-49) |
| Chấp nhận | giữ `true`; chạy thêm bước kiểm tra lại (phòng thủ, FR-061) |
| **Từ chối** | về `false` (lô Từ chối không tính là "đang đặt", FR-036) |
| *Cho phép điều chỉnh* | biển cũ giữ `true`; biển sửa số hoặc thêm mới `false` rồi `true` ở lần gửi lại |
| **Điều chỉnh sau Đặt thành công** (FR-066, G-18) | biển thêm mới vào thẳng *Đã đặt* với `giu_cho = true`; sửa biển *Đã đặt* giữ `giu_cho = true` (vi phạm unique → **chặn** như khi Gửi) |
| Trả biển (*Đã trả*) | `false` (số được đặt lại với xác nhận, FR-036d, G-5) |
| Thu hồi (*Đã trả* → *Thu hồi về xã*) | giữ `false` (*Thu hồi về xã* là trạng thái cuối và **giải phóng số** để đặt lại với xác nhận, FR-054, FR-036d, G-7, G-17) |
| Hủy biển / lô | `false` (giải phóng số, FR-054, FR-070) |

Cảnh báo/xác nhận **biển trùng với biển Đã trả hoặc Thu hồi về xã** (mục d): API lưu trả `409 DAT_LAI_CAN_XAC_NHAN` kèm danh sách; client gửi lại với
`xac_nhan_dat_lai=[...]`; biển mới ghi `dat_lai_xac_nhan=true` + audit log (G-12, G-17). Import đi qua `import_job` (hai bước).

### 5.4 Quy tắc phân tích biển số (`domain/bien_so.py`, FR-030..035, FR-038)

- Chuẩn hóa Unicode **NFC**, cắt khoảng trắng, chữ hoa (`Đ` giữ nguyên).
- Mẫu: `^(\d{2})([A-ZĐ0-9]{1,3})-(\d{1,3})\.(\d{1,2})$` → `MaTinh`, `SeriChu`, phần nguyên, phần thập phân. Dấu `-` chỉ để tách, `11A--234.56` không khớp (FR-031, AC-20).
- Đệm `SeriSo`: phần thập phân 1 chữ số → thêm `0` phải; phần nguyên < 3 chữ số → thêm `0` trái (FR-035, AC-22); `23.456` không hợp lệ.
- `SeriChu` tra trong `loai_pt` đang dùng → `LoaiPT`; nền biển chọn từ `nen_bien` đang dùng → `MauSac` (FR-032, FR-034).
- Kiểm tra `ngoai_tinh` (FR-038): nếu tỉnh quản lý có ít nhất 1 dòng `ma_bien_tinh` đang dùng và `MaTinh` không thuộc tập đó → đặt `ngoai_tinh = true` và trả cảnh báo (không chặn).
- Dựng `bien_so_day_du = MaTinh + SeriChu + "-" + SeriSo`; mọi API dùng chung hàm này (form nhập tay, import lô và import nhà máy trả về).

## 6. Giao diện (API / UI)

### 6.1 API REST `/api/v1` (JSON; lỗi theo mã máy + thông điệp tiếng Việt)

| Nhóm | Endpoint chính | Quyền | FR |
|---|---|---|---|
| Xác thực | `POST /auth/login`, `/auth/logout`, `/auth/doi-mat-khau` (4 bước FR-012), `/auth/totp/thiet-lap`, `/auth/totp/xac-nhan`, `POST /auth/quen-mat-khau` | công khai (có giới hạn tần suất) / đã đăng nhập | FR-010..014, 018, 019, 022 |
| Quản trị tài khoản | `GET /tai-khoan`, `POST /tai-khoan` (tạo tài khoản phụ FR-003); Admin: `POST /admin/tai-khoan/{id}/khoa`, `/mo-khoa`, `/dat-lai-mat-khau`, `GET/POST /admin/yeu-cau-cap-lai-mk` | `POST /tai-khoan`: ADMIN (mọi tỉnh/xã), TINH (xã trực thuộc); khóa/mở/đặt lại: ADMIN | FR-003, 015..018 |
| Audit | `GET /admin/audit-log`, `GET …/xuat` | ADMIN | FR-021 |
| Danh mục | `GET /danh-muc/{loai-pt, nen-bien, ma-bien-tinh, tinh, xa}`; Admin: `POST`, `PUT`, `POST …/ngung-dung` (cho `loai-pt`, `nen-bien`, `ma-bien-tinh`) | đọc: mọi vai trò; sửa: ADMIN | FR-001, 033, 034, 037, 038 |
| Lô | `GET/POST /lo`, `GET/PUT/DELETE /lo/{id}`, `POST /lo/{id}/gui`, `/dong-bo-lai`, `/chap-nhan`, `/chap-nhan-hang-loat`, `/tu-choi`, `/cho-phep-dieu-chinh`, `/hoan-tat-dieu-chinh`, `/rut-ve`, `/huy`, `/dat-thanh-cong` | theo loại lô + vai trò (§4.J spec) | FR-040..049, 061..071 |
| Biển trong lô | `GET/POST /lo/{id}/bien`, `PUT/DELETE /lo/{id}/bien/{bid}` (kể cả điều chỉnh sau *Đặt thành công* của tỉnh kèm `xac_nhan=true` + `ly_do`, FR-066), `POST /lo/{id}/import`, `POST /import/{token}/xac-nhan`, `GET /import/{token}/loi.xlsx`, `GET /import/file-mau.xlsx`, `POST /bien/kiem-tra` | xã/tỉnh chủ lô; tỉnh khi điều chỉnh sau đặt | FR-040..044, 066, 090 |
| Kho tỉnh | `POST /lo/{id}/nhap-kho`, `POST /lo/{id}/nhap-kho/import` (import file nhà máy trả về, FR-072), `POST /lo/{id}/chuyen-xa` (biên bản + người nhận + chức vụ + ngày nhận), `GET /kho` | TINH | FR-067, 068, 072 |
| Xã / biển | `GET /bien-da-nhan`, `POST /bien/tra`, `POST /bien/thu-hoi`, `POST /bien/huy` | XA; TINH với biển của lô tỉnh và hủy biển (FR-070) | FR-052..054, 070 |
| Tra cứu | `GET /bien/goi-y?q=…`, `GET /bien?…bộ lọc…` (có lọc `ngoai_tinh`) | mọi vai trò theo phạm vi (ADMIN chỉ đọc) | FR-038, 050, 060, 082 |
| Báo cáo | `GET /bao-cao/{r1..r5}`, `GET …/xuat` | mọi vai trò theo phạm vi | FR-080, 081 |

Thao tác không hoàn tác (`gui`, `chap-nhan-hang-loat`, `huy`, `chuyen-xa`, điều chỉnh sau `dat-thanh-cong`) yêu cầu trường `xac_nhan=true`; thiếu thì trả `409 CAN_XAC_NHAN` (FR-066, FR-091, hộp thoại ở UI).
Duyệt hàng loạt xử lý **mỗi lô một transaction** và trả kết quả từng lô, nên 1 lô lỗi không chặn 9 lô còn lại (AC-36).

### 6.2 Giao diện web (tiếng Việt, `dd/MM/yyyy HH:mm` UTC+7, tối thiểu 1366×768)

- **Chung:** đăng nhập, đổi mật khẩu 4 bước, thiết lập TOTP + mã khôi phục (Admin), khung điều hướng theo vai trò, cảnh báo hết hạn mật khẩu (≤ 7 ngày).
- **Admin:** tài khoản (tạo tài khoản phụ cho tỉnh/xã, khóa/mở/đặt lại), hàng đợi quên mật khẩu, audit log, danh mục `LoaiPT`/nền biển/`ma_bien_tinh`, tra cứu (chỉ đọc), báo cáo.
- **Tỉnh/thành:** tạo tài khoản phụ cho xã trực thuộc, lô xã trực thuộc (lọc, duyệt hàng loạt, từ chối + đánh dấu biển lỗi, cho phép điều chỉnh), **lô tỉnh**, **lô đặt nhà máy** (chọn lô thành phần, điều chỉnh sau Đặt thành công kèm xác nhận + lý do), kho (nhập kho chọn biển hoặc import file nhà máy trả về, chuyển xã từng phần kèm số biên bản + người nhận + chức vụ + ngày nhận), tra cứu (lọc cờ ngoại tỉnh), báo cáo.
- **Xã/phường:** lô của xã (bảng 6 cột, nhập tay/import, Gửi, theo dõi trạng thái và lịch sử), biển đã nhận, trả/thu hồi/hủy biển, tra cứu, báo cáo.
- Bảng biển ảo hóa (virtualized) cho 5.000 dòng; ô nhập biển hiển thị ngay `LoaiPT`, `MauSac`, `BienSoDayDu` và cảnh báo ngoại tỉnh nếu có (gọi `POST /bien/kiem-tra`, debounce) (FR-038, FR-090).
- Thiết kế: bảng màu HSL riêng; nhãn trạng thái dùng **đúng tên trong spec** (NFR-013).

## 7. Chiến lược kiểm thử

**Unit (không DB):** `domain/bien_so` (bảng ví dụ AC-18..22, AC-53 + Hypothesis: parse∘format ổn định), mọi bảng chuyển trạng thái (kiểm tra **mọi cặp trạng thái** ngoài sơ đồ bị chặn, AC-31), `password_policy` (AC-7).

**Integration (PostgreSQL thật):** transaction/nguyên tử, ràng buộc unique, `ScopeFilter`, đồng bộ + thử lại, import lô & import nhà máy trả về (tất cả hoặc không), báo cáo khớp danh sách tra cứu (AC-45).

**Đồng thời (NFR-010):** hai luồng cùng Gửi lô chứa một biển → đúng một thành công (AC-49); hai lô cùng Số công văn → đúng một được tạo.

**Bảo mật:** ma trận *vai trò × endpoint × đối tượng ngoài phạm vi* sinh tự động từ OpenAPI → mọi ô ngoài phạm vi phải 403/404 (AC-17, AC-52); quét `bandit`, `pip-audit`, `npm audit`; kiểm tra không có mật khẩu rõ trong DB/log (AC-14); kiểm tra CSRF, XSS (CSP), tiêm SQL.

**Kiểm chứng tiêu chí chấp nhận:**

| AC | Cách kiểm tra |
|---|---|
| AC-1, 2, 23, 52 | Test sau `seed`: đếm 34/3.321/86; cột loại đơn vị đúng; tên không chứa "Tp"; 1 + 34 + 3.321 tài khoản; tạo tài khoản phụ theo quyền Admin/Tỉnh/Xã (AC-52) |
| AC-3..13, 16 | Integration + giả lập thời gian (đóng băng đồng hồ) cho 30 phút/90 ngày; E2E luồng đổi mật khẩu |
| AC-14 | Quét DB dump và log tìm mật khẩu mặc định/rõ |
| AC-15 | Chuỗi thao tác rồi lọc audit; thử `UPDATE/DELETE` trên `audit_log` bằng vai trò ứng dụng phải bị từ chối |
| AC-17 | Ma trận bảo mật ở trên |
| AC-18..22, 24, 25, 53 | Unit + integration; AC-24 gồm ca biển *Đã trả*/*Thu hồi về xã* cần xác nhận; AC-53 kiểm tra cảnh báo và cờ `ngoai_tinh` |
| AC-26..32 | Integration luồng lô xã; test sơ đồ J.1 |
| AC-33..35 | Integration tra cứu (gợi ý, lọc kết hợp), trả/thu hồi (*Thu hồi về xã* là trạng thái cuối, giải phóng số)/hủy |
| AC-36..44, 51, 54 | Integration luồng lô tỉnh/lô đặt nhà máy/điều chỉnh sau đặt (AC-40)/nhập kho & import nhà máy trả về (AC-41, AC-54)/chuyển từng phần đủ 4 trường biên bản, người nhận, chức vụ, ngày nhận (AC-42) |
| AC-45, 46 | So số liệu báo cáo với đếm trực tiếp; E2E kiểm tra hộp xác nhận |
| AC-47 | `Locust` + sinh 5.000.000 biển bằng `COPY`; đo p95 tra cứu/danh sách, import 5.000 dòng, duyệt 200 lô, xuất 100.000 dòng. Cần môi trường riêng |
| AC-48 | Diễn tập khôi phục `pg_dump` trên DB thử, ghi thời gian vào `ops/restore-log.md` |
| AC-49 | Test đồng thời ở trên |
| AC-50 | Playwright (Chromium/Edge/Firefox) + quét OWASP ZAP baseline; đọc lại file xuất bằng thư viện xlsx để kiểm tra `MĐ1`, `Đặc khu` |

Ghi chú AC-36: nhờ chỉ mục `giu_cho` (§5.3), biển trùng bị chặn từ lúc Gửi nên bước kiểm tra lại khi Chấp nhận là phòng thủ; ca "biển trùng mới phát sinh" được kiểm bằng test đơn vị trên bộ kiểm tra dùng kho giả (không thể tạo dữ liệu vi phạm index trong DB thật).

## 8. Bảo mật & vận hành

- **Secrets:** `.env` (đã ignore): `DATABASE_URL`, `ADMIN_INITIAL_PASSWORD`, `TOTP_ENC_KEY`, `SESSION_SECRET`. Không đưa vào repo; cung cấp `.env.example` không có giá trị thật. Mật khẩu mặc định tỉnh/xã chỉ xuất hiện ở hằng số seed (đã công khai trong spec FR-002).
- **Vai trò DB (least privilege):** `biensoxe_owner` (migration) và `biensoxe_app` (chỉ `SELECT/INSERT/UPDATE/DELETE` trên bảng nghiệp vụ). `audit_log`: `app` chỉ có `INSERT, SELECT`; thêm trigger chặn `UPDATE/DELETE/TRUNCATE`; partition theo tháng, lưu ≥ 24 tháng (NFR-011); `cli create-partitions` chạy hằng tháng.
- **Chống lộ thông tin:** đăng nhập luôn chạy so khớp băm giả cho tên không tồn tại để thông báo và thời gian giống nhau (FR-010, AC-4); đối tượng ngoài phạm vi trả 404.
- **Giới hạn tần suất:** đăng nhập, quên mật khẩu, kiểm tra biển, import (bảng đếm trong DB theo IP + tên) (FR-014, FR-018).
- **Header:** CSP chặt (`default-src 'self'`), `X-Content-Type-Options`, `Referrer-Policy`, `frame-ancestors 'none'`; HSTS ở reverse proxy; TLS ≥ 1.2 (NFR-008).
- **Import an toàn:** chỉ nhận `.xlsx` (kiểm tra magic `PK` + cấu trúc zip), từ chối nếu có `vbaProject.bin`, giới hạn 5 MB, giới hạn kích thước giải nén (chống zip bomb), chỉ sheet đầu, đọc giá trị không đọc công thức.
- **Sao lưu (NFR-006):** `pg_dump` hằng ngày giữ ≥ 30 ngày + kiểm tra toàn vẹn; diễn tập khôi phục mỗi quý (runbook trong `ops/`). RPO ≤ 24 giờ.
- **Sẵn sàng 99,5% (NFR-005):** một nút ứng dụng + một PostgreSQL, tự khởi động lại bằng dịch vụ hệ điều hành; HA nhiều nút nằm ngoài plan này.
- **Triển khai/rollback:** migration Alembic có `downgrade`; trước mỗi lần nâng cấp chụp `pg_dump`; build frontend vào `backend/static`; rollback = triển khai lại bản trước + khôi phục dump nếu migration không đảo ngược được.
- **Múi giờ/Unicode:** lưu `timestamptz` (UTC), hiển thị UTC+7; DB `UTF8`; so khớp `bien_so_day_du` chính xác (không dùng collation bỏ dấu).

## 9. Rủi ro & giảm thiểu

| Rủi ro | Ảnh hưởng | Giảm thiểu |
|---|---|---|
| **R-1** Máy chưa có PostgreSQL/Docker | Không chạy/kiểm thử được | Đã chốt cài PostgreSQL 17 bản Windows (hoặc bản portable cục bộ) ở task thiết lập môi trường (T001) |
| **R-2** Băm Argon2 cho 3.355 tài khoản lâu (vài phút) và đăng nhập đồng loạt đầu giờ tốn CPU | Seed/đăng nhập chậm | Seed song song; băm trong threadpool; đo ở AC-47; chỉnh `t`/`m` bằng cấu hình nhưng không dưới mức OWASP |
| **R-3** Báo cáo gộp trên 5.000.000 biển vượt 3 giây | Vi phạm NFR-001 | Chỉ mục phủ; nếu đo không đạt, thêm bảng tổng hợp `bien_thong_ke` cập nhật trong cùng transaction, hoặc partition `bien` theo `tinh_ma` |
| **R-4** Một `BienSoDayDu` có thể có nhiều bản ghi (đặt lại sau *Đã trả*/*Thu hồi về xã*) làm tra cứu hiện nhiều kết quả cùng số | Gây nhầm | UI hiển thị rõ trạng thái/lô từng bản ghi, đưa bản ghi đang tồn tại lên trước |
| **R-5** Các chi tiết G-15…G-18 trong spec | Hành vi khác kỳ vọng | Đã được người dùng xác nhận ngày 2026-10-28 |
| **R-6** Đồng bộ chạy trong cùng DB nên gần như không thất bại; nhánh thử lại khó kiểm thử | Lỗi ẩn trong nhánh ít chạy | Bơm lỗi giả (fault injection) trong test AC-29; giữ worker đơn giản |
| **R-7** Cập nhật hàng loạt `giu_cho` cho lô 5.000 biển | Chờ khóa khi nhiều xã cùng gửi | Khóa theo lô; cập nhật bằng một câu lệnh; đo ở NFR-003/004 |
| **R-8** Mất `TOTP_ENC_KEY` hoặc mã khôi phục Admin | Admin bị khóa ngoài | Quy trình vận hành FR-018 + runbook; sao lưu khóa tách khỏi DB |

**Phương án đã loại (tổng hợp):** microservices, Celery/Redis, JWT, RLS của PostgreSQL (kiểm soát phạm vi ở `ScopeFilter` + ma trận test là đủ), event sourcing (lịch sử bằng bảng riêng là đủ), tách "lô tỉnh" và "lô đặt nhà máy" thành hai bảng (khó bảo đảm duy nhất mã dùng chung).

**Quyết định câu hỏi mở (đã chốt 2026-10-28)**

- **Q-1:** Cài PostgreSQL 17 bản Windows (hoặc bản portable chạy cục bộ) cho phát triển và kiểm thử.
- **Q-2:** Đã xác nhận G-15, G-16, G-17, G-18 trong `spec.md` §8.

## 10. Bảng truy vết

| Yêu cầu | Phần trong plan |
|---|---|
| FR-001, FR-004 | §5.1 (`tinh`, `xa_phuong`, `loai_don_vi`, CHECK `tai_khoan`), seed |
| FR-002, FR-003 | §5.1 seed, §6.1 `POST /tai-khoan` (Admin/Tỉnh tạo tài khoản phụ), D-04 |
| FR-010, FR-011, FR-012 | §6.1 `auth/*`, D-05, §8 |
| FR-013, FR-014 | §4 `password_policy`, §5.1 `lich_su_mat_khau`, `so_lan_sai`, `khoa_den` |
| FR-015, FR-016, FR-017 | §6.1 quản trị tài khoản, D-05 (hủy phiên) |
| FR-018 | §5.1 `yeu_cau_cap_lai_mk`, §6.1, §8 giới hạn tần suất |
| FR-019 | D-06, §5.1 `ma_khoi_phuc_2fa`, §6.2 |
| FR-020 | D-04, D-12 |
| FR-021 | §5.1 `audit_log`, §8 (append-only, partition) |
| FR-022 | D-05, §5.1 `session` |
| FR-023 | §1 (`ScopeFilter`), §4 `repositories`, §7 ma trận bảo mật |
| FR-030..FR-035 | §5.4, §5.2 `bien`, D-07 |
| FR-036 | §5.2 `bien`, §5.3 (`giu_cho`, unique index, xác nhận đặt lại cho *Đã trả*/*Thu hồi về xã*) |
| FR-037, FR-033, FR-034 | §5.1 `loai_pt`, `nen_bien`, §6.1 Danh mục |
| FR-038 | §5.1 `ma_bien_tinh`, §5.2 `bien.ngoai_tinh`, §5.4, §6.1 Danh mục & Tra cứu |
| FR-040, FR-041, FR-043 | §5.2 `lo`/`bien`, §6.1 Lô/Biển, §6.2 |
| FR-042 | D-07, §5.2 `import_job`, §8 Import an toàn, D-11 |
| FR-044 | D-10, §5.2 `sync_job`, §6.1 `gui`, `dong-bo-lai` |
| FR-045 | §5.2 `lo` (`ma_lo`, unique theo công văn), G-1/G-11 |
| FR-046, FR-048 | §1 (máy trạng thái), §4 `domain/state_*`, §5.2 `lo_lich_su` |
| FR-047, FR-049, FR-061 | §6.1 `tu-choi`, `cho-phep-dieu-chinh`, `chap-nhan*`; §5.3 vòng đời `giu_cho`; `lo.so_lan_dat` |
| FR-050, FR-051, FR-060 | §5.2 chỉ mục, §6.1 Tra cứu |
| FR-052, FR-053, FR-054 | §5.2 `ban_giao`, `bien.giao` (`THU_HOI_VE_XA` giải phóng số), `bien_lich_su`, §6.1 Xã |
| FR-062, FR-071 | §5.2 `lo` (loại TINH), `state_lo_tinh`, §6.1 |
| FR-063, FR-064, FR-065, FR-066, FR-069 | §5.2 `lo` (loại DAT_NHA_MAY, `lo_cha_id`, FK phức hợp, unique chung), `state_lo_dnm`, §5.3 & §6.1 điều chỉnh sau đặt |
| FR-067, FR-068, FR-072 | §6.1 Kho tỉnh (`nhap-kho`, `nhap-kho/import`, `chuyen-xa`), §5.2 `ban_giao` (đủ 4 trường), `import_job` |
| FR-070 | §6.1 Xã/biển (tỉnh hủy biển), §5.3 |
| FR-080, FR-081, FR-082 | §6.1 Báo cáo, D-07, §5.2 chỉ mục, R-3 |
| FR-090, FR-091 | §6.1 `bien/kiem-tra`, `xac_nhan`, §6.2 |
| NFR-001 | §5.2 chỉ mục, keyset, §7 AC-47, R-3 |
| NFR-002, NFR-016 | D-07, §7 AC-47 |
| NFR-003, NFR-004 | §6.1 (mỗi lô một transaction), D-03, R-7 |
| NFR-005, NFR-006 | §8 Sao lưu/Sẵn sàng, §7 AC-48 |
| NFR-007, NFR-012 | D-08, §6.2, §8 Múi giờ/Unicode |
| NFR-008, NFR-009 | D-05, D-09, §8 |
| NFR-010 | §1, §5.3, §5.2 unique, §7 Đồng thời |
| NFR-011 | §8 audit log partition ≥ 24 tháng |
| NFR-013 | §6.2 nhãn đúng spec, §5.2 `import_job` (báo cáo lỗi) |
| NFR-014 | §5.2 (không có trường dữ liệu công dân trong `bien`) |
| NFR-015 | D-11 |
