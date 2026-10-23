"""Public-facing approval gateway: intentionally has no account or catalog routes."""
from pathlib import Path
import os
import urllib.error
import urllib.request

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.concurrency import run_in_threadpool

ROOT = Path(__file__).resolve().parents[1]
OPERATIONS = {"review", "decision", "pdf"}


def forward(operation, authorization, raw):
    request = urllib.request.Request("http://127.0.0.1:8765/api/mobile/" + operation, data=raw or b"{}",
                                     headers={"Content-Type": "application/json", "Authorization": authorization}, method="POST")
    try:
        response = urllib.request.urlopen(request, timeout=55)
    except urllib.error.HTTPError as error:
        response = error
    except (urllib.error.URLError, TimeoutError, OSError):
        return JSONResponse({"detail": "mobile_service_offline"}, status_code=503)
    with response:
        body = response.read(20_000_001)
        if len(body) > 20_000_000:
            return JSONResponse({"detail": "mobile_response_too_large"}, status_code=502)
        kind = "application/pdf" if operation == "pdf" and response.status == 200 else "application/json"
        headers = {}
        if kind == "application/pdf":
            headers["Content-Disposition"] = 'attachment; filename="quotation.pdf"'
        return Response(body, status_code=response.status, media_type=kind, headers=headers)


def create_gateway(proxy=forward):
    app = FastAPI(title="Quote mobile approval", docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"
        return response

    @app.get("/health")
    def health():
        return {"mobile_gateway": True, "version": "1.6.1", "instance": os.getenv("WA_QUOTE_GATEWAY_INSTANCE", "")}

    @app.get("/mobile")
    def home():
        return FileResponse(ROOT / "mobile" / "index.html")

    @app.get("/mobile/{asset}")
    def asset_file(asset: str):
        if asset not in {"app.js", "style.css"}:
            raise HTTPException(404, "Not found")
        return FileResponse(ROOT / "mobile" / asset)

    @app.post("/api/mobile/{operation}")
    async def operation(operation: str, request: Request):
        if operation not in OPERATIONS:
            raise HTTPException(404, "Not found")
        authorization = request.headers.get("authorization", "")
        if len(authorization) > 1010:
            raise HTTPException(401, "mobile_invalid_link")
        chunks = []
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > 16384:
                raise HTTPException(413, "Request too large")
            chunks.append(chunk)
        return await run_in_threadpool(proxy, operation, authorization, b"".join(chunks))

    return app


app = create_gateway()
