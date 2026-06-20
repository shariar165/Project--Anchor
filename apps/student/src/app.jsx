// Anchor AI — App shell: header, C2C toggle, bottom nav, route container
// Depends on: icons.jsx, screens.jsx (declared globally)

const { useState, useEffect, useRef, useMemo, createContext, useContext } = React;

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

function GeofenceConsentModal({ onAccept, onDecline }) {
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
                    fontFamily:'var(--font-sans)', marginBottom:24 }}>
          Anchor can notify you when someone near you triggers an emergency alert.
          To do this we'll ask for two permissions next — <strong>location</strong>{' '}
          (shared anonymously, never stored beyond 10 minutes) and{' '}
          <strong>notifications</strong> (so the alert can pop up on your phone).
          You can turn both off at any time in Settings.
        </p>
        <button onClick={onAccept} className="btn btn-primary"
          style={{ width:'100%', height:48, borderRadius:12, fontSize:15, fontWeight:600, marginBottom:10 }}>
          Enable nearby alerts
        </button>
        <button onClick={onDecline}
          style={{ width:'100%', height:40, borderRadius:12, fontSize:14,
                   background:'transparent', border:'none', cursor:'pointer',
                   color:'var(--muted)', fontFamily:'var(--font-sans)' }}>
          Not now
        </button>
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

  const [mode, setMode] = useState(
    (stored?.isAuthenticated && stored?.user?.role === 'user') ? 'country' : 'campus'
  );
  const [lang, setLangRaw] = useState(
    localStorage.getItem('anchor_lang') === 'BN' ? 'BN' : 'EN'
  );       // 'EN' | 'BN'
  const setLang = (next) => {
    const val = next === 'BN' ? 'BN' : 'EN';
    try { localStorage.setItem('anchor_lang', val); } catch { /* storage unavailable */ }
    setLangRaw(val);
  };
  const [history, setHistory] = useState([]);
  const [auth, setAuth] = useState(
    stored || { isAuthenticated: false, user: null, authStep: null, pendingIdentifier: null }
  );
  const [route, setRoute] = useState({
    name: stored?.isAuthenticated ? 'home' : 'login',
    params: {},
  });
  const [geofenceConsent, setGeofenceConsent] = useState(
    localStorage.getItem('anchor_geofence_consent') === 'true'
  );
  const [showGeofencePrompt, setShowGeofencePrompt] = useState(false);
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
    if (userData.role === 'user') setMode('country');
    // Show the consent modal on first login, AND re-show it for a device that
    // consented to location earlier but never granted notification permission
    // (permission still 'default') — otherwise that device would never get a
    // token and never receive a push, with no way back to the in-app opt-in.
    const answered = localStorage.getItem('anchor_geofence_consent_answered') === 'true';
    const consented = localStorage.getItem('anchor_geofence_consent') === 'true';
    const notifUngranted = typeof Notification === 'undefined' || Notification.permission === 'default';
    if (!answered || (consented && notifUngranted)) {
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

  // Soft logout when a fetch helper detects an unrecoverable 401 (refresh failed
  // or refresh token gone). Avoids the full-page reload that flashes the login screen.
  useEffect(() => {
    const onExpired = () => logout();
    window.addEventListener('anchor:session-expired', onExpired);
    return () => window.removeEventListener('anchor:session-expired', onExpired);
  }, []);

  // Refresh / heal this device's FCM push token on every authenticated load,
  // including a restored session (the login call sites only fire on a fresh
  // login). Silent — never prompts; only registers when permission is already
  // granted. First-time opt-in happens at login or via the Profile toggle.
  useEffect(() => {
    if (!auth.isAuthenticated) return;
    if (window.syncPushToken) window.syncPushToken({ interactive: false });
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
        ['alert', 'lat', 'lng'].forEach(k => params.delete(k));
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

  const value = { mode, setMode, route, go, back, replace, lang, setLang, auth, login, logout,
                  setAuthPending, updateUser, geofenceConsent, setGeofenceConsent };
  return (
    <AppCtx.Provider value={value}>
      {children}
      {showGeofencePrompt && (
        <GeofenceConsentModal
          onAccept={async () => {
            // Receiving an alert fan-out needs BOTH location consent and a
            // registered FCM token. Request the two browser permissions in
            // sequence (awaiting each) so they never collide — Chrome shows one
            // permission prompt at a time and silently drops simultaneous ones.
            // Step 1 — location permission FIRST. Resolve on success OR error so
            // a denial doesn't hang the flow; this surfaces and waits out the
            // geolocation prompt before we ask for anything else.
            await new Promise((res) => {
              if (!navigator.geolocation) return res();
              navigator.geolocation.getCurrentPosition(res, res, { timeout: 10000, maximumAge: 60000 });
            });
            // Step 2 — notification permission SECOND, only after location is done.
            try { if (window.syncPushToken) await window.syncPushToken({ interactive: true }); } catch (_) { /* best-effort */ }
            // Step 3 — persist + start the location watcher (permission already
            // granted above, so watchPosition won't re-prompt).
            localStorage.setItem('anchor_geofence_consent', 'true');
            localStorage.setItem('anchor_geofence_consent_answered', 'true');
            setGeofenceConsent(true);
            setShowGeofencePrompt(false);
          }}
          onDecline={() => {
            localStorage.setItem('anchor_geofence_consent', 'false');
            localStorage.setItem('anchor_geofence_consent_answered', 'true');
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
  const { back, go, mode, auth } = useApp();
  const accent = mode === 'campus' ? 'var(--sage)' : 'var(--ember)';
  const unread = (typeof unreadCount === 'function') ? unreadCount(mode) : 0;
  const user = auth && auth.user;
  const initials = user && user.name
    ? user.name.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase()
    : 'SA';
  const isStudent = user && user.role === 'student';
  return (
    <div style={{
      position: 'sticky', top: 0, zIndex: 10,
      padding: '18px 20px 12px',
      background: transparent ? 'transparent' : 'rgba(247,243,238,0.85)',
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
            <IconArrowLeft size={14}/> Back
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
                  ? `Campus · ${user && user.tenant_id ? user.tenant_id.toUpperCase() : 'DIU'}`
                  : 'National · BD'}
              </div>
            </div>
          </div>
        )}

        <div style={{ flex: 1 }}/>

        <button onClick={() => go('notifications')} aria-label="Notifications" style={{
          position: 'relative', width: 38, height: 38, borderRadius: 999,
          background: 'rgba(255,255,255,0.6)', border: '1px solid var(--mist)',
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
  const { mode, setMode } = useApp();
  const isCampus = mode === 'campus';

  return (
    <div className="c2c-track" onClick={() => setMode(isCampus ? 'country' : 'campus')}
         role="switch" aria-checked={!isCampus}>
      <div className={`c2c-thumb ${isCampus ? 'campus' : 'country'}`}/>
      <div className={`c2c-label ${isCampus ? 'on' : 'off'}`} style={{ paddingRight: 26 }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <IconBuilding size={14}/> Campus
        </span>
        <span className="sub">DIU</span>
      </div>
      {/* Center C2C badge */}
      <div className="c2c-badge" aria-label="Campus to Country">C2C</div>
      <div className={`c2c-label ${!isCampus ? 'on' : 'off'}`} style={{ paddingLeft: 26 }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
          <IconGlobe size={14}/> National
        </span>
        <span className="sub">Bangladesh</span>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Bottom nav
// ─────────────────────────────────────────────────────────────
function BottomNav() {
  const { route, go } = useApp();
  const here = route.name;
  const items = [
    { k: 'home',    label: 'Home',    icon: IconHome },
    { k: 'cases',   label: 'My Cases',icon: IconFile },
    { k: 'alert',   label: 'Alert',   icon: IconShield, alert: true },
    { k: 'chat',    label: 'Anchor AI', icon: IconMessage },
    { k: 'profile', label: 'Profile', icon: IconUser },
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
function RouteView() {
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
    notices:      NoticesScreen,
    routines:     RoutinesScreen,
    'dept-rating': DeptRatingScreen,
    notifications: NotificationsScreen,
    profile: ProfileScreen,
    compose: ComposeScreen,
    rights:  RightsScreen,
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

  // Guard: unauthenticated users hitting an app route see LoginScreen
  const Comp = (!auth.isAuthenticated && !isAuthRoute)
    ? LoginScreen
    : (Map[route.name] || HomeScreen);

  return (
    <div key={route.name + mode} className={`screen ${mode === 'campus' ? 'tint-campus' : 'tint-country'}`}>
      <Comp params={route.params}/>
      {!isAuthRoute && <div style={{ height: 96 }}/>}
      {!isAuthRoute && <BottomNav/>}
    </div>
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
        {stage === 'app'     && <RouteView/>}
      </div>
    </AppProvider>
  );
}

Object.assign(window, { App, AppProvider, AppCtx, useApp, Header, C2CToggle, BottomNav });
