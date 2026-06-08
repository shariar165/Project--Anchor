# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the app

No build step. Open `index.html` directly in a browser, or serve the directory with any static server:

```
npx serve .
# or
python -m http.server 8080
```

The `src/*.jsx` files in the modular layout require being served over HTTP (not `file://`) due to browser CORS restrictions on relative script imports. The standalone `index.html` works from `file://` because all JSX is inlined.

## Architecture

This is a **no-build React prototype** using Babel in-browser transpilation. There is no npm, no bundler, no type-checker, and no test suite.

### Two entry points

- **`index.html`** — standalone, self-contained; all JSX from `src/` is inlined as `<script type="text/babel">` blocks. Tailwind v4 browser CDN. Works offline once cached.
- **`src/*.jsx`** — the modular source of truth. If you edit logic, edit here and re-inline into `index.html` manually (or re-run the bundling step that copies them in order).

### Global namespace pattern

There is no module system. Each `src/*.jsx` file exports its components by calling `Object.assign(window, { ComponentA, ComponentB, ... })` at the bottom. Scripts must be loaded in dependency order — that order is:

```
data → primitives → shell → entry → uni-dashboard → uni-complaints →
uni-routine → uni-misc → super → settings → tweaks-panel → app
```

### Routing

Hash-based (`window.location.hash`). The `useHashRoute` hook in `app.jsx` drives all navigation. Routes are prefixed `/university/...` or `/super/...`. No nested routing library.

### Two admin surfaces

| Surface | Accent color | Entry route |
|---|---|---|
| University Admin | `--sage` (green) | `/university/login` → `/university/dashboard` |
| Super Admin | `--ember` (red) | `/super/login` → `/super/dashboard` |

Both surfaces share the `AdminShell` layout (sidebar + topbar). The sidebar nav config lives inside `AdminShell` in `shell.jsx`; adding a new route requires adding it there **and** wiring it in the `uniView`/`supView` switch in `app.jsx`.

### Theming system

All colors are CSS custom properties on `:root` (see the `<style>` block in `index.html`). Three orthogonal tweak dimensions are applied as `data-*` attributes on `<html>` by `app.jsx`:

- `data-palette` — `civic | court | field | ops` (swaps accent colors)
- `data-voice` — `serif | sans | mono` (swaps heading typeface)
- `data-surface` — `paper | slate | canvas` (swaps card/border feel)

Dark mode adds `html.dark` class and is persisted to `localStorage` under key `anchor:dark`.

### Shared primitives (`src/primitives.jsx`)

All UI building blocks — `Icon`, `KpiCard`, `StatusPill`, `Card`, `PageHeader`, `PrimaryButton`, `GhostButton`, `DataTable`, `ConfirmModal`, `SlideOver`, `Timeline`, `Tag`, `MonoChip`, `AuditNote`, `useDark` — live here and are exposed on `window`. Use these; do not add one-off inline styles when a primitive covers the case.

### Mock data (`src/data.jsx`)

All sample data (complaints, alerts, tenants, audit log, timetable, etc.) lives in `window.AnchorData`. It is a plain JS object — no API calls. To add a new data set, add it to the IIFE in `data.jsx` and expose it in the `return` statement.

### Tweaks panel (`src/tweaks-panel.jsx`)

Ships its own isolated CSS string (`__TWEAKS_STYLE`) injected at runtime. The `useTweaks` hook stores state in React and also posts `__edit_mode_set_keys` messages to the parent frame (for the Claude Design host). The panel appears when it receives `__activate_edit_mode` via `postMessage`.
