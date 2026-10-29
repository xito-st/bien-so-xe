/**
 * Kịch bản kiểm thử E2E giao diện người dùng (AC-46, AC-50, FR-090, FR-091):
 * - Đăng nhập -> Đổi mật khẩu 4 bước -> Thiết lập 2FA Admin
 * - Xã lập lô, kiểm tra biển tại chỗ (hiển thị LoaiPT, MauSac, BienSoDayDu, cảnh báo ngoại tỉnh)
 * - Hộp thoại xác nhận trên các thao tác không hoàn tác (Gửi lô, Duyệt hàng loạt, Hủy lô/biển, Chuyển xã)
 */
export const E2E_SCENARIOS = [
  "AC-3..6: Đăng nhập và đổi mật khẩu lần đầu 4 bước",
  "AC-18..22, FR-090: Nhập biển số kiểm tra tại chỗ và hiển thị chuẩn hóa",
  "AC-46, FR-091: Hộp thoại xác nhận trước khi Gửi lô, Chấp nhận hàng loạt, Hủy, Chuyển xã",
  "AC-50, NFR-012: Hiển thị và xuất Excel tiếng Việt có dấu (MĐ1, Đặc khu) và múi giờ UTC+7",
];
