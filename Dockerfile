# ==========================================================
# Giai đoạn 1: Build Frontend (React + Vite)
# ==========================================================
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ ./
RUN npm run build

# ==========================================================
# Giai đoạn 2: Runtime Backend (Python 3.13 + FastAPI)
# ==========================================================
FROM python:3.13-slim AS backend

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

WORKDIR /app

# Cài đặt các công cụ hệ thống cần thiết
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt dependencies Python
COPY backend/pyproject.toml ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Copy mã nguồn backend và migrations
COPY backend/src ./src
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./
COPY backend/data ./data

# Copy sản phẩm build frontend từ Giai đoạn 1 vào thư mục static của backend
COPY --from=frontend-builder /app/backend/static ./static

# Tạo user không đặc quyền để tăng cường bảo mật
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Khởi chạy Alembic migration và Web Server
CMD ["sh", "-c", "alembic upgrade head && python -m biensoxe.cli serve --host 0.0.0.0 --port 8000"]
