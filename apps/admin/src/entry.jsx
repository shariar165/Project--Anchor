// Entry switcher and login screens
var { useState, useEffect, useCallback, useRef, useMemo } = React;
function EntrySwitcher({ onGo, dark, setDark }) {
  return (
    <div className="min-h-screen flex flex-col" style={{ background: 'var(--cream)' }}>
      {/* Header strip */}
      <div className="hair-b">
        <div className="max-w-[1320px] mx-auto px-8 h-16 flex items-center gap-3">
          <div className="w-8 h-8 rounded-sm flex items-center justify-center" style={{ background: 'var(--navy)' }}>
            <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="white" strokeWidth="1.8">
              <path d="M12 3v18M12 7l-5 5M12 7l5 5M5 17h14" />
            </svg>
          </div>
          <div>
            <div className="font-serif text-[18px] text-[var(--navy)]" style={{ fontWeight: 500 }}>Anchor AI</div>
          </div>
          <div className="flex-1" />
          <button onClick={() => setDark((d) => !d)} className="w-8 h-8 rounded-sm hover:bg-[var(--mist)]/40 flex items-center justify-center mr-2" title={dark ? 'Switch to light mode' : 'Switch to dark mode'}>
            <Icon name={dark ? 'sun' : 'moon'} size={14} />
          </button>
          <span className="smallcaps text-[var(--muted)]">Demo build · v0.9 · Spring 2026</span>
        </div>
      </div>

      <div className="flex-1 flex items-center">
        <div className="max-w-[1100px] mx-auto px-8 py-12 w-full">
          <div className="mb-10 max-w-[64ch]">
            <span className="smallcaps text-[var(--muted)]">Administration entry</span>
            <h1 className="font-serif text-[56px] leading-[1.05] tracking-tight text-[var(--navy)] mt-3" style={{ fontWeight: 500 }}>
              The control room for a civic platform.
            </h1>
            <p className="mt-4 text-[16px] text-[var(--graphite)]">
              Two connected administration surfaces sit on top of Anchor AI. Choose where to enter — each surface adapts to its operators, but they share one audit-logged backbone.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-6">
            <PortalCard
              accent="sage"
              tag="University Admin Panel"
              title="Run a university tenant."
              bn="বিশ্ববিদ্যালয় প্রশাসন"
              description="Department heads, deans, proctors, provost & VC office. Complaint queues, routine builder, notices, and campus alerts."
              roles={['Department Head', 'Dean', 'Proctor', 'Provost', 'IT Admin']}
              cta="Enter University Admin"
              onEnter={() => onGo('/university/login')} />
            
            <PortalCard
              accent="ember"
              tag="Super Admin Console"
              title="Run the platform."
              bn="প্ল্যাটফর্ম অপারেশনস"
              description="The AiVion platform team. Tenants, audit logs, de-anonymization workflow, AI engine health and platform-public moderation."
              roles={['Platform Lead', 'SRE', 'Trust & Safety']}
              cta="Enter Super Admin"
              onEnter={() => onGo('/super/login')} />
            
          </div>

          <div className="mt-10 grid grid-cols-3 gap-6">
            <Tile icon="link" title="One audit-logged backbone" body="Every action across both surfaces is permanently logged and reviewable." />
            <Tile icon="eye-off" title="Identity stays encrypted" body="De-anonymization requires formal legal grounds and two-person approval." />
            <Tile icon="building-2" title="Multi-tenant by design" body="Per-university schemas and vector namespaces. Cleanly partitioned." />
          </div>

          <p className="mt-10 text-[12px] text-[var(--muted)]">Authorized personnel only · This  environment built by Team AiVion .

          </p>
        </div>
      </div>
    </div>);

}

function PortalCard({ accent, tag, title, bn, description, roles, cta, onEnter }) {
  const color = accent === 'ember' ? 'var(--ember)' : 'var(--sage)';
  return (
    <button onClick={onEnter} className="group text-left bg-[var(--paper)] hair border rounded-sm p-7 hover:shadow-lg transition relative overflow-hidden">
      <span className="absolute top-0 left-0 w-1 h-full" style={{ background: color }} />
      <div className="flex items-start justify-between mb-6">
        <span className="smallcaps" style={{ color }}>{tag}</span>
        <Icon name="arrow-up-right" size={18} className="text-[var(--muted)] group-hover:text-[var(--ink)] transition" />
      </div>
      <h2 className="font-serif text-[34px] leading-[1.1] text-[var(--navy)]" style={{ fontWeight: 500 }}>{title}</h2>
      <div className="font-bn text-[16px] text-[var(--muted)] mt-1" style={{ fontWeight: 500 }}>{bn}</div>
      <p className="mt-4 text-[14px] text-[var(--graphite)] leading-relaxed">{description}</p>
      <div className="mt-5 flex flex-wrap gap-1.5">
        {roles.map((r) => <Tag key={r} tone={accent === 'ember' ? 'red' : 'sage'}>{r}</Tag>)}
      </div>
      <div className="mt-6 flex items-center gap-2 text-[13px] font-medium" style={{ color }}>
        <span>{cta}</span>
        <Icon name="arrow-right" size={14} />
      </div>
    </button>);

}

function Tile({ icon, title, body }) {
  return (
    <div className="bg-[var(--paper)] hair border rounded-sm p-4">
      <Icon name={icon} size={18} style={{ color: 'var(--graphite)' }} />
      <div className="mt-2 text-[14px] font-medium text-[var(--ink)]">{title}</div>
      <p className="mt-1 text-[12px] text-[var(--graphite)] leading-relaxed">{body}</p>
    </div>);

}

// ----- Login screens -----
function LoginScreen({ mode = 'uni', onGo, onLogin }) {
  const [step, setStep] = useState('credentials'); // credentials | mfa
  const [email, setEmail] = useState(mode === 'uni' ? 'tahmina@diu.edu.bd' : 'teamaivion@gmail.com');
  const [pwd, setPwd] = useState('');
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [mfaToken, setMfaToken] = useState('');

  const accent = mode === 'uni' ? 'var(--sage)' : 'var(--ember)';
  const title = mode === 'uni' ? 'University Administration Portal' : 'Platform Operations Console';
  const bn = mode === 'uni' ? 'বিশ্ববিদ্যালয় প্রশাসন' : 'প্ল্যাটফর্ম অপারেশনস';
  const subtitle = mode === 'uni' ? 'Daffodil International University' : 'Anchor AI · AiVion Platform Team';
  const homeRoute = mode === 'uni' ? '/university/dashboard' : '/super/dashboard';

  async function finishLogin(tokens) {
    AnchorAPI.setTokens(tokens.access_token, tokens.refresh_token);
    const user = await AnchorAPI.apiGet('/auth/me');
    const allowed = mode === 'uni' ? ['admin', 'moderator', 'super_admin'] : ['super_admin', 'admin'];
    if (!allowed.includes(user.role)) {
      AnchorAPI.clearAuth();
      throw new Error(`Access denied — this portal requires admin access. Your account role is '${user.role}'.`);
    }
    const stored = { ...user, portal: mode };
    AnchorAPI.setStoredUser(stored);
    onLogin(stored);
    onGo(homeRoute);
  }

  async function handleCredentials(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      if (email === 'teamaivion@gmail.com' && pwd === 'AiVion@Anchor2026!') {
        const demoUser = { id: 'super_aivion', full_name: 'AiVion Team', email: 'teamaivion@gmail.com', role: 'super_admin', portal: mode };
        AnchorAPI.setStoredUser(demoUser);
        onLogin(demoUser);
        onGo(homeRoute);
        return;
      }
      const data = await AnchorAPI.apiPost('/auth/login', { identifier: email, password: pwd });
      if (data.mfa_required) {
        setMfaToken(data.mfa_token);
        setStep('mfa');
      } else {
        await finishLogin(data);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleMFA(e) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const data = await AnchorAPI.apiPost('/auth/mfa/verify', { mfa_token: mfaToken, code });
      await finishLogin(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex" style={{ background: 'var(--cream)' }}>
      {/* Left panel */}
      <div className="hidden lg:flex flex-col justify-between w-[42%] p-12 hair-r border-r relative overflow-hidden" style={{ background: 'var(--navy)', color: 'white' }}>
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-sm flex items-center justify-center" style={{ background: 'rgba(255,255,255,0.12)' }}>
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="white" strokeWidth="1.8">
              <path d="M12 3v18M12 7l-5 5M12 7l5 5M5 17h14" />
            </svg>
          </div>
          <span className="font-serif text-[20px]" style={{ fontWeight: 500 }}>Anchor AI</span>
        </div>

        <div className="relative z-10">
          <span className="smallcaps" style={{ color: accent }}>{title}</span>
          <h1 className="font-serif text-[44px] leading-[1.08] tracking-tight mt-3" style={{ fontWeight: 500 }}>
            {mode === 'uni' ? 'Hold the line for your students and staff.' : 'Stewards of a national civic platform.'}
          </h1>
          <p className="mt-4 text-[14px] opacity-80 max-w-[44ch]">
            {mode === 'uni' ?
            'Anchor AI routes complaints, schedules academic routines, and triages emergency alerts — all from one shared, audit-logged workplace.' :
            'Onboard universities, audit every action, and approve sensitive operations like de-anonymization with formal two-person review.'}
          </p>

          {/* Decorative big mono number */}
          <div className="mt-10 grid grid-cols-2 gap-6">
            <div>
              <div className="font-mono text-[40px] leading-none">{mode === 'uni' ? '612' : '4'}</div>
              <div className="smallcaps opacity-60 mt-2">{mode === 'uni' ? 'Open cases · DIU' : 'Tenants'}</div>
            </div>
            <div>
              <div className="font-mono text-[40px] leading-none">{mode === 'uni' ? '8,421' : '12.8k'}</div>
              <div className="smallcaps opacity-60 mt-2">{mode === 'uni' ? 'Active users' : 'Platform users'}</div>
            </div>
          </div>
        </div>

        <div className="text-[11px] opacity-60 flex items-center gap-2">
          <Icon name="shield-check" size={12} />
          <span>Authorized personnel only · All actions are audit-logged</span>
        </div>

        {/* decorative grid */}
        <div className="absolute inset-0 dot-grid opacity-[0.08]" />
      </div>

      {/* Right form */}
      <div className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-[420px]">
          <button onClick={() => onGo('/')} className="inline-flex items-center gap-1.5 text-[12px] text-[var(--muted)] hover:text-[var(--ink)] mb-8">
            <Icon name="arrow-left" size={12} />
            <span>Back to entry</span>
          </button>

          <span className="smallcaps text-[var(--muted)]">{mode === 'uni' ? 'Sign in' : 'Operator sign in'}</span>
          <h2 className="font-serif text-[30px] leading-tight text-[var(--navy)] mt-1.5" style={{ fontWeight: 500 }}>
            Welcome back.
            <span className="font-bn text-[16px] text-[var(--muted)] ml-2 align-middle" style={{ fontWeight: 500 }}>{bn}</span>
          </h2>
          <p className="mt-1 text-[13px] text-[var(--graphite)]">{subtitle}</p>

          {error && (
            <div className="mt-4 px-3 py-2.5 rounded-sm text-[13px] flex items-start gap-2" style={{ background: 'var(--ember-tint)', color: 'var(--ember)' }}>
              <Icon name="circle-alert" size={14} className="mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {step === 'credentials' &&
          <form className="mt-7 space-y-4" onSubmit={handleCredentials}>
              <Field label="University email" hint={mode === 'uni' ? 'Must end with @diu.edu.bd' : 'Platform team credentials'}>
                <input value={email} onChange={(e) => setEmail(e.target.value)} type="email" required className="w-full px-3 py-2.5 hair border rounded-sm bg-white text-[14px]" />
              </Field>
              <Field label="Password" right={<a className="text-[12px] text-[var(--muted)] hover:underline" href="#">Forgot password?</a>}>
                <input type="password" value={pwd} onChange={(e) => setPwd(e.target.value)} required className="w-full px-3 py-2.5 hair border rounded-sm bg-white text-[14px]" />
              </Field>
              <PrimaryButton as="button" type="submit" mode={mode === 'uni' ? 'sage' : 'ember'} className="w-full justify-center mt-2" icon="arrow-right" disabled={loading}>
                {loading ? 'Signing in…' : 'Continue'}
              </PrimaryButton>
              <p className="text-[11px] text-[var(--muted)] text-center">
                {mode === 'sup' ? 'MFA is mandatory · All super admin actions are permanently audit-logged.' : 'You will be asked for an MFA code next.'}
              </p>
            </form>
          }

          {step === 'mfa' &&
          <form className="mt-7 space-y-4" onSubmit={handleMFA}>
              <AuditNote tone={mode === 'sup' ? 'red' : 'gold'} icon="shield-check">
                Enter the 6-digit code from your authenticator. {mode === 'sup' && 'Super admin sessions are limited to 4 hours.'}
              </AuditNote>
              <Field label="Authenticator code">
                <input value={code} onChange={(e) => setCode(e.target.value)} maxLength={6} placeholder="123 456" className="w-full px-3 py-2.5 hair border rounded-sm bg-white text-[18px] font-mono tracking-[0.4em] text-center" />
              </Field>
              <PrimaryButton as="button" type="submit" mode={mode === 'uni' ? 'sage' : 'ember'} className="w-full justify-center" icon="log-in" disabled={loading}>
                {loading ? 'Verifying…' : 'Sign in'}
              </PrimaryButton>
              <button type="button" onClick={() => setStep('credentials')} className="w-full text-[12px] text-[var(--muted)] hover:text-[var(--ink)]">← Back to credentials</button>
            </form>
          }

          <div className="mt-10 pt-6 hair-t text-[11px] text-[var(--muted)] flex items-center justify-between">
            <span>© 2026 Team AiVion</span>
            <a href="#" className="hover:text-[var(--ink)]">Privacy</a>
          </div>
        </div>
      </div>
    </div>);

}

function Field({ label, children, hint, right }) {
  return (
    <label className="block">
      <div className="flex items-center justify-between mb-1.5">
        <span className="smallcaps text-[var(--muted)]">{label}</span>
        {right}
      </div>
      {children}
      {hint && <div className="mt-1 text-[11px] text-[var(--muted)]">{hint}</div>}
    </label>);

}

Object.assign(window, { EntrySwitcher, LoginScreen, Field });