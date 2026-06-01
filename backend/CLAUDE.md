# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Backend Overview

FastAPI backend for **Anchor AI** — implements JWT auth (Ed25519), Argon2id+pepper passwords, TOTP MFA, refresh token rotation with theft detection, SHA-256 audit hash chain, multi-tenant student scoping, and anonymous complaint tracking.

**Stack:** FastAPI · PostgreSQL 15 · Redis 7 · SQLAlchemy 2.0 (async) · Alembic · Pydantic v2 · PyJWT (Ed25519/EdDSA)

## Running the App

Always use the **venv** — all dependencies are isolated there:

```powershell
# Activate venv in PowerShell
.\.venv\Scripts\Activate.ps1

# Or use the scripts helper
.\scripts.ps1 dev        # starts DB+Redis via docker compose, then uvicorn --reload
.\scripts.ps1 migrate    # alembic upgrade head
.\scripts.ps1 test       # pytest -x -v
.\scripts.ps1 gen-keys   # regenerate Ed25519 keypair (only needed once)
```

**Prerequisites before first run:**
1. Run `setup-docker.ps1` as Administrator (installs WSL2 + Docker Desktop to D:\)
2. `docker compose up -d db redis`
3. `.\scripts.ps1 migrate`
4. `uvicorn app.main:app --reload --port 8000` (or `.\scripts.ps1 dev`)

**Direct venv commands:**
```powershell
.venv\Scripts\python.exe -m pytest -x -v tests/test_login.py
.venv\Scripts\alembic.exe upgrade head
.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
```

## Architecture

### Request lifecycle
`main.py` → router (e.g. `routers/auth.py`) → service layer (`services/`) → ORM models (`models/`) → PostgreSQL/Redis

### Key files
- `app/config.py` — all env vars via pydantic-settings; `get_settings()` is `@lru_cache`
- `app/deps.py` — FastAPI dependencies: `get_current_user`, `require_role(*roles)`, `require_stepup`
- `app/database.py` — async SQLAlchemy engine + `get_db()` session dependency
- `app/redis.py` — Redis client + `get_redis()` dependency

### Services (pure business logic, no HTTP)
- `services/token.py` — Ed25519 JWT sign/verify via PyJWT + cryptography; `jti` deny-list in Redis
- `services/password.py` — HMAC-SHA256 pepper applied **before** Argon2id hashing
- `services/otp.py` — 6-digit OTP via `secrets.randbelow`, stored as Argon2id hash in Redis with TTL
- `services/mfa.py` — TOTP via pyotp; QR code as `data:image/png;base64,...`
- `services/audit.py` — SHA-256 hash chain: each row hashes `prev_hash + canonical_json(event)`

### Auth flow nuances
- **MFA login**: on success with MFA enabled, a UUID is stored in Redis (`mfa_pending:{token}`, 2-min TTL); client must POST to `/auth/mfa/verify` with that token — no partial JWT is issued
- **Refresh token theft**: if a previously-rotated refresh jti is replayed, ALL user sessions are revoked + `token_reuse_detected` audit event emitted
- **Token type field**: all JWTs include `"type": "access"|"refresh"|"stepup"` — stepup tokens are checked in `require_stepup()`

### Database notes
- All UUIDs generated server-side
- `audit_logs` is append-only (enforced at DB role level in production)
- `sessions.refresh_token_hash` stores Argon2id hash of the raw refresh JWT string
- Alembic auto-generates migrations from SQLAlchemy models: `alembic revision --autogenerate -m "description"`

## Environment
`.env` file is pre-populated (PASSWORD_PEPPER and SECRET_KEY are already generated). Keys are in `.keys/` (Ed25519 PEM files). Never commit `.env` or `.keys/`.

## JWT Notes
Uses **PyJWT** (not python-jose — python-jose does not support EdDSA). UUID values in payloads must be converted to `str()` before encoding — PyJWT does not serialize UUID objects.

## Security — Known Open Issues

These were identified during a security review on 2026-05-26. The issues below were **not fixed** and need follow-up work before production deployment.

| ID | Issue | Location | Effort |
|----|-------|----------|--------|
| SEC-12 | **TOTP secret stored plaintext** — `mfa_methods.secret_encrypted` stores the base32 TOTP secret unencrypted despite the field name. A DB breach exposes all MFA secrets. Needs KMS/envelope encryption. | `models/mfa.py`, `routers/mfa.py:46` | High |
| SEC-13 | **Refresh token rotation race condition** — two simultaneous requests with the same token can both pass the `is_blacklisted` check before either writes to Redis. Fix requires a Redis distributed lock or atomic `SET NX` compare-and-swap around the rotation. | `routers/auth.py:159` | Medium |
| SEC-14 | **Recovery code linear-scan timing** — `mfa_recovery` iterates Argon2 over all 10 unused codes; response time leaks the position of the matching code. Fix: constant-time scan (check all codes, record match index, never early-exit). | `routers/mfa.py:122` | Low |
| SEC-15 | **Step-up token not bound to session** — a captured step-up token can be replayed in a different session within the 5-minute window. Fix: include the issuing access token's JTI as a claim and verify it in `require_stepup`. | `routers/auth.py:347`, `deps.py:62` | Low |
| SEC-16 | **`X-Forwarded-For` trusted unconditionally** — `services/device.py:get_ip()` takes the first value in `X-Forwarded-For` without validating the upstream proxy. An attacker can spoof IP with `X-Forwarded-For: 127.0.0.1`. Fix: only trust the header when behind a known trusted proxy (configurable CIDR list). | `services/device.py:13` | Low |

> Issues SEC-01 through SEC-11 were fixed in the same review session (logout ownership, timing oracle, session invalidation on password reset, OTP race condition, verify-email suspended account bypass, rate limiting, CORS hardening, config pepper default guard, Ed25519 key caching, step-up user-active check).
