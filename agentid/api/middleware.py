"""Request-level anti-tamper: owner signature + replay protection."""
import time
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from agentid.core.signing import verify, hash_bytes

WRITE_PATHS = {"/v1/events"}


class OwnerSignatureMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and request.url.path in WRITE_PATHS:
            await _verify_request(request)
        return await call_next(request)


async def _verify_request(request: Request):
    ts_header = request.headers.get("X-Timestamp")
    sig_header = request.headers.get("X-Owner-Signature")

    if not ts_header or not sig_header:
        raise HTTPException(422, "Missing X-Timestamp or X-Owner-Signature headers")

    # Replay protection: reject requests older than 5 minutes
    try:
        ts = int(ts_header)
    except ValueError:
        raise HTTPException(422, "Invalid X-Timestamp")

    now_ms = int(time.time() * 1000)
    from agentid.config import settings
    if abs(now_ms - ts) > settings.replay_window_seconds * 1000:
        raise HTTPException(401, "Request timestamp expired (replay protection)")

    # Signature is verified per-event in the events route using the agent's public key
    # This middleware only checks timestamp presence; full sig verification is in deps.py
