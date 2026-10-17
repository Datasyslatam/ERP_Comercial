"""Middleware HTTP: id de petición, contexto, cabeceras de seguridad, límite de solicitudes, métricas y logs JSON."""
import json
import logging
import sys
import time
import uuid
from collections import defaultdict, deque
from threading import Lock

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

from app.core.config import get_settings
from app.core.context import RequestContext, set_context

REQUESTS = Counter("erp_http_requests_total", "Peticiones HTTP", ["method", "route", "status"])
LATENCY = Histogram("erp_http_request_seconds", "Latencia HTTP", ["method", "route"])


class JsonFormatter(logging.Formatter):
    _std = set(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {"message", "asctime"}

    def format(self, record: logging.LogRecord) -> str:
        data = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        data.update({k: v for k, v in record.__dict__.items() if k not in self._std})
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, default=str, ensure_ascii=False)


def setup_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(get_settings().log_level)


class SlidingWindowLimiter:
    """Límite por instancia. En despliegues con varias réplicas, complementar en el proxy (ver docs/seguridad)."""

    def __init__(self) -> None:
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str, limit: int, window: float = 60.0) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = SlidingWindowLimiter()


def client_ip(request: Request) -> str:
    """IP real considerando únicamente el número configurado de proxies de confianza."""
    hops = get_settings().trusted_proxy_count
    fwd = request.headers.get("x-forwarded-for")
    if fwd and hops > 0:
        parts = [p.strip() for p in fwd.split(",") if p.strip()]
        if len(parts) >= hops:
            return parts[-hops]
    return request.client.host if request.client else "unknown"


def install_middleware(app: FastAPI) -> None:
    settings = get_settings()

    @app.middleware("http")
    async def _core(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = rid
        ip = client_ip(request)
        set_context(RequestContext(ip=ip, request_id=rid))

        path = request.url.path
        if path.startswith("/api/"):
            is_login = path.endswith("/auth/login")
            limit = settings.login_rate_limit_per_minute if is_login else settings.rate_limit_per_minute
            if not limiter.allow(f"{'login' if is_login else 'api'}:{ip}", limit):
                return JSONResponse({"error": {"code": "rate_limited", "message": "Demasiadas solicitudes"}},
                                    status_code=429, headers={"Retry-After": "60"})

        start = time.perf_counter()
        response: Response = await call_next(request)
        elapsed = time.perf_counter() - start
        route = request.scope.get("route")
        route_path = getattr(route, "path", "unmatched")
        REQUESTS.labels(request.method, route_path, response.status_code).inc()
        LATENCY.labels(request.method, route_path).observe(elapsed)

        response.headers["X-Request-Id"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        if settings.environment in ("staging", "production"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        logging.getLogger("erp.http").info(
            "request", extra={"method": request.method, "path": path, "status": response.status_code,
                              "ms": round(elapsed * 1000, 1), "request_id": rid, "ip": ip}
        )
        return response

    @app.get("/metrics", include_in_schema=False)
    def metrics():
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
