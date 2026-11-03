# HƯỚNG DẪN TRIỂN KHAI HỆ THỐNG QUẢN LÝ BIỂN SỐ XE LÊN MÁY CHỦ VPS

Tài liệu này hướng dẫn chi tiết từng bước đưa hệ thống lên máy chủ VPS (Ubuntu/Debian) sử dụng **Docker Compose**, **FastAPI**, **PostgreSQL 17** và **Caddy Reverse Proxy** (tự động cấp chứng chỉ bảo mật HTTPS Let's Encrypt).

---

## 1. Cấu hình Máy chủ VPS Đề xuất

- **Hệ điều hành**: Ubuntu 22.04 LTS hoặc Ubuntu 24.04 LTS (x86_64).
- **Phần cứng đề xuất**:
  - **RAM**: Tối thiểu 2 GB (khuyến nghị 4 GB để xử lý import file lớn mượt mà).
  - **CPU**: 1 – 2 vCPU.
  - **Ổ cứng**: Tối thiểu 25 GB SSD (lưu trữ hàng triệu biển số chỉ tốn khoảng 2–4 GB).
- **Mở cổng Firewall (UFW / Security Group)**:
  - Cổng `22` (SSH để quản trị từ xa).
  - Cổng `80` (HTTP).
  - Cổng `443` (HTTPS).

---

## 2. Bước 1: Cài đặt Docker & Docker Compose trên VPS

Đăng nhập vào VPS qua SSH, chạy các lệnh sau:

```bash
# Cập nhật hệ thống
sudo apt-get update && sudo apt-get upgrade -y

# Cài đặt Docker tự động bằng script chính thức
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Cài đặt plugin Docker Compose
sudo apt-get install -y docker-compose-plugin

# Kiểm tra phiên bản
docker --version
docker compose version
```

---

## 3. Bước 2: Tải Mã nguồn Dự án lên VPS

Bạn có thể clone mã nguồn qua Git hoặc upload tệp zip lên thư mục `/opt/bien-so-xe`:

```bash
# Tạo thư mục và cấp quyền
sudo mkdir -p /opt/bien-so-xe
sudo chown -R $USER:$USER /opt/bien-so-xe
cd /opt/bien-so-xe

# Clone mã nguồn từ kho Git của bạn
git clone <URL_GIT_CUA_BAN> .
```

---

## 4. Bước 3: Cấu hình Biến môi trường (.env)

Tạo file `.env` từ file mẫu:

```bash
cp .env.production.example .env
nano .env
```

Chỉnh sửa các thông số quan trọng:
1. **`DOMAIN_NAME`**:
   - Nếu đã có tên miền và trỏ DNS A Record về IP của VPS (ví dụ `biensoxe.congantinh.vn`): điền `biensoxe.congantinh.vn`. Caddy sẽ **tự động lấy chứng chỉ SSL HTTPS miễn phí**.
   - Nếu chưa có tên miền (chỉ truy cập bằng IP VPS): điền `:80`.
2. **`POSTGRES_PASSWORD`**: Đặt mật khẩu mạnh cho database PostgreSQL.
3. **`ADMIN_INITIAL_PASSWORD`**: Đặt mật khẩu đăng nhập ban đầu cho tài khoản `ADMINS`.
4. Lưu và đóng file (`Ctrl + O`, `Enter`, `Ctrl + X`).

---

## 5. Bước 4: Khởi chạy Hệ thống bằng Docker Compose

Chỉ cần chạy 1 lệnh duy nhất:

```bash
docker compose up -d --build
```

**Quá trình này sẽ tự động:**
1. Build giao diện React + Vite thành tệp tĩnh tối ưu.
2. Build container Backend FastAPI.
3. Khởi động PostgreSQL 17 và kiểm tra trạng thái sức khỏe.
4. Tự động chạy Alembic migration cập nhật cấu trúc bảng.
5. Tự động nạp danh mục hành chính (34 tỉnh, 3.321 xã) và khởi tạo 3.356 tài khoản.
6. Tự động tạo 24 phân vùng cho nhật ký `audit_log`.
7. Khởi động Caddy cấp SSL và mở cổng 80/443.

Kiểm tra trạng thái các container:
```bash
docker compose ps
```
Cả 3 service `biensoxe-db`, `biensoxe-app`, `biensoxe-caddy` đều ở trạng thái `Up / healthy`.

---

## 6. Bước 5: Truy cập Ứng dụng

Mở trình duyệt web và truy cập:
- Theo tên miền: `https://biensoxe.yourdomain.com`
- Hoặc theo IP máy chủ: `http://<IP_VPS>`

**Tài khoản đăng nhập mặc định ban đầu:**
- **Cục C08 (Admin)**: `ADMINS` / Mật khẩu đã cấu hình trong `.env` (`ADMIN_INITIAL_PASSWORD`).
- **Cấp Tỉnh** (ví dụ Hà Nội): `01` / Mật khẩu: `Abc@!321` (bắt buộc đổi ở lần đầu).
- **Cấp Xã** (ví dụ Hoàn Kiếm): `10105001` / Mật khẩu: `Abc@321` (bắt buộc đổi ở lần đầu).

---

## 7. Bước 6: Cấu hình Sao lưu Tự động Hằng ngày (Cron Job)

Để bảo đảm an toàn dữ liệu và tuân thủ tiêu chuẩn RPO ≤ 24h, cấp quyền chạy script backup:

```bash
chmod +x /opt/bien-so-xe/ops/backup.sh
```

Mở crontab trên VPS:
```bash
crontab -e
```
Thêm dòng sau vào cuối để tự động sao lưu lúc **01:00 sáng hàng ngày**:
```bash
0 1 * * * /opt/bien-so-xe/ops/backup.sh >> /opt/bien-so-xe/ops/backups/backup.log 2>&1
```

---

## 8. Các Lệnh Vận hành Thường dùng

- **Xem log thời gian thực của ứng dụng:**
  ```bash
  docker compose logs -f app
  ```
- **Khởi động lại toàn bộ hệ thống:**
  ```bash
  docker compose restart
  ```
- **Dừng hệ thống:**
  ```bash
  docker compose down
  ```
- **Cập nhật mã nguồn mới:**
  ```bash
  git pull
  docker compose up -d --build
  ```
- **Khôi phục mật khẩu Admin (khi mất điện thoại 2FA hoặc quên pass):**
  ```bash
  docker exec -it biensoxe-app python -m biensoxe.cli reset-admin
  ```
- **Sao lưu CSDL thủ công ngay lập tức:**
  ```bash
  ./ops/backup.sh
  ```

