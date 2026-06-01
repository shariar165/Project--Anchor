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

function AppProvider({ children }) {
  // Must be declared before useState so the initial mode and route are derived correctly
  const getStoredAuth = () => {
    try { return JSON.parse(localStorage.getItem('anchor_auth')); } catch { return null; }
  };
  const stored = getStoredAuth();

  const [mode, setMode] = useState(
    (stored?.isAuthenticated && stored?.user?.role === 'user') ? 'country' : 'campus'
  );
  const [lang, setLang] = useState('EN');       // 'EN' | 'BN'
  const [history, setHistory] = useState([]);
  const [auth, setAuth] = useState(
    stored || { isAuthenticated: false, user: null, authStep: null, pendingIdentifier: null }
  );
  const [route, setRoute] = useState({
    name: stored?.isAuthenticated ? 'home' : 'login',
    params: {},
  });

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

  const login = (userData) => {
    const newAuth = { isAuthenticated: true, user: userData, authStep: null, pendingIdentifier: null };
    setAuth(newAuth);
    localStorage.setItem('anchor_auth', JSON.stringify(newAuth));
    if (userData.role === 'user') setMode('country');
  };
  const logout = () => {
    setAuth({ isAuthenticated: false, user: null, authStep: null, pendingIdentifier: null });
    localStorage.removeItem('anchor_auth');
    localStorage.removeItem('anchor_access_token');
    localStorage.removeItem('anchor_refresh_token');
    setHistory([]);
    setRoute({ name: 'login', params: {} });
  };
  const setAuthPending = (pending) => {
    setAuth(a => ({ ...a, ...pending }));
  };

  const value = { mode, setMode, route, go, back, lang, setLang, auth, login, logout, setAuthPending };
  return <AppCtx.Provider value={value}>{children}</AppCtx.Provider>;
}

// ─────────────────────────────────────────────────────────────
// Header — logo, mode word, bell, avatar
// ─────────────────────────────────────────────────────────────
function Header({ title, subtitle, back: showBack = false, transparent = false }) {
  const { back, mode, auth } = useApp();
  const accent = mode === 'campus' ? 'var(--sage)' : 'var(--ember)';
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

        <button style={{
          position: 'relative', width: 38, height: 38, borderRadius: 999,
          background: 'rgba(255,255,255,0.6)', border: '1px solid var(--mist)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          cursor: 'pointer', color: 'var(--navy)',
        }}>
          <IconBell size={17}/>
          <span style={{
            position: 'absolute', top: 6, right: 8, width: 7, height: 7, borderRadius: 999,
            background: 'var(--red)', border: '1.5px solid var(--cream)',
          }}/>
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
    feed:    FeedScreen,
    lawyers: LawyersScreen,
    notices: NoticesScreen,
    profile: ProfileScreen,
    compose: ComposeScreen,
    rights:  RightsScreen,
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
// Mount — single phone in a viewport (also responsive)
// ─────────────────────────────────────────────────────────────
function App() {
  // Splash flow: 'splash1' → 'splash2' → 'app'
  const [stage, setStage] = useState('splash1');

  // Auto-scale phone if viewport too small
  const wrapRef = useRef(null);
  const [scale, setScale] = useState(1);
  useEffect(() => {
    const measure = () => {
      const vh = window.innerHeight;
      const vw = window.innerWidth;
      const targetH = 874 + 96;
      const targetW = 402 + 80;
      const s = Math.min(1, vh / targetH, vw / targetW);
      setScale(s);
    };
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, []);

  return (
    <AppProvider>
      <div className="viewport-bg grain">
        <div ref={wrapRef} style={{
          transform: `scale(${scale})`, transformOrigin: 'center center',
          width: 402, height: 874,
        }}>
          <IOSDevice width={402} height={874} dark={stage === 'splash1'}>
            {stage === 'splash1' && <Splash1 onAdvance={() => setStage('splash2')}/>}
            {stage === 'splash2' && <Splash2 onAdvance={() => setStage('app')}/>}
            {stage === 'app'     && <RouteView/>}
          </IOSDevice>
        </div>
        <Caption/>
      </div>
    </AppProvider>
  );
}

function Caption() {
  return (
    <div style={{
      position: 'fixed', bottom: 18, left: 0, right: 0, textAlign: 'center',
      color: 'rgba(247,243,238,0.45)', fontFamily: 'var(--font-serif)',
      fontStyle: 'italic', fontSize: 12, letterSpacing: '0.01em',
      pointerEvents: 'none',
    }}>
      Anchor AI — Team AiVion · Daffodil International University
    </div>
  );
}

Object.assign(window, { App, AppProvider, AppCtx, useApp, Header, C2CToggle, BottomNav });
