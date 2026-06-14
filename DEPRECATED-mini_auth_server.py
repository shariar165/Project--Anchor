#!/usr/bin/env python3
"""
Anchor AI — Minimal auth server  (no Docker / PostgreSQL / Redis required)

Uses:  SQLite for users  |  in-memory dict for OTP TTLs  |  httpx for Brevo email

Email delivery priority:
  1. Brevo   — set BREVO_API_KEY env var  (recommended)
  2. Gmail   — set GMAIL_USER + GMAIL_APP_PASSWORD env vars
  3. SMTP    — set SMTP_HOST, SMTP_USER, SMTP_PASS env vars
  4. Dev mode — no env vars: code is printed to console AND returned in the
                API response so the frontend can display it on-screen.

Run:
  backend\\.venv\\Scripts\\python.exe mini_auth_server.py
  # then open index.html in browser (e.g. http://localhost:8080)
"""

import hashlib
import hmac
import os
import re
import secrets
import smtplib
import sqlite3
import time
from contextlib import asynccontextmanager
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

# ── Configuration ─────────────────────────────────────────────────
FRONTEND_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH      = os.path.join(FRONTEND_DIR, "anchor_users.db")
AUTH_SECRET  = os.getenv("AUTH_SECRET", secrets.token_hex(32))
OTP_TTL      = 300   # seconds
OTP_MAX_ATT  = 5


def _load_env():
    """Load backend/.env (and .env) into os.environ without overriding already-set vars."""
    for candidate in [
        os.path.join(FRONTEND_DIR, ".env"),
        os.path.join(FRONTEND_DIR, "backend", ".env"),
    ]:
        try:
            with open(candidate) as fh:
                for raw in fh:
                    line = raw.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip()
                    if k and k not in os.environ:
                        os.environ[k] = v
        except FileNotFoundError:
            pass

_load_env()

BREVO_KEY    = os.getenv("BREVO_API_KEY", "")
GMAIL_USER   = os.getenv("GMAIL_USER", "")
GMAIL_PASS   = os.getenv("GMAIL_APP_PASSWORD", "")
SMTP_HOST    = os.getenv("SMTP_HOST", "")
SMTP_PORT    = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER    = os.getenv("SMTP_USER", "")
SMTP_PASS    = os.getenv("SMTP_PASS", "")

SENDER_NAME  = os.getenv("BREVO_SENDER_NAME", "Anchor AI")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", os.getenv("BREVO_SENDER_EMAIL", GMAIL_USER or SMTP_USER or "noreply@anchor.ai"))

# ── In-memory OTP store ───────────────────────────────────────────
# key = "target:purpose" → {hash, expires, attempts}
_otps: dict = {}

# ── SQLite helpers ────────────────────────────────────────────────
def _con() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c

def init_db():
    with _con() as c:
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            TEXT PRIMARY KEY,
                name          TEXT NOT NULL,
                email         TEXT,
                phone         TEXT,
                password_hash TEXT NOT NULL,
                role          TEXT NOT NULL DEFAULT 'user',
                tenant_id     TEXT,
                verified      INTEGER NOT NULL DEFAULT 0,
                created_at    REAL NOT NULL,
                UNIQUE(email),
                UNIQUE(phone)
            )
        """)

def _user_by(field: str, val: str) -> Optional[dict]:
    with _con() as c:
        row = c.execute(f"SELECT * FROM users WHERE {field}=?", (val,)).fetchone()
    return dict(row) if row else None

def _create_user(uid, name, email, phone, pw_hash, role, tenant_id):
    with _con() as c:
        c.execute(
            "INSERT INTO users VALUES (?,?,?,?,?,?,?,0,?)",
            (uid, name,
             email.lower() if email else None,
             phone or None,
             pw_hash, role, tenant_id or None, time.time())
        )

def _mark_verified(email: str = None, phone: str = None):
    with _con() as c:
        if email:
            c.execute("UPDATE users SET verified=1 WHERE email=?", (email.lower(),))
        elif phone:
            c.execute("UPDATE users SET verified=1 WHERE phone=?", (phone,))

# ── Password ──────────────────────────────────────────────────────
def _hash_pw(pw: str) -> str:
    return hashlib.sha256((AUTH_SECRET + pw).encode()).hexdigest()

def _check_pw(pw: str, stored: str) -> bool:
    return hmac.compare_digest(_hash_pw(pw), stored)

# ── OTP ───────────────────────────────────────────────────────────
def _gen_otp(target: str, purpose: str) -> str:
    code = str(secrets.randbelow(1_000_000)).zfill(6)
    _otps[f"{target}:{purpose}"] = {
        "hash":     hashlib.sha256(code.encode()).hexdigest(),
        "expires":  time.time() + OTP_TTL,
        "attempts": 0,
    }
    return code

def _verify_otp(target: str, purpose: str, code: str) -> bool:
    key   = f"{target}:{purpose}"
    entry = _otps.get(key)
    if not entry:
        return False
    if time.time() > entry["expires"]:
        del _otps[key]
        return False
    if entry["attempts"] >= OTP_MAX_ATT:
        return False
    entry["attempts"] += 1
    ok = hmac.compare_digest(hashlib.sha256(code.encode()).hexdigest(), entry["hash"])
    if ok:
        del _otps[key]
    return ok

# ── Email ─────────────────────────────────────────────────────────
def _otp_email_html(name_or_title: str, code: str, purpose_line: str) -> str:
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;background:#F7F3EE;padding:32px;border-radius:16px">
      <h2 style="color:#0B1D35;margin:0 0 16px">{name_or_title}</h2>
      <p style="color:#444;margin:0 0 20px">{purpose_line}</p>
      <div style="background:#fff;border-radius:12px;padding:24px;text-align:center;margin:0 0 20px;border:1px solid #E5E0D6">
        <div style="font-size:36px;font-weight:700;letter-spacing:10px;color:#0B1D35">
          <strong>{code}</strong>
        </div>
      </div>
      <p style="color:#999;font-size:13px;margin:0">Expires in 5 minutes. Do not share this code.</p>
    </div>
    """


def _send_email(to: str, subject: str, html: str) -> tuple[bool, Optional[str]]:
    """Returns (sent_for_real, dev_code_or_None)."""
    match = re.search(r"<strong>(\d{6})</strong>", html)
    dev_code = match.group(1) if match else None

    # 1. Brevo
    if BREVO_KEY:
        try:
            with httpx.Client(timeout=10) as client:
                r = client.post(
                    "https://api.brevo.com/v3/smtp/email",
                    headers={"api-key": BREVO_KEY, "Content-Type": "application/json"},
                    json={
                        "sender":      {"name": SENDER_NAME, "email": SENDER_EMAIL},
                        "to":          [{"email": to}],
                        "subject":     subject,
                        "htmlContent": html,
                    },
                )
                r.raise_for_status()
            return True, None
        except Exception as exc:
            print(f"[BREVO ERROR] {exc}")

    # 2. Gmail SMTP
    if GMAIL_USER and GMAIL_PASS:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = f"{SENDER_NAME} <{GMAIL_USER}>"
            msg["To"]      = to
            msg.attach(MIMEText(html, "html"))
            with smtplib.SMTP("smtp.gmail.com", 587) as s:
                s.starttls()
                s.login(GMAIL_USER, GMAIL_PASS)
                s.send_message(msg)
            return True, None
        except Exception as exc:
            print(f"[GMAIL ERROR] {exc}")

    # 3. Custom SMTP
    if SMTP_HOST and SMTP_USER and SMTP_PASS:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = f"{SENDER_NAME} <{SMTP_USER}>"
            msg["To"]      = to
            msg.attach(MIMEText(html, "html"))
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
                s.starttls()
                s.login(SMTP_USER, SMTP_PASS)
                s.send_message(msg)
            return True, None
        except Exception as exc:
            print(f"[SMTP ERROR] {exc}")

    # 4. Dev mode fallback
    print(f"\n{'='*55}")
    print(f"[DEV EMAIL]  To: {to}")
    print(f"  Subject  : {subject}")
    if dev_code:
        print(f"  >>> OTP CODE: {dev_code} <<<")
    print(f"{'='*55}\n")
    return False, dev_code


# ── Schemas ───────────────────────────────────────────────────────
class RegisterReq(BaseModel):
    name:      str
    email:     Optional[str] = None
    phone:     Optional[str] = None
    password:  str
    role:      str = "user"
    tenant_id: Optional[str] = None

class VerifyReq(BaseModel):
    identifier: str   # email or phone
    code:       str

class LoginReq(BaseModel):
    identifier: str   # email or phone
    password:   str

class ResendReq(BaseModel):
    identifier: str


# ── FastAPI app ───────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    mode = ("Brevo" if BREVO_KEY
            else "Gmail" if GMAIL_USER
            else "SMTP"  if SMTP_HOST
            else "DEV MODE — code shown in UI (no email sent)")
    print(f"\n  Anchor AI Auth Server")
    print(f"  App      : http://localhost:8001          <- open this in your browser")
    print(f"  Users DB : {DB_PATH}")
    print(f"  Email    : {mode}")
    print(f"  API docs : http://localhost:8001/docs\n")
    yield

app = FastAPI(title="Anchor AI Auth", version="1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/auth/register")
def register(req: RegisterReq):
    if not req.email and not req.phone:
        raise HTTPException(400, "Email or phone number is required.")
    if req.email and _user_by("email", req.email.lower()):
        raise HTTPException(400, "An account with this email already exists.")
    if req.phone and _user_by("phone", req.phone):
        raise HTTPException(400, "An account with this phone number already exists.")

    uid = "usr_" + secrets.token_hex(6)
    _create_user(uid, req.name, req.email, req.phone, _hash_pw(req.password), req.role, req.tenant_id)

    target   = req.email or req.phone
    is_email = bool(req.email)
    code     = _gen_otp(target if not is_email else target.lower(), "registration")

    dev_code: Optional[str] = None
    if is_email:
        _, dev_code = _send_email(
            req.email,
            "Verify your Anchor AI email",
            _otp_email_html(f"Hi {req.name},", code, "Enter this code to verify your Anchor AI account:"),
        )
    else:
        print(f"[SMS OTP] To: {req.phone}  Code: {code}")
        dev_code = code  # always show phone OTP in UI for this prototype

    resp: dict = {"message": "Verification code sent", "is_email": is_email}
    if dev_code:
        resp["dev_code"] = dev_code
    return resp


@app.post("/auth/verify-email")
@app.post("/auth/verify-otp")
def verify(req: VerifyReq):
    is_email = "@" in req.identifier
    target   = req.identifier.lower() if is_email else req.identifier

    if not _verify_otp(target, "registration", req.code):
        raise HTTPException(400, "Invalid or expired code. Request a new one.")

    if is_email:
        _mark_verified(email=target)
        user = _user_by("email", target)
    else:
        _mark_verified(phone=target)
        user = _user_by("phone", target)

    if not user:
        raise HTTPException(500, "User record not found after verification.")

    return {
        "message": "Account verified",
        "user": {
            "id":        user["id"],
            "name":      user["name"],
            "role":      user["role"],
            "tenant_id": user["tenant_id"],
            "mfa":       False,
        },
    }


@app.post("/auth/login")
def login(req: LoginReq):
    identifier = req.identifier.strip()
    is_email   = "@" in identifier
    user       = (_user_by("email", identifier.lower())
                  if is_email else _user_by("phone", identifier))

    if not user:
        raise HTTPException(401, "No account found with this email or phone number.")
    if not user["verified"]:
        raise HTTPException(401, "Account not verified yet. Check your email for the verification code.")
    if not _check_pw(req.password, user["password_hash"]):
        raise HTTPException(401, "Incorrect password.")

    return {
        "message": "Login successful",
        "user": {
            "id":        user["id"],
            "name":      user["name"],
            "role":      user["role"],
            "tenant_id": user["tenant_id"],
            "mfa":       False,
        },
    }


@app.post("/auth/resend-verification")
def resend(req: ResendReq):
    identifier = req.identifier.strip()
    is_email   = "@" in identifier
    target     = identifier.lower() if is_email else identifier
    user       = _user_by("email", target) if is_email else _user_by("phone", target)

    if not user:
        raise HTTPException(404, "No account found.")
    if user["verified"]:
        raise HTTPException(400, "Account is already verified.")

    code = _gen_otp(target, "registration")
    dev_code: Optional[str] = None

    if is_email:
        _, dev_code = _send_email(
            target,
            "Your new Anchor AI verification code",
            _otp_email_html("New verification code", code, "Use this code to verify your Anchor AI account:"),
        )
    else:
        print(f"[SMS OTP] Resend to: {target}  Code: {code}")
        dev_code = code

    resp: dict = {"message": "New verification code sent."}
    if dev_code:
        resp["dev_code"] = dev_code
    return resp


@app.post("/auth/forgot-password")
def forgot_password(req: ResendReq):
    identifier = req.identifier.strip()
    is_email   = "@" in identifier
    target     = identifier.lower() if is_email else identifier
    user       = _user_by("email", target) if is_email else _user_by("phone", target)

    dev_code: Optional[str] = None
    if user:
        code = _gen_otp(target, "password_reset")
        if is_email:
            _, dev_code = _send_email(
                target,
                "Reset your Anchor AI password",
                _otp_email_html("Password reset", code, "Use this code to reset your Anchor AI password:"),
            )
        else:
            print(f"[SMS OTP] Password reset to: {target}  Code: {code}")
            dev_code = code

    # Always return success to avoid leaking whether the account exists
    resp: dict = {"message": "If an account exists, a reset code was sent."}
    if dev_code:
        resp["dev_code"] = dev_code
    return resp


@app.get("/")
def serve_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/{filepath:path}")
def serve_static(filepath: str):
    full = os.path.join(FRONTEND_DIR, filepath)
    if os.path.isfile(full):
        return FileResponse(full)
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False)
