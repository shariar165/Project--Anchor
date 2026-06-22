// Profile screen for both University Admin and Super Admin.
// Reads the signed-in user from /auth/me (self-healing the stored user), shows
// identity, the Super-Admin-assigned approval-chain position, security state, and
// account metadata. Name/phone edits persist via PATCH /auth/me.
var { useState, useEffect, useCallback, useRef, useMemo } = React;

// Approval-chain positions a Super Admin can assign (mirrors STAFF_POSITIONS in the backend).
const POSITION_LABELS = {
  mentor: 'Mentor',
  department_head: 'Department Head',
  dean: 'Dean',
  accounts: 'Accounts Officer',
};

const ROLE_LABELS = {
  super_admin: 'Super Admin',
  admin: 'Administrator',
  moderator: 'Moderator',
  user: 'User',
  student: 'Student',
};

// What each assigned position means in the application approval chain
// (source of truth: services/api/app/services/application_svc.py _NEXT_LEVEL).
const CHAIN_INFO = {
  mentor: {
    stage: 'Stage 1 · Mentor',
    desc: 'You are the first reviewer for applications assigned to you. Approving forwards them to the Dean.',
    next: 'Dean',
  },
  department_head: {
    stage: 'Department stage · Department Head',
    desc: 'You review applications at the department stage. Approving forwards them to the Dean.',
    next: 'Dean',
  },
  dean: {
    stage: 'Stage 2 · Dean',
    desc: 'You review applications escalated from mentors and department heads. Approving forwards them to Accounts.',
    next: 'Accounts',
  },
  accounts: {
    stage: 'Stage 3 · Accounts',
    desc: 'You give final clearance. Approving completes the application — there is no further stage.',
    next: '— (final stage)',
  },
};

function fmtDateTime(s) {
  if (!s) return '—';
  try {
    return new Date(s).toLocaleString('en-GB', {
      day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  } catch (e) { return String(s); }
}

function initialsOf(name) {
  if (!name) return '—';
  return name.split(' ').filter(Boolean).map(w => w[0]).join('').slice(0, 2).toUpperCase();
}

// Read-only label/value row.
function InfoRow({ label, children, mono = false }) {
  return (
    <div className="hair-b border-b last:border-b-0 py-3 flex items-start gap-6">
      <div className="smallcaps text-[var(--muted)] w-[180px] shrink-0 pt-0.5">{label}</div>
      <div className={`flex-1 min-w-0 text-[13.5px] text-[var(--ink)] ${mono ? 'font-mono text-[12.5px]' : ''}`}>{children}</div>
    </div>
  );
}

function ProfileScreen({ mode = 'uni', onGo }) {
  const accent = mode === 'sup' ? 'ember' : 'sage';
  const accentVar = mode === 'sup' ? 'var(--ember)' : 'var(--sage)';

  const [user, setUser] = useState(() => AnchorAPI.getStoredUser());
  const [loadErr, setLoadErr] = useState('');
  const [fullName, setFullName] = useState((user && user.full_name) || '');
  const [phone, setPhone] = useState((user && user.phone) || '');
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');
  const [saveErr, setSaveErr] = useState('');

  // Re-fetch /auth/me on mount: keeps the stored user fresh (older logins predate
  // staff_position / tenant_name) and guarantees the assigned role renders immediately.
  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const fresh = await AnchorAPI.apiGet('/auth/me');
        if (!alive) return;
        const merged = { ...fresh, portal: mode };
        AnchorAPI.setStoredUser(merged);
        setUser(merged);
        setFullName(fresh.full_name || '');
        setPhone(fresh.phone || '');
      } catch (e) {
        if (alive) setLoadErr(e.message || 'Could not load your profile');
      }
    })();
    return () => { alive = false; };
  }, [mode]);

  const positionLabel = user && user.staff_position ? POSITION_LABELS[user.staff_position] : null;
  const roleLabel = user ? (ROLE_LABELS[user.role] || user.role) : '';
  const badge = mode === 'sup'
    ? 'Super Admin · AiVion'
    : (positionLabel || roleLabel);

  const dirty = user && (
    (fullName.trim() && fullName.trim() !== user.full_name) ||
    (!user.phone_verified && phone.trim() && phone.trim() !== (user.phone || ''))
  );

  const save = useCallback(async () => {
    if (!user) return;
    setSaving(true); setSaveErr(''); setSaveMsg('');
    try {
      const body = {};
      if (fullName.trim() && fullName.trim() !== user.full_name) body.full_name = fullName.trim();
      if (!user.phone_verified && phone.trim() && phone.trim() !== (user.phone || '')) body.phone = phone.trim();
      if (Object.keys(body).length === 0) { setSaving(false); return; }
      await AnchorAPI.apiPatch('/auth/me', body);
      const fresh = await AnchorAPI.apiGet('/auth/me');
      const merged = { ...fresh, portal: mode };
      AnchorAPI.setStoredUser(merged);
      setUser(merged);
      setFullName(fresh.full_name || '');
      setPhone(fresh.phone || '');
      setSaveMsg('Profile updated.');
    } catch (e) {
      setSaveErr(e.message || 'Could not save changes');
    } finally {
      setSaving(false);
    }
  }, [user, fullName, phone, mode]);

  if (!user) {
    return (
      <>
        <PageHeader title="My profile" bn="আমার প্রোফাইল" accent={accent}
          description="Account, role, and security." />
        <Card>
          <p className="text-[13px] text-[var(--graphite)]">
            {loadErr || 'Loading your profile…'}
          </p>
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="My profile"
        bn="আমার প্রোফাইল"
        accent={accent}
        description={mode === 'uni'
          ? 'Your account, your assigned role on the approval chain, and your security status.'
          : 'Your platform operator account and security status.'}
      />

      {loadErr && (
        <div className="mb-4"><AuditNote tone="red" icon="circle-alert">{loadErr}</AuditNote></div>
      )}

      {/* Identity header */}
      <Card className="mb-5">
        <div className="flex items-center gap-4">
          <span className="w-16 h-16 rounded-full flex items-center justify-center text-white text-[22px] font-medium shrink-0"
            style={{ background: 'var(--navy)' }}>
            {initialsOf(user.full_name)}
          </span>
          <div className="min-w-0">
            <div className="font-serif text-[24px] leading-tight text-[var(--navy)]" style={{ fontWeight: 500 }}>
              {user.full_name}
            </div>
            <div className="text-[13px] text-[var(--muted)] mt-0.5">{user.email || user.phone || '—'}</div>
            <div className="flex items-center gap-2 mt-2 flex-wrap">
              <span className="inline-flex items-center gap-2 px-2.5 py-1 rounded-sm hair border bg-white">
                <span className="w-1.5 h-1.5 rounded-full" style={{ background: accentVar }} />
                <span className="smallcaps text-[var(--muted)]">{badge}</span>
              </span>
              {mode === 'uni' && positionLabel && (
                <Tag tone="navy">{roleLabel}</Tag>
              )}
              {user.tenant_name && <Tag tone={accent === 'ember' ? 'red' : 'sage'} icon="building-2">{user.tenant_name}</Tag>}
              {user.mfa_enabled
                ? <Tag tone="sage" icon="shield-check">MFA on</Tag>
                : <Tag tone="gold" icon="shield-alert">MFA off</Tag>}
            </div>
          </div>
        </div>
      </Card>

      {/* Personal information (editable) */}
      <Card className="mb-5">
        <SectionLabel>Personal information</SectionLabel>

        <div className="hair-b border-b py-3 flex items-start gap-6">
          <div className="smallcaps text-[var(--muted)] w-[180px] shrink-0 pt-2">Full name</div>
          <div className="flex-1 min-w-0">
            <input value={fullName} onChange={e => setFullName(e.target.value)}
              className="w-full max-w-[360px] px-3 py-2 hair border rounded-sm bg-white text-[14px]" />
          </div>
        </div>

        <div className="hair-b border-b py-3 flex items-start gap-6">
          <div className="smallcaps text-[var(--muted)] w-[180px] shrink-0 pt-2">Phone</div>
          <div className="flex-1 min-w-0">
            {user.phone_verified ? (
              <div className="flex items-center gap-2">
                <span className="font-mono text-[13px] text-[var(--ink)]">{user.phone || '—'}</span>
                <Tag tone="sage" icon="check">Verified</Tag>
              </div>
            ) : (
              <>
                <input value={phone} onChange={e => setPhone(e.target.value)} placeholder="01XXXXXXXXX"
                  className="w-full max-w-[360px] px-3 py-2 hair border rounded-sm bg-white font-mono text-[13px]" />
                <div className="mt-1 text-[11px] text-[var(--muted)]">Bangladesh format · 01[3–9] followed by 8 digits.</div>
              </>
            )}
          </div>
        </div>

        <InfoRow label="Email">
          <div className="flex items-center gap-2">
            <span>{user.email || '—'}</span>
            {user.email && (user.email_verified
              ? <Tag tone="sage" icon="check">Verified</Tag>
              : <Tag tone="gold">Unverified</Tag>)}
          </div>
        </InfoRow>
        <InfoRow label="Account role">{roleLabel}</InfoRow>
        {mode === 'uni' && (
          <InfoRow label="Assigned position">
            {positionLabel
              ? <Tag tone="navy">{positionLabel}</Tag>
              : <span className="text-[var(--muted)]">Not assigned</span>}
          </InfoRow>
        )}

        <div className="mt-4 pt-4 hair-t border-t flex items-center justify-between gap-3">
          <div className="text-[12px] min-h-[18px]">
            {saveErr && <span className="text-[var(--red)] inline-flex items-center gap-1.5"><Icon name="circle-alert" size={13} />{saveErr}</span>}
            {saveMsg && !saveErr && <span className="text-[var(--sage)] inline-flex items-center gap-1.5"><Icon name="check" size={13} />{saveMsg}</span>}
          </div>
          <PrimaryButton mode={accent} size="sm" icon={saving ? 'loader' : 'check'}
            onClick={save} disabled={saving || !dirty}>
            {saving ? 'Saving…' : 'Save changes'}
          </PrimaryButton>
        </div>
      </Card>

      {/* Role & permissions — University admin only */}
      {mode === 'uni' && (
        <Card className="mb-5">
          <SectionLabel>Role &amp; permissions</SectionLabel>
          {user.staff_position && CHAIN_INFO[user.staff_position] ? (
            <>
              <div className="flex items-center gap-2 mb-3">
                <Tag tone="navy" icon="git-merge">{CHAIN_INFO[user.staff_position].stage}</Tag>
                <span className="text-[12px] text-[var(--muted)]">Assigned by the Super Admin</span>
              </div>
              <p className="text-[13.5px] text-[var(--graphite)] leading-relaxed">
                {CHAIN_INFO[user.staff_position].desc}
              </p>
              <div className="mt-3">
                <InfoRow label="Forwards to">{CHAIN_INFO[user.staff_position].next}</InfoRow>
                <InfoRow label="Review queue">
                  <button onClick={() => onGo && onGo('/university/applications')}
                    className="text-[var(--sage)] hover:underline inline-flex items-center gap-1">
                    Open application review <Icon name="arrow-right" size={13} />
                  </button>
                </InfoRow>
              </div>
            </>
          ) : (
            <AuditNote tone="gold" icon="user-cog">
              The Super Admin has not yet assigned you an approval-chain position. Once a position
              (Mentor, Department Head, Dean, or Accounts) is assigned, your review responsibilities
              will appear here.
            </AuditNote>
          )}
        </Card>
      )}

      {/* Security & MFA */}
      <Card className="mb-5">
        <SectionLabel right={
          <GhostButton size="sm" icon="settings"
            onClick={() => onGo && onGo(mode === 'uni' ? '/university/settings' : '/super/settings')}>
            Security settings
          </GhostButton>
        }>Security &amp; MFA</SectionLabel>
        <InfoRow label="Multi-factor auth">
          {user.mfa_enabled
            ? <Tag tone="sage" icon="shield-check">Enabled · TOTP</Tag>
            : <Tag tone="gold" icon="shield-alert">Not enabled</Tag>}
        </InfoRow>
        <InfoRow label="Email verified">
          {user.email_verified ? <Tag tone="sage" icon="check">Yes</Tag> : <Tag tone="gold">No</Tag>}
        </InfoRow>
        <InfoRow label="Phone verified">
          {user.phone_verified ? <Tag tone="sage" icon="check">Yes</Tag> : <Tag tone="mist">No</Tag>}
        </InfoRow>
        <InfoRow label="Password">
          <div className="flex items-start gap-2">
            <Icon name="info" size={14} className="mt-0.5 text-[var(--muted)]" />
            <span className="text-[13px] text-[var(--graphite)]">
              Your sign-in credentials are managed in the main Anchor app. To change your password,
              use <span className="font-medium">Forgot password</span> on the Anchor app sign-in screen.
            </span>
          </div>
        </InfoRow>
      </Card>

      {/* Account metadata */}
      <Card>
        <SectionLabel>Account</SectionLabel>
        {mode === 'uni' && (
          <InfoRow label="University">{user.tenant_name || '—'}</InfoRow>
        )}
        <InfoRow label="User ID" mono>{user.id}</InfoRow>
        <InfoRow label="Last sign-in">{fmtDateTime(user.last_login_at)}</InfoRow>
        {typeof user.total_filings === 'number' && mode === 'uni' && (
          <InfoRow label="Filings submitted">{user.total_filings}</InfoRow>
        )}
      </Card>
    </>
  );
}

Object.assign(window, { ProfileScreen });
