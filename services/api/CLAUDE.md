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

### Full API Surface

| Prefix | Router file | Auth | Purpose |
|--------|-------------|------|---------|
| `/auth/...` | `routers/auth.py` | varies | Register, login, refresh, logout, verify-email, step-up, `/me` |
| `/auth/mfa/...` | `routers/mfa.py` | required | TOTP setup/verify, recovery codes |
| `/auth/sessions` | `routers/sessions.py` | required | List & revoke active sessions |
| `/complaints/track/{code}` | `routers/tracking.py` | none | Anonymous complaint status lookup |
| `/ai/chat` | `routers/ai.py` | required | 7-stage RAG pipeline (POST) |
| `/ai/health` | `routers/ai.py` | none | AI subsystem status |
| `/v1/alerts/...` | `routers/alerts.py` | varies | Alert events, responses, evidence |
| `/v1/users/me/fcm-token` | `routers/alerts.py` | required | Register FCM push token (POST) |
| `/v1/users/me/location` | `routers/alerts.py` | required | Upsert location snapshot + geofence consent (POST) |
| `/v1/admin/alerts/...` | `routers/admin_alerts.py` | admin | Alert management, stats, zone CRUD |
| `/v1/admin/geofence` | `routers/geofence.py` | admin | Campus boundary polygon (GET/POST) |
| `/v1/applications/...` | `routers/applications.py` | required | Campus application submissions |
| `/v1/feed/...` | `routers/feed.py` | varies | Verification feed posts, signals, flags |
| `/v1/feed/admin/...` | `routers/feed_admin.py` | admin | Feed moderation dashboard |
| `/v1/filings/...` | `routers/filings.py` | required | Complaints, reports, grievances |
| `/v1/notices` | `routers/notices.py` | optional | Campus notices (draft/publish) |
| `/v1/zones` | `routers/zones.py` | none | Active safety zones with bbox filter |
| `/v1/lawyers` | `routers/lawyers.py` | none | Verified lawyer directory |
| `/v1/routines` | `routers/routines.py` | optional | Academic class schedules (draft/publish) |
| `/v1/departments/...` | `routers/dept_ratings.py` | optional | Dept ratings + per-dept summary |
| `/v1/admin/users/...` | `routers/admin_users.py` | admin/super_admin | List users, create admin/moderator, patch role/status |
| `/v1/admin/campus-zones/...` | `routers/campus_zones.py` | admin | Campus polygon zones (zone_type=campus only) |
| `/v1/super-admin/zones/...` | `routers/super_zones.py` | super_admin | Red/purple/black zone CRUD (polygon + circle) |
| `/v1/admin/timetable/...` | `routers/admin_timetable.py` | admin | CP-SAT timetable CRUD, solver jobs, NL edits, publish |
| `/health` | `main.py` | none | DB + Redis liveness probe |

### Services (pure business logic, no HTTP)
- `services/token.py` — Ed25519 JWT sign/verify via PyJWT + cryptography; `jti` deny-list in Redis
- `services/password.py` — HMAC-SHA256 pepper applied **before** Argon2id hashing; uses low cost in `ENVIRONMENT=testing`
- `services/otp.py` — 6-digit OTP via `secrets.randbelow`, stored as Argon2id hash in Redis with TTL
- `services/mfa.py` — TOTP via pyotp; QR code as `data:image/png;base64,...`
- `services/audit.py` — SHA-256 hash chain: each row hashes `prev_hash + canonical_json(event)`
- `services/alert_svc.py` — full alert fan-out: creates `Zone`, queries `UserLocationSnapshot` for consenting nearby users, calls `fcm_svc.send_batch()`, records `AlertNotification` rows
- `services/fcm.py` — lazy Firebase Admin SDK init; degrades gracefully when `FCM_SERVICE_ACCOUNT_JSON_PATH` is unset; `send_to_token()` / `send_batch()` (max 500 tokens/call)
- `services/geofence.py` — tenant campus boundary polygon storage/retrieval
- `services/notice_svc.py`, `routine_svc.py`, `dept_rating_svc.py` — campus-specific content services
- `services/feed_svc.py` — feed post CRUD, trust-weighted signal scoring, archival logic, post-state machine
- `services/feed_prescreen.py` — AI pre-screening gate: regex block patterns first, then keyword-hint check per category; rejects or flags before publish
- `services/feed_sse.py` — Redis pub/sub bridge for real-time signal-count pushes; `GET /v1/feed/{id}/signals/stream` is an SSE endpoint; keepalive comment sent every 30 s
- `services/feed_attachment_svc.py` — validates MIME type, SHA-256 deduplicates, stores to `uploads/feed/`; limits configurable in `config.py` (`FEED_MAX_ATTACHMENTS`, `FEED_MAX_ATTACHMENT_MB`)
- `services/feed_moderation_svc.py` — records `VerificationFeedModeration` rows; drives the false-alarm strike system and trust-tier promotions
- `services/timetable_svc.py` — CRUD for all timetable entities (terms, batches, sections, rooms, courses, faculty, offerings, constraints)
- `services/timetable_solver.py` — CP-SAT constraint solver (Google OR-Tools); `run_solve_job()` runs as a FastAPI `BackgroundTask`; `nl_to_entry_edit()` translates natural-language schedule edits via Ollama; solver supports warm-start from `prev_entries` for perturbation runs

### Common patterns

**Service error convention** — services raise `ValueError` for domain errors (duplicate, already-published, etc.); routers catch and convert to `HTTPException(409)`.

**Optional auth** — endpoints that show different content to admins vs. public use `HTTPBearer(auto_error=False)` + `Security()`:
```python
_opt_bearer = HTTPBearer(auto_error=False)

async def _opt_user(
    creds: HTTPAuthorizationCredentials | None = Security(_opt_bearer),
    db: AsyncSession = Depends(get_db),
    redis=Depends(get_redis),
) -> TokenData | None:
    if creds is None:
        return None
    try:
        payload = decode_token(creds.credentials)
        if payload.get("type") != "access":
            return None
        td = TokenData(payload)
        if await is_blacklisted(redis, td.jti):
            return None
        result = await db.execute(select(User).where(User.id == td.user_id))
        user = result.scalars().first()
        return td if user and user.status == AccountStatus.active else None
    except Exception:
        return None
```
Used in: `routers/notices.py`, `routers/routines.py`.

**Draft/publish state machine** — Notices, routines, feed posts, filings, and applications all use a `status`/`state` string column (`draft → published → archived`). Students see only `published`; admin/moderator sees all. `server_default="published"` in migrations preserves existing rows when status columns are added.

**Pagination** — all list endpoints use `page: int = Query(default=1, ge=1)` with `PAGE_SIZE = 20` offset-limit in the service.

**Multi-tenant scoping** — `token.tenant_id` (from JWT) scopes data per university. Notices, routines, and ratings store `tenant_id`; service filters by it when non-null. `StudentCampusSettings.department` is the canonical source of a student's department string.

**Route ordering** — when a parameterized route like `/{dept}/summary` and a literal like `/ratings/mine` share a prefix, register the literal first or FastAPI captures "mine" as `{dept}`.

### Roles

`Role` enum in `models/user.py`: `student | user | moderator | admin | super_admin`

- `super_admin` bypasses all `require_role()` checks (`deps.py`). It is not assignable via the normal registration flow — use `create_superadmin.py` (see below).
- Non-`super_admin` admins are scoped to their own `tenant_id` when listing users via `/v1/admin/users`.
- `PATCH /v1/admin/users/{id}/role` requires `super_admin`; `PATCH /{id}/status` requires `admin` or `moderator`.

**Seeding a super admin** (run once after `alembic upgrade head`):

```powershell
cd services/api
.\.venv\Scripts\python.exe create_superadmin.py <password>
```

This creates (or resets) the `teamaivion@gmail.com` account with `role=super_admin`. Re-running it updates the password and resets the role — safe to run multiple times.

### Auth flow nuances
- **MFA login**: on success with MFA enabled, a UUID is stored in Redis (`mfa_pending:{token}`, 2-min TTL); client must POST to `/auth/mfa/verify` with that token — no partial JWT is issued
- **Refresh token theft**: if a previously-rotated refresh jti is replayed, ALL user sessions are revoked + `token_reuse_detected` audit event emitted
- **Token type field**: all JWTs include `"type": "access"|"refresh"|"stepup"` — stepup tokens are checked in `require_stepup()`

### Database notes
- All UUIDs generated server-side
- `audit_logs` is append-only (enforced at DB role level in production)
- `sessions.refresh_token_hash` stores Argon2id hash of the raw refresh JWT string
- Alembic auto-generates migrations from SQLAlchemy models: `alembic revision --autogenerate -m "description"`
- Migration chain: `035cab04b834_initial_schema` → `1e240152fca9_alert_system` → `a3f7c8d2e1b5_application_system` → `b9f2a1c3d4e5_verification_feed` → `c5d3e2f1a0b9_filing_system` → `d4e5f6a7b8c9_notices_and_lawyers` → `e5f6a7b8c9d0_routine_notice_status_dept_rating` → `f0a1b2c3d4e5_add_super_admin_role` → `37afe0ddaa21_add_tenant_geofences` → `a8b3c4d5e6f7_unified_zones` → `b1c2d3e4f5a6_radius_m_nullable` → `c0d1e2f3a4b5_timetable_generator`
- The `super_admin` enum value was added as an `ALTER TYPE` (PostgreSQL only). The SQLite test path does not run enum DDL, so the `super_admin` role works in tests via the string-based `Role` enum in Python.

## Testing

Tests use SQLite in-memory + fakeredis — no Docker needed. `conftest.py` sets `ENVIRONMENT=testing` before any imports so Argon2 uses low cost (`memory_cost=256`).

**Core fixtures** (all `pytest_asyncio.fixture`):
- `db_session` — fresh SQLite schema per test; overrides `get_db` so the test and handler share the same session
- `mock_redis` — `FakeRedis`; yields `(redis, dict)` for back-compat with tests that unpack both
- `client` — `httpx.AsyncClient` against the FastAPI ASGI app; depends on both above
- `registered_user` — registers + verifies a `user`-role account; returns `{email, password, tokens}`

**Admin re-login pattern** — after updating a user's role in the DB, re-login to get a fresh JWT that carries the new role:
```python
async def _make_admin_and_relogin(client, db_session, email, password):
    await db_session.execute(update(User).where(User.email == email).values(role="admin"))
    await db_session.commit()
    resp = await client.post("/auth/login", json={"identifier": email, "password": password})
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}
```

**Publish helper** — for draft/publish tests, factor out the publish step:
```python
async def _publish(client, headers, resource_id, prefix="/v1/notices"):
    r = await client.post(f"{prefix}/{resource_id}/publish", headers=headers)
    assert r.status_code == 200
    return r.json()
```

**Rate limiting** — the `_disable_rate_limit` autouse fixture sets `limiter.enabled = False` so 429s never appear mid-suite. Re-enable in tests that specifically exercise rate limits.

**HTTPBearer 401 vs 403** — `HTTPBearer()` returns 401 when no `Authorization` header is present (not 403). Assert `status_code in (401, 403)` when testing unauthenticated access to a guarded route.

## Environment
`.env` file is pre-populated (PASSWORD_PEPPER and SECRET_KEY are already generated). Keys are in `.keys/` (Ed25519 PEM files). Never commit `.env` or `.keys/`.

**FCM config** (required for push notifications):
```
FCM_PROJECT_ID=project-anchor-76170
FCM_SERVICE_ACCOUNT_JSON_PATH=C:/Users/Acer/Downloads/project-anchor-76170-firebase-adminsdk-fbsvc-e6d1d3d97a.json
```
Use forward slashes in the path — backslashes are treated as escape sequences by python-dotenv.

**Alert fan-out tuning** (all in `app/config.py`, safe to override in `.env`):
- `ALERT_ZONE_RADIUS_M=1000` — initial nearby-user search radius
- `ALERT_LOCATION_STALENESS_MINUTES=10` — max age of location snapshot for fan-out targeting
- `ALERT_NEARBY_PAUSE_THRESHOLD=3` — responders needed to pause fan-out

**Known `.env` issue** — the pre-existing `CLAUDE MESSAGE=` line (space in key name) causes a python-dotenv warning on every startup. It is cosmetic and does not break config loading.

**AI warmup** — the RAG service (`services/rag`) auto-loads `sample_corpus.py` into the `national` ChromaDB namespace at startup if empty. The Core API no longer runs warmup directly. Set `DISABLE_AI_WARMUP=true` in `services/rag/.env` to skip on memory-constrained deployments (e.g. Railway without a persistent volume — the 400 MB sentence-transformer models cause an OOM crash loop on ephemeral containers).

**Registration flow** — `POST /auth/register` stores the payload as JSON in Redis (`reg_payload:{identifier}`, TTL = `otp_ttl`) and creates no DB row. The `User` row is created as `active` only when the OTP is successfully verified via `/auth/verify-email` or `/auth/verify-phone`. This prevents ghost accounts — if the OTP expires, both Redis keys vanish and the user can re-register cleanly. Old `pending_verification` rows (from before this fix) are deleted on sight when a new registration arrives for the same identifier.

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
