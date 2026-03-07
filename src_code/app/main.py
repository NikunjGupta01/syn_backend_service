# System imports
import uvicorn
import redis.asyncio as redis
from starlette.types import Scope
from fastapi import FastAPI, Request
from app.net.client import HTTPClient
from fastapi.security import HTTPBasic
from app.config.config import settings
from app.models import init_db, get_db
from app.libraries.Logger import Logger
from contextlib import asynccontextmanager
from app.helpers.ErrorCodes import ErrorCodes
from fastapi.openapi.utils import get_openapi
from app.router_registry import router_registry
from fastapi.middleware.cors import CORSMiddleware
from app.helpers.ErrorMessages import ErrorMessages
from app.controllers.APIResponse import APIResponse
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from app.middleware.redis_rate_limiter import init_redis, redis_rate_limiter

ALLOWED_CSP_ORIGINS = " ".join(settings.FRONTEND_ORIGINS.split(","))


# Lifespan hook for startup tasks
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    try:
        await init_redis()
    except Exception as e:
        Logger.get_instance().log_warning({"message": f"Redis init failed: {e}"})    
    yield
    if getattr(app.state, "redis", None):
        await app.state.redis.close()


# FastAPI app initialization (✅ Swagger UI enabled at /docs)
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
    openapi_tags=[{"name": "SYNQUERRA", "description": "Backend"}],
    docs_url="/docs",
    redoc_url=None,
    openapi_url="/openapi.json"
)

# Custom OpenAPI schema generator to remove "schemas"
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

security = HTTPBasic()

# Register routers
for r in router_registry:
    app.include_router(
        r["router"],
        prefix=r.get("prefix", ""),
        tags=r.get("tags", []),
        include_in_schema=r.get("include_in_schema", True),
    )

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.FRONTEND_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Custom security headers middleware
class CustomHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Scope, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), camera=(), microphone=(), interest-cohort=()"
        )

        path = request["path"]

        if path.startswith("/docs") or path.startswith("/openapi.json"):
            csp = [
                "default-src 'self' https://cdn.jsdelivr.net",
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
                "img-src 'self' data: https://fastapi.tiangolo.com",
                "object-src 'none'",
            ]
        else:
            csp = [
                "default-src 'none'",
                "frame-ancestors 'none'",
                "base-uri 'none'",
                "form-action 'none'",
                "img-src 'self'",
                f"connect-src 'self' {ALLOWED_CSP_ORIGINS}".strip(),
            ]

        response.headers["Content-Security-Policy"] = "; ".join(csp)

        return response
    
# Assign UUID per request middleware
@app.middleware("http")
async def assign_new_uuid_per_request(request: Request, call_next):
    Logger.get_instance(set_uuid=True)
    return await call_next(request)

# Apply security headers middleware
app.add_middleware(CustomHeaderMiddleware)

# Initialize HTTP client
client = None

@app.on_event("startup")
async def startup_event():
    global client
    client = HTTPClient()


# Health & Utility Endpoints

@app.get("/", summary="Welcome to SYNQUERRA API", include_in_schema=True, status_code=200)
def home():
    return JSONResponse(status_code=200, content={"status": "ok"})


# Register middleware at creation time
app.middleware("http")(redis_rate_limiter)

@app.get("/ping-redis")
async def ping_redis():
    from app.middleware.redis_rate_limiter import redis_client
    if not redis_client:
        return {"status": "error", "message": "Redis not connected"}
    pong = await redis_client.ping()
    return {"status": "ok", "pong": pong}

@app.get("/dbhealth", summary="Validate Database Health", include_in_schema=True)
async def get_db_health():
    logger = Logger.get_instance()
    try:
        engine = get_db()
        pingpong = await engine.client.admin.command("ping")
        if not pingpong.get("ok"):
            response = APIResponse.error("Database is not responding", 500)
            logger.log_critical({
                **response,
                ErrorMessages.EXP: 'pingpong status ok',
                ErrorMessages.EXP_CODE: ErrorCodes.MN_0002
            })
            return JSONResponse(content=response, status_code=500)

        response = APIResponse.success('Database connected.')
        return JSONResponse(content=response, status_code=200)

    except Exception as e:
        response = APIResponse.error("Database connection fail", 500)
        logger.log_critical({
            **response,
            ErrorMessages.EXP: str(e),
            ErrorMessages.EXP_CODE: ErrorCodes.MN_0003
        })
        return JSONResponse(content=response, status_code=500)


# Run the application
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=80, reload=True)
