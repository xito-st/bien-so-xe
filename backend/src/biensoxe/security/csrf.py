import hmac

from fastapi import HTTPException, Request, status

from biensoxe.security.session import CSRF_HEADER_NAME

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def verify_csrf_if_required(request: Request, expected_csrf_token: str) -> None:
    """Kiểm tra CSRF token nếu client gửi header X-CSRF-Token hoặc bật chế độ bắt buộc (D-05, NFR-009)."""
    if request.method in SAFE_METHODS:
        return
    provided = request.headers.get(CSRF_HEADER_NAME)
    if provided is not None and not hmac.compare_digest(provided, expected_csrf_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Mã chống giả mạo yêu cầu (CSRF token) không hợp lệ.",
        )

