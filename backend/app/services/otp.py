import secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from app.config import get_settings

_ph = PasswordHasher(memory_cost=19456, time_cost=2, parallelism=1)

OTP_PURPOSES = frozenset({"registration", "login", "password_reset", "stepup", "dms_checkin"})


def _key(target: str, purpose: str) -> str:
    return f"otp:{target}:{purpose}"


def _attempts_key(target: str, purpose: str) -> str:
    return f"otp_attempts:{target}:{purpose}"


async def generate_and_store(redis, target: str, purpose: str) -> str:
    settings = get_settings()
    code = str(secrets.randbelow(1_000_000)).zfill(6)
    hashed = _ph.hash(code)
    await redis.set(_key(target, purpose), hashed, ex=settings.otp_ttl)
    await redis.delete(_attempts_key(target, purpose))
    return code


async def verify(redis, target: str, purpose: str, code: str) -> bool:
    settings = get_settings()
    attempts_key = _attempts_key(target, purpose)

    # INCR is atomic: increment first so concurrent requests can't both sneak past the limit
    new_attempts = await redis.incr(attempts_key)
    await redis.expire(attempts_key, settings.otp_ttl)
    if new_attempts > settings.otp_max_attempts:
        return False

    stored_hash = await redis.get(_key(target, purpose))
    if not stored_hash:
        return False

    try:
        _ph.verify(stored_hash, code)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False

    await redis.delete(_key(target, purpose))
    await redis.delete(attempts_key)
    return True
