// auth.jsx — Authentication & verification screens for Anchor AI
// Spec: §5 Registration, §7 Email verify, §8 OTP, §9 Login, §11 Password,
//       §12 Anonymous tracking, §13 MFA, §14 Step-up
// Depends on: icons.jsx (global icon components), app.jsx (useApp)

const { useState, useEffect, useRef } = React;

const AUTH_API = 'http://localhost:8000';

async function apiPost(path, body) {
  const res = await fetch(AUTH_API + path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!res.ok) {
    const err = new Error(data.detail || data.message || 'Request failed');
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

function saveTokens(access_token, refresh_token) {
  localStorage.setItem('anchor_access_token', access_token);
  localStorage.setItem('anchor_refresh_token', refresh_token);
}

// ── Firebase Web Push (fill in config to enable push notifications) ──────────
// Public keys — safe to commit. Get from Firebase Console → Project Settings → Web app.
const FIREBASE_CONFIG = {
  apiKey:            'AIzaSyBqQtlcZ536HFiNVEFGuURfeeQa37UtVeM',
  authDomain:        'project-anchor-76170.firebaseapp.com',
  projectId:         'project-anchor-76170',
  storageBucket:     'project-anchor-76170.firebasestorage.app',
  messagingSenderId: '915588225145',
  appId:             '1:915588225145:web:1a7bb87daa31a1c4fb5ca8',
};
// Get from Firebase Console → Project Settings → Cloud Messaging → Web Push certificates (VAPID key)
const FIREBASE_VAPID_KEY = 'YOUR_VAPID_KEY_HERE'; // FILL IN to activate web push

async function registerFCMToken() {
  if (typeof firebase === 'undefined') return;
  if (!FIREBASE_VAPID_KEY || FIREBASE_VAPID_KEY === 'YOUR_VAPID_KEY_HERE') return;
  if (!('serviceWorker' in navigator) || !('Notification' in window)) return;
  try {
    if (!firebase.apps.length) firebase.initializeApp(FIREBASE_CONFIG);
    const messaging = firebase.messaging();
    const permission = await Notification.requestPermission();
    if (permission !== 'granted') return;
    const swReg = await navigator.serviceWorker.register('/firebase-messaging-sw.js');
    const fcmToken = await messaging.getToken({ vapidKey: FIREBASE_VAPID_KEY, serviceWorkerRegistration: swReg });
    if (!fcmToken) return;
    let deviceId = localStorage.getItem('anchor_device_id');
    if (!deviceId) {
      deviceId = 'web-' + Math.random().toString(36).slice(2, 18);
      localStorage.setItem('anchor_device_id', deviceId);
    }
    await fetch(AUTH_API + '/v1/users/me/fcm-token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + getAccessToken() },
      body: JSON.stringify({ fcm_token: fcmToken, device_id: deviceId, platform: 'web' }),
    });
    console.info('[FCM] Token registered');
  } catch (err) {
    console.warn('[FCM] Registration failed:', err);
  }
}
function getAccessToken() {
  return localStorage.getItem('anchor_access_token');
}
async function apiGet(path) {
  const res = await fetch(AUTH_API + path, {
    headers: { 'Authorization': 'Bearer ' + getAccessToken() },
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || 'Request failed');
  return data;
}

// ─────────────────────────────────────────────────────────────
// SHARED UTILITIES
// ─────────────────────────────────────────────────────────────

function OTPInput({ value, onChange, onComplete }) {
  const refs = [useRef(), useRef(), useRef(), useRef(), useRef(), useRef()];
  const digits = (value + '      ').slice(0, 6).split('');

  const handleChange = (i, e) => {
    const v = e.target.value.replace(/\D/g, '').slice(-1);
    const arr = [...digits];
    arr[i] = v;
    const joined = arr.join('').trimEnd ? arr.join('') : arr.join('');
    onChange(joined.replace(/ /g, ''));
    if (v && i < 5) refs[i + 1].current.focus();
    const full = arr.join('').replace(/ /g, '');
    if (full.length === 6 && onComplete) onComplete(full);
  };

  const handleKeyDown = (i, e) => {
    if (e.key === 'Backspace' && !digits[i].trim() && i > 0) {
      refs[i - 1].current.focus();
    }
  };

  const handlePaste = (e) => {
    e.preventDefault();
    const p = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6);
    onChange(p);
    if (p.length > 0) refs[Math.min(p.length, 5)].current.focus();
    if (p.length === 6 && onComplete) onComplete(p);
  };

  return (
    <div className="otp-grid">
      {digits.map((d, i) => (
        <input
          key={i}
          ref={refs[i]}
          className={'otp-box' + (d.trim() ? ' filled' : '')}
          type="text"
          inputMode="numeric"
          maxLength={1}
          value={d.trim()}
          onChange={e => handleChange(i, e)}
          onKeyDown={e => handleKeyDown(i, e)}
          onPaste={i === 0 ? handlePaste : undefined}
          autoComplete="one-time-code"
        />
      ))}
    </div>
  );
}

function PwStrength({ pw }) {
  if (!pw) return null;
  const rules = [
    { l: '12+ characters', ok: pw.length >= 12 },
    { l: 'Uppercase, lowercase & number', ok: /[A-Z]/.test(pw) && /[a-z]/.test(pw) && /\d/.test(pw) },
    { l: 'Special character', ok: /[^A-Za-z0-9]/.test(pw) },
  ];
  return (
    <div className="pw-strength">
      {rules.map(r => (
        <div key={r.l} className="pw-rule" style={{ color: r.ok ? 'var(--sage)' : 'var(--muted)' }}>
          <IconCheck size={10} sw={r.ok ? 3 : 1.5} stroke={r.ok ? 'var(--sage)' : 'var(--mist-2)'} />
          {r.l}
        </div>
      ))}
    </div>
  );
}

// ResendBtn now calls onResend() which returns a Promise<string|null> (dev_code or null)
function ResendBtn({ onResend, onDevCode }) {
  const [secs, setSecs] = useState(60);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (secs <= 0) return;
    const t = setTimeout(() => setSecs(s => s - 1), 1000);
    return () => clearTimeout(t);
  }, [secs]);

  const handleResend = async () => {
    setBusy(true);
    try {
      const devCode = await onResend();
      if (devCode && onDevCode) onDevCode(devCode);
    } catch (_) {}
    setBusy(false);
    setSecs(60);
  };

  if (secs > 0) return (
    <span style={{ fontSize: 12.5, color: 'var(--muted)', fontFamily: 'var(--font-sans)' }}>
      Resend in {secs}s
    </span>
  );
  return (
    <button
      onClick={handleResend}
      disabled={busy}
      style={{ border: 'none', background: 'none', cursor: 'pointer', color: 'var(--navy)', fontSize: 12.5, fontFamily: 'var(--font-sans)', fontWeight: 500, padding: 0 }}
    >
      {busy ? 'Sending…' : 'Resend code →'}
    </button>
  );
}

function Spinner() {
  return (
    <span style={{
      display: 'inline-block', width: 15, height: 15,
      border: '2px solid rgba(255,255,255,0.35)', borderTopColor: '#fff',
      borderRadius: '50%', animation: 'spin 0.65s linear infinite', verticalAlign: 'middle',
    }} />
  );
}

function BackBtn({ onPress }) {
  return (
    <button
      onClick={onPress}
      style={{
        border: '1px solid var(--mist-2)', borderRadius: 999, padding: '6px 12px 6px 8px',
        display: 'inline-flex', alignItems: 'center', gap: 4, background: 'transparent',
        cursor: 'pointer', color: 'var(--navy)', fontFamily: 'var(--font-sans)',
        fontSize: 12, fontWeight: 500,
      }}
    >
      <IconArrowLeft size={13} /> Back
    </button>
  );
}


// ─────────────────────────────────────────────────────────────
// LOGIN SCREEN  (spec §9)
// ─────────────────────────────────────────────────────────────
function LoginScreen() {
  const { go, mode, login, setAuthPending } = useApp();
  const accent = mode === 'campus' ? 'var(--sage)' : 'var(--ember)';

  const [tab, setTab] = useState('email');
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPw, setShowPw] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleLogin = async () => {
    if (!identifier.trim() || !password.trim()) {
      setError('Please fill in both fields.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      const data = await apiPost('/auth/login', { identifier: identifier.trim(), password });
      if (data.mfa_required) {
        sessionStorage.setItem('anchor_mfa_token', data.mfa_token);
        go('mfa-verify');
        return;
      }
      saveTokens(data.access_token, data.refresh_token);
      const me = await apiGet('/auth/me');
      login({
        id:        String(me.id),
        name:      me.full_name,
        role:      me.role,
        tenant_id: me.tenant_id ? String(me.tenant_id) : null,
        mfa:       me.mfa_enabled,
      });
      registerFCMToken();
      go('home');
    } catch (err) {
      if (err.status === 403 && err.message === 'Email/phone not verified') {
        // Account exists but OTP was never completed — trigger a resend and go verify
        const id = identifier.trim();
        const isEmail = id.includes('@');
        try {
          await apiPost('/auth/resend-verification', { identifier: id });
        } catch (_) {}
        setAuthPending({
          authStep: isEmail ? 'verify_email' : 'verify_phone',
          pendingIdentifier: id,
        });
        go(isEmail ? 'verify-email' : 'verify-otp', { identifier: id, name: '' });
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-wrap" style={{ paddingTop: 50 }}>
      {/* Logo */}
      <div style={{ padding: '28px 24px 0', textAlign: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 12, marginBottom: 8 }}>
          <div style={{
            width: 44, height: 44, borderRadius: 13,
            background: 'var(--navy)', color: '#F7F3EE',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="5" r="2" />
              <path d="M12 7v15" /><path d="M5 12h14" /><path d="M3 16a9 9 0 0 0 18 0" />
            </svg>
          </div>
          <div className="auth-logo">
            Anchor<span style={{ color: accent, fontStyle: 'italic' }}>.</span>
          </div>
        </div>
        <div className="eyebrow" style={{ color: 'var(--muted)' }}>
          {mode === 'campus' ? 'Campus Trust Layer · DIU' : 'National Civic Platform · BD'}
        </div>
      </div>

      <div style={{ flex: 1, padding: '28px 24px 0' }}>
        {/* Email / Phone tabs */}
        <div style={{
          display: 'flex', background: 'var(--cream-2)',
          borderRadius: 12, padding: 3, marginBottom: 20,
        }}>
          {['email', 'phone'].map(t => (
            <button key={t}
              onClick={() => { setTab(t); setIdentifier(''); setError(''); }}
              style={{
                flex: 1, padding: '9px 0', borderRadius: 10, border: 'none', cursor: 'pointer',
                fontFamily: 'var(--font-sans)', fontSize: 13, fontWeight: 500,
                background: tab === t ? '#fff' : 'transparent',
                color: tab === t ? 'var(--navy)' : 'var(--muted)',
                boxShadow: tab === t ? '0 1px 4px rgba(0,0,0,0.08)' : 'none',
                transition: 'all 0.15s',
              }}>
              {t === 'email' ? 'Email' : 'Phone'}
            </button>
          ))}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="auth-field">
            <div className="eyebrow">{tab === 'email' ? 'Email address' : 'Phone number'}</div>
            <input
              className="auth-input"
              type={tab === 'email' ? 'email' : 'tel'}
              placeholder={tab === 'email' ? 'you@diu.edu.bd' : '01XXXXXXXXX'}
              value={identifier}
              onChange={e => { setIdentifier(e.target.value); setError(''); }}
              autoComplete={tab === 'email' ? 'email' : 'tel'}
            />
          </div>
          <div className="auth-field">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div className="eyebrow">Password</div>
              <button
                onClick={() => go('forgot-password')}
                style={{ border: 'none', background: 'none', cursor: 'pointer', color: 'var(--navy)', fontSize: 11.5, fontFamily: 'var(--font-sans)', fontWeight: 500, padding: 0 }}>
                Forgot?
              </button>
            </div>
            <div style={{ position: 'relative' }}>
              <input
                className="auth-input"
                type={showPw ? 'text' : 'password'}
                placeholder="••••••••••••"
                value={password}
                onChange={e => { setPassword(e.target.value); setError(''); }}
                onKeyDown={e => e.key === 'Enter' && handleLogin()}
                autoComplete="current-password"
                style={{ paddingRight: 46 }}
              />
              <button
                onClick={() => setShowPw(s => !s)}
                style={{
                  position: 'absolute', right: 12, top: '50%', transform: 'translateY(-50%)',
                  border: 'none', background: 'none', cursor: 'pointer', color: 'var(--muted)',
                  display: 'flex', alignItems: 'center', padding: 2,
                }}>
                <IconEyeOff size={16} />
              </button>
            </div>
          </div>
        </div>

        {error && (
          <div style={{
            marginTop: 12, padding: '10px 14px', borderRadius: 10,
            background: 'rgba(232,49,42,0.07)', border: '1px solid rgba(232,49,42,0.2)',
            color: 'var(--red)', fontSize: 12.5, fontFamily: 'var(--font-sans)',
          }}>
            {error}
            {error === 'Invalid credentials' && (
              <div style={{ marginTop: 6, color: 'var(--ink-2)', fontSize: 12 }}>
                Haven't verified your account yet?{' '}
                <button onClick={() => go('register')} style={{ border: 'none', background: 'none', cursor: 'pointer', color: 'var(--navy)', fontWeight: 600, fontSize: 12, fontFamily: 'var(--font-sans)', padding: 0 }}>
                  Register again →
                </button>
              </div>
            )}
          </div>
        )}

        <button
          onClick={handleLogin}
          disabled={loading}
          className="btn btn-primary"
          style={{
            width: '100%', marginTop: 20, height: 48, fontSize: 15, fontWeight: 600,
            borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center',
            gap: 8, opacity: loading ? 0.85 : 1,
          }}>
          {loading ? <><Spinner /> Signing in…</> : 'Sign in'}
        </button>
      </div>

      {/* Bottom row */}
      <div style={{ padding: '22px 24px 36px', display: 'flex', flexDirection: 'column', gap: 12, alignItems: 'center' }}>
        <div className="auth-divider" style={{ width: '100%' }}>New to Anchor AI</div>
        <button
          onClick={() => go('register')}
          className="btn btn-ghost"
          style={{ width: '100%', height: 44, borderRadius: 12, fontSize: 14 }}>
          Create account
        </button>
        <button
          onClick={() => go('tracking-lookup')}
          style={{
            border: 'none', background: 'none', cursor: 'pointer', color: 'var(--muted)',
            fontSize: 12, fontFamily: 'var(--font-sans)', padding: '4px 0',
          }}>
          Track a complaint without logging in →
        </button>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// REGISTER CHOICE  (spec §5.1)
// ─────────────────────────────────────────────────────────────
function RegisterChoiceScreen() {
  const { go, back } = useApp();

  const paths = [
    {
      key: 'student',
      icon: <IconBuilding size={22} />,
      title: 'University Student',
      desc: 'Verified via university email domain. Access campus complaints, academic grievances, hostel reports, and all national features.',
      pills: ['Campus access', 'National access'],
      accent: 'var(--sage)',
      accentBg: 'rgba(74,107,92,0.09)',
      accentBorder: 'rgba(74,107,92,0.2)',
      pillStyle: { color: 'var(--sage)', borderColor: 'rgba(74,107,92,0.28)', background: 'rgba(74,107,92,0.07)' },
    },
    {
      key: 'user',
      icon: <IconGlobe size={22} />,
      title: 'General Public',
      desc: 'Phone-verified account for Bangladesh citizens. File FIR/GD drafts, access AI Legal Companion, lawyer directory, and emergency alerts.',
      pills: ['National access'],
      accent: 'var(--ember)',
      accentBg: 'rgba(196,69,54,0.08)',
      accentBorder: 'rgba(196,69,54,0.18)',
      pillStyle: { color: 'var(--ember)', borderColor: 'rgba(196,69,54,0.28)', background: 'rgba(196,69,54,0.07)' },
    },
  ];

  return (
    <div className="auth-wrap" style={{ paddingTop: 50 }}>
      <div style={{ padding: '20px 24px 0' }}>
        <BackBtn onPress={back} />
        <div style={{ marginTop: 20 }}>
          <div className="eyebrow" style={{ marginBottom: 6 }}>Join Anchor AI</div>
          <h2 className="serif" style={{ margin: 0, fontSize: 26, fontWeight: 500, color: 'var(--navy)', lineHeight: 1.15 }}>
            Choose your<br />account type
          </h2>
        </div>
      </div>

      <div style={{ padding: '24px 24px 0', display: 'flex', flexDirection: 'column', gap: 14 }}>
        {paths.map(p => (
          <button key={p.key}
            onClick={() => go('register-form', { path: p.key })}
            style={{
              background: 'rgba(255,255,255,0.82)', border: '1.5px solid var(--mist)',
              borderRadius: 18, padding: 20, textAlign: 'left', cursor: 'pointer',
              width: '100%', transition: 'border-color 0.15s',
            }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 14 }}>
              <div style={{
                width: 44, height: 44, borderRadius: 12, flexShrink: 0,
                background: p.accentBg, border: '1px solid ' + p.accentBorder,
                color: p.accent, display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                {p.icon}
              </div>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--navy)', fontFamily: 'var(--font-sans)', marginBottom: 5 }}>{p.title}</div>
                <div style={{ fontSize: 12.5, color: 'var(--muted)', lineHeight: 1.55 }}>{p.desc}</div>
                <div style={{ marginTop: 10, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {p.pills.map(pl => (
                    <span key={pl} className="pill" style={p.pillStyle}>{pl}</span>
                  ))}
                </div>
              </div>
            </div>
          </button>
        ))}
      </div>

      <div style={{ padding: '20px 24px 36px', textAlign: 'center' }}>
        <div style={{ fontSize: 11.5, color: 'var(--muted)', lineHeight: 1.65, fontFamily: 'var(--font-sans)' }}>
          University email domains are independently verified by Anchor AI.<br />
          Phone verification required for all accounts.
        </div>
      </div>
    </div>
  );
}

// Field and Checkbox are module-level so React sees a stable component
// reference across RegisterFormScreen re-renders (avoids unmount-on-keystroke).
function Field({ label, val, set, type = 'text', ph = '', err = '', ac = '', onClear }) {
  return (
    <div className="auth-field">
      <div className="eyebrow">{label}</div>
      <input
        className={'auth-input' + (err ? ' error' : '')}
        type={type} placeholder={ph} value={val} autoComplete={ac}
        onChange={e => { set(e.target.value); if (onClear) onClear(); }}
        style={err ? { borderColor: 'var(--red)' } : {}}
      />
      {err && <div style={{ fontSize: 11.5, color: 'var(--red)', fontFamily: 'var(--font-sans)' }}>{err}</div>}
    </div>
  );
}

function Checkbox({ label, checked, set, err, onClear }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
      <label style={{ display: 'flex', gap: 12, alignItems: 'flex-start', cursor: 'pointer' }}>
        <div
          onClick={() => { set(s => !s); if (onClear) onClear(); }}
          style={{
            width: 20, height: 20, borderRadius: 6, flexShrink: 0, marginTop: 1,
            border: '1.5px solid ' + (checked ? 'var(--navy)' : (err ? 'var(--red)' : 'var(--mist-2)')),
            background: checked ? 'var(--navy)' : 'transparent',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'all 0.15s',
          }}>
          {checked && <IconCheck size={11} stroke="#F7F3EE" sw={3} />}
        </div>
        <span style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.55, fontFamily: 'var(--font-sans)' }}>{label}</span>
      </label>
      {err && <div style={{ fontSize: 11.5, color: 'var(--red)', fontFamily: 'var(--font-sans)', paddingLeft: 32 }}>{err}</div>}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// REGISTER FORM  (spec §5.2–5.4)
// ─────────────────────────────────────────────────────────────
function RegisterFormScreen({ params }) {
  const { go, back, setAuthPending } = useApp();
  const isStudent = params && params.path === 'student';

  const [name, setName] = useState('');
  const [uniEmail, setUniEmail] = useState('');
  const [userEmail, setUserEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [pw, setPw] = useState('');
  const [pwConf, setPwConf] = useState('');
  const [terms, setTerms] = useState(false);
  const [dataCons, setDataCons] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errs, setErrs] = useState({});

  const validate = () => {
    const e = {};
    if (!name.trim()) e.name = 'Full name is required';
    if (isStudent && !/^[^\s@]+@[^\s@]+\.edu\.bd$/.test(uniEmail.trim())) e.uniEmail = 'Must be a university email ending in .edu.bd';
    if (!isStudent && userEmail.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(userEmail.trim())) {
      e.userEmail = 'Enter a valid email address';
    }
    if (!/^(\+?880|0)?1[3-9]\d{8}$/.test(phone.replace(/\s/g, ''))) e.phone = 'Enter a valid Bangladesh phone number';
    if (pw.length < 12) e.pw = 'Password must be at least 12 characters';
    if (pw !== pwConf) e.pwConf = 'Passwords do not match';
    if (!terms) e.terms = 'You must agree to the Terms of Service';
    if (!dataCons) e.dataCons = 'Data processing consent is required';
    return e;
  };

  const clearErrs = () => setErrs({});

  const handleSubmit = async () => {
    const e = validate();
    if (Object.keys(e).length > 0) { setErrs(e); return; }
    setErrs({});
    setLoading(true);
    const normalizedPhone = phone.replace(/\s/g, '').replace(/^\+?880/, '0');
    const verifyViaEmail = isStudent || Boolean(userEmail.trim());
    const verifyIdentifier = verifyViaEmail
      ? (isStudent ? uniEmail.trim() : userEmail.trim())
      : normalizedPhone;
    try {
      const payload = {
        full_name:    name.trim(),
        email:        isStudent ? uniEmail.trim() : (userEmail.trim() || undefined),
        phone:        normalizedPhone,
        password:     pw,
        role:         isStudent ? 'student' : 'user',
        terms:        true,
        data_consent: true,
      };
      Object.keys(payload).forEach(k => payload[k] === undefined && delete payload[k]);

      const data = await apiPost('/auth/register', payload);

      setAuthPending({
        authStep: verifyViaEmail ? 'verify_email' : 'verify_phone',
        pendingIdentifier: verifyIdentifier,
      });
      go(verifyViaEmail ? 'verify-email' : 'verify-otp', {
        identifier: verifyIdentifier,
        name: name.trim(),
        devCode: data.dev_otp || null,
      });
    } catch (err) {
      if (err.status === 409 && err.data && err.data.pending_verification) {
        // Account exists but unverified — backend resent OTP, redirect to verify
        setAuthPending({
          authStep: verifyViaEmail ? 'verify_email' : 'verify_phone',
          pendingIdentifier: verifyIdentifier,
        });
        go(verifyViaEmail ? 'verify-email' : 'verify-otp', {
          identifier: verifyIdentifier,
          name: name.trim(),
          devCode: (err.data && err.data.dev_otp) || null,
        });
      } else if (err.status === 409) {
        setErrs({ submit: 'An account with this email or phone already exists.', showLogin: true });
      } else {
        setErrs({ submit: err.message });
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-wrap" style={{ paddingTop: 50 }}>
      <div style={{ padding: '20px 24px 0' }}>
        <BackBtn onPress={back} />
        <div style={{ marginTop: 16 }}>
          <div className="eyebrow" style={{ marginBottom: 4 }}>
            {isStudent ? 'University Student' : 'General Public'} account
          </div>
          <h2 className="serif" style={{ margin: 0, fontSize: 24, fontWeight: 500, color: 'var(--navy)' }}>
            Create your account
          </h2>
        </div>
      </div>

      <div style={{ padding: '20px 24px 0', display: 'flex', flexDirection: 'column', gap: 14 }}>
        <Field label="Full name" val={name} set={setName} ph="Sadia Akter" err={errs.name} ac="name" onClear={clearErrs} />
        {isStudent && (
          <Field label="University email" val={uniEmail} set={setUniEmail} type="email" ph="you@diu.edu.bd" err={errs.uniEmail} ac="email" onClear={clearErrs} />
        )}
        {!isStudent && (
          <div>
            <Field label="Email address" val={userEmail} set={setUserEmail} type="email" ph="you@gmail.com" err={errs.userEmail} ac="email" onClear={clearErrs} />
            <div style={{ fontSize: 11.5, color: 'var(--muted)', fontFamily: 'var(--font-sans)', marginTop: 4 }}>
              Optional · used for account notifications via email
            </div>
          </div>
        )}
        <Field label="Phone number" val={phone} set={setPhone} type="tel" ph="01XXXXXXXXX" err={errs.phone} ac="tel" onClear={clearErrs} />
        <div className="auth-field">
          <div className="eyebrow">Password</div>
          <input
            className={'auth-input' + (errs.pw ? ' error' : '')}
            type="password" placeholder="12+ characters" value={pw}
            onChange={e => { setPw(e.target.value); clearErrs(); }}
            autoComplete="new-password"
            style={errs.pw ? { borderColor: 'var(--red)' } : {}}
          />
          {errs.pw && <div style={{ fontSize: 11.5, color: 'var(--red)', fontFamily: 'var(--font-sans)' }}>{errs.pw}</div>}
          <PwStrength pw={pw} />
        </div>
        <Field label="Confirm password" val={pwConf} set={setPwConf} type="password" ph="Repeat password" err={errs.pwConf} ac="new-password" onClear={clearErrs} />

        <div style={{ height: 1, background: 'var(--mist)', margin: '4px 0' }} />

        <Checkbox
          label="I agree to the Terms of Service and Privacy Policy."
          checked={terms} set={setTerms} err={errs.terms} onClear={clearErrs}
        />
        <Checkbox
          label="I consent to my data being processed for civic complaint management and legal assistance."
          checked={dataCons} set={setDataCons} err={errs.dataCons} onClear={clearErrs}
        />

        {errs.submit && (
          <div style={{
            padding: '10px 14px', borderRadius: 10,
            background: 'rgba(232,49,42,0.07)', border: '1px solid rgba(232,49,42,0.2)',
            color: 'var(--red)', fontSize: 12.5, fontFamily: 'var(--font-sans)',
          }}>
            {errs.submit}
            {errs.showLogin && (
              <button
                onClick={() => go('login')}
                style={{
                  display: 'block', marginTop: 8, color: 'var(--navy)',
                  background: 'none', border: 'none', cursor: 'pointer',
                  fontFamily: 'var(--font-sans)', fontSize: 12.5, fontWeight: 600, padding: 0,
                }}>
                Log in instead →
              </button>
            )}
          </div>
        )}

        <button
          onClick={handleSubmit}
          disabled={loading}
          className="btn btn-primary"
          style={{
            width: '100%', marginTop: 4, height: 48, fontSize: 15, fontWeight: 600,
            borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center',
            gap: 8, opacity: loading ? 0.85 : 1,
          }}>
          {loading ? <><Spinner /> Creating account…</> : 'Create account'}
        </button>
      </div>
      <div style={{ height: 40 }} />
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// VERIFY EMAIL  (spec §7)
// ─────────────────────────────────────────────────────────────
function VerifyEmailScreen({ params }) {
  const { go, login } = useApp();
  const email    = (params && params.identifier) || '';
  const userName = (params && params.name) || 'Student';
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [devCode, setDevCode] = useState((params && params.devCode) || null);

  const masked = typeof email === 'string' && email.includes('@')
    ? email.replace(/^(.{2})(.*)(@.*)$/, (_, a, b, c) => a + '*'.repeat(Math.max(2, b.length)) + c)
    : email;

  const verify = async (val) => {
    const c = val || code;
    if (c.replace(/ /g, '').length < 6) return;
    setLoading(true);
    setError('');
    try {
      const data = await apiPost('/auth/verify-email', { token: email + ':' + c });
      saveTokens(data.access_token, data.refresh_token);
      const me = await apiGet('/auth/me');
      login({
        id:        String(me.id),
        name:      me.full_name,
        role:      me.role,
        tenant_id: me.tenant_id ? String(me.tenant_id) : null,
        mfa:       me.mfa_enabled,
      });
      registerFCMToken();
      go('home');
    } catch (err) {
      setError(err.message);
      setCode('');
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    setCode('');
    setError('');
    const data = await apiPost('/auth/resend-verification', { identifier: email });
    return data.dev_otp || null;
  };

  return (
    <div className="auth-wrap" style={{ paddingTop: 64 }}>
      <div style={{ padding: '0 24px', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
        <div style={{
          width: 64, height: 64, borderRadius: 999,
          background: 'rgba(74,107,92,0.1)', border: '1.5px solid rgba(74,107,92,0.22)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 14,
        }}>
          <IconBell size={28} stroke="var(--sage)" />
        </div>
        <h2 className="serif" style={{ margin: '0 0 8px', fontSize: 24, fontWeight: 500, color: 'var(--navy)' }}>
          Check your inbox
        </h2>
        <p style={{ margin: 0, fontSize: 13.5, color: 'var(--muted)', lineHeight: 1.6, fontFamily: 'var(--font-sans)' }}>
          We sent a 6-digit code to<br />
          <strong style={{ color: 'var(--navy)' }}>{masked}</strong>
        </p>
      </div>

      <div style={{ padding: '32px 24px 0', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20 }}>
        <OTPInput value={code} onChange={setCode} onComplete={verify} />

        {devCode && (
          <div style={{
            width: '100%', padding: '10px 14px', borderRadius: 10,
            background: 'rgba(74,107,92,0.08)', border: '1px dashed rgba(74,107,92,0.35)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <span style={{ fontSize: 11.5, color: 'var(--sage)', fontFamily: 'var(--font-sans)' }}>Dev code:</span>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 18, fontWeight: 700, letterSpacing: '0.2em', color: 'var(--navy)' }}>{devCode}</span>
          </div>
        )}

        {error && (
          <div style={{ fontSize: 12.5, color: 'var(--red)', textAlign: 'center', fontFamily: 'var(--font-sans)' }}>
            {error}
          </div>
        )}

        <button
          onClick={() => verify()}
          disabled={loading || code.replace(/ /g, '').length < 6}
          className="btn btn-primary"
          style={{
            width: '100%', height: 48, fontSize: 15, fontWeight: 600, borderRadius: 12,
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            opacity: (loading || code.replace(/ /g, '').length < 6) ? 0.6 : 1,
          }}>
          {loading ? <><Spinner /> Verifying…</> : 'Verify email'}
        </button>

        <ResendBtn onResend={handleResend} onDevCode={setDevCode} />
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// VERIFY OTP — phone  (spec §8)
// ─────────────────────────────────────────────────────────────
function VerifyOTPScreen({ params }) {
  const { go, login } = useApp();
  const phone    = (params && params.identifier) || '';
  const userName = (params && params.name) || 'User';
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [devCode, setDevCode] = useState((params && params.devCode) || null);

  const masked = typeof phone === 'string'
    ? phone.replace(/^(\+?8?8?0?1\d{1})\d+(\d{3})$/, (_, a, b) => a + '****' + b)
    : phone;

  const verify = async (val) => {
    const c = val || code;
    if (c.replace(/ /g, '').length < 6) return;
    setLoading(true);
    setError('');
    try {
      const data = await apiPost('/auth/verify-phone', { phone: phone, code: c });
      saveTokens(data.access_token, data.refresh_token);
      const me = await apiGet('/auth/me');
      login({
        id:        String(me.id),
        name:      me.full_name,
        role:      me.role,
        tenant_id: me.tenant_id ? String(me.tenant_id) : null,
        mfa:       me.mfa_enabled,
      });
      registerFCMToken();
      go('home');
    } catch (err) {
      setError(err.message);
      setCode('');
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    setCode('');
    setError('');
    const data = await apiPost('/auth/resend-verification', { identifier: phone });
    return data.dev_otp || null;
  };

  return (
    <div className="auth-wrap" style={{ paddingTop: 64 }}>
      <div style={{ padding: '0 24px', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
        <div style={{
          width: 64, height: 64, borderRadius: 999,
          background: 'rgba(196,69,54,0.08)', border: '1.5px solid rgba(196,69,54,0.2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 14,
        }}>
          <IconPhone size={28} stroke="var(--ember)" />
        </div>
        <h2 className="serif" style={{ margin: '0 0 8px', fontSize: 24, fontWeight: 500, color: 'var(--navy)' }}>
          Verify your phone
        </h2>
        <p style={{ margin: 0, fontSize: 13.5, color: 'var(--muted)', lineHeight: 1.6, fontFamily: 'var(--font-sans)' }}>
          We sent an OTP to<br />
          <strong style={{ color: 'var(--navy)' }}>{masked}</strong>
        </p>
      </div>

      <div style={{ padding: '32px 24px 0', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20 }}>
        <OTPInput value={code} onChange={setCode} onComplete={verify} />

        {devCode && (
          <div style={{
            width: '100%', padding: '10px 14px', borderRadius: 10,
            background: 'rgba(196,69,54,0.07)', border: '1px dashed rgba(196,69,54,0.3)',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          }}>
            <span style={{ fontSize: 11.5, color: 'var(--ember)', fontFamily: 'var(--font-sans)' }}>Dev code:</span>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 18, fontWeight: 700, letterSpacing: '0.2em', color: 'var(--navy)' }}>{devCode}</span>
          </div>
        )}

        {error && (
          <div style={{ fontSize: 12.5, color: 'var(--red)', textAlign: 'center', fontFamily: 'var(--font-sans)' }}>
            {error}
          </div>
        )}

        <button
          onClick={() => verify()}
          disabled={loading || code.replace(/ /g, '').length < 6}
          className="btn btn-primary"
          style={{
            width: '100%', height: 48, fontSize: 15, fontWeight: 600, borderRadius: 12,
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            opacity: (loading || code.replace(/ /g, '').length < 6) ? 0.6 : 1,
          }}>
          {loading ? <><Spinner /> Verifying…</> : 'Verify phone'}
        </button>

        <ResendBtn onResend={handleResend} onDevCode={setDevCode} />
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// FORGOT PASSWORD  (spec §11.4)
// ─────────────────────────────────────────────────────────────
function ForgotPasswordScreen() {
  const { go, back } = useApp();
  const [identifier, setIdentifier] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [devCode, setDevCode] = useState(null);

  const submit = async () => {
    if (!identifier.trim()) return;
    setLoading(true);
    try {
      const data = await apiPost('/auth/forgot-password', { identifier: identifier.trim() });
      if (data.dev_code) setDevCode(data.dev_code);
      setSent(true);
    } catch (_) {
      setSent(true); // don't reveal whether account exists
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-wrap" style={{ paddingTop: 50 }}>
      <div style={{ padding: '20px 24px 0' }}>
        <BackBtn onPress={back} />
      </div>

      {!sent ? (
        <div style={{ padding: '28px 24px 0' }}>
          <div className="eyebrow" style={{ marginBottom: 5 }}>Account recovery</div>
          <h2 className="serif" style={{ margin: '0 0 8px', fontSize: 24, fontWeight: 500, color: 'var(--navy)' }}>
            Reset your password
          </h2>
          <p style={{ margin: '0 0 24px', fontSize: 13.5, color: 'var(--muted)', lineHeight: 1.6, fontFamily: 'var(--font-sans)' }}>
            Enter your email address or phone number and we'll send you a reset code.
          </p>
          <div className="auth-field" style={{ marginBottom: 16 }}>
            <div className="eyebrow">Email or phone number</div>
            <input
              className="auth-input"
              type="text"
              placeholder="you@diu.edu.bd or 01XXXXXXXXX"
              value={identifier}
              onChange={e => setIdentifier(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && submit()}
            />
          </div>
          <button
            onClick={submit}
            disabled={loading || !identifier.trim()}
            className="btn btn-primary"
            style={{
              width: '100%', height: 48, fontSize: 15, fontWeight: 600, borderRadius: 12,
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              opacity: (loading || !identifier.trim()) ? 0.6 : 1,
            }}>
            {loading ? <><Spinner /> Sending…</> : 'Send reset code'}
          </button>
        </div>
      ) : (
        <div style={{ padding: '40px 24px 0', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: 16 }}>
          <div style={{
            width: 64, height: 64, borderRadius: 999,
            background: 'rgba(74,107,92,0.1)', border: '1.5px solid rgba(74,107,92,0.22)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <IconCheck size={28} stroke="var(--sage)" sw={2.5} />
          </div>
          <div>
            <h2 className="serif" style={{ margin: '0 0 8px', fontSize: 24, fontWeight: 500, color: 'var(--navy)' }}>
              Code sent
            </h2>
            <p style={{ margin: 0, fontSize: 13.5, color: 'var(--muted)', lineHeight: 1.6, fontFamily: 'var(--font-sans)' }}>
              If an account exists, a reset code was sent.<br />It expires in 5 minutes.
            </p>
          </div>
          <button
            onClick={() => go('login')}
            className="btn btn-ghost"
            style={{ width: '100%', height: 44, borderRadius: 12, fontSize: 14, marginTop: 8 }}>
            Back to sign in
          </button>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// MFA VERIFY — during login  (spec §13)
// ─────────────────────────────────────────────────────────────
function MFAVerifyScreen() {
  const { go, login } = useApp();
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showRecovery, setShowRecovery] = useState(false);
  const [recoveryCode, setRecoveryCode] = useState('');

  const complete = () => {
    login({
      id: 'usr_mfa_' + Math.random().toString(36).slice(2, 6),
      name: 'MFA User',
      role: 'user',
      tenant_id: null,
      mfa: true,
    });
    registerFCMToken();
    go('home');
  };

  const verify = (val) => {
    const c = val || code;
    if (c.replace(/ /g, '').length < 6) return;
    setLoading(true);
    setError('');
    // BACKEND INTEGRATION POINT: POST /auth/mfa/verify
    setTimeout(() => { setLoading(false); complete(); }, 900);
  };

  const useRecovery = () => {
    if (!recoveryCode.trim()) return;
    setLoading(true);
    // BACKEND INTEGRATION POINT: POST /auth/mfa/recovery
    setTimeout(() => { setLoading(false); complete(); }, 900);
  };

  return (
    <div className="auth-wrap" style={{ paddingTop: 64 }}>
      <div style={{ padding: '0 24px', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
        <div style={{
          width: 64, height: 64, borderRadius: 999,
          background: 'rgba(11,29,53,0.06)', border: '1.5px solid var(--mist)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 14,
        }}>
          <IconShield size={28} stroke="var(--navy)" />
        </div>
        <h2 className="serif" style={{ margin: '0 0 8px', fontSize: 24, fontWeight: 500, color: 'var(--navy)' }}>
          Two-factor check
        </h2>
        <p style={{ margin: 0, fontSize: 13.5, color: 'var(--muted)', lineHeight: 1.6, fontFamily: 'var(--font-sans)' }}>
          Enter the 6-digit code from your authenticator app.
        </p>
      </div>

      <div style={{ padding: '32px 24px 0', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20 }}>
        <OTPInput value={code} onChange={setCode} onComplete={verify} />

        {error && <div style={{ fontSize: 12.5, color: 'var(--red)', textAlign: 'center' }}>{error}</div>}

        <button
          onClick={() => verify()}
          disabled={loading || code.replace(/ /g, '').length < 6}
          className="btn btn-primary"
          style={{
            width: '100%', height: 48, fontSize: 15, fontWeight: 600, borderRadius: 12,
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            opacity: (loading || code.replace(/ /g, '').length < 6) ? 0.6 : 1,
          }}>
          {loading ? <><Spinner /> Verifying…</> : 'Confirm'}
        </button>

        {/* Recovery code accordion */}
        <div style={{ width: '100%', borderTop: '1px solid var(--mist)', paddingTop: 16 }}>
          <button
            onClick={() => setShowRecovery(s => !s)}
            style={{
              border: 'none', background: 'none', cursor: 'pointer',
              fontSize: 13, color: 'var(--navy)', fontFamily: 'var(--font-sans)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              gap: 5, padding: 0, width: '100%',
            }}>
            Lost access to your authenticator?
            <span style={{ display: 'inline-block', transition: 'transform 0.2s', transform: showRecovery ? 'rotate(90deg)' : 'none' }}>
              <IconChevronRight size={12} />
            </span>
          </button>
          {showRecovery && (
            <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 10 }}>
              <p style={{ margin: 0, fontSize: 12.5, color: 'var(--muted)', textAlign: 'center', lineHeight: 1.5, fontFamily: 'var(--font-sans)' }}>
                Enter one of your 10 one-time recovery codes.
              </p>
              <input
                className="auth-input"
                placeholder="XXXX-XXXX-XXXX"
                value={recoveryCode}
                onChange={e => setRecoveryCode(e.target.value.toUpperCase())}
                style={{ textAlign: 'center', fontFamily: 'var(--font-mono)', letterSpacing: '0.1em' }}
              />
              <button
                onClick={useRecovery}
                disabled={loading || !recoveryCode.trim()}
                className="btn btn-ghost"
                style={{ height: 44, borderRadius: 12, fontSize: 13, opacity: !recoveryCode.trim() ? 0.5 : 1 }}>
                {loading ? 'Checking…' : 'Use recovery code'}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// MFA SETUP — from Profile → Security  (spec §13.3–13.4)
// ─────────────────────────────────────────────────────────────
const MOCK_TOTP_SECRET = 'JBSW Y3DP EHPK 3PXP';
const MOCK_RECOVERY_CODES = [
  'A1B2-C3D4-E5F6', 'G7H8-I9J0-K1L2',
  'M3N4-O5P6-Q7R8', 'S9T0-U1V2-W3X4',
  'Y5Z6-A7B8-C9D0', 'E1F2-G3H4-I5J6',
  'K7L8-M9N0-O1P2', 'Q3R4-S5T6-U7V8',
  'W9X0-Y1Z2-A3B4', 'C5D6-E7F8-G9H0',
];

function MFASetupScreen() {
  const { back } = useApp();
  const [step, setStep] = useState(1);
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  const verifyCode = (val) => {
    const c = val || code;
    if (c.replace(/ /g, '').length < 6) return;
    setLoading(true);
    // BACKEND INTEGRATION POINT: POST /auth/mfa/enroll/verify
    setTimeout(() => { setLoading(false); setStep(3); }, 900);
  };

  const copySecret = () => {
    try { navigator.clipboard.writeText(MOCK_TOTP_SECRET.replace(/\s/g, '')); } catch (e) {}
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const StepDot = ({ n }) => (
    <div style={{
      width: 26, height: 26, borderRadius: 999, flexShrink: 0,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: n < step ? 'var(--sage)' : (n === step ? 'var(--navy)' : 'var(--mist)'),
      color: n <= step ? '#fff' : 'var(--muted)',
      fontSize: 12, fontWeight: 600, fontFamily: 'var(--font-sans)',
      transition: 'all 0.2s',
    }}>
      {n < step ? <IconCheck size={11} stroke="#fff" sw={3} /> : n}
    </div>
  );

  return (
    <div className="auth-wrap" style={{ paddingTop: 50 }}>
      <div style={{ padding: '20px 24px 0', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <BackBtn onPress={back} />
        <div className="eyebrow" style={{ fontSize: 10 }}>Two-factor auth</div>
        <div style={{ width: 70 }} />
      </div>

      {/* Step indicator */}
      <div style={{ display: 'flex', alignItems: 'center', padding: '18px 40px 0', gap: 0 }}>
        <StepDot n={1} />
        <div style={{ flex: 1, height: 2, background: step > 1 ? 'var(--sage)' : 'var(--mist)', transition: 'background 0.3s', margin: '0 6px' }} />
        <StepDot n={2} />
        <div style={{ flex: 1, height: 2, background: step > 2 ? 'var(--sage)' : 'var(--mist)', transition: 'background 0.3s', margin: '0 6px' }} />
        <StepDot n={3} />
      </div>

      {step === 1 && (
        <div style={{ padding: '24px 24px 0', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20 }}>
          <div style={{ textAlign: 'center' }}>
            <h2 className="serif" style={{ margin: '0 0 6px', fontSize: 22, fontWeight: 500, color: 'var(--navy)' }}>
              Scan with your app
            </h2>
            <p style={{ margin: 0, fontSize: 13, color: 'var(--muted)', lineHeight: 1.55, fontFamily: 'var(--font-sans)' }}>
              Use Aegis, Google Authenticator, or any TOTP app.
            </p>
          </div>
          <div className="qr-placeholder">
            <svg width="42" height="42" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="square">
              <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
              <rect x="3" y="14" width="7" height="7" />
              <path d="M14 14h2m2 0h1m-3 2v1m0 2h2m1 0v2m-4-2h1" />
            </svg>
            <span>QR code renders<br />in production</span>
          </div>
          <div style={{ width: '100%', background: 'var(--cream-2)', borderRadius: 12, padding: '12px 14px' }}>
            <div className="eyebrow" style={{ marginBottom: 7 }}>Manual entry key</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{ flex: 1, fontFamily: 'var(--font-mono)', fontSize: 14, letterSpacing: '0.1em', color: 'var(--navy)' }}>
                {MOCK_TOTP_SECRET}
              </div>
              <button
                onClick={copySecret}
                style={{
                  border: '1px solid var(--mist-2)', borderRadius: 8, padding: '5px 10px',
                  background: '#fff', cursor: 'pointer', fontSize: 12,
                  fontFamily: 'var(--font-sans)', color: 'var(--navy)', flexShrink: 0,
                }}>
                {copied ? '✓ Copied' : 'Copy'}
              </button>
            </div>
          </div>
          <button onClick={() => setStep(2)} className="btn btn-primary"
            style={{ width: '100%', height: 48, fontSize: 15, fontWeight: 600, borderRadius: 12 }}>
            I've scanned it
          </button>
        </div>
      )}

      {step === 2 && (
        <div style={{ padding: '24px 24px 0', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 20 }}>
          <div style={{ textAlign: 'center' }}>
            <h2 className="serif" style={{ margin: '0 0 6px', fontSize: 22, fontWeight: 500, color: 'var(--navy)' }}>
              Enter the code
            </h2>
            <p style={{ margin: 0, fontSize: 13, color: 'var(--muted)', lineHeight: 1.55, fontFamily: 'var(--font-sans)' }}>
              Enter the 6-digit code your app shows now.
            </p>
          </div>
          <OTPInput value={code} onChange={setCode} onComplete={verifyCode} />
          <button
            onClick={() => verifyCode()}
            disabled={loading || code.replace(/ /g, '').length < 6}
            className="btn btn-primary"
            style={{
              width: '100%', height: 48, fontSize: 15, fontWeight: 600, borderRadius: 12,
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
              opacity: (loading || code.replace(/ /g, '').length < 6) ? 0.6 : 1,
            }}>
            {loading ? <><Spinner /> Verifying…</> : 'Confirm code'}
          </button>
        </div>
      )}

      {step === 3 && (
        <div style={{ padding: '20px 24px 0' }}>
          <div style={{ textAlign: 'center', marginBottom: 20 }}>
            <div style={{
              width: 52, height: 52, borderRadius: 999,
              background: 'rgba(74,107,92,0.1)', border: '1.5px solid rgba(74,107,92,0.22)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 12px',
            }}>
              <IconShield size={24} stroke="var(--sage)" />
            </div>
            <h2 className="serif" style={{ margin: '0 0 6px', fontSize: 22, fontWeight: 500, color: 'var(--navy)' }}>
              Two-factor enabled
            </h2>
            <p style={{ margin: 0, fontSize: 13, color: 'var(--muted)', lineHeight: 1.55, fontFamily: 'var(--font-sans)' }}>
              Save these recovery codes securely.<br />Each code can only be used once.
            </p>
          </div>
          <div className="recovery-grid">
            {MOCK_RECOVERY_CODES.map(c => (
              <div key={c} className="recovery-code">{c}</div>
            ))}
          </div>
          <div style={{
            marginTop: 14, padding: '10px 14px', borderRadius: 10,
            background: 'rgba(232,49,42,0.06)', border: '1px solid rgba(232,49,42,0.18)',
          }}>
            <div style={{ fontSize: 12, color: 'var(--red)', lineHeight: 1.55, fontFamily: 'var(--font-sans)' }}>
              Store these codes somewhere safe. They cannot be shown again.
            </div>
          </div>
          <button
            onClick={back}
            className="btn btn-primary"
            style={{ width: '100%', marginTop: 16, height: 48, fontSize: 15, fontWeight: 600, borderRadius: 12 }}>
            I've saved my codes
          </button>
          <div style={{ height: 36 }} />
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// TRACKING LOOKUP — no login required  (spec §12.2)
// ─────────────────────────────────────────────────────────────
const MOCK_TRACKING = {
  'ANCH123456789A': {
    ref: 'ANCH123456789A',
    title: 'Harassment complaint — Hostel Block C [details redacted]',
    status: 'escalated',
    statusLabel: 'Escalated',
    level: 'Level 2 — Department Review',
    lastUpdated: '23 May 2026, 11:14 AM',
    adminNote: 'Complaint received and reviewed. Forwarded to the Department Grievance Committee for formal inquiry.',
  },
};

function TrackingLookupScreen() {
  const { go } = useApp();
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [notFound, setNotFound] = useState(false);

  const STATUS_LABELS = {
    received:     'Submitted',
    under_review: 'Under Review',
    escalated:    'Escalated',
    resolved:     'Resolved',
    dismissed:    'Dismissed',
    withdrawn:    'Withdrawn',
  };

  const lookup = async () => {
    const key = code.toUpperCase().replace(/[^A-Z0-9]/g, '');
    if (key.length < 8) return;
    setLoading(true);
    setResult(null);
    setNotFound(false);
    try {
      const res = await fetch(`${AUTH_API}/complaints/track/${key}`);
      const data = await res.json();
      if (!res.ok || !data.found) {
        setNotFound(true);
      } else {
        setResult({
          ref:         data.code,
          title:       'Anonymous complaint [details redacted]',
          status:      data.status,
          statusLabel: STATUS_LABELS[data.status] || data.status,
          level:       '—',
          lastUpdated: '—',
          adminNote:   data.status_message || 'No update from admin yet.',
        });
      }
    } catch (_) {
      setNotFound(true);
    } finally {
      setLoading(false);
    }
  };

  const statusColors = {
    submitted:    'var(--muted)',
    received:     'var(--muted)',
    under_review: 'var(--gold)',
    escalated:    'var(--ember)',
    resolved:     'var(--sage)',
    dismissed:    'var(--muted)',
    withdrawn:    'var(--muted)',
  };

  const cleanLen = code.replace(/[^A-Z0-9]/gi, '').length;

  return (
    <div className="auth-wrap" style={{ paddingTop: 50 }}>
      <div style={{ padding: '20px 24px 0' }}>
        <button
          onClick={() => go('login')}
          style={{
            border: '1px solid var(--mist-2)', borderRadius: 999, padding: '6px 12px 6px 8px',
            display: 'inline-flex', alignItems: 'center', gap: 4, background: 'transparent',
            cursor: 'pointer', color: 'var(--navy)', fontFamily: 'var(--font-sans)',
            fontSize: 12, fontWeight: 500,
          }}>
          <IconArrowLeft size={13} /> Sign in
        </button>
        <div style={{ marginTop: 18 }}>
          <div className="eyebrow" style={{ marginBottom: 5 }}>Anonymous access</div>
          <h2 className="serif" style={{ margin: '0 0 8px', fontSize: 24, fontWeight: 500, color: 'var(--navy)' }}>
            Track your complaint
          </h2>
          <p style={{ margin: 0, fontSize: 13, color: 'var(--muted)', lineHeight: 1.6, fontFamily: 'var(--font-sans)' }}>
            Enter the 12-character code you received when filing. No login required.
          </p>
        </div>
      </div>

      <div style={{ padding: '24px 24px 0', display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div className="auth-field">
          <div className="eyebrow">Tracking code</div>
          <input
            className="auth-input"
            placeholder="ANCH123456789A"
            value={code}
            onChange={e => {
              setCode(e.target.value.toUpperCase());
              setNotFound(false);
              setResult(null);
            }}
            onKeyDown={e => e.key === 'Enter' && lookup()}
            style={{ fontFamily: 'var(--font-mono)', letterSpacing: '0.07em', textTransform: 'uppercase' }}
          />
          <div style={{ fontSize: 11.5, color: 'var(--muted)', fontFamily: 'var(--font-sans)' }}>
            Demo code: ANCH123456789A
          </div>
        </div>

        <button
          onClick={lookup}
          disabled={loading || cleanLen < 8}
          className="btn btn-primary"
          style={{
            width: '100%', height: 48, fontSize: 15, fontWeight: 600, borderRadius: 12,
            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
            opacity: (loading || cleanLen < 8) ? 0.6 : 1,
          }}>
          {loading ? <><Spinner /> Looking up…</> : 'Look up complaint'}
        </button>

        {notFound && (
          <div style={{
            padding: '12px 14px', borderRadius: 12,
            background: 'rgba(232,49,42,0.06)', border: '1px solid rgba(232,49,42,0.18)',
            fontSize: 13, color: 'var(--red)', fontFamily: 'var(--font-sans)',
          }}>
            Code not found. Check the code and try again.
          </div>
        )}

        {result && (
          <div style={{
            background: 'rgba(255,255,255,0.85)', border: '1px solid var(--mist)',
            borderRadius: 16, padding: 18, animation: 'pageIn 240ms both',
          }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10, marginBottom: 12 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--navy)', lineHeight: 1.35 }}>
                  {result.title}
                </div>
                <div style={{ marginTop: 4, fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--font-mono)', letterSpacing: '0.05em' }}>
                  {result.ref}
                </div>
              </div>
              <span
                className="pill"
                style={{ color: statusColors[result.status] || 'var(--navy)', flexShrink: 0 }}>
                {result.statusLabel}
              </span>
            </div>
            <div style={{ height: 1, background: 'var(--mist)', margin: '10px 0' }} />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
              <div>
                <div className="eyebrow" style={{ fontSize: 9, marginBottom: 3 }}>Escalation level</div>
                <div style={{ fontSize: 12, color: 'var(--navy)', fontFamily: 'var(--font-sans)', lineHeight: 1.4 }}>{result.level}</div>
              </div>
              <div>
                <div className="eyebrow" style={{ fontSize: 9, marginBottom: 3 }}>Last updated</div>
                <div style={{ fontSize: 12, color: 'var(--navy)', fontFamily: 'var(--font-sans)', lineHeight: 1.4 }}>{result.lastUpdated}</div>
              </div>
            </div>
            <div style={{
              padding: '10px 12px', borderRadius: 10,
              background: 'var(--cream-2)', border: '1px dashed var(--mist-2)',
            }}>
              <div className="eyebrow" style={{ fontSize: 9, marginBottom: 4 }}>Admin note</div>
              <div style={{ fontSize: 12, color: 'var(--ink-2)', lineHeight: 1.6, fontFamily: 'var(--font-sans)' }}>
                {result.adminNote}
              </div>
            </div>
          </div>
        )}
      </div>
      <div style={{ height: 40 }} />
    </div>
  );
}

// Export all screens to global scope for RouteView in app.jsx
Object.assign(window, {
  LoginScreen,
  RegisterChoiceScreen,
  RegisterFormScreen,
  VerifyEmailScreen,
  VerifyOTPScreen,
  ForgotPasswordScreen,
  MFAVerifyScreen,
  MFASetupScreen,
  TrackingLookupScreen,
});
