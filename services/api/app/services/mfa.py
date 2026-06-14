import secrets
import base64
import io
import pyotp
import qrcode
from argon2 import PasswordHasher

_ph = PasswordHasher(memory_cost=19456, time_cost=2, parallelism=1)


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def make_otpauth_uri(secret: str, email: str, issuer: str = "Anchor AI") -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name=issuer)


def make_qr_data_url(uri: str) -> str:
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    encoded = base64.b64encode(buf.getvalue()).decode()
    return f"data:image/png;base64,{encoded}"


def verify_totp(secret: str, code: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)


def generate_recovery_codes(count: int = 10) -> list[str]:
    return [f"{secrets.token_hex(4).upper()}-{secrets.token_hex(4).upper()}" for _ in range(count)]


def hash_recovery_code(code: str) -> str:
    return _ph.hash(code)


def verify_recovery_code(plain: str, hashed: str) -> bool:
    from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
