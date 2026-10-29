from pathlib import Path
import uuid

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from biensoxe import __version__
from biensoxe.api import audit as audit_api
from biensoxe.api import auth as auth_api
from biensoxe.api import bao_cao as bao_cao_api
from biensoxe.api import bien as bien_api
from biensoxe.api import danh_muc as danh_muc_api
from biensoxe.api import import_excel as import_excel_api
from biensoxe.api import kho as kho_api
from biensoxe.api import lo as lo_api
from biensoxe.api import tai_khoan as tai_khoan_api
from biensoxe.api import tra_cuu as tra_cuu_api
from biensoxe.logging import configure_logging, request_id_ctx

STATIC_DIR = Path(__file__).resolve().parents[2] / "static"


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="Phần mềm quản lý đặt và cấp phát biển số xe",
        version=__version__,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )

    @app.middleware("http")
    async def security_and_request_id_middleware(request: Request, call_next) -> Response:
        req_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token = request_id_ctx.set(req_id)
        try:
            response: Response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data:; font-src 'self' data:; frame-ancestors 'none'"
            )
            return response
        finally:
            request_id_ctx.reset(token)

    @app.get("/api/v1/health", tags=["system"])
    def health_check() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    app.include_router(auth_api.router)
    app.include_router(tai_khoan_api.router)
    app.include_router(danh_muc_api.router)
    app.include_router(audit_api.router)
    app.include_router(lo_api.router)
    app.include_router(bien_api.router)
    app.include_router(import_excel_api.router)
    app.include_router(kho_api.router)
    app.include_router(tra_cuu_api.router)
    app.include_router(bao_cao_api.router)

    if STATIC_DIR.exists():
        assets_dir = STATIC_DIR / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def serve_spa(full_path: str):
            if full_path.startswith("api/"):
                return JSONResponse(status_code=404, content={"detail": "Không tìm thấy đường dẫn"})
            candidate = (STATIC_DIR / full_path).resolve()
            if full_path and candidate.is_file() and STATIC_DIR.resolve() in candidate.parents:
                return FileResponse(str(candidate))
            index_file = STATIC_DIR / "index.html"
            if index_file.is_file():
                return FileResponse(
                    str(index_file),
                    headers={"Cache-Control": "no-store, must-revalidate"},
                )
            return JSONResponse(status_code=404, content={"detail": "Chưa build giao diện"})

    return app


app = create_app()
