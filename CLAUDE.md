# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Anchor AI** is a civic trust platform with two layers:

1. **Frontend prototype** — React 18 SPA (CDN + Babel Standalone, no build step) in the repo root
2. **Backend API** — FastAPI + PostgreSQL + Redis in `backend/`; see `backend/CLAUDE.md` for full backend guidance

Both layers share two operating modes:
- **Campus Mode** (DIU — Daffodil International University): complaints, applications, academic routine, campus notices
- **National Mode** (Bangladesh): FIR/GD drafting, lawyer directory, red zone safety maps, legal rights

---

## Frontend Prototype

### Running

Open `index.html` directly in a browser, or use any static file server:

```bash
npx http-server . -p 8080
```

No npm install, no build step, no environment variables.

### File Load Order (critical)

`index.html` imports scripts top-to-bottom — order matters because each file uses globals defined by earlier files:

1. `ios-frame.jsx` — IOSDevice frame component
2. `icons.jsx` — SVG icon components
3. `splash.jsx` — Splash1, Splash2 intro screens
4. `screens.jsx` — HomeScreen, ChatScreen, AlertScreen
5. `screens-2.jsx` — CasesScreen, MapScreen, FeedScreen, LawyersScreen, etc.
6. `app.jsx` — App shell, AppCtx, Header, BottomNav, RouteView (mounts last)

`design_*.jsx` / `design_*.css` files are the earlier design exploration copies — they are not loaded by `index.html` and are kept as reference only.

### Architecture

**State & Routing** — `AppCtx` (React context in `app.jsx`) is the single source of truth:
- `mode`: `'campus' | 'country'` — drives accent colors (sage ↔ ember) and tile content
- `route`: `{ name, params }` — current screen
- `lang`: `'EN' | 'BN'`
- `history`: array for back-navigation

Navigation: `go(name, params)` pushes; `back()` pops. No router library.

`RouteView` in `app.jsx` is a switch on `route.name` that mounts the appropriate screen component. All screens receive `{ go, back, mode, lang }` from context.

**Data** — All hardcoded in `screens-2.jsx`: `ACTIVE_CASES`, `MOCK_LAWYERS`, `ZONES`, inline chat response strings. No localStorage — state resets on refresh.

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

Key utility classes: `.eyebrow`, `.pill`, `.card`, `.btn`/`.btn-primary`/`.btn-ghost`, `.tile`, `.botnav`, `.c2c-track`

### Key UI Patterns

- **C2CToggle** (`app.jsx`): Animated mode switch — flipping swaps the accent color CSS var and re-renders the tile grid
- **IOSDevice** (`ios-frame.jsx`): Pure CSS/SVG iPhone frame; no image assets
- **3-Phase Alert** (`screens.jsx`): Before/During/After tabs; press-and-hold button fills SVG ring over 4s
- **Splash animation**: Uses `animation-fill-mode: forwards` — do not remove or splash state leaks into app shell

---

## Backend — Quick Reference

Full guidance is in `backend/CLAUDE.md`. Key points for root-level context:

### Running

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
docker compose up -d db redis
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### Testing (no Docker required)

Tests use SQLite in-memory + fakeredis — runs without Postgres/Redis:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -x -v
# single file:
.\.venv\Scripts\python.exe -m pytest -x -v tests/test_login.py
```

### API Surface

| Prefix | Router file | Purpose |
|--------|-------------|---------|
| `/auth/...` | `routers/auth.py` | Register, login, refresh, logout, verify-email, step-up |
| `/auth/mfa/...` | `routers/mfa.py` | TOTP setup/verify, recovery codes |
| `/auth/sessions` | `routers/sessions.py` | List & revoke active sessions |
| `/complaints/track/{code}` | `routers/tracking.py` | Anonymous complaint status lookup |
| `/ai/chat` | `routers/ai.py` | 7-stage RAG pipeline (POST) |
| `/ai/health` | `routers/ai.py` | AI subsystem status |
| `/health` | `main.py` | DB + Redis liveness probe |

### AI Pipeline (`backend/app/ai/`)

`pipeline.py` orchestrates 7 stages in sequence:

```
Stage 0  safety.py        — emergency / injection pre-flight
Stage 1  stage1_query.py  — intent classification + entity extraction (Qwen3 via Ollama)
Stage 2  stage2_retrieval.py — hybrid dense (ChromaDB) + BM25, RRF merge
Stage 3  stage3_corrective.py — confidence gate; falls back to web search if below threshold
Stage 3b               — exit ramp + lawyer referral if confidence < ABSOLUTE_FLOOR
Stage 4  stage4_generation.py — legal reasoning scaffold with citation grounding
Stage 5  stage5_verify.py — claim-level verification; can trigger regeneration
Stage 6  stage6_output.py — language adaptation, citations, disclaimer
Stage 7  (inline in pipeline.py) — anonymised audit log
```

LLM: **Ollama** (local) with `qwen3:8b` (main) / `qwen3:1.7b` (fast). Automatically falls back to a deterministic stub when Ollama is offline, so tests and CI work without a GPU. Vector store: **ChromaDB** persisted at `backend/data/chromadb`. Namespaces: `national` (shared) and `diu` (campus-scoped).

### Security issues tracked (open — not yet fixed)

See `backend/CLAUDE.md` § "Security — Known Open Issues" for SEC-12 through SEC-16.
