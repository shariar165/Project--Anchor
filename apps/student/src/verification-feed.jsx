// verification-feed.jsx — Verification Feed (student/user + admin)
// Depends on: icons.jsx, app.jsx (useApp, Header), applications.jsx (apiFetch, getToken)
// Load order: after applications.jsx, before app.jsx

const VF_BASE = window.ANCHOR_API_URL || 'http://localhost:8000';

// Re-use apiFetch from applications.jsx (already global)
// If not available, define local version
const vfFetch = typeof apiFetch === 'function' ? apiFetch : async (path, opts = {}, _retry = true) => {
  const res = await fetch(VF_BASE + path, {
    ...opts,
    headers: { 'Authorization': 'Bearer ' + (localStorage.getItem('anchor_access_token') || ''), ...(opts.headers || {}) },
  });
  if (!res.ok) { let d = 'Request failed'; try { const j = await res.json(); d = j.detail || d; } catch {} throw new Error(d); }
  if (res.status === 204) return null;
  return res.json();
};

// ─── Constants ────────────────────────────────────────────────────────────────

const FEED_STATE_META = {
  live:              { label: 'Live',          color: 'var(--sage)',   bg: 'rgba(74,107,92,0.10)' },
  under_review:      { label: 'Under Review',  color: 'var(--gold)',   bg: 'rgba(184,137,58,0.12)' },
  pending_ai:        { label: 'Checking…',     color: 'var(--muted)',  bg: 'rgba(107,102,96,0.10)' },
  taken_down:        { label: 'Taken Down',    color: 'var(--red)',    bg: 'rgba(232,49,42,0.12)' },
  marked_fake:       { label: 'Marked Fake',   color: 'var(--ember)',  bg: 'rgba(196,69,54,0.12)' },
  deleted_by_author: { label: 'Deleted',       color: 'var(--muted)',  bg: 'rgba(107,102,96,0.10)' },
};

const CATEGORIES = [
  { k: 'incident',       label: 'Incident',       icon: '🚨' },
  { k: 'missing_person', label: 'Missing Person',  icon: '🔍' },
  { k: 'road',           label: 'Road',            icon: '🛣️' },
  { k: 'safety',         label: 'Safety',          icon: '⚠️' },
  { k: 'civic_event',    label: 'Civic Event',     icon: '📢' },
];

const VF_CAT_ART = {
  incident: 'protest', missing_person: 'building', road: 'road',
  safety: 'court', civic_event: 'building',
};

const TRUST_META = {
  none:   { label: 'Verified',       color: 'var(--muted)', icon: '👤' },
  bronze: { label: 'Trusted Bronze', color: '#CD7F32',       icon: '🛡️' },
  silver: { label: 'Trusted Silver', color: '#A8A9AD',       icon: '🛡️' },
  gold:   { label: 'Trusted Gold',   color: 'var(--gold)',   icon: '🛡️' },
};

// ─── Shared mini components ───────────────────────────────────────────────────

function FeedStatePill({ state }) {
  const m = FEED_STATE_META[state] || FEED_STATE_META.pending_ai;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      background: m.bg, color: m.color, border: `1px solid ${m.color}33`,
      borderRadius: 999, padding: '2px 8px', fontSize: 10, fontWeight: 600,
    }}>{m.label}</span>
  );
}

function TrustBadge({ tier }) {
  const m = TRUST_META[tier] || TRUST_META.none;
  if (tier === 'none') return null;
  return (
    <span style={{ fontSize: 10, color: m.color, fontWeight: 600 }}>
      {m.icon} {m.label}
    </span>
  );
}

function StepUpModal({ onDone, onCancel }) {
  const [pw, setPw] = React.useState('');
  const [err, setErr] = React.useState('');
  const [loading, setLoading] = React.useState(false);

  const submit = async () => {
    setLoading(true); setErr('');
    try {
      const res = await vfFetch('/auth/stepup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password: pw }),
      });
      localStorage.setItem('anchor_stepup_token', res.stepup_token);
      onDone(res.stepup_token);
    } catch (e) { setErr(e.message); }
    setLoading(false);
  };

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(11,29,53,0.7)', zIndex: 100,
      display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
    }}>
      <div style={{
        width: '100%', maxWidth: 402, background: 'var(--cream)', borderRadius: '20px 20px 0 0',
        padding: '28px 24px 40px',
      }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--navy)', marginBottom: 6 }}>
          Confirm your identity
        </div>
        <div style={{ fontSize: 13, color: 'var(--ink-2)', marginBottom: 18 }}>
          This action requires your password.
        </div>
        <input
          type="password" value={pw} onChange={e => setPw(e.target.value)}
          placeholder="Password"
          onKeyDown={e => e.key === 'Enter' && submit()}
          style={{
            width: '100%', padding: '12px 14px', borderRadius: 10, fontSize: 14,
            border: '1.5px solid var(--mist-2)', background: 'white', marginBottom: 12,
            boxSizing: 'border-box',
          }}
        />
        {err && <div style={{ color: 'var(--red)', fontSize: 12, marginBottom: 10 }}>{err}</div>}
        <div style={{ display: 'flex', gap: 10 }}>
          <button onClick={onCancel} className="btn btn-ghost" style={{ flex: 1 }}>Cancel</button>
          <button onClick={submit} disabled={loading || !pw} className="btn btn-primary" style={{ flex: 1 }}>
            {loading ? 'Verifying…' : 'Confirm'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Verification Feed Screen — newspaper layout ─────────────────────────────
// DEPRECATED: the `feed` and `news-feed` routes both now render FeedScreen
// (screens-2.jsx), which has the professional layout + inline Corroborate/Challenge
// and a campus/national edition toggle. This component is no longer routed to.

function VerificationFeedScreen() {
  const { go, back, mode, auth } = useApp();
  const canSeeCampus = mode === 'campus' && !!auth?.user?.tenant_id;
  const [scope, setScope] = React.useState(canSeeCampus ? 'campus' : 'national');
  const [tab, setTab]     = React.useState('latest'); // top | latest | trusted
  const [posts, setPosts] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError]     = React.useState('');
  const accent = mode === 'campus' ? 'var(--sage)' : 'var(--ember)';

  React.useEffect(() => { loadPosts(); }, [scope, tab]);

  async function loadPosts() {
    setLoading(true); setError('');
    try {
      const sort = tab === 'latest' ? 'recent' : 'corroborate';
      const data = await vfFetch(`/v1/feed?scope=${scope}&sort=${sort}&page=1&page_size=30`);
      let items = Array.isArray(data) ? data : (data?.items ?? []);
      if (tab === 'trusted') items = items.filter(p => p.admin_confirmed);
      setPosts(items);
    } catch (_) { setPosts([]); }
    setLoading(false);
  }

  const today = new Date().toLocaleDateString('en-GB', { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' });

  const displayPosts = tab === 'trusted' ? posts.filter(p => p.admin_confirmed) : posts;
  const issueNum = String(displayPosts[0]?.post_number || 1).padStart(3, '0');
  const hero = displayPosts[0] || null;
  const rest = displayPosts.slice(1);
  const editionLabel = scope === 'campus' ? 'Campus edition · Daffodil' : 'National edition · Bangladesh';

  return (
    <div style={{ background: 'var(--cream)', minHeight: '100%' }}>

      {/* ── Masthead ── */}
      <div style={{ padding: '12px 16px 0', borderBottom: '2px solid var(--navy)' }}>
        {/* Top row: back + title + issue */}
        <div style={{ display: 'flex', alignItems: 'baseline', marginBottom: 2 }}>
          <button onClick={back} style={{ background: 'none', border: 'none', padding: '0 10px 0 0', cursor: 'pointer', color: 'var(--navy)', fontSize: 18, lineHeight: 1 }}>←</button>
          <div style={{ flex: 1, fontFamily: 'var(--font-serif)', fontSize: 26, fontWeight: 700, color: 'var(--navy)', letterSpacing: '-0.5px', lineHeight: 1 }}>
            The Anchor <em>Verified</em>
          </div>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9.5, color: 'var(--muted)', textAlign: 'right', lineHeight: 1.4 }}>
            VOL. 1 · {issueNum}
          </div>
        </div>
        {/* Sub-row: edition + date + moderated */}
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: 'var(--muted)', marginBottom: 10, lineHeight: 1.5 }}>
          <span>{editionLabel} · {today}</span>
          <span style={{ whiteSpace: 'nowrap', marginLeft: 8 }}>Human-moderated</span>
        </div>
        {/* Scope toggles (campus users only) */}
        {canSeeCampus && (
          <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
            {[['national','National'],['campus','Campus · DIU']].map(([s,l]) => (
              <button key={s} onClick={() => setScope(s)} style={{
                fontSize: 10, padding: '2px 10px', borderRadius: 999, fontWeight: 600,
                background: scope === s ? 'var(--brand)' : 'transparent',
                color: scope === s ? 'white' : 'var(--muted)',
                border: `1px solid ${scope === s ? 'var(--navy)' : 'var(--mist)'}`,
                cursor: 'pointer',
              }}>{l}</button>
            ))}
          </div>
        )}
        {/* Tab bar */}
        <div style={{ display: 'flex', gap: 6, paddingBottom: 10 }}>
          {[['top','Top stories'],['latest','Latest'],['trusted','Trusted only']].map(([k,l]) => (
            <button key={k} onClick={() => setTab(k)} style={{
              fontSize: 12, padding: '6px 14px', borderRadius: 999,
              background: tab === k ? 'var(--brand)' : 'transparent',
              color: tab === k ? 'white' : 'var(--muted)',
              border: `1px solid ${tab === k ? 'var(--navy)' : 'var(--mist)'}`,
              fontWeight: tab === k ? 700 : 500, cursor: 'pointer',
            }}>{l}</button>
          ))}
        </div>
      </div>

      {/* ── Loading ── */}
      {loading && <div style={{ textAlign: 'center', padding: 40, color: 'var(--muted)', fontSize: 13 }}>Loading…</div>}

      {/* ── Empty state ── */}
      {!loading && displayPosts.length === 0 && (
        <div style={{ textAlign: 'center', padding: '48px 24px', color: 'var(--muted)', fontSize: 13, fontFamily: 'var(--font-sans)' }}>
          <div style={{ fontSize: 24, marginBottom: 10 }}>📰</div>
          No verified stories yet in this edition.
        </div>
      )}

      {/* ── Breaking strip ── */}
      {hero && (
        <div style={{ background: 'var(--brand)', padding: '7px 16px', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, fontWeight: 700, color: accent, letterSpacing: 1, textTransform: 'uppercase' }}>
            Anchor Verified · {scope === 'campus' ? 'Campus Edition' : 'National'}
          </span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'rgba(255,255,255,0.45)', marginLeft: 'auto', whiteSpace: 'nowrap' }}>
            {new Date(hero.created_at).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
      )}

      {/* ── Hero post ── */}
      {hero && (
        <div onClick={() => go('feed-post', { id: hero.id })} style={{ cursor: 'pointer', borderBottom: '1px solid var(--mist)' }}>
          {/* Hero illustration */}
          <div style={{ width: '100%', height: 210, position: 'relative', overflow: 'hidden', background: 'var(--brand)' }}>
            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <NewsArt variant={VF_CAT_ART[hero.category] || 'protest'}/>
            </div>
            <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, background: 'var(--bar-bg)', padding: '5px 14px', borderTop: '1px solid var(--mist)' }}>
              <span style={{ fontSize: 10, color: 'var(--muted)', fontStyle: 'italic' }}>
                <strong style={{ fontStyle: 'normal', color: 'var(--navy)' }}>Photo —</strong> community report, cross-checked against official sources
              </span>
            </div>
          </div>
          {/* Article text */}
          <div style={{ padding: '14px 16px 16px' }}>
            <div style={{ fontFamily: 'var(--font-serif)', fontSize: 12, fontStyle: 'italic', color: accent, marginBottom: 4 }}>
              {scope === 'campus' ? 'Campus' : 'National'} · {(hero.category || 'top_story').replace(/_/g, ' ')}:
            </div>
            <div style={{ fontFamily: 'var(--font-serif)', fontSize: 25, fontWeight: 700, color: 'var(--navy)', lineHeight: 1.15, marginBottom: 8, letterSpacing: '-0.3px' }}>
              {hero.title}
            </div>
            <div style={{ fontSize: 10.5, color: 'var(--muted)', marginBottom: 10, letterSpacing: 0.3 }}>
              by <strong style={{ color: 'var(--navy)', textTransform: 'uppercase', fontSize: 9.5 }}>Anchor Verifiers</strong>
            </div>
            {hero.body && (
              <div style={{ fontSize: 13.5, color: 'var(--ink)', lineHeight: 1.7, overflow: 'hidden' }}>
                <span style={{
                  float: 'left', fontFamily: 'var(--font-serif)', fontSize: 46,
                  fontWeight: 700, lineHeight: 0.82, marginRight: 5, marginTop: 7,
                  color: 'var(--navy)',
                }}>
                  {hero.body.charAt(0).toUpperCase()}
                </span>
                {hero.body.slice(1, 220)}{hero.body.length > 220 ? '…' : ''}
              </div>
            )}
            <div style={{ clear: 'both', marginTop: 12, paddingTop: 10, borderTop: '1px solid var(--mist)', display: 'flex', gap: 14, alignItems: 'center' }}>
              <span style={{ fontSize: 11, color: 'var(--sage)', fontWeight: 700 }}>✓ {hero.signal_counts?.corroborate || 0} corroborate</span>
              <span style={{ fontSize: 11, color: 'var(--ember)', fontWeight: 700 }}>✗ {hero.signal_counts?.challenge || 0} challenge</span>
              {hero.admin_confirmed && <span style={{ fontSize: 10, color: 'var(--gold)', fontWeight: 700, marginLeft: 'auto' }}>✓ Confirmed</span>}
            </div>
          </div>
        </div>
      )}

      {/* ── Secondary posts ── */}
      <div style={{ paddingBottom: 80 }}>
        {rest.map((p, i) => {
          const sc  = p.signal_counts || {};
          const cat = CATEGORIES.find(c => c.k === p.category) || CATEGORIES[0];
          return (
            <div key={p.id} onClick={() => go('feed-post', { id: p.id })} style={{
              padding: '14px 16px', borderBottom: '1px solid var(--mist)',
              cursor: 'pointer', display: 'flex', gap: 12, alignItems: 'flex-start',
            }}>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 9, color: 'var(--muted)', fontWeight: 700, letterSpacing: 0.9, marginBottom: 4, textTransform: 'uppercase' }}>
                  {cat.icon} {cat.label}
                  {p.admin_confirmed && <span style={{ color: 'var(--gold)', marginLeft: 6 }}>✓ Confirmed</span>}
                </div>
                <div style={{ fontFamily: 'var(--font-serif)', fontSize: 15, fontWeight: 600, color: 'var(--navy)', lineHeight: 1.3, marginBottom: 6 }}>
                  {p.title}
                </div>
                <div style={{ display: 'flex', gap: 10, fontSize: 10.5, alignItems: 'center' }}>
                  <span style={{ color: 'var(--sage)', fontWeight: 600 }}>✓ {sc.corroborate || 0}</span>
                  <span style={{ color: 'var(--ember)', fontWeight: 600 }}>✗ {sc.challenge || 0}</span>
                  <span style={{ color: 'var(--muted)', marginLeft: 'auto', fontFamily: 'var(--font-mono)', fontSize: 10 }}>
                    {new Date(p.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                  </span>
                </div>
              </div>
              <div style={{ width: 68, height: 68, borderRadius: 8, overflow: 'hidden', flexShrink: 0, background: 'var(--brand)', position: 'relative' }}>
                <NewsArt variant={VF_CAT_ART[p.category] || ['protest','traffic','court','road'][i % 4]}/>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Publish Screen ───────────────────────────────────────────────────────────

function PublishScreen() {
  const { go, back, replace, mode, auth } = useApp();
  // Campus scope is offered whenever the app is in Campus mode (DIU students).
  const canPublishCampus = mode === 'campus';
  const accent = mode === 'campus' ? 'var(--sage)' : 'var(--ember)';

  // The compose form is autosaved (anchor_draft_feed) so a half-written post survives
  // a hard reload — and keep-alive already preserves it across in-session navigation.
  // step + form are stored together; per-field setters keep the call sites unchanged.
  // Cleared on successful publish and on logout.
  const _defaultDraft = () => ({
    step: 0,
    form: {
      category: '', scope: mode === 'campus' ? 'campus' : 'national',
      title: '', body: '', tags: [], geo_lat: '', geo_lng: '', geo_address: '', attachmentIds: [],
    },
  });
  const _persistDraft = window.usePersistentState || ((k, init) => React.useState(init));
  const [draft, setDraft] = _persistDraft('anchor_draft_feed', _defaultDraft);
  const step = draft.step;
  const setStep = (v) => setDraft(d => ({ ...d, step: (typeof v === 'function' ? v(d.step) : v) }));
  const form = draft.form;
  const setForm = (v) => setDraft(d => ({ ...d, form: (typeof v === 'function' ? v(d.form) : v) }));
  const clearDraft = () => setDraft(_defaultDraft());
  const [tagInput, setTagInput] = React.useState('');
  const [uploading, setUploading] = React.useState(false);
  const [publishing, setPublishing] = React.useState(false);
  const [error, setError] = React.useState('');
  const [showStepUp, setShowStepUp] = React.useState(false);
  const [stepupToken, setStepupToken] = React.useState('');

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const addTag = () => {
    const t = tagInput.trim().replace(/^#/, '');
    if (t && form.tags.length < 5 && !form.tags.includes(t)) {
      set('tags', [...form.tags, t]);
    }
    setTagInput('');
  };

  const uploadFile = async (file) => {
    setUploading(true);
    try {
      const fd = new FormData();
      // Need a post_id — create a placeholder post first or use a temp UUID
      // For simplicity, upload without post_id association (attach after publish)
      // This is a simplified flow: attach after post creation
      setError('File upload requires publishing first. Files will be attached after.');
    } catch (e) { setError(e.message); }
    setUploading(false);
  };

  const doPublish = async (suToken) => {
    setPublishing(true); setError('');
    try {
      const payload = {
        scope: form.scope,
        category: form.category,
        title: form.title,
        body: form.body,
        tags: form.tags,
      };
      if (form.geo_lat) payload.geo_lat = parseFloat(form.geo_lat);
      if (form.geo_lng) payload.geo_lng = parseFloat(form.geo_lng);
      if (form.geo_address) payload.geo_address = form.geo_address;

      // Use raw fetch — NOT apiFetch — so we handle 401 ourselves without triggering
      // apiFetch's redirect-to-login behavior when a step-up token expires.
      const res = await fetch(VF_BASE + '/v1/feed', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ' + suToken,
        },
        body: JSON.stringify(payload),
      });

      if (res.status === 401) {
        localStorage.removeItem('anchor_stepup_token');
        setShowStepUp(true);
        setPublishing(false);
        return;
      }

      if (!res.ok) {
        let detail = 'Publish failed';
        try {
          const d = await res.json();
          detail = typeof d.detail === 'string' ? d.detail : (d.detail?.message || JSON.stringify(d.detail));
        } catch {}
        throw new Error(detail);
      }

      const data = await res.json();
      // Published — drop the saved draft so the (kept-alive) form resets to blank.
      clearDraft();
      // replace() instead of go() so the device Back button skips the publish
      // form (which would otherwise remount at step 0) and returns to the feed.
      replace('feed-post', { id: data.post_id });
    } catch (e) {
      setError(e.message);
    }
    setPublishing(false);
  };

  const handlePublish = async () => {
    const su = localStorage.getItem('anchor_stepup_token');
    if (!su) { setShowStepUp(true); return; }
    doPublish(su);
  };

  const steps = ['Category', 'Scope', 'Compose', 'Location', 'Media', 'Review'];

  return (
    <>
      <Header title={`Publish — ${steps[step]}`} back/>
      {showStepUp && (
        <StepUpModal
          onDone={t => { setStepupToken(t); setShowStepUp(false); doPublish(t); }}
          onCancel={() => setShowStepUp(false)}
        />
      )}

      {/* Step indicator */}
      <div style={{ display: 'flex', gap: 4, padding: '12px 20px' }}>
        {steps.map((_, i) => (
          <div key={i} style={{
            flex: 1, height: 3, borderRadius: 2,
            background: i <= step ? accent : 'var(--mist)',
          }}/>
        ))}
      </div>

      <div style={{ padding: '0 20px 100px', overflowY: 'auto', maxHeight: 'calc(100vh - 160px)' }}>
        {/* Step 0: Category */}
        {step === 0 && (
          <div>
            <div className="eyebrow" style={{ marginBottom: 16 }}>Choose a category</div>
            {CATEGORIES.map(c => (
              <button key={c.k} onClick={() => { set('category', c.k); setStep(1); }} style={{
                display: 'flex', alignItems: 'center', gap: 14, width: '100%',
                padding: '14px 16px', borderRadius: 12, marginBottom: 10,
                background: form.category === c.k ? `${accent}15` : 'var(--surface)',
                border: `1.5px solid ${form.category === c.k ? accent : 'var(--mist)'}`,
                textAlign: 'left',
              }}>
                <span style={{ fontSize: 24 }}>{c.icon}</span>
                <div>
                  <div style={{ fontWeight: 600, color: 'var(--navy)', fontSize: 14 }}>{c.label}</div>
                </div>
              </button>
            ))}
          </div>
        )}

        {/* Step 1: Scope */}
        {step === 1 && (
          <div>
            <div className="eyebrow" style={{ marginBottom: 16 }}>Choose scope</div>
            {[
              { k: 'national', label: 'National', desc: 'Visible to all users across Bangladesh' },
              ...(canPublishCampus ? [{ k: 'campus', label: 'Campus · DIU', desc: 'Visible only to DIU students' }] : []),
            ].map(s => (
              <button key={s.k} onClick={() => set('scope', s.k)} style={{
                display: 'block', width: '100%', padding: '14px 16px', borderRadius: 12,
                marginBottom: 10, textAlign: 'left',
                background: form.scope === s.k ? `${accent}15` : 'var(--surface)',
                border: `1.5px solid ${form.scope === s.k ? accent : 'var(--mist)'}`,
              }}>
                <div style={{ fontWeight: 600, color: 'var(--navy)', fontSize: 14 }}>{s.label}</div>
                <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 2 }}>{s.desc}</div>
              </button>
            ))}
          </div>
        )}

        {/* Step 2: Compose */}
        {step === 2 && (
          <div>
            <div className="eyebrow" style={{ marginBottom: 12 }}>Write your post</div>
            <div style={{ marginBottom: 4, fontSize: 12, color: 'var(--muted)', display: 'flex', justifyContent: 'space-between' }}>
              <span>Title</span><span>{form.title.length}/100</span>
            </div>
            <input value={form.title} onChange={e => set('title', e.target.value)}
              maxLength={100} placeholder="Brief, factual headline…"
              style={{
                width: '100%', padding: '12px 14px', borderRadius: 10, fontSize: 14,
                border: '1.5px solid var(--mist-2)', background: 'white', marginBottom: 14, boxSizing: 'border-box',
              }}
            />
            <div style={{ marginBottom: 4, fontSize: 12, color: 'var(--muted)', display: 'flex', justifyContent: 'space-between' }}>
              <span>Description</span><span>{form.body.length}/1000</span>
            </div>
            <textarea value={form.body} onChange={e => set('body', e.target.value)}
              maxLength={1000} rows={5} placeholder="What happened? Where? When? Who?"
              style={{
                width: '100%', padding: '12px 14px', borderRadius: 10, fontSize: 13,
                border: '1.5px solid var(--mist-2)', background: 'white', marginBottom: 14,
                boxSizing: 'border-box', resize: 'none', lineHeight: 1.6,
              }}
            />
            <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 6 }}>Tags (up to 5)</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 8 }}>
              {form.tags.map(t => (
                <span key={t} style={{
                  background: `${accent}15`, color: accent, borderRadius: 999,
                  padding: '3px 10px', fontSize: 12, fontWeight: 600,
                  display: 'flex', alignItems: 'center', gap: 6,
                }}>
                  #{t}
                  <span onClick={() => set('tags', form.tags.filter(x => x !== t))}
                    style={{ cursor: 'pointer', opacity: 0.6 }}>×</span>
                </span>
              ))}
            </div>
            {form.tags.length < 5 && (
              <div style={{ display: 'flex', gap: 8 }}>
                <input value={tagInput} onChange={e => setTagInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && addTag()}
                  placeholder="#tag" style={{
                    flex: 1, padding: '8px 12px', borderRadius: 8, fontSize: 13,
                    border: '1.5px solid var(--mist-2)', background: 'white',
                  }}
                />
                <button onClick={addTag} style={{
                  padding: '8px 14px', borderRadius: 8, background: accent,
                  color: 'white', fontWeight: 600, fontSize: 13, border: 'none',
                }}>Add</button>
              </div>
            )}
          </div>
        )}

        {/* Step 3: Location */}
        {step === 3 && (
          <div>
            <div className="eyebrow" style={{ marginBottom: 12 }}>Add location (optional)</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
              <div>
                <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>Latitude</div>
                <input type="number" step="any" value={form.geo_lat}
                  onChange={e => set('geo_lat', e.target.value)} placeholder="23.7104"
                  style={{ width: '100%', padding: '10px 12px', borderRadius: 8, fontSize: 13, border: '1.5px solid var(--mist-2)', background: 'white', boxSizing: 'border-box' }}
                />
              </div>
              <div>
                <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>Longitude</div>
                <input type="number" step="any" value={form.geo_lng}
                  onChange={e => set('geo_lng', e.target.value)} placeholder="90.4074"
                  style={{ width: '100%', padding: '10px 12px', borderRadius: 8, fontSize: 13, border: '1.5px solid var(--mist-2)', background: 'white', boxSizing: 'border-box' }}
                />
              </div>
            </div>
            <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>Address / Landmark</div>
            <input value={form.geo_address} onChange={e => set('geo_address', e.target.value)}
              placeholder="e.g. Mirpur 10 roundabout, Dhaka"
              style={{ width: '100%', padding: '10px 12px', borderRadius: 8, fontSize: 13, border: '1.5px solid var(--mist-2)', background: 'white', boxSizing: 'border-box' }}
            />
            {form.category === 'missing_person' && (
              <div style={{ marginTop: 14, padding: '10px 14px', borderRadius: 10, background: 'rgba(184,137,58,0.1)', border: '1px solid var(--gold)', fontSize: 12, color: 'var(--ink-2)', lineHeight: 1.5 }}>
                ⚠️ Precise location may expose a private address. Consider using a nearby landmark instead.
              </div>
            )}
          </div>
        )}

        {/* Step 4: Media */}
        {step === 4 && (
          <div>
            <div className="eyebrow" style={{ marginBottom: 12 }}>Attach media (optional)</div>
            <div style={{
              border: '2px dashed var(--mist-2)', borderRadius: 12, padding: '32px 20px',
              textAlign: 'center', color: 'var(--muted)', fontSize: 13,
            }}>
              <div style={{ fontSize: 28, marginBottom: 8 }}>📎</div>
              <div style={{ marginBottom: 4, fontWeight: 600 }}>Photos, videos, documents</div>
              <div style={{ fontSize: 11 }}>Max 5 files · 10 MB each</div>
              <div style={{ fontSize: 11, marginTop: 8, color: 'var(--muted)' }}>
                File upload will be available after publishing
              </div>
            </div>
          </div>
        )}

        {/* Step 5: Review & Publish */}
        {step === 5 && (
          <div>
            <div className="eyebrow" style={{ marginBottom: 14 }}>Review & publish</div>
            <div className="card" style={{ marginBottom: 12, padding: '14px 16px' }}>
              <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>
                {CATEGORIES.find(c => c.k === form.category)?.icon} {CATEGORIES.find(c => c.k === form.category)?.label} · {form.scope === 'campus' ? 'Campus' : 'National'}
              </div>
              <div className="serif" style={{ fontSize: 16, fontWeight: 600, color: 'var(--navy)', marginBottom: 6 }}>{form.title}</div>
              <div style={{ fontSize: 13, color: 'var(--ink-2)', lineHeight: 1.6 }}>{form.body}</div>
              {form.tags.length > 0 && (
                <div style={{ marginTop: 8, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                  {form.tags.map(t => (
                    <span key={t} style={{ fontSize: 11, color: accent, background: `${accent}12`, borderRadius: 999, padding: '2px 8px' }}>#{t}</span>
                  ))}
                </div>
              )}
              {form.geo_address && (
                <div style={{ marginTop: 8, fontSize: 12, color: 'var(--muted)' }}>📍 {form.geo_address}</div>
              )}
            </div>
            <div style={{
              padding: '12px 14px', borderRadius: 10, background: 'rgba(196,69,54,0.07)',
              border: '1px solid rgba(196,69,54,0.2)', fontSize: 12, color: 'var(--ink-2)', marginBottom: 16, lineHeight: 1.5,
            }}>
              ⚠️ Publishing false information may result in account restrictions per the Verification Feed policy.
            </div>
            {error && <div style={{ color: 'var(--red)', fontSize: 13, marginBottom: 10 }}>{error}</div>}
            <button onClick={handlePublish} disabled={publishing} className="btn btn-primary" style={{ width: '100%' }}>
              {publishing ? 'Publishing…' : 'Publish'}
            </button>
          </div>
        )}

        {/* Navigation buttons */}
        {step < 5 && (
          <div style={{ display: 'flex', gap: 10, marginTop: 24 }}>
            <button onClick={() => step > 0 ? setStep(s => s - 1) : back()} className="btn btn-ghost" style={{ flex: 1 }}>
              {step === 0 ? 'Cancel' : 'Back'}
            </button>
            {step > 0 && (
              <button onClick={() => setStep(s => s + 1)} className="btn btn-primary" style={{ flex: 2 }}
                disabled={
                  (step === 0 && !form.category) ||
                  (step === 2 && (form.title.length < 5 || form.body.length < 20))
                }>
                {step === 4 ? 'Review' : 'Continue'}
              </button>
            )}
          </div>
        )}
      </div>
    </>
  );
}

// ─── Post Detail Screen ───────────────────────────────────────────────────────

function PostDetailScreen({ params = {} }) {
  const { go, back, mode, auth } = useApp();
  const accent = mode === 'campus' ? 'var(--sage)' : 'var(--ember)';
  const [post, setPost] = React.useState(null);
  const [counts, setCounts] = React.useState({ corroborate: 0, challenge: 0, flags: 0, user_signal: null });
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');
  const [showFlag, setShowFlag] = React.useState(false);
  const [showStepUp, setShowStepUp] = React.useState(false);
  const [pendingEdit, setPendingEdit] = React.useState(false);
  const esRef = React.useRef(null);

  React.useEffect(() => {
    if (!params.id) return;
    loadPost();
    // SSE
    const es = new EventSource(`${VF_BASE}/v1/feed/${params.id}/stream`);
    es.onmessage = e => {
      try { const d = JSON.parse(e.data); setCounts(c => ({ ...c, ...d })); } catch {}
    };
    esRef.current = es;
    return () => es.close();
  }, [params.id]);

  async function loadPost() {
    setLoading(true);
    try {
      const data = await vfFetch(`/v1/feed/${params.id}`);
      setPost(data);
      if (data.signal_counts) setCounts(data.signal_counts);
    } catch (e) { setError(e.message); }
    setLoading(false);
  }

  async function signal(type) {
    try {
      const data = await vfFetch(`/v1/feed/${params.id}/${type}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}),
      });
      setCounts(data.counts);
    } catch (e) { setError(e.message); }
  }

  async function flagPost(reason) {
    try {
      await vfFetch(`/v1/feed/${params.id}/flag`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ flag_reason: reason }),
      });
      setShowFlag(false);
    } catch (e) { setError(e.message); }
  }

  if (loading) return <><Header title="Post" back/><div style={{ textAlign: 'center', padding: 60, color: 'var(--muted)' }}>Loading…</div></>;
  if (error && !post) return <><Header title="Post" back/><div style={{ textAlign: 'center', padding: 40, color: 'var(--red)' }}>{error}</div></>;
  if (!post) return null;

  const isOwner = auth.user && post.publisher_user_id && auth.user.id === post.publisher_user_id;
  const cat = CATEGORIES.find(c => c.k === post.category);
  const userSig = counts.user_signal;

  return (
    <>
      <Header title="Verification" back/>
      <div style={{ padding: '0 0 100px' }}>
        {/* Meta */}
        <div style={{ padding: '14px 20px 0' }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: 8 }}>
            {cat && <span style={{ fontSize: 11, color: 'var(--muted)' }}>{cat.icon} {cat.label}</span>}
            <FeedStatePill state={post.state} />
            {post.admin_confirmed && <span style={{ fontSize: 10, color: 'var(--gold)', fontWeight: 700 }}>✓ Admin-confirmed</span>}
            <span style={{ fontSize: 10, color: 'var(--muted)', marginLeft: 'auto', fontFamily: 'var(--font-mono)' }}>{post.post_number}</span>
          </div>
          <div className="serif" style={{ fontSize: 20, fontWeight: 700, color: 'var(--navy)', lineHeight: 1.35, marginBottom: 12 }}>
            {post.title}
          </div>
          <div style={{ fontSize: 14, color: 'var(--ink-2)', lineHeight: 1.7, marginBottom: 14 }}>
            {post.body}
          </div>
          {post.tags && post.tags.length > 0 && (
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginBottom: 12 }}>
              {post.tags.map(t => (
                <span key={t} style={{ fontSize: 11, color: accent, background: `${accent}12`, borderRadius: 999, padding: '2px 8px' }}>#{t}</span>
              ))}
            </div>
          )}
          {post.geo_address && (
            <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 12 }}>📍 {post.geo_address}</div>
          )}
        </div>

        <div style={{ height: 1, background: 'var(--mist)', margin: '0 20px 14px' }}/>

        {/* Signal counts */}
        <div style={{ padding: '0 20px', marginBottom: 14 }}>
          <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 8, fontWeight: 600 }}>COMMUNITY SIGNALS</div>
          <div style={{ display: 'flex', gap: 20 }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--sage)' }}>{counts.corroborate}</div>
              <div style={{ fontSize: 10, color: 'var(--muted)' }}>Corroborate</div>
            </div>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--ember)' }}>{counts.challenge}</div>
              <div style={{ fontSize: 10, color: 'var(--muted)' }}>Challenge</div>
            </div>
            {counts.flags > 0 && (
              <div style={{ textAlign: 'center' }}>
                <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--gold)' }}>{counts.flags}</div>
                <div style={{ fontSize: 10, color: 'var(--muted)' }}>Flags</div>
              </div>
            )}
          </div>
        </div>

        {/* Action buttons */}
        {!isOwner && (
          <div style={{ padding: '0 20px', display: 'flex', gap: 10, marginBottom: 16 }}>
            <button onClick={() => signal('corroborate')} style={{
              flex: 1, padding: '10px', borderRadius: 10, fontWeight: 700, fontSize: 13,
              background: userSig === 'corroborate' ? 'var(--sage)' : 'rgba(74,107,92,0.1)',
              color: userSig === 'corroborate' ? 'white' : 'var(--sage)',
              border: `1.5px solid ${userSig === 'corroborate' ? 'var(--sage)' : 'rgba(74,107,92,0.3)'}`,
            }}>✓ Corroborate</button>
            <button onClick={() => signal('challenge')} style={{
              flex: 1, padding: '10px', borderRadius: 10, fontWeight: 700, fontSize: 13,
              background: userSig === 'challenge' ? 'var(--ember)' : 'rgba(196,69,54,0.08)',
              color: userSig === 'challenge' ? 'white' : 'var(--ember)',
              border: `1.5px solid ${userSig === 'challenge' ? 'var(--ember)' : 'rgba(196,69,54,0.3)'}`,
            }}>✗ Challenge</button>
            <button onClick={() => setShowFlag(true)} style={{
              padding: '10px 14px', borderRadius: 10, fontWeight: 600, fontSize: 13,
              background: 'transparent', color: 'var(--muted)', border: '1.5px solid var(--mist-2)',
            }}>⋯</button>
          </div>
        )}

        {isOwner && post.state === 'live' && (
          <div style={{ padding: '0 20px', display: 'flex', gap: 10, marginBottom: 16 }}>
            <button onClick={() => go('feed-publish', { editId: post.id })} className="btn btn-ghost" style={{ flex: 1 }}>Edit</button>
          </div>
        )}

        {error && <div style={{ padding: '0 20px', color: 'var(--red)', fontSize: 12 }}>{error}</div>}

        {/* Flag sheet */}
        {showFlag && (
          <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 50, display: 'flex', alignItems: 'flex-end' }}>
            <div style={{ width: '100%', background: 'var(--cream)', borderRadius: '20px 20px 0 0', padding: '24px 20px 40px' }}>
              <div style={{ fontWeight: 700, fontSize: 16, color: 'var(--navy)', marginBottom: 14 }}>Flag for review</div>
              {['harassment','off_topic','wrong_category','illegal_content','spam','other'].map(r => (
                <button key={r} onClick={() => flagPost(r)} style={{
                  display: 'block', width: '100%', padding: '12px 16px', textAlign: 'left',
                  borderRadius: 10, marginBottom: 8, background: 'white', border: '1px solid var(--mist)',
                  fontSize: 14, color: 'var(--navy)',
                }}>{r.replace(/_/g, ' ')}</button>
              ))}
              <button onClick={() => setShowFlag(false)} className="btn btn-ghost" style={{ width: '100%', marginTop: 4 }}>Cancel</button>
            </div>
          </div>
        )}
      </div>
    </>
  );
}

// ─── Feed Profile Screen ──────────────────────────────────────────────────────

function FeedProfileScreen() {
  const { auth, mode } = useApp();
  const accent = mode === 'campus' ? 'var(--sage)' : 'var(--ember)';
  const [profile, setProfile] = React.useState(null);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => { load(); }, []);

  async function load() {
    try {
      const d = await vfFetch('/v1/feed/me/profile');
      setProfile(d);
    } catch {}
    setLoading(false);
  }

  const milestones = [5, 10, 15];
  const current = profile ? profile.confirmed_accurate_count : 0;
  const nextMilestone = milestones.find(m => m > current) || 15;
  const progress = Math.min((current / nextMilestone) * 100, 100);

  return (
    <>
      <Header title="Trust Profile" back/>
      <div style={{ padding: '20px 20px 80px' }}>
        {loading ? <div style={{ textAlign: 'center', padding: 40, color: 'var(--muted)' }}>Loading…</div> : profile && (
          <>
            <div className="card" style={{ padding: '20px 18px', marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 16 }}>
                <div style={{
                  width: 48, height: 48, borderRadius: '50%',
                  background: `${accent}20`, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 22,
                }}>
                  {TRUST_META[profile.trust_tier]?.icon || '👤'}
                </div>
                <div>
                  <div style={{ fontWeight: 700, color: 'var(--navy)', fontSize: 16 }}>
                    {auth.user?.name || 'You'}
                  </div>
                  <div style={{ fontSize: 12, color: TRUST_META[profile.trust_tier]?.color || 'var(--muted)', fontWeight: 600 }}>
                    {TRUST_META[profile.trust_tier]?.label || 'Verified User'}
                  </div>
                </div>
              </div>

              {/* Progress bar */}
              <div style={{ marginBottom: 14 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--muted)', marginBottom: 6 }}>
                  <span>{current} confirmed posts</span>
                  <span>{nextMilestone} for next badge</span>
                </div>
                <div style={{ height: 6, borderRadius: 3, background: 'var(--mist)', overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${progress}%`, background: accent, borderRadius: 3, transition: 'width 0.5s' }}/>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <div style={{ textAlign: 'center', padding: '12px', borderRadius: 10, background: 'rgba(74,107,92,0.08)' }}>
                  <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--sage)' }}>{profile.confirmed_accurate_count}</div>
                  <div style={{ fontSize: 11, color: 'var(--muted)' }}>Confirmed accurate</div>
                </div>
                <div style={{ textAlign: 'center', padding: '12px', borderRadius: 10, background: 'rgba(196,69,54,0.08)' }}>
                  <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--ember)' }}>{profile.confirmed_fake_count}</div>
                  <div style={{ fontSize: 11, color: 'var(--muted)' }}>Confirmed fake</div>
                </div>
              </div>
            </div>

            <div style={{ fontSize: 12, color: 'var(--muted)', lineHeight: 1.6, padding: '0 4px' }}>
              Trust badges are earned by publishing accurate posts that are confirmed by both the community and an admin moderator. Bronze at 5 · Silver at 10 · Gold at 15.
            </div>
          </>
        )}
      </div>
    </>
  );
}

// ─── Feed Admin Screen ────────────────────────────────────────────────────────

function FeedAdminScreen() {
  const { go, auth } = useApp();
  const [tab, setTab] = React.useState('flagged');
  const [posts, setPosts] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');

  const isAdmin = auth.user?.role === 'admin' || auth.user?.role === 'moderator';

  React.useEffect(() => {
    if (!isAdmin) go('home');
    else load();
  }, [tab]);

  async function load() {
    setLoading(true); setError('');
    try {
      const data = await vfFetch(`/v1/feed/admin/queue?tab=${tab}`);
      setPosts(data);
    } catch (e) { setError(e.message); }
    setLoading(false);
  }

  const TAB_LABELS = { flagged: '🔴 Flagged', pre_publish: '🟡 Pre-Publish', confirmation: '🟢 Confirmation' };

  return (
    <>
      <Header title="Moderation Queue" back/>
      <div className="tabbar">
        {Object.entries(TAB_LABELS).map(([k, l]) => (
          <button key={k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}
            style={{ fontSize: 12 }}>{l}</button>
        ))}
      </div>
      <div style={{ paddingBottom: 80 }}>
        {loading && <div style={{ textAlign: 'center', padding: 40, color: 'var(--muted)', fontSize: 13 }}>Loading…</div>}
        {error && <div style={{ textAlign: 'center', padding: 20, color: 'var(--red)', fontSize: 13 }}>{error}</div>}
        {!loading && posts.length === 0 && (
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--muted)', fontSize: 13 }}>Queue is empty.</div>
        )}
        {posts.map(p => (
          <div key={p.id} onClick={() => go('feed-moderate', { id: p.id })} className="card"
            style={{ margin: '0 16px 10px', padding: '14px 16px', cursor: 'pointer', borderRadius: 14 }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 6 }}>
              <FeedStatePill state={p.state}/>
              {p.flag_count > 0 && (
                <span style={{ fontSize: 10, color: 'var(--red)', fontWeight: 600 }}>⚑ {p.flag_count} flags</span>
              )}
              <TrustBadge tier={p.publisher_trust_tier}/>
            </div>
            <div className="serif" style={{ fontSize: 14, fontWeight: 600, color: 'var(--navy)', marginBottom: 4 }}>{p.title}</div>
            <div style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>{p.post_number}</div>
          </div>
        ))}
      </div>
    </>
  );
}

// ─── Feed Moderate Screen ─────────────────────────────────────────────────────

function FeedModerateScreen({ params = {} }) {
  const { go, back, auth } = useApp();
  const [data, setData] = React.useState(null);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');
  const [actionErr, setActionErr] = React.useState('');
  const [note, setNote] = React.useState('');
  const [pubNote, setPubNote] = React.useState('');
  const [showStepUp, setShowStepUp] = React.useState(false);
  const [pendingAction, setPendingAction] = React.useState(null);
  const [enabled, setEnabled] = React.useState({});

  React.useEffect(() => {
    if (params.id) load();
  }, [params.id]);

  async function load() {
    setLoading(true);
    try { setData(await vfFetch(`/v1/feed/admin/${params.id}`)); } catch (e) { setError(e.message); }
    setLoading(false);
  }

  // Anti-misclick: enable button after delay
  function armButton(key, delayMs) {
    setEnabled(e => ({ ...e, [key]: false }));
    setTimeout(() => setEnabled(e => ({ ...e, [key]: true })), delayMs);
  }

  React.useEffect(() => {
    armButton('confirm', 1000);
    armButton('mark_fake', 2000);
    armButton('take_down', 1500);
  }, [params.id]);

  async function doAction(action, token) {
    setActionErr('');
    const headers = {
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + (token || localStorage.getItem('anchor_stepup_token') || localStorage.getItem('anchor_access_token') || ''),
    };
    const body = { internal_note: note || undefined, public_note: pubNote || undefined };
    try {
      await vfFetch(`/v1/feed/admin/${params.id}/${action.replace('_', '-')}`, {
        method: 'POST', headers, body: JSON.stringify(body),
      });
      back();
    } catch (e) {
      if (e.message && (e.message.includes('401') || e.message.includes('Step-up'))) {
        setPendingAction(action);
        setShowStepUp(true);
      } else {
        setActionErr(e.message);
      }
    }
  }

  const requiresStepUp = ['confirm', 'mark_fake', 'take_down', 'restore'];
  const isOwner = data && auth.user && data.publisher_user_id === auth.user.id;

  if (loading) return <><Header title="Review" back/><div style={{ textAlign: 'center', padding: 60, color: 'var(--muted)' }}>Loading…</div></>;
  if (error) return <><Header title="Review" back/><div style={{ padding: 20, color: 'var(--red)', fontSize: 13 }}>{error}</div></>;
  if (!data) return null;

  const post = data;
  const cat = CATEGORIES.find(c => c.k === post.category);

  return (
    <>
      <Header title="Moderate Post" back/>
      {showStepUp && (
        <StepUpModal
          onDone={t => { setShowStepUp(false); if (pendingAction) doAction(pendingAction, t); }}
          onCancel={() => { setShowStepUp(false); setPendingAction(null); }}
        />
      )}
      <div style={{ padding: '16px 20px 100px', overflowY: 'auto' }}>
        {/* Post info */}
        <div className="card" style={{ padding: '14px 16px', marginBottom: 12 }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8, flexWrap: 'wrap' }}>
            {cat && <span style={{ fontSize: 11, color: 'var(--muted)' }}>{cat.icon} {cat.label}</span>}
            <FeedStatePill state={post.state}/>
            {post.admin_confirmed && <span style={{ fontSize: 10, color: 'var(--gold)', fontWeight: 700 }}>✓ Confirmed</span>}
          </div>
          <div className="serif" style={{ fontSize: 16, fontWeight: 700, color: 'var(--navy)', marginBottom: 8 }}>{post.title}</div>
          <div style={{ fontSize: 13, color: 'var(--ink-2)', lineHeight: 1.6, marginBottom: 8 }}>{post.body}</div>
          <div style={{ fontSize: 10, color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>{post.post_number}</div>
        </div>

        {/* Publisher trust */}
        {post.publisher_trust && (
          <div style={{ padding: '10px 14px', borderRadius: 10, background: 'var(--surface)', border: '1px solid var(--mist)', marginBottom: 12, fontSize: 12 }}>
            <span style={{ fontWeight: 600 }}>Publisher: </span>
            <TrustBadge tier={post.publisher_trust.trust_tier}/>
            <span style={{ color: 'var(--muted)', marginLeft: 8 }}>
              {post.publisher_trust.confirmed_accurate_count} accurate · {post.publisher_trust.confirmed_fake_count} fake
            </span>
          </div>
        )}

        {/* Signal counts */}
        {post.signal_counts && (
          <div style={{ display: 'flex', gap: 16, padding: '10px 14px', borderRadius: 10, background: 'var(--surface)', border: '1px solid var(--mist)', marginBottom: 12, fontSize: 13 }}>
            <span style={{ color: 'var(--sage)', fontWeight: 700 }}>✓ {post.signal_counts.corroborate}</span>
            <span style={{ color: 'var(--ember)', fontWeight: 700 }}>✗ {post.signal_counts.challenge}</span>
            {post.signal_counts.flags > 0 && <span style={{ color: 'var(--red)', fontWeight: 700 }}>⚑ {post.signal_counts.flags} flags</span>}
          </div>
        )}

        {/* Flags */}
        {post.flags && post.flags.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--muted)', marginBottom: 6 }}>FLAGS</div>
            {post.flags.map((f, i) => (
              <div key={i} style={{ fontSize: 12, color: 'var(--ink-2)', padding: '6px 10px', borderRadius: 8, background: 'rgba(196,69,54,0.06)', marginBottom: 4 }}>
                <span style={{ fontWeight: 600 }}>{f.flag_reason}</span>
                {f.note && <span style={{ color: 'var(--muted)' }}>: {f.note}</span>}
              </div>
            ))}
          </div>
        )}

        {/* Notes */}
        <div style={{ marginBottom: 12 }}>
          <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>Internal note (optional)</div>
          <textarea value={note} onChange={e => setNote(e.target.value)} rows={2}
            style={{ width: '100%', padding: '10px 12px', borderRadius: 10, fontSize: 13, border: '1.5px solid var(--mist-2)', background: 'white', boxSizing: 'border-box', resize: 'none' }}
          />
        </div>
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 11, color: 'var(--muted)', marginBottom: 4 }}>Public note (required for fake/takedown, min 30 chars)</div>
          <textarea value={pubNote} onChange={e => setPubNote(e.target.value)} rows={2}
            style={{ width: '100%', padding: '10px 12px', borderRadius: 10, fontSize: 13, border: '1.5px solid var(--mist-2)', background: 'white', boxSizing: 'border-box', resize: 'none' }}
          />
        </div>

        {actionErr && <div style={{ color: 'var(--red)', fontSize: 12, marginBottom: 10 }}>{actionErr}</div>}

        {/* Action buttons */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {!isOwner && (
            <button onClick={() => doAction('confirm')} disabled={!enabled.confirm} style={{
              padding: '13px', borderRadius: 12, fontWeight: 700, fontSize: 14,
              background: enabled.confirm ? 'var(--sage)' : 'var(--mist)', color: enabled.confirm ? 'white' : 'var(--muted)', border: 'none',
            }}>
              {enabled.confirm ? '✓ Confirm as Accurate' : 'Hold…'}
            </button>
          )}
          <button onClick={() => doAction('mark_fake')} disabled={!enabled.mark_fake || pubNote.length < 30} style={{
            padding: '13px', borderRadius: 12, fontWeight: 700, fontSize: 14,
            background: enabled.mark_fake && pubNote.length >= 30 ? 'var(--ember)' : 'var(--mist)',
            color: enabled.mark_fake && pubNote.length >= 30 ? 'white' : 'var(--muted)', border: 'none',
          }}>
            ✗ Mark as Fake
          </button>
          <button onClick={() => doAction('take_down')} disabled={!enabled.take_down || pubNote.length < 30} style={{
            padding: '13px', borderRadius: 12, fontWeight: 700, fontSize: 14,
            background: enabled.take_down && pubNote.length >= 30 ? 'var(--red)' : 'var(--mist)',
            color: enabled.take_down && pubNote.length >= 30 ? 'white' : 'var(--muted)', border: 'none',
          }}>
            ↓ Take Down
          </button>
          <div style={{ display: 'flex', gap: 10 }}>
            <button onClick={() => doAction('no_action')} className="btn btn-ghost" style={{ flex: 1 }}>No Action</button>
            <button onClick={() => doAction('defer')} className="btn btn-ghost" style={{ flex: 1 }}>Defer 24h</button>
          </div>
          {post.state === 'taken_down' || post.state === 'marked_fake' ? (
            <button onClick={() => doAction('restore')} style={{
              padding: '12px', borderRadius: 12, fontWeight: 600, fontSize: 13,
              background: 'transparent', color: 'var(--sage)', border: '1.5px solid var(--sage)',
            }}>↑ Restore Post</button>
          ) : null}
        </div>
      </div>
    </>
  );
}

// ─── Expose globals ───────────────────────────────────────────────────────────

window.VerificationFeedScreen = VerificationFeedScreen;
window.PublishScreen           = PublishScreen;
window.PostDetailScreen        = PostDetailScreen;
window.FeedProfileScreen       = FeedProfileScreen;
window.FeedAdminScreen         = FeedAdminScreen;
window.FeedModerateScreen      = FeedModerateScreen;
