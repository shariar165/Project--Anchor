# Anchor AI — Architecture

Anchor AI is a civic trust platform for Bangladesh. One FastAPI backend serves three frontends: a student mobile app (campus safety, complaints, legal aid), a university admin panel, and a planned super-admin console. A separate RAG service (Phase 3) runs the 7-stage legal AI pipeline so it cannot starve the main API.

---

## Repository Layout

```
anchor/
├── README.md                    # 90-second pitch + quick start
├── ARCHITECTURE.md              # this file
├── LICENSE
├── docker-compose.yml           # full-stack local: db, redis, rag, api
├── .env.example
│
├── apps/
│   ├── student/                 # React 18 SPA — campus + national modes
│   │   ├── src/                 # 11 JSX component files
│   │   ├── index.html           # entry point; no build step
│   │   ├── firebase-messaging-sw.js
│   │   └── vercel.json
│   └── admin/                   # University + Super Admin panel
│       ├── src/                 # 13 JSX files (incl. timetable, complaints)
│       ├── index.html
│       └── vercel.json
│
├── services/
│   ├── api/                     # FastAPI Core — auth, users, alerts, feed, ...
│   │   ├── app/
│   │   │   ├── main.py
│   │   │   ├── routers/         # 22 route files
│   │   │   ├── services/        # 25 service modules
│   │   │   ├── models/          # 20 SQLAlchemy ORM models
│   │   │   ├── schemas/         # 13 Pydantic schema files
│   │   │   ├── config.py        # pydantic-settings; get_settings()
│   │   │   └── deps.py          # get_current_user, require_role(*roles)
│   │   ├── alembic/             # 12 migrations (all schema changes go here)
│   │   ├── tests/               # 18 test files; SQLite + fakeredis in-memory
│   │   └── Dockerfile
│   └── rag/                     # RAG Service — standalone FastAPI
│       ├── app/
│       │   ├── main.py          # /chat  /ingest  /health
│       │   └── pipeline/        # 7-stage corrective RAG (stage0–stage6)
│       └── Dockerfile
│
├── docs/
│   ├── specs/                   # architecture + feature specs
│   └── design-exports/          # design_*.jsx prototype exports (not shipped)
│
└── scripts/
    ├── dev.sh                   # one-command local startup
    └── gen-api-types.sh         # OpenAPI → TypeScript types (Phase 5)
```

---

## Apps

### `apps/student/`

No-build React 18 SPA. CDN React + Babel Standalone; JSX transpiled in-browser. Served by Vercel with `outputDirectory: "."` (no build step).

**Two operating modes** (toggled by `C2CToggle` in `app.jsx`):
- **Campus Mode** (DIU): complaints, applications, academic routine, campus notices, dept ratings
- **National Mode** (Bangladesh): FIR/GD drafting, lawyer directory, red-zone safety maps, legal rights

**Script load order** (dependency order matters — no module bundler):
1. `ios-frame.jsx` → `icons.jsx` → `splash.jsx` → `screens.jsx` → `screens-2.jsx`
2. `chat-pro.jsx` → `auth.jsx` → `applications.jsx` → `filings.jsx`
3. `verification-feed.jsx` → `app.jsx`

**State** lives in `AppCtx` (`app.jsx`): `mode`, `route`, `lang`, `auth`, `geofenceConsent`. Navigation via `go(name, params)` / `back()` — no router library.

**Auth tokens** in `localStorage`: `anchor_access_token`, `anchor_refresh_token`, `anchor_auth`.

**API helpers** exported as window globals: `apiFetch` (applications.jsx), `filingApiFetch` (filings.jsx) — all target `http://localhost:8000`.

**Push notifications**: FCM via `firebase-messaging-sw.js` service worker. Requires `env.js` (gitignored; copy from `env.example.js`).

### `apps/admin/`

No-build React 18 admin panel. Two surfaces sharing `AdminShell` layout:

| Surface | Route prefix | Accent | Key files |
|---|---|---|---|
| University Admin | `/university/*` | `--sage` (green) | `uni-dashboard`, `uni-complaints`, `uni-timetable`, `uni-misc`, `uni-routine` |
| Super Admin | `/super/*` | `--ember` (red) | `super.jsx` |

Hash-based routing via `useHashRoute` in `app.jsx`. All API calls via `AnchorAPI` (`src/api.jsx`) — reads `anchor_admin_access_token` from `localStorage`, auto-refreshes on 401. Base URL: `http://localhost:8000`.

Theming: `data-palette` (civic/court/field/ops), `data-voice` (serif/sans/mono), `data-surface` (paper/slate/canvas). Dark mode via `html.dark` class, persisted to `localStorage` key `anchor:dark`.

---

## Services

### `services/api/` — FastAPI Core

**Stack:** FastAPI · PostgreSQL 15 · Redis 7 · SQLAlchemy 2.0 (async) · Alembic · Pydantic v2 · PyJWT (Ed25519/EdDSA)

**Security:** Argon2id + HMAC-SHA256 pepper, Ed25519 JWTs, TOTP MFA, refresh token rotation with theft detection, SHA-256 audit hash chain.

**Key dependencies:**
- `app/deps.py` — `get_current_user()`, `require_role(*roles)`, `require_stepup()`. `super_admin` bypasses all role gates.
- `app/config.py` — all env vars via `pydantic-settings`; `get_settings()` is `@lru_cache`

**API surface summary:**

| Prefix | Purpose |
|---|---|
| `/auth/...` | Register, login, refresh, logout, verify-email, step-up, `/me` |
| `/auth/mfa/...` | TOTP setup/verify, recovery codes |
| `/auth/sessions` | List & revoke sessions |
| `/ai/chat` | Proxy to RAG service |
| `/v1/alerts/...` | Alert events + geofenced fan-out |
| `/v1/users/me/location` | GPS snapshot + geofence consent |
| `/v1/feed/...` | Verification feed (posts, signals, moderation) |
| `/v1/filings/...` | Complaints, reports, grievances |
| `/v1/applications/...` | Campus submissions |
| `/v1/notices` | Campus notices (draft/publish) |
| `/v1/routines` | Academic schedules (draft/publish) |
| `/v1/lawyers` | Verified lawyer directory |
| `/v1/departments/...` | Department ratings |
| `/v1/zones` | Active safety zones |
| `/v1/admin/...` | Alert mgmt, user mgmt, timetable, geofence, zones |
| `/v1/super-admin/zones/...` | Red/purple/black zone CRUD |
| `/complaints/track/{code}` | Anonymous complaint lookup |
| `/health` | DB + Redis liveness |

### `services/rag/` — RAG Service

**Stack:** FastAPI · ChromaDB · sentence-transformers · BM25 · Ollama (Qwen3)

Standalone FastAPI process. Not exposed publicly — Core API proxies `/ai/chat` to it. Protected by `X-Internal-Secret` shared header.

**7-stage corrective pipeline:**

```
Stage 0  stage0_safety.py       — emergency / injection pre-flight
Stage 1  stage1_query.py        — intent classification + entity extraction
Stage 2  stage2_retrieval.py    — dense (ChromaDB) + BM25, RRF merge, rerank
Stage 3  stage3_corrective.py   — confidence gate; web search fallback
Stage 4  stage4_generation.py   — legal reasoning scaffold with citations
Stage 5  stage5_verify.py       — claim-level verification; can trigger regen
Stage 6  stage6_output.py       — language adaptation, citations, disclaimer
```

**Endpoints:**
- `POST /chat` — run the full pipeline
- `POST /ingest` — load sample legal corpus (admin/setup)
- `GET  /health` — pipeline component availability

Vector store: ChromaDB at `data/chromadb`. Namespaces: `national` (Bangladesh law), `diu` (DIU campus).
LLM: Ollama with `qwen3:1.7b` (fast) / `qwen3:8b`. Falls back to deterministic stub when Ollama is offline.

---

## Data Flow

```
Browser (student app / admin)
    │
    ▼  JWT in Authorization header
services/api   :8000  ──────── Postgres :5433
    │                  └────── Redis    :6379
    │  POST /ai/chat (internal, X-Internal-Secret)
    ▼
services/rag   :8001  ──────── ChromaDB  (named volume)
                       └────── Ollama    (host machine)

Out-of-band: Firebase Cloud Messaging (push notifications)
```

The only process boundary that matters for availability: if `services/rag` goes down, `/ai/chat` returns 503 and the rest of the API stays healthy.

---

## Alert Fan-Out

1. User holds button 4 s → confirms → `POST /v1/alerts/trigger {lat, lng}`
2. Backend creates `AlertEvent` + `Zone`, enqueues background task
3. Task queries `UserLocationSnapshot` (consent=true, last_seen < 10 min, within radius)
4. Fetches `UserFCMToken` rows → `fcm_svc.send_batch()` (max 500/call)
5. Service worker `onBackgroundMessage` → `showNotification()`

Location snapshots kept fresh by `watchPosition` in `AppProvider` (one POST per 90 s).

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| No bundler for frontends | Zero build-time complexity; CDN React + Babel works for prototype scale |
| Ed25519 JWTs | Smaller tokens, fast verification, modern algo |
| Argon2id + HMAC-SHA256 pepper | Defense-in-depth: pepper means a DB dump alone is not enough to crack passwords |
| CP-SAT for timetable | Hard constraints (no room double-booking, faculty clash) are cleanly modeled as CSP |
| RAG as separate process | Ollama model load (400 MB sentence-transformers) can OOM constrained deployments; isolating prevents starving auth/alert handlers |
| Single Postgres for both services | RAG does not touch DB; two DBs adds ops cost with no benefit at this scale |

---

## Environment Variables

### `services/api/.env`

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | yes | `postgresql+asyncpg://user:pass@host/db` |
| `REDIS_URL` | yes | `redis://localhost:6379/0` |
| `JWT_PRIVATE_KEY_PATH` | yes | Path to Ed25519 PEM private key |
| `JWT_PUBLIC_KEY_PATH` | yes | Path to Ed25519 PEM public key |
| `PASSWORD_PEPPER` | yes (prod) | 32-byte hex; never change after users created |
| `SECRET_KEY` | yes (prod) | 32-byte hex |
| `RAG_SERVICE_URL` | yes | `http://localhost:8001` (or `http://rag:8001` in Docker) |
| `RAG_INTERNAL_SECRET` | recommended | Shared secret for API→RAG auth |
| `FCM_SERVICE_ACCOUNT_JSON_PATH` | optional | Firebase Admin SDK JSON; push disabled if unset |
| `OLLAMA_BASE_URL` | optional | Default `http://localhost:11434` |
| `BREVO_API_KEY` | optional | Email delivery; falls back to Gmail SMTP |
| `GMAIL_USER` / `GMAIL_APP_PASSWORD` | optional | Gmail SMTP fallback |
| `ENVIRONMENT` | optional | `development` / `production` (controls docs visibility) |
| `DISABLE_AI_WARMUP` | optional | Set `true` to skip 400 MB model load on startup |

### `services/rag/.env`

| Variable | Description |
|---|---|
| `OLLAMA_BASE_URL` | Default `http://localhost:11434` |
| `CHROMADB_PATH` | Default `data/chromadb` |
| `RAG_INTERNAL_SECRET` | Must match the API service value |
| `DISABLE_AI_WARMUP` | Skip corpus warmup on startup |

### `apps/student/` (runtime, gitignored)

Copy `env.example.js` → `env.js`. Values from Firebase Console.

---

## Deployment

| Component | Target | Notes |
|---|---|---|
| Student app | Vercel | Root Directory: `apps/student` |
| Admin panel | Vercel | Root Directory: `apps/admin` |
| Core API | Render / Railway free | Auto-deploy on `main`, `services/api/` |
| RAG service | Render (separate service) | Heavier; keep on separate plan |
| Postgres | Render Postgres free / Supabase | One DB shared by Core API only |
| ChromaDB | Persistent volume on RAG host | Named Docker volume locally |
| Ollama | Inside RAG container or host | Model pulled on first boot |
| FCM | Firebase | Service-account JSON in API env |

**Cold-start note:** Render free tier sleeps after 15 min idle. RAG cold start is ~60 s (model load). Add an UptimeRobot pinger on demo day hitting `/health` every 10 min.
