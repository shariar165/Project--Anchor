// Anchor AI — App shell: header, C2C toggle, bottom nav, route container
// Depends on: icons.jsx, screens.jsx (declared globally)

const { useState, useEffect, useLayoutEffect, useRef, useMemo, createContext, useContext } = React;

// ─────────────────────────────────────────────────────────────
// Shared app state
// ─────────────────────────────────────────────────────────────
const AppCtx = createContext(null);
const useApp = () => useContext(AppCtx);

const AUTH_ROUTES = new Set([
  'login', 'register', 'register-form',
  'verify-email', 'verify-otp', 'forgot-password',
  'mfa-verify', 'mfa-setup', 'tracking-lookup',
]);

// ─────────────────────────────────────────────────────────────
// State preservation — keep-alive cache + persistence helpers
// ─────────────────────────────────────────────────────────────
// The bottom-nav tab roots are never evicted from the keep-alive cache, so
// switching tabs always returns to exactly where you left each one.
const TAB_ROOTS = new Set(['home', 'cases', 'alert', 'chat', 'profile']);
// Beyond the tab roots, keep at most this many recently-visited screens mounted
// (LRU). Bounds memory and the number of concurrent background effects.
const MAX_CACHED = 12;

// A stable identity for a screen instance. Detail screens carry an id/conv so two
// different items get distinct, independently-preserved instances; returning to the
// same route+item restores the same one. Tab roots collapse to just their name.
function slotKeyFor(route) {
  const p = (route && route.params) || {};
  const disc = (p.id != null ? p.id
    : p.stationId != null ? p.stationId
    : (p.conv && p.conv.id != null) ? p.conv.id
    : p.focusAlert != null ? p.focusAlert
    : '');
  return (route ? route.name : 'home') + '::' + disc;
}

// Whether the screen a component is rendered inside is the currently-visible one.
// Real-time screens (e.g. chat SSE) read this to pause work while hidden.
const ScreenVisibilityCtx = createContext(true);
const useScreenVisible = () => useContext(ScreenVisibilityCtx);

// useState backed by localStorage — survives a hard reload, not just a remount.
// Same guarded try/catch pattern as the theme/lang state. Supports functional
// updates; passing `undefined` removes the key.
function usePersistentState(key, initial) {
  const [val, setVal] = useState(() => {
    try {
      const raw = localStorage.getItem(key);
      if (raw !== null) return JSON.parse(raw);
    } catch (_) { /* storage unavailable or bad JSON */ }
    return typeof initial === 'function' ? initial() : initial;
  });
  const set = (next) => {
    setVal(prev => {
      const resolved = typeof next === 'function' ? next(prev) : next;
      try {
        if (resolved === undefined) localStorage.removeItem(key);
        else localStorage.setItem(key, JSON.stringify(resolved));
      } catch (_) { /* storage unavailable */ }
      return resolved;
    });
  };
  return [val, set];
}

// Human-readable guidance for each push-capability reason returned by
// window.syncPushToken / getPushCapability. Shared by the consent modal and the
// Profile notification toggle so the messaging stays consistent.
function pushReasonMessage(reason) {
  switch (reason) {
    case 'granted':
    case 'ok':
    case 'default':
      return null; // nothing to warn about
    case 'ios-needs-install':
      return 'On iPhone, tap the Share button, then "Add to Home Screen", and open Anchor from the icon to receive alerts.';
    case 'ios-chrome':
      return 'On iPhone, open Anchor in Safari (not Chrome), then "Add to Home Screen" to receive alerts.';
    case 'denied':
      return 'Notifications are blocked. Enable them for this site in your browser settings to receive alerts.';
    case 'insecure-context':
      return 'Notifications need a secure (https) connection.';
    default:
      return "This browser can't receive push notifications, so alerts may not pop up on this device.";
  }
}

function GeofenceConsentModal({ onComplete, onDismiss }) {
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState(null);   // inline result message after enabling
  const [done, setDone] = useState(false);  // requests finished — show result + Done

  // Requests location, then notifications, in sequence (Chrome shows one prompt at
  // a time and silently drops simultaneous ones). Persists consent only when a real
  // position was obtained, and surfaces exactly why push did/didn't enable.
  //
  // iOS WebKit differs: Notification.requestPermission() must run SYNCHRONOUSLY in
  // the user gesture — any await before it (like waiting for a GPS fix) makes iOS
  // silently drop the prompt, so push never enables. We therefore branch: on iOS we
  // request notifications FIRST (in the tap), then location. Android keeps the
  // original location-first order verbatim, since it works perfectly there.
  const handleEnable = async () => {
    setBusy(true);
    setNote(null);

    const cap = window.getPushCapability ? window.getPushCapability() : null;
    const isIOS = !!(cap && cap.isIOS);

    const requestLocation = () => new Promise((res) => {
      if (!navigator.geolocation) return res(null);
      navigator.geolocation.getCurrentPosition(
        (p) => res(p),
        () => res(null),
        { timeout: 10000, maximumAge: 60000 }
      );
    });

    let position = null;
    let pushReason = 'unsupported';

    if (isIOS) {
      // iOS branch — notifications FIRST (synchronous in the gesture), then location.
      try {
        if (typeof Notification !== 'undefined' && Notification.requestPermission) {
          await Notification.requestPermission();
        }
        // Permission is now already resolved; a silent sync just mints + POSTs the token.
        if (window.syncPushToken) pushReason = await window.syncPushToken({ interactive: false });
      } catch (_) { /* best-effort */ }
      position = await requestLocation();
    } else {
      // Android / desktop branch — UNCHANGED: location first, then notifications.
      position = await requestLocation();
      try {
        if (window.syncPushToken) pushReason = await window.syncPushToken({ interactive: true });
      } catch (_) { /* best-effort */ }
    }

    const locationGranted = !!position;

    // Let the parent persist consent + post the first snapshot.
    onComplete({ locationGranted, position, pushReason });

    // Build an inline note if anything needs the user's attention.
    const msgs = [];
    if (!locationGranted) msgs.push('Location is off — enable it to receive nearby alerts.');
    const pushMsg = pushReasonMessage(pushReason);
    if (pushMsg) msgs.push(pushMsg);

    setBusy(false);
    if (msgs.length === 0) {
      onDismiss();  // all good — close immediately
    } else {
      setNote(msgs.join(' '));
      setDone(true);
    }
  };

  return (
    <div style={{ position:'fixed', inset:0, zIndex:9999, background:'rgba(11,29,53,0.55)',
                  backdropFilter:'blur(4px)', display:'flex', alignItems:'flex-end', justifyContent:'center' }}>
      <div style={{ background:'var(--cream)', borderRadius:'24px 24px 0 0', padding:'28px 24px 40px',
                    width:'100%', maxWidth:402 }}>
        <div style={{ width:40, height:4, borderRadius:999, background:'var(--mist)',
                      margin:'0 auto 22px' }}/>
        <div style={{ fontSize:22, fontWeight:500, color:'var(--navy)', fontFamily:'var(--font-serif)',
                      marginBottom:12 }}>Enable nearby alerts?</div>
        <p style={{ fontSize:13.5, color:'var(--muted)', lineHeight:1.65,
                    fontFamily:'var(--font-sans)', marginBottom: note ? 16 : 24 }}>
          Anchor can notify you when someone near you triggers an emergency alert.
          To do this we'll ask for two permissions next — <strong>location</strong>{' '}
          (shared anonymously, never stored beyond 10 minutes) and{' '}
          <strong>notifications</strong> (so the alert can pop up on your phone).
          You can turn both off at any time in Settings.
        </p>

        {note && (
          <div style={{ marginBottom:18, padding:'12px 14px', borderRadius:12,
                        background:'rgba(196,69,54,0.08)', border:'1px solid rgba(196,69,54,0.22)',
                        color:'var(--ember)', fontSize:12.5, lineHeight:1.55, fontFamily:'var(--font-sans)' }}>
            {note}
          </div>
        )}

        {!done ? (
          <>
            <button onClick={handleEnable} disabled={busy} className="btn btn-primary"
              style={{ width:'100%', height:48, borderRadius:12, fontSize:15, fontWeight:600,
                       marginBottom:10, opacity: busy ? 0.7 : 1 }}>
              {busy ? 'Requesting permissions…' : 'Enable nearby alerts'}
            </button>
            <button onClick={onDismiss} disabled={busy}
              style={{ width:'100%', height:40, borderRadius:12, fontSize:14,
                       background:'transparent', border:'none', cursor: busy ? 'default' : 'pointer',
                       color:'var(--muted)', fontFamily:'var(--font-sans)' }}>
              Not now
            </button>
          </>
        ) : (
          <button onClick={onDismiss} className="btn btn-primary"
            style={{ width:'100%', height:48, borderRadius:12, fontSize:15, fontWeight:600 }}>
            Got it
          </button>
        )}
      </div>
    </div>
  );
}

function AppProvider({ children }) {
  // Must be declared before useState so the initial mode and route are derived correctly
  const getStoredAuth = () => {
    try { return JSON.parse(localStorage.getItem('anchor_auth')); } catch { return null; }
  };
  const stored = getStoredAuth();

  // Restore the last route + back-stack across a reload / PWA reopen. Only when the
  // stored session is authenticated, the snapshot is fresh, and it points at an app
  // (non-auth) route — otherwise fall back to today's defaults. Functions can't be
  // serialized, so any callbacks in params are simply dropped on restore (the screen
  // remounts and re-derives them); in-session keep-alive preserves the live object.
  const NAV_FRESH_MS = 2 * 60 * 60 * 1000; // 2h
  const getStoredNav = () => {
    try {
      const parsed = JSON.parse(localStorage.getItem('anchor_nav_state'));
      if (!parsed || !parsed.route || typeof parsed.ts !== 'number') return null;
      if (Date.now() - parsed.ts > NAV_FRESH_MS) return null;
      if (AUTH_ROUTES.has(parsed.route.name)) return null;
      return parsed;
    } catch { return null; }
  };
  const storedNav = (stored && stored.isAuthenticated) ? getStoredNav() : null;

  // Campus is student-only. Default-deny: anyone who is NOT a confirmed student
  // (general 'user', admin, moderator, or an unexpected/stale role) gets national.
  // Keeps the pre-login screen on campus branding (stored is null before auth).
  const [mode, setMode] = useState(
    (storedNav && (storedNav.mode === 'campus' || storedNav.mode === 'country'))
      ? storedNav.mode
      : (stored?.isAuthenticated && stored?.user?.role !== 'student') ? 'country' : 'campus'
  );
  // 'EN' | 'BN' | 'BI' (bilingual/mixed). Any unknown/stale stored value → 'EN'.
  const normLang = (v) => (v === 'BN' || v === 'BI') ? v : 'EN';
  const [lang, setLangRaw] = useState(() => {
    try { return normLang(localStorage.getItem('anchor_lang')); } catch { return 'EN'; }
  });
  const setLang = (next) => {
    const val = normLang(next);
    try { localStorage.setItem('anchor_lang', val); } catch { /* storage unavailable */ }
    setLangRaw(val);
  };
  // Translate helper bound to the active language. type: 'ui' (default) | 'content'.
  const tr = (key, type) => (window.tStr ? window.tStr(key, lang, type) : key);

  // Theme — 'light' | 'dark'. First-run default follows the device
  // (prefers-color-scheme); once the user makes an explicit choice it is stored
  // under 'anchor_theme' and wins from then on. Storage reads are guarded the
  // same way as anchor_lang (private mode / disabled storage can throw).
  const systemPrefersDark = () => {
    try { return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches; }
    catch { return false; }
  };
  const [theme, setThemeRaw] = useState(() => {
    try {
      const saved = localStorage.getItem('anchor_theme');
      if (saved === 'light' || saved === 'dark') return saved;
    } catch { /* storage unavailable */ }
    return systemPrefersDark() ? 'dark' : 'light';
  });
  const setTheme = (next) => {
    const val = next === 'dark' ? 'dark' : 'light';
    try { localStorage.setItem('anchor_theme', val); } catch { /* storage unavailable */ }
    setThemeRaw(val);
  };
  const toggleTheme = () => setTheme(theme === 'dark' ? 'light' : 'dark');

  const [history, setHistory] = useState(
    (storedNav && Array.isArray(storedNav.history)) ? storedNav.history : []
  );
  const [auth, setAuth] = useState(
    stored || { isAuthenticated: false, user: null, authStep: null, pendingIdentifier: null }
  );
  const [route, setRoute] = useState(
    storedNav ? storedNav.route : {
      name: stored?.isAuthenticated ? 'home' : 'login',
      params: {},
    }
  );
  const [geofenceConsent, setGeofenceConsent] = useState(
    localStorage.getItem('anchor_geofence_consent') === 'true'
  );
  const [showGeofencePrompt, setShowGeofencePrompt] = useState(false);
  const [notifUnread, setNotifUnread] = useState(0);
  const watchIdRef = useRef(null);
  const lastLocationPostRef = useRef(0);

  const go = (name, params = {}) => {
    setHistory(h => [...h, route]);
    setRoute({ name, params });
  };
  const back = () => {
    setHistory(h => {
      if (h.length === 0) {
        setRoute({ name: auth.isAuthenticated ? 'home' : 'login', params: {} });
        return [];
      }
      const prev = h[h.length - 1];
      setRoute(prev);
      return h.slice(0, -1);
    });
  };
  // Navigate WITHOUT pushing the current route onto history (replace-in-place).
  // Used after publishing so Back skips the now-stale multi-step form.
  const replace = (name, params = {}) => setRoute({ name, params });

  const login = (userData) => {
    const newAuth = { isAuthenticated: true, user: userData, authStep: null, pendingIdentifier: null };
    setAuth(newAuth);
    localStorage.setItem('anchor_auth', JSON.stringify(newAuth));
    // Students are campus-first (can toggle to national); everyone else is national-only.
    setMode(userData.role === 'student' ? 'campus' : 'country');
    // First-run opt-in: show the consent modal on a device that hasn't answered yet,
    // but only where a browser prompt can actually help. On iOS-in-a-tab (or other
    // environments that can't receive push), the persistent AlertReadinessCTA shows
    // the right guidance ("Add to Home Screen") instead — popping a modal there is a
    // dead end. Every other not-ready state is covered by that always-present CTA.
    const answered = localStorage.getItem('anchor_geofence_consent_answered') === 'true';
    const cap = window.getPushCapability ? window.getPushCapability() : { reason: 'default' };
    const promptCanHelp = ['default', 'granted', 'ok', 'denied'].includes(cap.reason);
    if (!answered && promptCanHelp) {
      setShowGeofencePrompt(true);
    }
  };
  const logout = () => {
    // Best-effort: stop this device receiving pushes for the signed-out user.
    // Must run before the access token is cleared (the DELETE call needs it).
    try { window.deregisterPushToken && window.deregisterPushToken(); } catch (_) { /* best-effort */ }
    setAuth({ isAuthenticated: false, user: null, authStep: null, pendingIdentifier: null });
    localStorage.removeItem('anchor_auth');
    localStorage.removeItem('anchor_access_token');
    localStorage.removeItem('anchor_refresh_token');
    localStorage.removeItem('anchor_geofence_consent');
    localStorage.removeItem('anchor_geofence_consent_answered');
    // Clear preserved navigation + screen state so the next user starts clean and
    // no stale active-alert / form drafts leak across accounts on this device.
    try {
      localStorage.removeItem('anchor_nav_state');
      localStorage.removeItem('anchor_alert_active');
      Object.keys(localStorage)
        .filter(k => k.indexOf('anchor_draft_') === 0)
        .forEach(k => localStorage.removeItem(k));
    } catch (_) { /* storage unavailable */ }
    setGeofenceConsent(false);
    setHistory([]);
    setRoute({ name: 'login', params: {} });
  };
  const setAuthPending = (pending) => {
    setAuth(a => ({ ...a, ...pending }));
  };
  // Patch fields on the logged-in user (e.g. mfa flag after enrollment) and persist.
  const updateUser = (patch) => {
    setAuth(a => {
      if (!a.user) return a;
      const next = { ...a, user: { ...a.user, ...patch } };
      try { localStorage.setItem('anchor_auth', JSON.stringify(next)); } catch { /* storage unavailable */ }
      return next;
    });
  };

  // Reflect the active language on <html> so CSS can swap in the Bangla font for
  // full-BN mode (styles.css [data-lang="BN"]). EN / BI keep the Latin stack.
  useEffect(() => {
    try { document.documentElement.setAttribute('data-lang', lang); } catch (_) { /* SSR/no-DOM */ }
  }, [lang]);

  // Reflect the active theme on <html> (styles.css [data-theme="dark"]) and keep
  // the mobile status-bar tint (<meta name="theme-color">) in sync.
  useEffect(() => {
    try {
      document.documentElement.setAttribute('data-theme', theme);
      const meta = document.querySelector('meta[name="theme-color"]');
      if (meta) meta.setAttribute('content', theme === 'dark' ? '#0E1620' : '#0B1D35');
    } catch (_) { /* SSR/no-DOM */ }
  }, [theme]);

  // Follow the device theme as it changes — but only while the user has not made
  // an explicit choice (no stored 'anchor_theme'). An explicit pick always wins.
  useEffect(() => {
    if (!window.matchMedia) return;
    let mq;
    try { mq = window.matchMedia('(prefers-color-scheme: dark)'); } catch { return; }
    const onChange = (e) => {
      let saved = null;
      try { saved = localStorage.getItem('anchor_theme'); } catch { /* ignore */ }
      if (saved !== 'light' && saved !== 'dark') setThemeRaw(e.matches ? 'dark' : 'light');
    };
    if (mq.addEventListener) mq.addEventListener('change', onChange);
    else if (mq.addListener) mq.addListener(onChange);  // older Safari
    return () => {
      if (mq.removeEventListener) mq.removeEventListener('change', onChange);
      else if (mq.removeListener) mq.removeListener(onChange);
    };
  }, []);

  // Soft logout when a fetch helper detects an unrecoverable 401 (refresh failed
  // or refresh token gone). Avoids the full-page reload that flashes the login screen.
  useEffect(() => {
    const onExpired = () => logout();
    window.addEventListener('anchor:session-expired', onExpired);
    return () => window.removeEventListener('anchor:session-expired', onExpired);
  }, []);

  // Persist the current route + back-stack (+ mode) so a reload / PWA reopen lands
  // exactly where the user left off. Only snapshot authenticated app routes; auth
  // routes (login/register) are never restored. Read back on boot by getStoredNav().
  useEffect(() => {
    if (!auth.isAuthenticated || AUTH_ROUTES.has(route.name)) return;
    try {
      localStorage.setItem('anchor_nav_state',
        JSON.stringify({ route, history, mode, ts: Date.now() }));
    } catch (_) { /* storage unavailable */ }
  }, [route, history, mode, auth.isAuthenticated]);

  // Refresh / heal this device's FCM push token on every authenticated load,
  // including a restored session (the login call sites only fire on a fresh
  // login). Silent — never prompts; only registers when permission is already
  // granted. First-time opt-in happens at login or via the Profile toggle.
  useEffect(() => {
    if (!auth.isAuthenticated) return;
    if (window.syncPushToken) window.syncPushToken({ interactive: false });
  }, [auth.isAuthenticated]);

  // Publish this device's E2EE public key on every authenticated load so that any
  // verified lawyer is immediately reachable for encrypted chat (and citizens'
  // first messages can be encrypted without waiting). Silent and best-effort.
  useEffect(() => {
    if (!auth.isAuthenticated) return;
    if (window.E2EE && E2EE.supported) { E2EE.ensureKeyPair().catch(() => {}); }
  }, [auth.isAuthenticated]);

  // Push deep-link: tapping an alert notification opens "/?alert=<event_id>"
  // (cold start) or — if the app is already open — the service worker posts an
  // "anchor-open-alert" message. Either way, land on the live map for that alert.
  useEffect(() => {
    const openAlert = (eventId, lat, lng) => {
      if (!auth.isAuthenticated) return;
      go('map', { focusAlert: eventId || undefined, lat, lng });
    };
    // 1) Cold start — once authenticated, read and then strip the ?alert= params
    //    so a refresh or history navigation doesn't re-trigger it. If the session
    //    hasn't restored yet, leave the param in place; this effect re-runs when
    //    auth.isAuthenticated flips true.
    try {
      const params = new URLSearchParams(window.location.search);
      const a = params.get('alert');
      if (a && auth.isAuthenticated) {
        openAlert(a, params.get('lat'), params.get('lng'));
        ['alert', 'lat', 'lng', 'respond'].forEach(k => params.delete(k));
        const qs = params.toString();
        window.history.replaceState({}, '', window.location.pathname + (qs ? '?' + qs : ''));
      }
    } catch (_) { /* URL API unavailable */ }
    // 2) App already open — message from the service worker's notificationclick.
    const onMsg = (e) => {
      if (e.data && e.data.type === 'anchor-open-alert') openAlert(e.data.eventId, e.data.lat, e.data.lng);
    };
    if (navigator.serviceWorker) navigator.serviceWorker.addEventListener('message', onMsg);
    return () => {
      if (navigator.serviceWorker) navigator.serviceWorker.removeEventListener('message', onMsg);
    };
  }, [auth.isAuthenticated]);

  useEffect(() => {
    if (!auth.isAuthenticated || !geofenceConsent) {
      if (watchIdRef.current !== null) {
        navigator.geolocation.clearWatch(watchIdRef.current);
        watchIdRef.current = null;
      }
      return;
    }
    if (!navigator.geolocation) return;
    const THROTTLE_MS = 90_000;
    watchIdRef.current = navigator.geolocation.watchPosition(
      (pos) => {
        const now = Date.now();
        if (now - lastLocationPostRef.current < THROTTLE_MS) return;
        lastLocationPostRef.current = now;
        const accessToken = localStorage.getItem('anchor_access_token');
        if (!accessToken) return;
        fetch((window.ANCHOR_API_URL || 'http://localhost:8000') + '/v1/users/me/location', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + accessToken },
          body: JSON.stringify({ lat: pos.coords.latitude, lng: pos.coords.longitude, geofence_consent: true }),
        }).catch(err => console.warn('[Location] Snapshot failed:', err));
      },
      (err) => console.info('[Location] watchPosition error:', err.code),
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 60000 }
    );
    return () => {
      if (watchIdRef.current !== null) {
        navigator.geolocation.clearWatch(watchIdRef.current);
        watchIdRef.current = null;
      }
    };
  }, [auth.isAuthenticated, geofenceConsent]);

  // Live unread notification count for the header bell. Polls the backend while
  // authenticated and re-fetches on demand when a screen marks notifications read
  // (the NotificationsScreen dispatches 'anchor:notif-changed'). Falls back to 0
  // silently when offline so the badge never blocks rendering.
  useEffect(() => {
    if (!auth.isAuthenticated) { setNotifUnread(0); return; }
    let cancelled = false;
    const m = mode === 'country' ? 'country' : 'campus';
    const fetchCount = () => {
      if (typeof apiFetch !== 'function') return;
      apiFetch('/v1/notifications/unread-count?mode=' + m)
        .then((d) => { if (!cancelled && d && typeof d.unread_count === 'number') setNotifUnread(d.unread_count); })
        .catch(() => { /* offline — keep last known count */ });
    };
    fetchCount();
    const id = setInterval(fetchCount, 60_000);
    const onChanged = () => fetchCount();
    window.addEventListener('anchor:notif-changed', onChanged);
    return () => {
      cancelled = true;
      clearInterval(id);
      window.removeEventListener('anchor:notif-changed', onChanged);
    };
  }, [auth.isAuthenticated, mode]);

  const value = { mode, setMode, route, go, back, replace, lang, setLang, tr, auth, login, logout,
                  setAuthPending, updateUser, geofenceConsent, setGeofenceConsent,
                  theme, setTheme, toggleTheme, notifUnread };
  return (
    <AppCtx.Provider value={value}>
      {children}
      {showGeofencePrompt && (
        <GeofenceConsentModal
          onComplete={({ locationGranted, position }) => {
            // The modal already ran the two permission prompts in sequence. Here we
            // only persist the OUTCOME: consent is true only when a real position
            // was obtained (so we never mark a device "consented" while location is
            // actually blocked, which would leave it eligible-but-snapshotless).
            localStorage.setItem('anchor_geofence_consent_answered', 'true');
            if (locationGranted && position) {
              localStorage.setItem('anchor_geofence_consent', 'true');
              setGeofenceConsent(true);
              // Post the first snapshot immediately so the device is eligible for
              // fan-out right away (and shows up in the super-admin GPS view)
              // without waiting for the throttled watchPosition callback.
              const accessToken = localStorage.getItem('anchor_access_token');
              if (accessToken) {
                fetch((window.ANCHOR_API_URL || 'http://localhost:8000') + '/v1/users/me/location', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + accessToken },
                  body: JSON.stringify({
                    lat: position.coords.latitude,
                    lng: position.coords.longitude,
                    geofence_consent: true,
                  }),
                }).catch(err => console.warn('[Location] Initial snapshot failed:', err));
              }
            } else {
              localStorage.setItem('anchor_geofence_consent', 'false');
              setGeofenceConsent(false);
            }
          }}
          onDismiss={() => {
            // If the user closed without ever resolving (tapped "Not now"), record
            // that they answered so the modal doesn't reappear every load — the
            // persistent CTA on Home/Alert still offers a one-tap enable.
            if (localStorage.getItem('anchor_geofence_consent_answered') !== 'true') {
              localStorage.setItem('anchor_geofence_consent', 'false');
              localStorage.setItem('anchor_geofence_consent_answered', 'true');
            }
            setShowGeofencePrompt(false);
          }}
        />
      )}
    </AppCtx.Provider>
  );
}

// ─────────────────────────────────────────────────────────────
// Header — logo, mode word, bell, avatar
// ─────────────────────────────────────────────────────────────
function Header({ title, subtitle, back: showBack = false, transparent = false }) {
  const { back, go, mode, auth, tr, notifUnread } = useApp();
  const accent = mode === 'campus' ? 'var(--sage)' : 'var(--ember)';
  const unread = notifUnread || 0;
  const user = auth && auth.user;
  const initials = user && user.name
    ? user.name.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase()
    : 'SA';
  const isStudent = user && user.role === 'student';
  return (
    <div style={{
      position: 'sticky', top: 0, zIndex: 10,
      padding: '18px 20px 12px',
      background: transparent ? 'transparent' : 'var(--bar-bg)',
      backdropFilter: 'blur(14px)',
      WebkitBackdropFilter: 'blur(14px)',
      borderBottom: transparent ? 'none' : '1px solid var(--mist)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        {showBack ? (
          <button onClick={back} style={{
            background: 'transparent', border: '1px solid var(--mist-2)',
            borderRadius: 999, padding: '6px 10px 6px 8px', display: 'flex',
            alignItems: 'center', gap: 4, cursor: 'pointer', color: 'var(--navy)',
            fontFamily: 'var(--font-sans)', fontSize: 12, fontWeight: 500,
          }}>
            <IconArrowLeft size={14}/> {tr('btn_back')}
          </button>
        ) : (
          <div style={{ display: 'flex', alignItems: 'center', gap: 9 }}>
            <div className="logo-mark">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="5" r="2"/>
                <path d="M12 7v15"/>
                <path d="M5 12h14"/>
                <path d="M3 16a9 9 0 0 0 18 0"/>
              </svg>
            </div>
            <div>
              <div className="serif" style={{ fontSize: 18, lineHeight: 1, fontWeight: 500, letterSpacing: '-0.01em', color: 'var(--navy)' }}>
                Anchor<span style={{ color: accent, fontStyle: 'italic' }}>.</span>
              </div>
              <div className="eyebrow" style={{ marginTop: 3, color: 'var(--muted)' }}>
                {mode === 'campus'
                  ? `${tr('hdr_campus')} · ${user && user.tenant_id ? user.tenant_id.toUpperCase() : 'DIU'}`
                  : tr('hdr_national')}
              </div>
            </div>
          </div>
        )}

        <div style={{ flex: 1 }}/>

        <button onClick={() => go('notifications')} aria-label="Notifications" style={{
          position: 'relative', width: 38, height: 38, borderRadius: 999,
          background: 'var(--surface)', border: '1px solid var(--mist)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          cursor: 'pointer', color: 'var(--navy)',
        }}>
          <IconBell size={17}/>
          {unread > 0 && (
            <span style={{
              position: 'absolute', top: unread > 9 ? 1 : 3, right: unread > 9 ? 1 : 4,
              minWidth: 15, height: 15, padding: '0 3px', borderRadius: 999,
              background: 'var(--red)', border: '1.5px solid var(--cream)', color: '#fff',
              fontSize: 9, fontWeight: 700, lineHeight: '12px', boxSizing: 'border-box',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: 'var(--font-sans)',
            }}>{unread > 9 ? '9+' : unread}</span>
          )}
        </button>

        <div style={{
          width: 38, height: 38, borderRadius: 999, position: 'relative',
          background: 'linear-gradient(135deg, #C9B7A2, #8E7A60)',
          color: '#F7F3EE', display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'var(--font-serif)', fontWeight: 500, fontSize: 14, letterSpacing: '0.02em',
          border: '1px solid rgba(11,29,53,0.1)',
        }}>
          {initials}
          {isStudent && <span title="Verified university email" style={{
            position: 'absolute', bottom: -2, right: -2, width: 14, height: 14, borderRadius: 999,
            background: 'var(--gold)', display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#fff', border: '2px solid var(--cream)',
          }}>
            <IconCheck size={8} sw={3}/>
          </span>}
        </div>
      </div>

      {title && (
        <div style={{ marginTop: 14 }}>
          {subtitle && <div className="eyebrow" style={{ marginBottom: 4 }}>{subtitle}</div>}
          <h1 className="h-display" style={{ margin: 0, fontSize: 28, lineHeight: 1.08 }}>{title}</h1>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// C2C Toggle — the signature element
// ─────────────────────────────────────────────────────────────
function C2CToggle() {
  const { mode, setMode, tr } = useApp();
  const isCampus = mode === 'campus';

  return (
    <div className="c2c-track" onClick={() => setMode(isCampus ? 'country' : 'campus')}
         role="switch" aria-checked={!isCampus}>
      <div className={`c2c-thumb ${isCampus ? 'campus' : 'country'}`}/>
      <div className={`c2c-label ${isCampus ? 'on' : 'off'}`} style={{ paddingRight: 26 }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <IconBuilding size={14}/> {tr('c2c_campus')}
        </span>
        <span className="sub">{tr('c2c_campus_sub')}</span>
      </div>
      {/* Center C2C badge */}
      <div className="c2c-badge" aria-label="Campus to Country">C2C</div>
      <div className={`c2c-label ${!isCampus ? 'on' : 'off'}`} style={{ paddingLeft: 26 }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <IconGlobe size={14}/> {tr('c2c_national')}
        </span>
        <span className="sub">{tr('c2c_national_sub')}</span>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Bottom nav
// ─────────────────────────────────────────────────────────────
function BottomNav() {
  const { route, go, tr } = useApp();
  const here = route.name;
  const items = [
    { k: 'home',    label: tr('nav_home'),    icon: IconHome },
    { k: 'cases',   label: tr('nav_cases'),   icon: IconFile },
    { k: 'alert',   label: tr('nav_alert'),   icon: IconShield, alert: true },
    { k: 'chat',    label: tr('nav_chat'),    icon: IconMessage },
    { k: 'profile', label: tr('nav_profile'), icon: IconUser },
  ];

  return (
    <div className="botnav">
      {items.map(it => {
        const Active = here === it.k;
        const Ico = it.icon;
        if (it.alert) {
          return (
            <button key={it.k} onClick={() => go('alert')} className="alert-btn">
              <div className="alert-ring"><Ico size={22}/></div>
              <span style={{ marginTop: 2 }}>{it.label}</span>
            </button>
          );
        }
        return (
          <button key={it.k} onClick={() => go(it.k)} className={Active ? 'active' : ''}>
            <Ico size={20}/>
            <span>{it.label}</span>
          </button>
        );
      })}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Route renderer
// ─────────────────────────────────────────────────────────────
// Persistent, dismissible call-to-action shown on the Home/Alert screens when this
// device is NOT ready to receive emergency pushes — i.e. notifications aren't granted
// or location consent is off. This is how a user gets EVERY device into the deliverable
// state: the browser only grants permission on a user gesture, so a one-tap button here
// drives both prompts. Re-appears on the next load while the device stays not-ready.
function AlertReadinessCTA() {
  const { auth, geofenceConsent, setGeofenceConsent } = useApp();
  const [dismissed, setDismissed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [, force] = useState(0);  // re-evaluate capability after enabling

  if (!auth.isAuthenticated || dismissed) return null;

  const cap = (window.getPushCapability && window.getPushCapability()) || { reason: 'ok' };
  const notifReady = cap.reason === 'granted';
  const locReady = geofenceConsent;
  if (notifReady && locReady) return null;

  const pushMsg = notifReady ? null : pushReasonMessage(cap.reason);
  const detail =
    pushMsg ? pushMsg
    : !locReady ? 'Share your location so we can alert you when someone nearby needs help.'
    : 'Turn on notifications so emergency alerts pop up on this device.';

  const enable = async () => {
    setBusy(true);
    // Location first (so it's eligible + visible to operators), notifications second.
    if (!locReady) {
      const position = await new Promise((res) => {
        if (!navigator.geolocation) return res(null);
        navigator.geolocation.getCurrentPosition((p) => res(p), () => res(null),
          { timeout: 10000, maximumAge: 60000 });
      });
      if (position) {
        localStorage.setItem('anchor_geofence_consent', 'true');
        localStorage.setItem('anchor_geofence_consent_answered', 'true');
        setGeofenceConsent(true);
        const t = localStorage.getItem('anchor_access_token');
        if (t) {
          fetch((window.ANCHOR_API_URL || 'http://localhost:8000') + '/v1/users/me/location', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + t },
            body: JSON.stringify({ lat: position.coords.latitude, lng: position.coords.longitude, geofence_consent: true }),
          }).catch(() => {});
        }
      }
    }
    try { if (window.syncPushToken) await window.syncPushToken({ interactive: true }); } catch (_) {}
    setBusy(false);
    force(n => n + 1);
  };

  // iOS-in-a-tab cannot enable push at all from a button — only guidance helps.
  const actionable = cap.reason !== 'ios-needs-install' && cap.reason !== 'ios-chrome'
    && cap.reason !== 'unsupported' && cap.reason !== 'insecure-context';

  return (
    <div style={{ margin: '12px 16px 0', padding: '14px 16px', borderRadius: 16,
                  background: 'rgba(196,69,54,0.07)', border: '1px solid rgba(196,69,54,0.22)' }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        <div style={{ flexShrink: 0, marginTop: 1, color: 'var(--ember)' }}>
          <IconBell size={18} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--navy)', fontFamily: 'var(--font-sans)' }}>
            Emergency alerts are off on this device
          </div>
          <div style={{ fontSize: 12, color: 'var(--muted)', lineHeight: 1.5, marginTop: 3, fontFamily: 'var(--font-sans)' }}>
            {detail}
          </div>
          <div style={{ display: 'flex', gap: 8, marginTop: 10, alignItems: 'center' }}>
            {actionable && (
              <button onClick={enable} disabled={busy}
                style={{ height: 34, padding: '0 14px', borderRadius: 10, border: 'none',
                         background: 'var(--ember)', color: '#fff', fontSize: 12.5, fontWeight: 600,
                         cursor: busy ? 'default' : 'pointer', opacity: busy ? 0.7 : 1, fontFamily: 'var(--font-sans)' }}>
                {busy ? 'Enabling…' : 'Turn on alerts'}
              </button>
            )}
            <button onClick={() => setDismissed(true)}
              style={{ height: 34, padding: '0 10px', borderRadius: 10, border: 'none', background: 'transparent',
                       color: 'var(--muted)', fontSize: 12.5, cursor: 'pointer', fontFamily: 'var(--font-sans)' }}>
              Dismiss
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// Keep-alive screen host. Every visited app route is mounted once and kept in the
// DOM; inactive screens are hidden with display:none instead of unmounting, so their
// React state (active alert, open tab, scroll, half-filled form) survives navigation.
// Auth routes are never cached — they always render fresh.
function RouteHost() {
  const { route, mode, auth } = useApp();
  const isAuthRoute = AUTH_ROUTES.has(route.name);

  const Map = {
    // App screens
    home:    HomeScreen,
    chat:    ChatProScreen,
    cases:   CasesScreen,
    case:    CaseDetailScreen,
    alert:   AlertScreen,
    map:     MapScreen,
    feed:            FeedScreen,
    'news-feed':     FeedScreen,
    'feed-publish':  PublishScreen,
    'feed-post':     PostDetailScreen,
    'feed-profile':  FeedProfileScreen,
    'feed-admin':    FeedAdminScreen,
    'feed-moderate': FeedModerateScreen,
    lawyers:      LawyersScreen,
    messages:      ConversationsScreen,
    'chat-thread': ChatThreadScreen,
    'apply-lawyer': ApplyLawyerScreen,
    notices:      NoticesScreen,
    routines:     RoutinesScreen,
    'dept-rating': DeptRatingScreen,
    notifications: NotificationsScreen,
    profile: ProfileScreen,
    compose: ComposeScreen,
    rights:  RightsScreen,
    // National-mode: FIR/GD drafting + officer scorecard
    'police-reports':    PoliceReportsListScreen,
    'new-police-report': NewPoliceReportScreen,
    'police-report':     PoliceReportDetailScreen,
    'officer-scorecard': OfficerScorecardScreen,
    'police-station':    StationDetailScreen,
    'rate-station':      RateStationScreen,
    // Campus application system
    'applications':    ApplicationsListScreen,
    'new-application': NewApplicationScreen,
    'application':     ApplicationDetailScreen,
    'campus-settings': CampusSettingsScreen,
    // Filing system (complaints, reports, grievances)
    'filings':          FilingsListScreen,
    'new-filing':       NewFilingScreen,
    'filing':           FilingDetailScreen,
    'classroom-report': ClassroomReportScreen,
    // Auth screens (loaded from auth.jsx)
    'login':           LoginScreen,
    'register':        RegisterChoiceScreen,
    'register-form':   RegisterFormScreen,
    'verify-email':    VerifyEmailScreen,
    'verify-otp':      VerifyOTPScreen,
    'forgot-password': ForgotPasswordScreen,
    'mfa-verify':      MFAVerifyScreen,
    'mfa-setup':       MFASetupScreen,
    'tracking-lookup': TrackingLookupScreen,
  };

  const tintClass = `screen ${mode === 'campus' ? 'tint-campus' : 'tint-country'}`;
  const activeKey = slotKeyFor(route);

  // Cache of mounted screens and each one's last scroll position. Membership is
  // computed during render (deterministic, idempotent) so the active slot's DOM
  // exists in the same commit and scroll restore can target it.
  const slotsRef = useRef([]);
  const scrollRef = useRef({});       // slotKey -> last window.scrollY
  const activeKeyRef = useRef(activeKey);
  activeKeyRef.current = activeKey;    // keep the scroll listener pointed at the live key

  // Drop the whole cache on logout so the next user never sees a stale screen.
  useEffect(() => {
    if (!auth.isAuthenticated) {
      slotsRef.current = [];
      scrollRef.current = {};
    }
  }, [auth.isAuthenticated]);

  // Continuously remember the active screen's scroll position (the app scrolls the
  // window, not a per-screen box) so returning to a kept-alive screen restores its
  // place. Recording as the user scrolls avoids reading a value already clamped by
  // the outgoing screen being hidden.
  useEffect(() => {
    const onScroll = () => {
      const k = activeKeyRef.current;
      if (k) scrollRef.current[k] = window.scrollY || window.pageYOffset || 0;
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  // Restore the incoming screen's scroll on every route switch, before paint.
  useLayoutEffect(() => {
    if (isAuthRoute || !auth.isAuthenticated) return;
    window.scrollTo(0, scrollRef.current[activeKey] || 0);
  }, [activeKey, isAuthRoute, auth.isAuthenticated]);

  // Auth screens (and any pre-auth state) render fresh and uncached.
  if (isAuthRoute || !auth.isAuthenticated) {
    const Comp = (!auth.isAuthenticated && !isAuthRoute) ? LoginScreen : (Map[route.name] || HomeScreen);
    return (
      <div className={tintClass}>
        <Comp params={route.params}/>
      </div>
    );
  }

  // Update the keep-alive membership: move/insert the active slot, keep every tab
  // root, and LRU-cap the rest. Tab roots and detail screens never collide because
  // slotKeyFor() discriminates by item id.
  {
    const cur = slotsRef.current;
    const others = cur.filter(s => s.key !== activeKey);
    const all = [{ key: activeKey, route }, ...others];
    const roots = all.filter(s => TAB_ROOTS.has(s.route.name));
    const nonRoots = all.filter(s => !TAB_ROOTS.has(s.route.name)).slice(0, MAX_CACHED);
    slotsRef.current = [...roots, ...nonRoots];
    const liveKeys = new Set(slotsRef.current.map(s => s.key));
    Object.keys(scrollRef.current).forEach(k => { if (!liveKeys.has(k)) delete scrollRef.current[k]; });
  }

  return (
    <>
      {slotsRef.current.map(s => {
        const active = s.key === activeKey;
        const Comp = Map[s.route.name] || HomeScreen;
        const onCTA = s.route.name === 'home' || s.route.name === 'alert';
        return (
          <div key={s.key} className={tintClass}
               style={{ display: active ? 'block' : 'none' }}
               aria-hidden={active ? undefined : true}>
            <ScreenVisibilityCtx.Provider value={active}>
              {onCTA && <AlertReadinessCTA/>}
              <Comp params={s.route.params}/>
              <div style={{ height: 96 }}/>
            </ScreenVisibilityCtx.Provider>
          </div>
        );
      })}
      <BottomNav/>
    </>
  );
}

// ─────────────────────────────────────────────────────────────
// Mount — responsive app shell (full-bleed on mobile, centered
// column on desktop). See .app-shell in styles.css.
// ─────────────────────────────────────────────────────────────
function App() {
  // Splash flow: 'splash1' → 'splash2' → 'app'
  const [stage, setStage] = useState('splash1');

  return (
    <AppProvider>
      <div className="app-shell grain">
        {stage === 'splash1' && <Splash1 onAdvance={() => setStage('splash2')}/>}
        {stage === 'splash2' && <Splash2 onAdvance={() => setStage('app')}/>}
        {stage === 'app'     && <RouteHost/>}
      </div>
    </AppProvider>
  );
}

Object.assign(window, { App, AppProvider, AppCtx, useApp, Header, C2CToggle, BottomNav,
                        usePersistentState, useScreenVisible });
