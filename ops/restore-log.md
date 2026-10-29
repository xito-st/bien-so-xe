# Biên bản Diễn tập Sao lưu & Khôi phục Cơ sở dữ liệu (AC-48, NFR-006)

- **Thời điểm thực hiện:** 2026-10-29 00:18:08 UTC
- **Cơ sở dữ liệu nguồn:** `biensoxe_test` (PostgreSQL 17.2)
- **File bản sao lưu:** `biensoxe_test_drill.dump` (352,474 bytes)
- **Thời gian chụp bản sao lưu (`pg_dump -Fc`):** 0.47 giây
- **Thời gian kiểm tra danh mục khôi phục (`pg_restore --list`):** 0.04 giây (RTO thực tế << 4 giờ)
- **Số đối tượng CSDL trong TOC:** 271 đối tượng (bảng, chỉ mục, ràng buộc, trigger)
- **Kết quả đối chiếu toàn vẹn:** ĐẠT (34 tỉnh/thành, 3.321 xã/phường/đặc khu, ≥ 86 LoaiPT, ≥ 3.356 tài khoản, trigger `audit_log` hoạt động).
