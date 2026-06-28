# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Anchor AI** is a civic trust platform organized as a monorepo with four layers:

1. **Student app** — React 18 SPA (CDN + Babel Standalone, no build step) in `apps/student/`
2. **Admin panel** — no-build React prototype in `apps/admin/`
3. **Core API** — FastAPI + PostgreSQL + Redis in `services/api/`; see `services/api/CLAUDE.md` for full backend guidance
4. **RAG service** — standalone FastAPI microservice in `services/rag/`; hosts the 7-stage legal AI pipeline

Both frontend layers share two operating modes:
- **Campus Mode** (DIU — Daffodil International University): complaints, applications, academic routine, campus notices
- **National Mode** (Bangladesh): FIR/GD drafting, lawyer directory, red zone safety maps, legal rights

### Repo layout

```
apps/
  student/          # No-build React SPA — CDN + Babel Standalone
    src/            # All JSX + CSS source (ios-frame.jsx … app.jsx, styles.css)
    index.html      # Entry point — loads scripts from src/ in dependency order
    firebase-messaging-sw.js  # Service worker (must stay at web root, not in src/)
    env.example.js  # Copy to env.js and fill in Firebase values (gitignored)
  admin/            # No-build React admin panel
    src/            # Modular JSX files
    index.html      # Self-contained — all JSX inlined as <script type="text/babel">

services/
  api/              # FastAPI Core API — auth, alerts, feed, timetable, etc.
  rag/              # FastAPI RAG microservice — 7-stage AI pipeline

docs/
  design-exports/   # Earlier design exploration files (design_*.jsx / design_*.css)
  specs/            # Spec documents and known-issue write-ups

skills/             # Domain "skill" packs that ground RAG/backend prompts
  src/              # Editable skill sources (one dir per *.skill)
  *.skill           # Packed skill bundles consumed by skill_loader.py
  pack-skills.ps1   # Re-pack src/ → *.skill after editing a skill source

scripts/
  dev.sh            # One-command local startup (db+redis, rag:8001, api:8000)

docker-compose.yml  # Full-stack 4-container orchestration (db, redis, rag, api)
.env.example        # Documented env vars for all services
ARCHITECTURE.md     # Condensed architecture overview
```

---

## Student App (`apps/student/`)

### First-run setup

Firebase config is **not** hardcoded — copy the example files and fill in your project values:

```bash
cd apps/student
cp env.example.js env.js                        # Firebase web app config + VAPID key
cp firebase-sw-env.example.js firebase-sw-env.js  # must match env.js values
```

Values come from Firebase Console → Project Settings → Your Apps (web app) and → Cloud Messaging → Web Push certificates (VAPID key). Both files are `.gitignore`d.

### Running

```bash
cd apps/student
python -m http.server 8080        # Python — works for SW registration (needs HTTP, not file://)
npx http-server . -p 8080         # Node alternative
```

The service worker (`firebase-messaging-sw.js`) requires the app to be served over HTTP — `file://` will not register it.

### File Load Order (critical)

`apps/student/index.html` imports scripts top-to-bottom from `src/` — order matters because each file uses globals defined by earlier files. `src/strings.jsx` loads first as a plain `<script>` (not Babel) to expose translation strings before any component compiles; the rest load as `<script type="text/babel">`:

0. `src/strings.jsx` — i18n string tables (plain script, loads before everything)
1. `src/ios-frame.jsx` — IOSDevice frame component
2. `src/icons.jsx` — SVG icon components
3. `src/splash.jsx` — Splash1, Splash2 intro screens
4. `src/screens.jsx` — HomeScreen, ChatScreen, AlertScreen
5. `src/screens-2.jsx` — CasesScreen, MapScreen, FeedScreen, LawyersScreen, RoutinesScreen, DeptRatingScreen, NoticesScreen, ProfileScreen
6. `src/chat-pro.jsx` — Advanced chat interface
7. `src/auth.jsx` — Login, Register, MFA, EmailVerify, OTP, TrackingLookup; holds `registerFCMToken()` and `FIREBASE_CONFIG`
8. `src/applications.jsx` — Application submission screens; exports `apiFetch` and `getToken` as globals
9. `src/filings.jsx` — Complaint/filing screens; uses `filingApiFetch` global
10. `src/verification-feed.jsx` — Verification feed screens; uses `apiFetch` from `applications.jsx`
11. `src/e2ee.jsx` — `window.E2EE` helper: WebCrypto ECDH(P-256)→AES-GCM; `ensureKeyPair/deriveKey/encrypt/decrypt`. Needs `apiFetch`
12. `src/messaging.jsx` — `ConversationsScreen`, `ChatThreadScreen` (E2EE user↔lawyer chat), `ApplyLawyerScreen`. Uses `E2EE` + `apiFetch`
13. `src/police-reports.jsx` — National-mode FIR/GD police report screens
14. `src/officer-scorecards.jsx` — Officer accountability scorecard screens
15. `src/app.jsx` — App shell, AppCtx, Header, BottomNav, RouteView, GeofenceConsentModal (mounts last)

Firebase SDK CDN scripts load between Leaflet and the component scripts — they must be before `src/auth.jsx`.

Design exploration copies live in `docs/design-exports/` and are not loaded by `index.html`.

### Architecture

**State & Routing** — `AppCtx` (React context in `src/app.jsx`) is the single source of truth:
- `mode`: `'campus' | 'country'` — drives accent colors (sage ↔ ember) and tile content
- `route`: `{ name, params }` — current screen
- `lang`: `'EN' | 'BN'`
- `history`: array for back-navigation
- `auth`: `{ isAuthenticated, user, authStep, pendingIdentifier }` — persisted to `localStorage('anchor_auth')`
- `geofenceConsent`: `boolean` — whether user consents to location sharing for alert fan-out; persisted to `localStorage('anchor_geofence_consent')`

Navigation: `go(name, params)` pushes; `back()` pops. No router library.

**Auth persistence** — tokens are stored in `localStorage`:
- `anchor_auth` — serialized auth state (user profile, role, tenant_id)
- `anchor_access_token` — JWT access token; read directly via `localStorage.getItem` in AlertScreen and via `getAccessToken()` in auth.jsx
- `anchor_refresh_token` — JWT refresh token
- `anchor_geofence_consent` — `'true'|'false'` geofence opt-in
- `anchor_geofence_consent_answered` — `'true'` once the first-run modal has been dismissed
- `anchor_device_id` — stable device identifier for FCM token registration
- `anchor_e2ee_priv` / `anchor_e2ee_pub` — this device's ECDH keypair (JWK) for E2EE lawyer chat. **Private key never leaves the browser**; clearing storage or switching device loses the ability to decrypt old messages.

**E2EE lawyer chat** — `src/messaging.jsx` + `src/e2ee.jsx` implement end-to-end encrypted user↔lawyer messaging. The server (`/v1/conversations`) only ever stores ciphertext + IV; encryption keys are derived client-side (ECDH→AES-GCM) from the counterpart's public key fetched via `/v1/e2ee/keys/{user_id}`. Live delivery uses an `EventSource` SSE stream (`/v1/conversations/{id}/stream?token=…`, token in query because `EventSource` can't set headers). `AppProvider` publishes the device public key on every authenticated load so verified lawyers are reachable immediately.

**API helpers (globals)** — several modules export helper functions as window globals:
- `apiFetch(path, opts)` from `src/applications.jsx` — adds `Authorization` header
- `filingApiFetch(path, opts)` from `src/filings.jsx`
- `vfFetch(path, opts)` from `src/verification-feed.jsx`
- `alertApiPost(path, body, token)` from `src/screens.jsx` — used by AlertScreen

All helpers target `http://localhost:8000`. For production, update the `AUTH_API` / base URL constants in each file.

**Data** — Mock data in `src/screens-2.jsx` (`ACTIVE_CASES`, `MOCK_LAWYERS`, `ZONES`) is used as fallback when the backend is offline.

### Firebase Push Notifications

FCM web push requires three things to work end-to-end:

1. **`src/auth.jsx`** — `FIREBASE_CONFIG` and `FIREBASE_VAPID_KEY` are read from `window.ENV` (populated by `env.js` — see First-run setup above). `registerFCMToken()` is called fire-and-forget after every login completion (4 call sites). It no-ops if `FIREBASE_VAPID_KEY` is the placeholder string.

2. **`firebase-messaging-sw.js`** — service worker at `apps/student/` root; must be served at `/firebase-messaging-sw.js`. Already has real Firebase project config. Handles `onBackgroundMessage` to show push notifications.

3. **Backend** — `FCM_SERVICE_ACCOUNT_JSON_PATH` set in `services/api/.env` pointing to the Firebase Admin SDK service account JSON. FCM service (`services/api/app/services/fcm.py`) degrades gracefully if unconfigured.

> **Invariant — same project on both sides.** The client (`env.js` / `firebase-sw-env.js` / VAPID key) and the backend service-account JSON **must be the same Firebase project** (currently `project-anchor-e008b`, sender `621805042876`). A mismatch makes the Admin SDK reject every token as `SenderIdMismatch`, so no notification is ever delivered. Verify alignment via `GET /v1/admin/alerts/push-health` → `project_match: true`.

### Alert Fan-Out Chain

The complete path from button press to push notification:

1. `AlertScreen.handleConfirmSend` → `getCurrentPosition()` (5s timeout) → `POST /v1/alerts/trigger {lat, lng, gps_accuracy_m, gps_status}` with token from `localStorage.getItem('anchor_access_token')` (not from AppCtx — auth context does not carry the token)
2. Backend creates `AlertEvent` + `Zone`, enqueues `notify_nearby_users` background task
3. `notify_nearby_users` queries `UserLocationSnapshot WHERE geofence_consent=true AND last_seen_at > now()-10min` → fetches `UserFCMToken` rows → `fcm_svc.send_batch()`
4. Service worker `onBackgroundMessage` fires → `showNotification()`

Location snapshots are kept fresh by `watchPosition` in `AppProvider` (throttled to one POST per 90s to `POST /v1/users/me/location`). Polling only runs when `auth.isAuthenticated && geofenceConsent`.

### Design System

CSS custom properties in `src/styles.css`:

```
--navy: #0B1D35    primary dark
--cream: #F7F3EE   paper background
--sage: #4A6B5C    campus mode accent
--ember: #C44536   national mode accent
--gold: #B8893A    trust/verification badge
--red: #E8312A     alert/emergency
--mist: #E5E0D6    hairline borders
```

Typography: **Fraunces** (serif headings) · **Inter Tight** (UI/body) · **Hind Siliguri** (Bangla) · **JetBrains Mono** (case IDs)

Key utility classes: `.eyebrow`, `.pill`, `.card`, `.btn`/`.btn-primary`/`.btn-ghost`, `.tile`, `.botnav`

### Key UI Patterns

- **C2CToggle** (`src/app.jsx`): Animated mode switch — flipping swaps the accent color CSS var and re-renders the tile grid
- **IOSDevice** (`src/ios-frame.jsx`): Pure CSS/SVG iPhone frame; no image assets
- **3-Phase Alert** (`src/screens.jsx`): Before/During/After tabs; 4s press-and-hold fills SVG ring, then confirmation modal before `POST /v1/alerts/trigger`
- **GeofenceConsentModal** (`src/app.jsx`): Bottom-sheet shown once on first login; accept/decline stored in localStorage; re-accessible via ProfileScreen → Location toggle
- **Splash animation**: Uses `animation-fill-mode: forwards` — do not remove or splash state leaks into app shell

---

## Admin Panel (`apps/admin/`)

No-build React prototype. Full source in `apps/admin/src/`. Deploys to Vercel as a separate project (root directory: `apps/admin`).

### Running

```bash
cd apps/admin
python -m http.server 8081        # Python
npx serve .                        # Node alternative
```

Must be served over HTTP — `file://` breaks relative script imports due to browser CORS.

### Entry Points

- **`index.html`** — standalone, self-contained; all JSX from `src/` is inlined as `<script type="text/babel">` blocks. Works offline once cached.
- **`src/*.jsx`** — modular source of truth. Edit here; if you change logic, re-inline into `index.html` manually in dependency order.

### File Load Order (critical)

No module system — each file exposes components via `Object.assign(window, { ... })`. Load order:

```
data → api → primitives → shell → entry → uni-dashboard → uni-complaints →
uni-applications → uni-routine → uni-timetable → uni-misc → super → settings →
tweaks-panel → app
```

### Architecture

Two surfaces sharing the `AdminShell` layout (`src/shell.jsx`):

| Surface | Accent | Entry route | Key file |
|---------|--------|-------------|----------|
| University Admin | `--sage` (green) | `/university/login` → `/university/dashboard` | `src/uni-*.jsx` |
| Super Admin | `--ember` (red) | `/super/login` → `/super/dashboard` | `src/super.jsx` |

Hash-based routing via `useHashRoute` in `src/app.jsx`. Adding a new screen requires wiring it in both the sidebar nav config inside `AdminShell` (`shell.jsx`) **and** the `uniView`/`supView` switch in `app.jsx`.

All API calls go through `AnchorAPI` in `src/api.jsx` — reads `anchor_admin_access_token` from `localStorage` and auto-refreshes on 401.

### Theming System

Colors are CSS custom properties on `:root`. Three orthogonal tweak dimensions set as `data-*` attributes on `<html>` by `app.jsx`:

- `data-palette` — `civic | court | field | ops` (swaps accent colors)
- `data-voice` — `serif | sans | mono` (swaps heading typeface)
- `data-surface` — `paper | slate | canvas` (swaps card/border feel)

Dark mode adds `html.dark` class, persisted to `localStorage` under key `anchor:dark`.

### Shared Primitives (`src/primitives.jsx`)

All UI building blocks live here and are exposed on `window`: `Icon`, `KpiCard`, `StatusPill`, `Card`, `PageHeader`, `PrimaryButton`, `GhostButton`, `DataTable`, `ConfirmModal`, `SlideOver`, `Timeline`, `Tag`, `MonoChip`, `AuditNote`, `useDark`. Use these — do not add one-off inline styles when a primitive covers the case.

### Mock Data (`src/data.jsx`)

All sample data (complaints, alerts, tenants, audit log, timetable, etc.) lives in `window.AnchorData` — a plain JS object, no API calls. To add a new data set, add it to the IIFE in `data.jsx` and expose it in the `return` statement.

### Tweaks Panel (`src/tweaks-panel.jsx`)

Ships its own isolated CSS string (`__TWEAKS_STYLE`) injected at runtime. Appears when the panel receives `__activate_edit_mode` via `postMessage`. The `useTweaks` hook stores state in React and posts `__edit_mode_set_keys` messages to the parent frame.

### Alert Console (Super Admin)

`/super/alerts` in `src/super.jsx` — four tabs: Active, Historical, False-alarm moderation, Analytics. Calls:
- `GET /v1/admin/alerts`, `GET /v1/admin/alerts/stats`, `GET /v1/admin/alerts/{id}`
- `POST /v1/admin/alerts/{id}/ack|resolve|false`

### Red Zone Map (`/super/red-zones`)

Leaflet map with full zone CRUD. Calls `GET|POST /v1/admin/zones`, `PATCH|DELETE /v1/admin/zones/{id}`.

---

## Core API — Quick Reference (`services/api/`)

Full guidance is in `services/api/CLAUDE.md`. Key points:

### Running

```powershell
# From repo root — start db and redis only (rag runs separately)
docker compose up -d db redis      # PostgreSQL on :5433, Redis on :6379

cd services/api
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
```

Or use the root `docker-compose.yml` to bring up all 4 services at once:

```powershell
docker compose up --build
```

Config is in `services/api/.env`. Note the pre-existing `CLAUDE MESSAGE=` line (space in key) causes a dotenv warning but does not prevent the app from loading.

### Testing (no Docker required)

Tests use SQLite in-memory + fakeredis:

```powershell
cd services/api
.\.venv\Scripts\python.exe -m pytest -x -v
# single file:
.\.venv\Scripts\python.exe -m pytest -x -v tests/test_alerts.py
```

### Seeding

```powershell
cd services/api
.\.venv\Scripts\python.exe create_superadmin.py <password>
# Creates/resets teamaivion@gmail.com as super_admin. Safe to re-run.
```

### API Surface

| Prefix | Router file | Auth | Purpose |
|--------|-------------|------|---------|
| `/auth/...` | `routers/auth.py` | varies | Register, login, refresh, logout, verify-email, step-up, `/me` |
| `/auth/mfa/...` | `routers/mfa.py` | required | TOTP setup/verify, recovery codes |
| `/auth/sessions` | `routers/sessions.py` | required | List & revoke active sessions |
| `/complaints/track/{code}` | `routers/tracking.py` | none | Anonymous complaint status lookup |
| `/ai/chat` | `routers/ai.py` | required | Proxies to RAG service (POST) |
| `/ai/health` | `routers/ai.py` | none | RAG service health proxy |
| `/v1/alerts/...` | `routers/alerts.py` | varies | Alert events, responses, evidence |
| `/v1/users/me/fcm-token` | `routers/alerts.py` | required | Register FCM push token (`POST`) |
| `/v1/users/me/location` | `routers/alerts.py` | required | Upsert location snapshot + geofence consent (`POST`) |
| `/v1/admin/alerts/...` | `routers/admin_alerts.py` | admin | Alert management, stats, zone listing |
| `/v1/applications/...` | `routers/applications.py` | required | Campus application submissions |
| `/v1/feed/...` | `routers/feed.py` | varies | Verification feed posts, signals, flags |
| `/v1/feed/admin/...` | `routers/feed_admin.py` | admin | Feed moderation dashboard |
| `/v1/filings/...` | `routers/filings.py` | required | Complaints, reports, grievances |
| `/v1/notices` | `routers/notices.py` | optional | Campus notices (draft/publish) |
| `/v1/notifications/...` | `routers/notifications.py` | required | In-app notification feed: list (`?mode=`), unread-count, mark read / read-all, get/put preferences |
| `/v1/admin/notifications` | `routers/admin_notifications.py` | admin | Live-ops aggregate bell (derived counts) + admin channel preferences |
| `/v1/zones` | `routers/zones.py` | none | Active safety zones with bbox filter |
| `/v1/admin/geofence` | `routers/geofence.py` | admin | Campus boundary polygon (GET/POST) |
| `/v1/admin/zones` | `routers/admin_alerts.py` | admin | Red zone CRUD |
| `/v1/lawyers` | `routers/lawyers.py` | none | Verified lawyer directory |
| `/v1/lawyers/apply` · `/v1/lawyers/me` | `routers/lawyers.py` | required | Self-service lawyer application + own application status |
| `/v1/admin/lawyers/...` | `routers/admin_lawyers.py` | super_admin | List lawyer applications; verify (upgrades account to `lawyer` role) / reject |
| `/v1/e2ee/keys` | `routers/e2ee.py` | required | Upload own / fetch another user's E2EE public key |
| `/v1/conversations/...` | `routers/messaging.py` | required | E2EE user↔lawyer chat: start, list, messages, SSE stream, read |
| `/v1/legal-rights` | `routers/legal_rights.py` | none | Legal rights reference content |
| `/v1/routines` | `routers/routines.py` | optional | Academic class schedules (draft/publish) |
| `/v1/departments/...` | `routers/dept_ratings.py` | optional | Dept ratings + per-dept summary |
| `/v1/admin/users/...` | `routers/admin_users.py` | admin/super_admin | User management |
| `/v1/admin/campus-zones/...` | `routers/campus_zones.py` | admin | Campus polygon zones (zone_type=campus only) |
| `/v1/super-admin/zones/...` | `routers/super_zones.py` | super_admin | Red/purple/black zone CRUD (polygon + circle) |
| `/v1/admin/timetable/...` | `routers/admin_timetable.py` | admin | CP-SAT timetable CRUD, solver jobs, NL edits |
| `/v1/admin/applications/...` | `routers/admin_applications.py` | admin | Application review queue + stats (stage-based approval chain) |
| `/v1/admin/audit...` | `routers/admin_audit.py` | super_admin | Audit log read, hash-chain verify, export |
| `/v1/admin/deanonymization/...` | `routers/deanonymization.py` | admin/super_admin | De-anonymization requests; two-person approval + time-limited identity reveal |
| `/v1/police-reports/...` | `routers/police_reports.py` | required | National-mode FIR/GD police report drafting + submission |
| `/v1/officer-scorecards/...` | `routers/officer_scorecards.py` | varies | Public officer accountability scorecards + ratings |
| `/v1/admin/officer-scorecards/...` | `routers/admin_officer_scorecards.py` | admin | Officer scorecard moderation/management |
| `/v1/admin/analytics/...` | `routers/admin_analytics.py` | admin | University-admin analytics dashboards |
| `/v1/super-admin/tenants/...` | `routers/admin_tenants.py` | super_admin | Tenant (university) provisioning + management |
| `/v1/super-admin/config/...` | `routers/super_config.py` | super_admin | Platform-wide configuration |
| `/v1/super-admin/corpus/...` | `routers/super_corpus.py` | super_admin | RAG legal corpus management (ingest/list) |
| `/v1/super-admin/ai-health/...` | `routers/super_ai_health.py` | super_admin | RAG/AI pipeline health + diagnostics |
| `/v1/super-admin/analytics/...` | `routers/super_analytics.py` | super_admin | Platform-wide analytics |
| `/v1/super-admin/incidents/...` | `routers/super_incidents.py` | super_admin | Cross-tenant incident oversight |
| `/v1/super-admin/keys/...` | `routers/super_keys.py` | super_admin | Signing/API key management |
| `/health` | `main.py` | none | DB + Redis liveness probe |

---

## RAG Service — Quick Reference (`services/rag/`)

Standalone FastAPI microservice that hosts the 7-stage legal AI pipeline. The Core API (`/ai/chat`) proxies here after enforcing JWT auth; RAG never sees user JWTs — only a shared `X-Internal-Secret` header.

### Running

```powershell
cd services/rag
pip install -r requirements.txt
.\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8001
```

### Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /chat` | Run full 7-stage RAG pipeline; body passed through from Core API |
| `GET /health` | Check embedder, ChromaDB, and Ollama availability |
| `POST /ingest` | Load built-in sample corpus into ChromaDB (dev/demo only) |

### AI Pipeline (`services/rag/app/pipeline/`)

`pipeline.py` orchestrates 7 stages:

```
Stage 0  stage0_safety.py       — emergency / injection pre-flight
Stage 1  stage1_query.py        — intent classification + entity extraction (Qwen3 via Ollama)
Stage 2  stage2_retrieval.py    — hybrid dense (ChromaDB) + BM25, RRF merge
Stage 3  stage3_corrective.py   — confidence gate; falls back to web search if below threshold
Stage 3b                        — exit ramp + lawyer referral if confidence < ABSOLUTE_FLOOR
Stage 4  stage4_generation.py   — legal reasoning scaffold with citation grounding
Stage 5  stage5_verify.py       — claim-level verification; can trigger regeneration
Stage 6  stage6_output.py       — language adaptation, citations, disclaimer
Stage 7  (inline)               — anonymised audit log
```

LLM: **Ollama** (local) with `qwen3:8b` / `qwen3:1.7b` (fast). Falls back to a deterministic stub when Ollama is offline. Vector store: **ChromaDB** at `services/rag/data/chromadb`. Namespaces: `national` and `diu`.

**Skill grounding** — `skill_loader.py` loads the packed `*.skill` bundles from the repo-root `skills/` directory and injects their `grounding.md` content into pipeline prompts (e.g. FIR/GD drafting, feed moderation). After editing a skill source under `skills/src/`, re-run `skills/pack-skills.ps1` to regenerate the `*.skill` bundles the loader reads.

To ingest new legal documents into ChromaDB: use `services/rag/app/pipeline/ingestion.py` → `ingest_document()`. Chunks get contextual prefixes from the LLM before embedding (Anthropic-style contextual retrieval). Warm-up at startup auto-loads `sample_corpus.py` into the `national` namespace if empty; set `DISABLE_AI_WARMUP=true` in `services/rag/.env` to skip this on memory-constrained deployments (e.g. Railway without a persistent volume — the 400 MB sentence-transformer causes OOM otherwise).

### RAG ↔ API wiring

`services/api/app/routers/ai.py` is an HTTP proxy: it enforces JWT auth, then forwards the request body to `RAG_SERVICE_URL/chat` with `X-Internal-Secret`. On `ConnectError` it returns 503; on pipeline error it proxies the RAG status code. Configure via:

```
# services/api/.env
RAG_SERVICE_URL=http://localhost:8001
RAG_INTERNAL_SECRET=<shared-secret>

# services/rag/.env
RAG_INTERNAL_SECRET=<same-shared-secret>
```

---

## Timetable Generator (`services/api/app/services/timetable_solver.py`)

CP-SAT constraint solver (Google OR-Tools) that generates clash-free academic timetables. Exposed via `/v1/admin/timetable/...`:

- Data setup: Terms → Batches/Sections → Rooms → Courses → Faculty profiles → Offerings → Eligibility → Schedule config → Constraints
- `POST /v1/admin/timetable/solve` — enqueues a `TimetableSolveJob`; solver runs as a background task, writing `TimetableEntry` rows with `result_version`
- `POST /v1/admin/timetable/entries/{id}/edit` — manual drag-drop entry correction; validates no conflicts
- `POST /v1/admin/timetable/nl-edit` — natural language edit (e.g. "move Dr. Ahmed's Thursday slot to Tuesday") via `nl_to_entry_edit()`
- `POST /v1/admin/timetable/publish` — sets `published=true` on all entries for a term+version; students then see their schedule via `/v1/routines`
- `GET /v1/admin/timetable/validate` — returns all hard-constraint violations for a result version

The solver honors `TimetableConstraint` rows with `enforcement=hard|soft` and `weight`. `solver_status` on `TimetableSolveJob` reflects OR-Tools outcome: `OPTIMAL`, `FEASIBLE`, or `INFEASIBLE` (with `infeasible_core` populated for debugging).

### Known production blockers

- **`docs/specs/todo-registration-ghost-accounts.md`** — Registration ghost-account bug: **Fixed.** `POST /auth/register` now stores the payload in Redis (same TTL as the OTP) and creates no DB row. The `User` row is created as `active` only on successful OTP verification. Old `pending_verification` ghost rows are cleaned up on sight.
- **Security** — See `services/api/CLAUDE.md` § "Security — Known Open Issues" for SEC-12 through SEC-16 (TOTP secret stored plaintext, refresh token rotation race, step-up token binding, etc.).
