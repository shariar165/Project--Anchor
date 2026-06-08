# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Anchor AI** is a civic trust platform with three layers:

1. **Frontend prototype** — React 18 SPA (CDN + Babel Standalone, no build step) in the repo root
2. **Backend API** — FastAPI + PostgreSQL + Redis in `backend/`; see `backend/CLAUDE.md` for full backend guidance
3. **Admin panel** — no-build React prototype in `admin/`; has its own `admin/CLAUDE.md`

Both frontend layers share two operating modes:
- **Campus Mode** (DIU — Daffodil International University): complaints, applications, academic routine, campus notices
- **National Mode** (Bangladesh): FIR/GD drafting, lawyer directory, red zone safety maps, legal rights

---

## Frontend Prototype

### Running

```bash
python -m http.server 8080        # Python — works for SW registration (needs HTTP, not file://)
npx http-server . -p 8080         # Node alternative
```

The service worker (`firebase-messaging-sw.js`) requires the app to be served over HTTP — `file://` will not register it.

### File Load Order (critical)

`index.html` imports scripts top-to-bottom — order matters because each file uses globals defined by earlier files:

1. `ios-frame.jsx` — IOSDevice frame component
2. `icons.jsx` — SVG icon components
3. `splash.jsx` — Splash1, Splash2 intro screens
4. `screens.jsx` — HomeScreen, ChatScreen, AlertScreen
5. `screens-2.jsx` — CasesScreen, MapScreen, FeedScreen, LawyersScreen, RoutinesScreen, DeptRatingScreen, NoticesScreen, ProfileScreen
6. `chat-pro.jsx` — Advanced chat interface
7. `auth.jsx` — Login, Register, MFA, EmailVerify, OTP, TrackingLookup; holds `registerFCMToken()` and `FIREBASE_CONFIG`
8. `applications.jsx` — Application submission screens; exports `apiFetch` and `getToken` as globals
9. `filings.jsx` — Complaint/filing screens; uses `filingApiFetch` global
10. `verification-feed.jsx` — Verification feed screens; uses `apiFetch` from `applications.jsx`
11. `app.jsx` — App shell, AppCtx, Header, BottomNav, RouteView, GeofenceConsentModal (mounts last)

Firebase SDK CDN scripts load between Leaflet and the component scripts — they must be before `auth.jsx`.

`design_*.jsx` / `design_*.css` files are earlier design exploration copies — not loaded by `index.html`.

### Architecture

**State & Routing** — `AppCtx` (React context in `app.jsx`) is the single source of truth:
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

**API helpers (globals)** — several modules export helper functions as window globals:
- `apiFetch(path, opts)` from `applications.jsx` — adds `Authorization` header
- `filingApiFetch(path, opts)` from `filings.jsx`
- `vfFetch(path, opts)` from `verification-feed.jsx`
- `alertApiPost(path, body, token)` from `screens.jsx` — used by AlertScreen

All helpers target `http://localhost:8000`. For production, update the `AUTH_API` / base URL constants in each file.

**Data** — Mock data in `screens-2.jsx` (`ACTIVE_CASES`, `MOCK_LAWYERS`, `ZONES`) is used as fallback when the backend is offline.

### Firebase Push Notifications

FCM web push requires three things to work end-to-end:

1. **`auth.jsx`** — `FIREBASE_CONFIG` (already set to real project values) and `FIREBASE_VAPID_KEY` (fill in from Firebase Console → Project Settings → Cloud Messaging → Web Push certificates).  `registerFCMToken()` is called fire-and-forget after every login completion (4 call sites). It no-ops if `FIREBASE_VAPID_KEY` is still the placeholder.

2. **`firebase-messaging-sw.js`** — service worker at repo root; must be served at `/firebase-messaging-sw.js`. Already has real Firebase project config. Handles `onBackgroundMessage` to show push notifications.

3. **Backend** — `FCM_SERVICE_ACCOUNT_JSON_PATH` set in `backend/.env` pointing to the Firebase Admin SDK service account JSON. FCM service (`backend/app/services/fcm.py`) degrades gracefully if unconfigured.

### Alert Fan-Out Chain

The complete path from button press to push notification:

1. `AlertScreen.handleConfirmSend` → `getCurrentPosition()` (5s timeout) → `POST /v1/alerts/trigger {lat, lng, gps_accuracy_m, gps_status}` with token from `localStorage.getItem('anchor_access_token')` (not from AppCtx — auth context does not carry the token)
2. Backend creates `AlertEvent` + `Zone`, enqueues `notify_nearby_users` background task
3. `notify_nearby_users` queries `UserLocationSnapshot WHERE geofence_consent=true AND last_seen_at > now()-10min` → fetches `UserFCMToken` rows → `fcm_svc.send_batch()`
4. Service worker `onBackgroundMessage` fires → `showNotification()`

Location snapshots are kept fresh by `watchPosition` in `AppProvider` (throttled to one POST per 90s to `POST /v1/users/me/location`). Polling only runs when `auth.isAuthenticated && geofenceConsent`.

### Design System

CSS custom properties in `styles.css`:

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

- **C2CToggle** (`app.jsx`): Animated mode switch — flipping swaps the accent color CSS var and re-renders the tile grid
- **IOSDevice** (`ios-frame.jsx`): Pure CSS/SVG iPhone frame; no image assets
- **3-Phase Alert** (`screens.jsx`): Before/During/After tabs; 4s press-and-hold fills SVG ring, then confirmation modal before `POST /v1/alerts/trigger`
- **GeofenceConsentModal** (`app.jsx`): Bottom-sheet shown once on first login; accept/decline stored in localStorage; re-accessible via ProfileScreen → Location toggle
- **Splash animation**: Uses `animation-fill-mode: forwards` — do not remove or splash state leaks into app shell

---

## Admin Panel (`admin/`)

No-build React prototype. Full source in `admin/src/`. Deploys to Vercel as a separate project (root directory: `admin/`).

### Running

```bash
cd admin
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
data → primitives → shell → entry → uni-dashboard → uni-complaints →
uni-routine → uni-misc → super → settings → tweaks-panel → app
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

## Backend — Quick Reference

Full guidance is in `backend/CLAUDE.md`. Key points:

### Running

```powershell
cd backend
docker compose up -d db redis      # PostgreSQL on :5433, Redis on :6379
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
```

Docker Compose reads `backend/.env` — note the pre-existing `CLAUDE MESSAGE=` line (space in key) causes a dotenv warning but does not prevent the app from loading.

### Testing (no Docker required)

Tests use SQLite in-memory + fakeredis:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -x -v
# single file:
.\.venv\Scripts\python.exe -m pytest -x -v tests/test_alerts.py
```

### Seeding

```powershell
cd backend
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
| `/ai/chat` | `routers/ai.py` | required | 7-stage RAG pipeline (POST) |
| `/ai/health` | `routers/ai.py` | none | AI subsystem status |
| `/v1/alerts/...` | `routers/alerts.py` | varies | Alert events, responses, evidence |
| `/v1/users/me/fcm-token` | `routers/alerts.py` | required | Register FCM push token (`POST`) |
| `/v1/users/me/location` | `routers/alerts.py` | required | Upsert location snapshot + geofence consent (`POST`) |
| `/v1/admin/alerts/...` | `routers/admin_alerts.py` | admin | Alert management, stats, zone listing |
| `/v1/applications/...` | `routers/applications.py` | required | Campus application submissions |
| `/v1/feed/...` | `routers/feed.py` | varies | Verification feed posts, signals, flags |
| `/v1/feed/admin/...` | `routers/feed_admin.py` | admin | Feed moderation dashboard |
| `/v1/filings/...` | `routers/filings.py` | required | Complaints, reports, grievances |
| `/v1/notices` | `routers/notices.py` | optional | Campus notices (draft/publish) |
| `/v1/zones` | `routers/zones.py` | none | Active safety zones with bbox filter |
| `/v1/admin/geofence` | `routers/geofence.py` | admin | Campus boundary polygon (GET/POST) |
| `/v1/admin/zones` | `routers/admin_alerts.py` | admin | Red zone CRUD |
| `/v1/lawyers` | `routers/lawyers.py` | none | Verified lawyer directory |
| `/v1/routines` | `routers/routines.py` | optional | Academic class schedules (draft/publish) |
| `/v1/departments/...` | `routers/dept_ratings.py` | optional | Dept ratings + per-dept summary |
| `/v1/admin/users/...` | `routers/admin_users.py` | admin/super_admin | User management |
| `/health` | `main.py` | none | DB + Redis liveness probe |

### AI Pipeline (`backend/app/ai/`)

`pipeline.py` orchestrates 7 stages:

```
Stage 0  safety.py          — emergency / injection pre-flight
Stage 1  stage1_query.py    — intent classification + entity extraction (Qwen3 via Ollama)
Stage 2  stage2_retrieval.py — hybrid dense (ChromaDB) + BM25, RRF merge
Stage 3  stage3_corrective.py — confidence gate; falls back to web search if below threshold
Stage 3b                    — exit ramp + lawyer referral if confidence < ABSOLUTE_FLOOR
Stage 4  stage4_generation.py — legal reasoning scaffold with citation grounding
Stage 5  stage5_verify.py   — claim-level verification; can trigger regeneration
Stage 6  stage6_output.py   — language adaptation, citations, disclaimer
Stage 7  (inline)           — anonymised audit log
```

LLM: **Ollama** (local) with `qwen3:8b` / `qwen3:1.7b` (fast). Falls back to a deterministic stub when Ollama is offline. Vector store: **ChromaDB** at `backend/data/chromadb`. Namespaces: `national` and `diu`.

### Security issues tracked (open — not yet fixed)

See `backend/CLAUDE.md` § "Security — Known Open Issues" for SEC-12 through SEC-16.
