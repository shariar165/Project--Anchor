"""
Standalone auth server for local dev — no Docker, no PostgreSQL, no Redis.
SQLite (built-in) + in-memory token store. Mirrors the full app's endpoints.
"""
import hmac
import hashlib
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path

import jwt
from argon2 import PasswordHasher
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding, NoEncryption, PrivateFormat, PublicFormat, load_pem_private_key,
)
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr
import uvicorn

# ── Config ────────────────────────────────────────────────────────────────────
DB_PATH = "mini_auth.db"
KEYS_DIR = Path(".keys")
PRIVATE_KEY_PATH = KEYS_DIR / "ed25519_private.pem"
PUBLIC_KEY_PATH = KEYS_DIR / "ed25519_public.pem"
_PEPPER = secrets.token_bytes(32)   # ephemeral — fine for local dev
ACCESS_TTL = 900        # 15 min
REFRESH_TTL = 604800    # 7 days

# ── Ed25519 keys ──────────────────────────────────────────────────────────────
def _load_or_generate_keys() -> tuple[str, str]:
    if PRIVATE_KEY_PATH.exists():
        priv_key = load_pem_private_key(PRIVATE_KEY_PATH.read_bytes(), password=None)
    else:
        priv_key = Ed25519PrivateKey.generate()
        KEYS_DIR.mkdir(parents=True, exist_ok=True)
        PRIVATE_KEY_PATH.write_bytes(
            priv_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
        )
        PUBLIC_KEY_PATH.write_bytes(
            priv_key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)
        )
        print(f"  Generated new Ed25519 keypair → {KEYS_DIR}/")
    priv_pem = priv_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()).decode()
    pub_pem = priv_key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode()
    return priv_pem, pub_pem

PRIVATE_KEY_PEM, PUBLIC_KEY_PEM = _load_or_generate_keys()

# ── Password ──────────────────────────────────────────────────────────────────
_ph = PasswordHasher()

def _peppered(password: str) -> str:
    return hmac.new(_PEPPER, password.encode(), hashlib.sha256).hexdigest()

def hash_password(password: str) -> str:
    return _ph.hash(_peppered(password))

def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return _ph.verify(stored_hash, _peppered(password))
    except Exception:
        return False

# ── JWT ───────────────────────────────────────────────────────────────────────
_revoked_jtis: set[str] = set()
_live_refresh_jtis: dict[str, str] = {}  # jti → user_id

def _issue(user_id: str, kind: str, ttl: int) -> tuple[str, str]:
    jti = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "jti": jti,
        "type": kind,
        "iat": now,
        "exp": now + timedelta(seconds=ttl),
    }
    return jwt.encode(payload, PRIVATE_KEY_PEM, algorithm="EdDSA"), jti

def _verify(token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(token, PUBLIC_KEY_PEM, algorithms=["EdDSA"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    if payload.get("type") != expected_type:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong token type")
    if payload["jti"] in _revoked_jtis:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token revoked")
    return payload

# ── SQLite ────────────────────────────────────────────────────────────────────
def _init_db() -> None:
    with sqlite3.connect(DB_PATH) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          TEXT PRIMARY KEY,
                email       TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role        TEXT NOT NULL DEFAULT 'user',
                created_at  TEXT NOT NULL
            )
        """)

@contextmanager
def _db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()

# ── FastAPI ───────────────────────────────────────────────────────────────────
app = FastAPI(title="Anchor AI — Mini Auth", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
_bearer = HTTPBearer()

# ── Schemas ───────────────────────────────────────────────────────────────────
class RegisterIn(BaseModel):
    email: EmailStr
    password: str

class LoginIn(BaseModel):
    email: EmailStr
    password: str

class RefreshIn(BaseModel):
    refresh_token: str

# ── Endpoints ─────────────────────────────────────────────────────────────────
@app.post("/auth/register", status_code=201)
def register(body: RegisterIn):
    uid = str(uuid.uuid4())
    try:
        with _db() as con:
            con.execute(
                "INSERT INTO users (id, email, password_hash, role, created_at) VALUES (?,?,?,?,?)",
                (uid, body.email, hash_password(body.password), "user",
                 datetime.now(timezone.utc).isoformat()),
            )
    except sqlite3.IntegrityError:
        raise HTTPException(400, "Email already registered")
    return {"id": uid, "email": body.email}


@app.post("/auth/login")
def login(body: LoginIn):
    with _db() as con:
        row = con.execute("SELECT * FROM users WHERE email=?", (body.email,)).fetchone()
    if not row or not verify_password(row["password_hash"], body.password):
        raise HTTPException(401, "Invalid credentials")
    access, _ = _issue(row["id"], "access", ACCESS_TTL)
    refresh, r_jti = _issue(row["id"], "refresh", REFRESH_TTL)
    _live_refresh_jtis[r_jti] = row["id"]
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer"}


@app.post("/auth/refresh")
def refresh(body: RefreshIn):
    payload = _verify(body.refresh_token, "refresh")
    jti, user_id = payload["jti"], payload["sub"]
    if jti not in _live_refresh_jtis:
        raise HTTPException(401, "Refresh token not recognised or already rotated")
    # rotate
    del _live_refresh_jtis[jti]
    _revoked_jtis.add(jti)
    access, _ = _issue(user_id, "access", ACCESS_TTL)
    new_refresh, r_jti = _issue(user_id, "refresh", REFRESH_TTL)
    _live_refresh_jtis[r_jti] = user_id
    return {"access_token": access, "refresh_token": new_refresh, "token_type": "bearer"}


@app.post("/auth/logout")
def logout(creds: HTTPAuthorizationCredentials = Depends(_bearer)):
    payload = _verify(creds.credentials, "access")
    _revoked_jtis.add(payload["jti"])
    return {"detail": "Logged out"}


@app.get("/auth/me")
def me(creds: HTTPAuthorizationCredentials = Depends(_bearer)):
    payload = _verify(creds.credentials, "access")
    with _db() as con:
        row = con.execute(
            "SELECT id, email, role FROM users WHERE id=?", (payload["sub"],)
        ).fetchone()
    if not row:
        raise HTTPException(404, "User not found")
    return {"id": row["id"], "email": row["email"], "role": row["role"]}


@app.get("/health")
def health():
    return {"status": "ok", "db": "sqlite", "cache": "in-memory"}


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    _init_db()
    print("\n  Anchor AI Mini Auth Server")
    print("  Docs  → http://localhost:8000/docs")
    print("  Health→ http://localhost:8000/health\n")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
