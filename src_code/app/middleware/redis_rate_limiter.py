import time
import redis.exceptions
from fastapi import Request
from redis import asyncio as aioredis
from app.config.config import settings
from fastapi.responses import JSONResponse
from app.helpers.ErrorCodes import ErrorCodes
from app.helpers.ErrorMessages import ErrorMessages
from app.controllers.APIResponse import APIResponse
from app.config.ClientRateLimit import CLIENT_LIMITS


DEFAULT_LIMIT = settings.RATE_LIMIT
WINDOW_SIZE = settings.WINDOW_SIZE
redis_client: aioredis.Redis | None = None

async def init_redis():
    """Initialize Redis connection."""
    global redis_client
    redis_client = aioredis.from_url(
        settings.REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=50
    )
    pong = await redis_client.ping()
    if pong:
        print(f"Redis connected: {settings.REDIS_URL}")
    else:
        raise RuntimeError("Redis ping failed")

def get_api_key(request: Request) -> str:
    """Read 'x-api-key' header in a case-insensitive way. Fallback to 'anonymous'."""
    headers = {k.lower(): v for k, v in request.headers.items()}
    api_key = headers.get("x-api-key", "").strip()
    if not api_key:  
        api_key = "anonymous"
    else:
        api_key = api_key.upper()
    print(f"Received API key: {api_key}")
    return api_key


def get_rate_key(api_key: str, path: str) -> str:
    """Single key per endpoint per API key."""
    endpoint = path.rstrip("/") or "/"
    return f"rl:{api_key}:{endpoint}"

async def redis_rate_limiter(request: Request, call_next):
    """Sliding window Redis rate limiter with per-API-key limits."""
    
    # Skip static and docs paths
    if request.url.path in ("/favicon.ico", "/docs", "/openapi.json", "/dbhealth") or request.url.path.startswith("/static"):
        return await call_next(request)

    if redis_client is None:
        return await call_next(request)

    api_key = get_api_key(request)

    # Apply client-specific limit if present, else default
    if api_key in CLIENT_LIMITS:
        limit, window = CLIENT_LIMITS[api_key]
    elif api_key == "anonymous":
        limit, window = DEFAULT_LIMIT, WINDOW_SIZE
    else:
        return JSONResponse(content=APIResponse.error("Invalid API key", ErrorCodes.UNAUTHORIZED),status_code=ErrorCodes.UNAUTHORIZED)

    now = int(time.time() * 1000)  # current timestamp in ms
    window_ms = window * 1000
    cutoff = now - window_ms

    redis_key = get_rate_key(api_key, request.url.path)

    # Add current request timestamp
    try:
        await redis_client.zadd(redis_key, {str(now): now})

        # Remove requests outside the window
        await redis_client.zremrangebyscore(redis_key, 0, cutoff)

        # Count requests in current window
        current_count = await redis_client.zcard(redis_key)

        # Log for debugging
        print(f"API Key: {api_key}, Path: {request.url.path}, "f"Requests in window: {current_count}, Limit: {limit}, Window: {window}s")

        # Ensure key expires automatically
        await redis_client.expire(redis_key, window)

        if current_count > limit:
            retry_after = await redis_client.pttl(redis_key) // 1000
            return JSONResponse(
                content=APIResponse.error(
                    f"{ErrorMessages.TOO_MANY_REQUESTS} — Limit {limit} per {window}s, retry after {retry_after}s",
                    ErrorCodes.TOO_MANY_REQUESTS
                ),
                status_code=ErrorCodes.TOO_MANY_REQUESTS,
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + retry_after),
                },
            )

        # Pass through request and add rate limit headers
        response = await call_next(request)
        ttl = await redis_client.pttl(redis_key) // 1000
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(limit - current_count, 0))
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + ttl)
        return response
    except (redis.exceptions.RedisError, OSError, ConnectionError):
        return await call_next(request)
