import hashlib
from fastapi import Request


def fingerprint(request: Request) -> str:
    ua = request.headers.get("user-agent", "")
    accept = request.headers.get("accept-language", "")
    ip = request.client.host if request.client else ""
    raw = f"{ua}|{accept}|{ip}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def get_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
