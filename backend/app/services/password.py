import hashlib
import hmac
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
import httpx
from app.config import get_settings

_ph = PasswordHasher(memory_cost=65536, time_cost=3, parallelism=4)


def _pepper(password: str) -> bytes:
    settings = get_settings()
    return hmac.new(settings.pepper_bytes, password.encode(), hashlib.sha256).digest()


def hash_password(password: str) -> str:
    return _ph.hash(_pepper(password))


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, _pepper(plain))
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    return _ph.check_needs_rehash(hashed)


async def check_pwned(password: str) -> bool:
    """Returns True if the password appears in HIBP (k-anonymity). Caller should reject."""
    settings = get_settings()
    if not settings.hibp_check_enabled:
        return False
    sha1 = hashlib.sha1(password.encode()).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(f"https://api.pwnedpasswords.com/range/{prefix}")
            resp.raise_for_status()
        return suffix in [line.split(":")[0] for line in resp.text.splitlines()]
    except Exception:
        return False
