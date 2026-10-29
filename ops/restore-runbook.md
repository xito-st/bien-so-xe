# Quy trình Sao lưu & Khôi phục Thảm họa (Runbook — NFR-005, NFR-006, AC-48)

## 1. Mục tiêu Phục hồi
- **RPO (Recovery Point Objective):** ≤ 24 giờ (chạy `ops/backup.ps1` định kỳ hằng ngày lúc 01:00 UTC+7, lưu trữ tối thiểu 30 ngày).
- **RTO (Recovery Time Objective):** ≤ 4 giờ (khôi phục từ file `.dump` định dạng custom của `pg_dump` bằng `pg_restore`).
- **Độ sẵn sàng (NFR-005):** ≥ 99,5% trong giờ hành chính (07:00–19:00 UTC+7).

## 2. Sao lưu Hằng ngày & Kiểm tra Toàn vẹn
Chạy lệnh PowerShell:
```powershell
powershell -ExecutionPolicy Bypass -File .\ops\backup.ps1 -Database biensoxe_dev
```
Script thực hiện:
1. Chụp bản sao lưu nhất quán bằng `pg_dump -Fc` (không khóa đọc/ghi).
2. Kiểm tra tính toàn vẹn của file `.dump` ngay lập tức bằng `pg_restore --list`.
3. Xóa các bản sao lưu quá hạn (> 30 ngày).

## 3. Quy trình Khôi phục (Restore Drill / Thực chiến)
1. Tạo cơ sở dữ liệu đích (hoặc làm sạch cơ sở dữ liệu cần khôi phục):
   ```powershell
   createdb -h 127.0.0.1 -p 5432 -U postgres biensoxe_restore_drill
   ```
2. Khôi phục từ file `.dump` mới nhất:
   ```powershell
   pg_restore -h 127.0.0.1 -p 5432 -U postgres --clean --if-exists --no-owner -d biensoxe_restore_drill .\ops\backups\<file>.dump
   ```
3. Kiểm tra đối chiếu số lượng bản ghi:
   - `tinh` = 34
   - `xa_phuong` = 3.321
   - `loai_pt` ≥ 86
   - `tai_khoan` ≥ 3.356
   - Kiểm tra trigger bất biến của `audit_log`.
4. Ghi biên bản diễn tập vào `ops/restore-log.md`.

## 4. Khôi phục Tài khoản Admin khi mất 2FA hoặc Mật khẩu (FR-018, R-8)
Trên máy chủ ứng dụng, chạy lệnh CLI vận hành:
```powershell
.\backend\.venv\Scripts\python.exe -m biensoxe.cli reset-admin
```
Lệnh sẽ đặt lại mật khẩu khởi tạo của `ADMINS`, tắt cờ `totp_da_bat`, thu hồi toàn bộ phiên đang mở và ghi sự kiện `DAT_LAI_MAT_KHAU_ADMIN` vào `audit_log`.
