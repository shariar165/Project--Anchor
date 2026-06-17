// filings.jsx — Complaint / Report / Grievance system (student-facing)
// Depends on: icons.jsx, app.jsx (useApp, Header)
// API base: http://localhost:8000

const { useState, useEffect, useRef, useCallback } = React;

const FILING_BASE = window.ANCHOR_API_URL || 'http://localhost:8000';

function getFilingToken() {
  return localStorage.getItem('anchor_access_token') || '';
}

async function filingApiFetch(path, opts = {}, _retry = true) {
  const res = await fetch(FILING_BASE + path, {
    ...opts,
    headers: {
      'Authorization': 'Bearer ' + getFilingToken(),
      ...(opts.headers || {}),
    },
  });
  if (res.status === 401 && _retry) {
    localStorage.removeItem('anchor_auth');
    localStorage.removeItem('anchor_access_token');
    localStorage.removeItem('anchor_refresh_token');
    window.location.reload();
    throw new Error('Session expired');
  }
  if (!res.ok) {
    let detail = 'Request failed';
    try { const d = await res.json(); detail = d.detail || detail; } catch {}
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

// ── State pill meta (using CSS variables) ────────────────────────────────────

const FILING_STATE_META = {
  draft:             { label: 'Draft',            color: 'var(--muted)',  bg: 'rgba(107,102,96,0.10)' },
  moderation_queue:  { label: 'Under review',     color: 'var(--gold)',   bg: 'rgba(184,137,58,0.12)' },
  routed:            { label: 'Routed',            color: 'var(--gold)',   bg: 'rgba(184,137,58,0.12)' },
  subject_notified:  { label: 'Notified',          color: 'var(--gold)',   bg: 'rgba(184,137,58,0.12)' },
  subject_responded: { label: 'Response received', color: 'var(--sage)',   bg: 'rgba(74,107,92,0.12)'  },
  under_review:      { label: 'In review',         color: 'var(--gold)',   bg: 'rgba(184,137,58,0.12)' },
  resolved:          { label: 'Resolved',          color: 'var(--sage)',   bg: 'rgba(74,107,92,0.12)'  },
  dismissed:         { label: 'Dismissed',         color: 'var(--muted)',  bg: 'rgba(107,102,96,0.10)' },
  withdrawn:         { label: 'Withdrawn',         color: 'var(--muted)',  bg: 'rgba(107,102,96,0.10)' },
  spam_rejected:     { label: 'Rejected',          color: 'var(--red)',    bg: 'rgba(232,49,42,0.10)'  },
};

function FilingStatePill({ state, size = 'sm' }) {
  const m = FILING_STATE_META[state] || FILING_STATE_META.draft;
  const fs = size === 'lg' ? 12 : 10.5;
  const px = size === 'lg' ? '5px 12px' : '3px 9px 4px';
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      background: m.bg, color: m.color, border: `1px solid ${m.color}33`,
      borderRadius: 999, padding: px, fontSize: fs, fontWeight: 600,
      fontFamily: 'var(--font-sans)',
    }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: m.color, flexShrink: 0 }}/>
      {m.label}
    </span>
  );
}

// ── Category meta ─────────────────────────────────────────────────────────────

const CATEGORY_META = {
  complaint: {
    label: 'Complaint',
    sub: 'Academic · teacher / course / exam',
    Icon: IconFile,
    color: 'var(--sage)',
  },
  grievance: {
    label: 'Grievance',
    sub: 'Department · resource / culture',
    Icon: IconGavel,
    color: 'var(--gold)',
  },
  report: {
    label: 'Report',
    sub: 'Hostel & classroom',
    Icon: IconBuilding,
    color: 'var(--ember)',
  },
};

// Template-specific structured fields
const FILING_TEMPLATE_FIELDS = {
  academic_rank1: [
    { k: 'course_code',   label: 'Course code',    placeholder: 'e.g. CSE-205' },
    { k: 'teacher_name',  label: 'Teacher name',   placeholder: 'e.g. Dr. Rahman' },
  ],
  academic_rank2: [
    { k: 'course_code',   label: 'Course code',    placeholder: 'e.g. CSE-205' },
    { k: 'teacher_name',  label: 'Teacher name',   placeholder: 'e.g. Dr. Rahman' },
    { k: 'incident_date', label: 'Date of incident', placeholder: 'e.g. 15 May 2026' },
    { k: 'location',      label: 'Location',        placeholder: 'e.g. Room 301, AB Building' },
  ],
  academic_rank3: [
    { k: 'incident_date', label: 'Date(s) of incident', placeholder: 'e.g. 15 May 2026' },
    { k: 'location',      label: 'Location',             placeholder: 'e.g. Room 301 / online' },
  ],
  dept_c1: [
    { k: 'issue_description', label: 'Issue description', placeholder: 'e.g. Projector in Room 301 broken since…' },
    { k: 'reported_date',     label: 'First reported on', placeholder: 'e.g. 1 May 2026' },
  ],
  dept_c3: [
    { k: 'period', label: 'Time period', placeholder: 'e.g. Spring 2026 semester' },
  ],
  classroom: [
    { k: 'room_number', label: 'Room number',  placeholder: 'e.g. AB-301' },
    { k: 'issue_type',  label: 'Issue type',   placeholder: 'e.g. projector, AC, seating…' },
  ],
  hall_tutor: [
    { k: 'hall_name',     label: 'Hall name',              placeholder: 'e.g. Bangabandhu Hall' },
    { k: 'tutor_name',    label: "Tutor's name (if known)", placeholder: 'Optional' },
    { k: 'incident_date', label: 'Date of incident',        placeholder: 'e.g. 15 May 2026' },
  ],
  hostel_incident: [
    { k: 'block_room',    label: 'Block / room',    placeholder: 'e.g. Block C, Room 207' },
    { k: 'incident_date', label: 'Date of incident', placeholder: 'e.g. 15 May 2026' },
  ],
  warden_misconduct: [
    { k: 'incident_date', label: 'Date of incident', placeholder: 'e.g. 15 May 2026' },
    { k: 'location',      label: 'Location',          placeholder: 'e.g. Warden office / hostel gate' },
  ],
};

// Routing target labels
const ROUTING_LABELS = {
  dept_head: 'Department Head',
  dean:      "Dean's Office",
  proctor:   'Proctor',
  provost:   'Provost',
  vc:        'Vice Chancellor',
};

// ── Shared styled input / textarea ────────────────────────────────────────────

function FField({ label, hint, children }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{
        fontSize: 10.5, fontWeight: 700, color: 'var(--muted)',
        textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 6,
        fontFamily: 'var(--font-sans)',
      }}>{label}</div>
      {children}
      {hint && <div style={{ fontSize: 10.5, color: 'var(--gold)', marginTop: 4 }}>💡 {hint}</div>}
    </div>
  );
}

function FInput({ value, onChange, placeholder }) {
  const [focused, setFocused] = useState(false);
  return (
    <input
      type="text"
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      onFocus={() => setFocused(true)}
      onBlur={() => setFocused(false)}
      style={{
        width: '100%', padding: '10px 12px', borderRadius: 10, boxSizing: 'border-box',
        border: `1px solid ${focused ? 'var(--sage)' : 'var(--mist)'}`,
        background: 'rgba(255,255,255,0.85)',
        boxShadow: focused ? '0 0 0 3px rgba(74,107,92,0.15)' : 'none',
        fontFamily: 'var(--font-sans)', fontSize: 13, color: 'var(--navy)', outline: 'none',
        transition: 'border-color 0.15s, box-shadow 0.15s',
      }}
    />
  );
}

function FTextarea({ value, onChange, placeholder, minHeight = 110 }) {
  const [focused, setFocused] = useState(false);
  return (
    <textarea
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      onFocus={() => setFocused(true)}
      onBlur={() => setFocused(false)}
      style={{
        width: '100%', minHeight, padding: '10px 12px', borderRadius: 10, boxSizing: 'border-box',
        border: `1px solid ${focused ? 'var(--sage)' : 'var(--mist)'}`,
        background: 'rgba(255,255,255,0.85)',
        boxShadow: focused ? '0 0 0 3px rgba(74,107,92,0.15)' : 'none',
        fontFamily: 'var(--font-sans)', fontSize: 13, color: 'var(--navy)', resize: 'vertical', outline: 'none',
        transition: 'border-color 0.15s, box-shadow 0.15s',
      }}
    />
  );
}

// ── Anonymity banner ──────────────────────────────────────────────────────────

function AnonymityBanner({ mode }) {
  if (mode === 'anonymous') return (
    <div style={{
      background: 'rgba(74,107,92,0.10)', border: '1px solid rgba(74,107,92,0.28)',
      borderRadius: 12, padding: '11px 14px', marginBottom: 16,
      display: 'flex', alignItems: 'flex-start', gap: 10,
    }}>
      <IconEyeOff size={15} stroke="var(--sage)" style={{ flexShrink: 0, marginTop: 1 }}/>
      <div style={{ fontSize: 12, color: 'var(--navy)', lineHeight: 1.55 }}>
        <strong style={{ color: 'var(--sage-2)' }}>This filing is anonymous.</strong> Your name, student ID, and contact are not visible to anyone reviewing this filing, including the subject.
      </div>
    </div>
  );
  if (mode === 'aggregated') return (
    <div style={{
      background: 'rgba(184,137,58,0.08)', border: '1px solid rgba(184,137,58,0.28)',
      borderRadius: 12, padding: '11px 14px', marginBottom: 16,
      display: 'flex', alignItems: 'flex-start', gap: 10,
    }}>
      <span style={{ fontSize: 14, flexShrink: 0 }}>📊</span>
      <div style={{ fontSize: 12, color: 'var(--navy)', lineHeight: 1.55 }}>
        Responses are <strong>aggregated anonymously</strong> at the department level.
      </div>
    </div>
  );
  return (
    <div style={{
      background: 'rgba(107,102,96,0.07)', border: '1px solid var(--mist)',
      borderRadius: 12, padding: '11px 14px', marginBottom: 16,
      display: 'flex', alignItems: 'flex-start', gap: 10,
    }}>
      <IconUser size={15} stroke="var(--muted)" style={{ flexShrink: 0, marginTop: 1 }}/>
      <div style={{ fontSize: 12, color: 'var(--ink-2)', lineHeight: 1.55 }}>
        This filing will be reviewed with your name visible to the reviewing admin. The subject will be told a filing exists but <strong>will not be told your identity</strong>.
      </div>
    </div>
  );
}

// ── Tracking code card ────────────────────────────────────────────────────────

function TrackingCodeCard({ code }) {
  const [copied, setCopied] = useState(false);
  const copy = () => {
    navigator.clipboard?.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };
  return (
    <div style={{
      background: 'rgba(74,107,92,0.08)', border: '1px solid rgba(74,107,92,0.30)',
      borderRadius: 14, padding: '16px 18px', marginTop: 16,
    }}>
      <div style={{
        fontSize: 10, fontWeight: 700, color: 'var(--sage-2)',
        letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 6,
      }}>
        Your anonymous tracking code
      </div>
      <div style={{
        fontFamily: 'var(--font-mono)', fontSize: 20, fontWeight: 700,
        color: 'var(--navy)', letterSpacing: '0.18em', marginBottom: 10,
      }}>
        {code}
      </div>
      <div style={{ fontSize: 11.5, color: 'var(--muted)', marginBottom: 12, lineHeight: 1.55 }}>
        ⚠ Save this code. We cannot recover anonymous filings if you lose it.
      </div>
      <button onClick={copy} className="btn btn-ghost" style={{ fontSize: 12, padding: '7px 16px' }}>
        {copied ? '✓ Copied' : 'Copy code'}
      </button>
    </div>
  );
}

// ── Step bar ──────────────────────────────────────────────────────────────────

function StepBar({ step, labels }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start', padding: '10px 20px 6px', gap: 0, flexShrink: 0,
    }}>
      {labels.map((label, i) => {
        const n = i + 1;
        const done = n < step;
        const active = n === step;
        return (
          <React.Fragment key={n}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: '0 0 auto' }}>
              <div style={{
                width: 28, height: 28, borderRadius: '50%',
                background: done ? 'var(--sage)' : active ? 'var(--navy)' : 'var(--mist)',
                color: done || active ? '#fff' : 'var(--muted)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: done ? 13 : 11, fontWeight: 700, fontFamily: 'var(--font-sans)',
                boxShadow: active ? '0 0 0 4px rgba(11,29,53,0.12)' : 'none',
                transition: 'background 0.2s',
              }}>
                {done ? <IconCheck size={12} sw={3}/> : n}
              </div>
              <div style={{
                fontSize: 9, marginTop: 4, textAlign: 'center', maxWidth: 40,
                color: active ? 'var(--navy)' : 'var(--muted)',
                fontFamily: 'var(--font-sans)', fontWeight: active ? 700 : 400,
                letterSpacing: '0.03em',
              }}>
                {label}
              </div>
            </div>
            {i < labels.length - 1 && (
              <div style={{
                flex: 1, height: 1.5,
                background: done ? 'var(--sage)' : 'var(--mist)',
                marginTop: 14, alignSelf: 'flex-start',
                transition: 'background 0.2s',
              }}/>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// FilingsListScreen
// ────────────────────────────────────────────────────────────────────────────

function FilingsListScreen({ params = {} }) {
  const { go } = useApp();
  const [tab, setTab] = useState(params.category || 'complaint');
  const [filings, setFilings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    filingApiFetch(`/v1/filings?category=${tab}&page=1`)
      .then(setFilings)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [tab]);

  const tabs = ['complaint', 'grievance', 'report'];

  return (
    <>
      <Header title="My Filings" subtitle="Complaints · Reports · Grievances" back/>

      {/* Tab bar — translucent pill style */}
      <div style={{ padding: '10px 20px 0' }}>
        <div style={{ display: 'flex', gap: 4, background: 'rgba(255,255,255,0.5)', borderRadius: 12, padding: 4 }}>
          {tabs.map(t => (
            <button key={t} onClick={() => setTab(t)} style={{
              flex: 1, padding: '8px 4px', borderRadius: 8, border: 'none', cursor: 'pointer',
              background: tab === t ? 'var(--navy)' : 'transparent',
              color: tab === t ? '#fff' : 'var(--muted)',
              fontFamily: 'var(--font-sans)', fontSize: 11.5, fontWeight: tab === t ? 600 : 400,
              transition: 'background 0.15s',
            }}>
              {CATEGORY_META[t].label}
            </button>
          ))}
        </div>
      </div>

      {/* List */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 20px 100px' }}>
        {loading && <div style={{ textAlign: 'center', padding: 40, color: 'var(--muted)', fontSize: 13 }}>Loading…</div>}
        {!loading && error && (
          <div style={{
            padding: 16, background: 'rgba(232,49,42,0.06)', borderRadius: 12,
            border: '1px solid rgba(232,49,42,0.2)', color: 'var(--red)', fontSize: 13, textAlign: 'center',
          }}>{error}</div>
        )}
        {!loading && !error && filings.length === 0 && (
          <div style={{ textAlign: 'center', paddingTop: 60 }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>
              {tab === 'complaint' ? '📋' : tab === 'grievance' ? '🏛' : '📝'}
            </div>
            <div className="serif" style={{ fontSize: 17, fontWeight: 500, color: 'var(--navy)', marginBottom: 6 }}>
              No {CATEGORY_META[tab].label.toLowerCase()}s yet
            </div>
            <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 24 }}>
              {CATEGORY_META[tab].sub}
            </div>
            <button onClick={() => go('new-filing', { category: tab })} className="btn btn-primary" style={{ margin: '0 auto' }}>
              + File a {CATEGORY_META[tab].label.toLowerCase()}
            </button>
          </div>
        )}
        {!loading && !error && filings.map(f => {
          const { Icon, color } = CATEGORY_META[f.category] || CATEGORY_META.complaint;
          const date = new Date(f.updated_at || f.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
          return (
            <button key={f.id} onClick={() => go('filing', { id: f.id })} style={{
              width: '100%', textAlign: 'left', background: 'rgba(255,255,255,0.7)',
              border: '1px solid var(--mist)', borderRadius: 14, padding: 14, marginBottom: 10,
              cursor: 'pointer', display: 'flex', alignItems: 'flex-start', gap: 12,
            }}>
              <div style={{
                width: 36, height: 36, borderRadius: 10, flexShrink: 0,
                background: `${color}15`, border: `1px solid ${color}30`,
                display: 'flex', alignItems: 'center', justifyContent: 'center', color,
              }}>
                <Icon size={16}/>
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span className="mono" style={{ fontSize: 10, color: 'var(--muted)' }}>
                    {f.filing_number || 'Draft'}
                  </span>
                  <FilingStatePill state={f.state}/>
                </div>
                <div className="serif" style={{ fontSize: 14, fontWeight: 500, color: 'var(--navy)', lineHeight: 1.25, marginBottom: 4 }}>
                  {f.template?.name || f.category}
                </div>
                <div style={{ fontSize: 11, color: 'var(--muted)' }}>
                  {f.state === 'draft' ? 'Not submitted' : f.state.replace(/_/g, ' ')}
                  {' · '}{date}
                </div>
              </div>
              <IconChevronRight size={14} stroke="var(--mist-2)"/>
            </button>
          );
        })}
      </div>

      {/* FAB */}
      <button onClick={() => go('new-filing', { category: tab })} style={{
        position: 'fixed', bottom: 108, right: 24, width: 52, height: 52,
        borderRadius: '50%', background: 'var(--navy)', color: '#fff',
        border: 'none', cursor: 'pointer', boxShadow: '0 4px 20px rgba(11,29,53,0.3)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 20,
      }}>
        <IconPlus size={22}/>
      </button>
    </>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// NewFilingScreen — 5-step wizard
// ────────────────────────────────────────────────────────────────────────────

const STEP_LABELS = ['Category', 'Type', 'Describe', 'Review', 'Submit'];

function NewFilingScreen({ params = {} }) {
  const { go, back } = useApp();
  const [step, setStep] = useState(1);
  const [category, setCategory] = useState(params.category || null);
  const [templates, setTemplates] = useState([]);
  const [template, setTemplate] = useState(null);
  const [showRank3Info, setShowRank3Info] = useState(false);
  const [fields, setFields] = useState({ body: '' });
  const [extraFields, setExtraFields] = useState({});
  const [filing, setFiling] = useState(null);
  const [trackingCode, setTrackingCode] = useState(null);
  const [attachments, setAttachments] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [submitted, setSubmitted] = useState(false);
  const fileRef = useRef(null);

  // Load templates when category selected
  useEffect(() => {
    if (!category) return;
    filingApiFetch('/v1/filings/templates')
      .then(all => setTemplates(all.filter(t => t.category === category)))
      .catch(() => setTemplates([]));
  }, [category]);

  // Create draft filing when template selected (Step 3)
  useEffect(() => {
    if (!template || filing) return;
    filingApiFetch('/v1/filings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ template_key: template.key, language: 'en' }),
    }).then(setFiling).catch(() => {});
  }, [template]);

  // Auto-save (debounced)
  const saveRef = useRef(null);
  const autoSave = useCallback((f, ex) => {
    clearTimeout(saveRef.current);
    saveRef.current = setTimeout(() => {
      if (!filing) return;
      filingApiFetch(`/v1/filings/${filing.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ body: f.body || '', field_values: { ...ex } }),
      }).catch(() => {});
    }, 1200);
  }, [filing]);

  const setField = (k, v) => {
    const nf = { ...fields, [k]: v };
    setFields(nf);
    autoSave(nf, extraFields);
  };
  const setExtra = (k, v) => {
    const ne = { ...extraFields, [k]: v };
    setExtraFields(ne);
    autoSave(fields, ne);
  };

  const handleFileSelect = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !filing) return;
    setUploading(true);
    const form = new FormData();
    form.append('file', file);
    try {
      const att = await filingApiFetch(`/v1/filings/${filing.id}/attachments`, { method: 'POST', body: form });
      setAttachments(a => [...a, att]);
    } catch (err) {
      alert('Upload failed: ' + err.message);
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const removeAttachment = async (attId) => {
    if (!filing) return;
    try {
      await filingApiFetch(`/v1/filings/${filing.id}/attachments/${attId}`, { method: 'DELETE' });
      setAttachments(a => a.filter(x => x.id !== attId));
    } catch {}
  };

  const handleSubmit = async () => {
    if (!filing) return;
    setSubmitting(true);
    setSubmitError(null);
    await filingApiFetch(`/v1/filings/${filing.id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ body: fields.body, field_values: { ...extraFields } }),
    }).catch(() => {});
    try {
      const result = await filingApiFetch(`/v1/filings/${filing.id}/submit`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
      });
      if (result.anonymous_tracking_code) setTrackingCode(result.anonymous_tracking_code);
      setFiling(result);
      setSubmitted(true);
    } catch (err) {
      setSubmitError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const bodyOk = fields.body.trim().length >= 50;

  // ── Step 1: Category ─────────────────────────────────────────────────────

  if (step === 1) return (
    <>
      <Header title="File" subtitle="Choose a category" back/>
      <StepBar step={step} labels={STEP_LABELS}/>
      <div style={{ padding: '16px 20px 100px' }}>
        <div className="eyebrow" style={{ marginBottom: 14 }}>What type of issue are you filing?</div>
        {Object.entries(CATEGORY_META).map(([key, meta]) => (
          <button key={key} onClick={() => { setCategory(key); setStep(2); }} style={{
            width: '100%', textAlign: 'left', background: 'rgba(255,255,255,0.7)',
            border: '1px solid var(--mist)', borderRadius: 14, padding: 16,
            marginBottom: 10, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 14,
          }}>
            <div style={{
              width: 44, height: 44, borderRadius: 12, flexShrink: 0,
              background: `${meta.color}15`, border: `1px solid ${meta.color}30`,
              display: 'flex', alignItems: 'center', justifyContent: 'center', color: meta.color,
            }}>
              <meta.Icon size={20}/>
            </div>
            <div style={{ flex: 1 }}>
              <div className="serif" style={{ fontSize: 16, fontWeight: 500, color: 'var(--navy)' }}>{meta.label}</div>
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 3 }}>{meta.sub}</div>
            </div>
            <IconChevronRight size={16} stroke="var(--mist-2)"/>
          </button>
        ))}
      </div>
    </>
  );

  // ── Step 2: Template ─────────────────────────────────────────────────────

  if (step === 2) {
    // Rank 3 explanation overlay
    if (showRank3Info) return (
      <>
        <Header title="Serious academic concern" back={false}/>
        <div style={{ padding: '24px 20px 100px' }}>
          <div style={{
            width: 52, height: 52, borderRadius: 14, background: 'rgba(74,107,92,0.12)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--sage)', marginBottom: 20,
          }}>
            <IconEyeOff size={24}/>
          </div>
          <div className="serif" style={{ fontSize: 22, fontWeight: 600, color: 'var(--navy)', marginBottom: 16, lineHeight: 1.25 }}>
            Your identity will be fully protected
          </div>
          <div style={{ fontSize: 13.5, color: 'var(--ink-2)', lineHeight: 1.7, marginBottom: 14 }}>
            Use this option for situations where you feel unsafe, threatened, or harassed in an academic setting.
          </div>
          <div style={{
            background: 'rgba(74,107,92,0.08)', border: '1px solid rgba(74,107,92,0.25)',
            borderRadius: 12, padding: '12px 16px', marginBottom: 14,
          }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--sage-2)', marginBottom: 6 }}>What happens next</div>
            {[
              'Goes directly to the Dean and Proctor — not your department',
              'Your identity is protected throughout and cannot be revealed',
              'The subject is never told who filed',
            ].map((t, i) => (
              <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 6 }}>
                <div style={{ width: 18, height: 18, borderRadius: '50%', background: 'var(--sage)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, fontSize: 10, fontWeight: 700 }}>✓</div>
                <div style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.5 }}>{t}</div>
              </div>
            ))}
          </div>
          <button onClick={() => { setTemplate(templates.find(t => t.key === 'academic_rank3')); setShowRank3Info(false); setStep(3); }}
                  className="btn btn-primary" style={{ width: '100%', marginBottom: 10 }}>
            Continue with this option
          </button>
          <button onClick={() => setShowRank3Info(false)} className="btn btn-ghost" style={{ width: '100%' }}>
            ← Pick a different type
          </button>
        </div>
      </>
    );

    return (
      <>
        <Header title={CATEGORY_META[category]?.label || 'Filing type'} back/>
        <StepBar step={step} labels={STEP_LABELS}/>
        <div style={{ padding: '14px 20px 100px' }}>
          <div className="eyebrow" style={{ marginBottom: 14 }}>Choose the filing type</div>
          {templates.length === 0 && (
            <div style={{ textAlign: 'center', padding: 32, color: 'var(--muted)', fontSize: 13 }}>Loading…</div>
          )}
          {templates.map(t => (
            <button key={t.key} onClick={() => {
              if (t.key === 'academic_rank3') { setShowRank3Info(true); return; }
              setTemplate(t); setStep(3);
            }} style={{
              width: '100%', textAlign: 'left', background: 'rgba(255,255,255,0.7)',
              border: '1px solid var(--mist)', borderRadius: 14, padding: 14, marginBottom: 10, cursor: 'pointer',
            }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                <div style={{ flex: 1 }}>
                  <div className="serif" style={{ fontSize: 14.5, fontWeight: 500, color: 'var(--navy)', marginBottom: 6 }}>
                    {t.name}
                  </div>
                  <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {t.anonymity_mode === 'anonymous' && (
                      <span style={{
                        fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 999,
                        background: 'rgba(74,107,92,0.12)', color: 'var(--sage-2)',
                        border: '1px solid rgba(74,107,92,0.2)', fontFamily: 'var(--font-sans)',
                      }}>🔒 Anonymous</span>
                    )}
                    {t.anonymity_mode === 'aggregated' && (
                      <span style={{
                        fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 999,
                        background: 'rgba(184,137,58,0.10)', color: 'var(--gold)',
                        border: '1px solid rgba(184,137,58,0.2)', fontFamily: 'var(--font-sans)',
                      }}>📊 Aggregated</span>
                    )}
                    <span style={{
                      fontSize: 10, padding: '2px 8px', borderRadius: 999,
                      background: 'var(--cream-2)', color: 'var(--muted)',
                      border: '1px solid var(--mist)', fontFamily: 'var(--font-sans)',
                    }}>→ {ROUTING_LABELS[t.routing_target] || t.routing_target}</span>
                  </div>
                </div>
                <IconChevronRight size={14} stroke="var(--mist-2)" style={{ flexShrink: 0, marginTop: 3 }}/>
              </div>
            </button>
          ))}
          <button onClick={() => setStep(1)} style={{
            background: 'none', border: 'none', color: 'var(--muted)',
            fontSize: 12.5, cursor: 'pointer', marginTop: 6, padding: '4px 0',
          }}>
            ← Back to categories
          </button>
        </div>
      </>
    );
  }

  // ── Step 3: Form ─────────────────────────────────────────────────────────

  if (step === 3) {
    const tplFields = FILING_TEMPLATE_FIELDS[template?.key] || [];
    const bodyPlaceholder = template?.key?.startsWith('academic')
      ? 'Describe what happened — include dates, places, and specific incidents. State facts only.'
      : template?.key?.startsWith('dept')
      ? 'Describe the issue clearly — when it started, how it affects students, what resolution you are requesting.'
      : 'Describe the situation — what happened, when, and what action you are asking for.';

    return (
      <>
        <Header title={template?.name} back/>
        <StepBar step={step} labels={STEP_LABELS}/>
        <div style={{ flex: 1, overflowY: 'auto', padding: '14px 20px', paddingBottom: 120 }}>
          <AnonymityBanner mode={template?.anonymity_mode}/>

          <FField label="What happened" hint={template?.proof_hint}>
            <FTextarea
              value={fields.body}
              onChange={e => setField('body', e.target.value)}
              placeholder={bodyPlaceholder}
              minHeight={120}
            />
            <div style={{
              fontSize: 11, color: bodyOk ? 'var(--sage)' : 'var(--muted)',
              textAlign: 'right', marginTop: 4,
            }}>
              {fields.body.trim().length} chars {bodyOk ? '✓ minimum met' : `— ${50 - fields.body.trim().length} more needed`}
            </div>
          </FField>

          {tplFields.map(f => (
            <FField key={f.k} label={f.label}>
              <FInput
                value={extraFields[f.k] || ''}
                onChange={e => setExtra(f.k, e.target.value)}
                placeholder={f.placeholder}
              />
            </FField>
          ))}
        </div>

        <div style={{
          padding: '12px 20px 24px', borderTop: '1px solid var(--mist)',
          background: 'var(--cream)', flexShrink: 0,
        }}>
          <button onClick={() => setStep(4)} disabled={!bodyOk} className="btn btn-primary" style={{ width: '100%', opacity: bodyOk ? 1 : 0.45 }}>
            Review before submitting →
          </button>
          <button onClick={() => setStep(2)} style={{
            background: 'none', border: 'none', color: 'var(--muted)',
            fontSize: 12, cursor: 'pointer', marginTop: 10, width: '100%',
          }}>
            ← Pick a different type
          </button>
        </div>
      </>
    );
  }

  // ── Step 4: Review ───────────────────────────────────────────────────────

  if (step === 4) {
    const tplFields = FILING_TEMPLATE_FIELDS[template?.key] || [];
    return (
      <>
        <Header title="Review" subtitle="Check before submitting" back/>
        <StepBar step={step} labels={STEP_LABELS}/>
        <div style={{ flex: 1, overflowY: 'auto', padding: '14px 20px', paddingBottom: 120 }}>
          <AnonymityBanner mode={template?.anonymity_mode}/>

          {/* Routing info */}
          <div style={{
            background: 'rgba(11,29,53,0.05)', border: '1px solid var(--mist)',
            borderRadius: 12, padding: '11px 16px', marginBottom: 16,
            display: 'flex', alignItems: 'center', gap: 10,
          }}>
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>Routed to</div>
            <div style={{ flex: 1, height: 1, background: 'var(--mist)' }}/>
            <div style={{
              fontSize: 13, fontWeight: 700, color: 'var(--navy)',
              background: 'rgba(11,29,53,0.07)', borderRadius: 8, padding: '4px 10px',
            }}>
              {ROUTING_LABELS[template?.routing_target] || template?.routing_target}
            </div>
          </div>

          {/* Document preview */}
          <div style={{
            background: 'rgba(255,255,255,0.85)', border: '1px solid var(--mist)',
            borderLeft: '3px solid var(--navy)', borderRadius: 12, padding: '16px 18px', marginBottom: 16,
          }}>
            <div style={{
              fontSize: 10, fontWeight: 700, color: 'var(--gold)',
              letterSpacing: '0.12em', textTransform: 'uppercase', marginBottom: 10,
              fontFamily: 'var(--font-sans)',
            }}>
              Your statement
            </div>
            <div style={{ fontSize: 13.5, color: 'var(--navy)', lineHeight: 1.7, whiteSpace: 'pre-wrap', fontFamily: 'var(--font-serif)' }}>
              {fields.body}
            </div>
            {tplFields.filter(f => extraFields[f.k]).map(f => (
              <div key={f.k} style={{ marginTop: 10, fontSize: 12, color: 'var(--ink-2)', borderTop: '1px solid var(--mist)', paddingTop: 8 }}>
                <strong style={{ color: 'var(--muted)', textTransform: 'uppercase', fontSize: 10, letterSpacing: '0.08em' }}>{f.label}</strong>
                <div style={{ marginTop: 2, fontSize: 13 }}>{extraFields[f.k]}</div>
              </div>
            ))}
          </div>

          {/* Attachments */}
          {attachments.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <div className="eyebrow" style={{ marginBottom: 8 }}>Proof attached</div>
              {attachments.map(a => (
                <div key={a.id} style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  background: 'rgba(74,107,92,0.08)', borderRadius: 8, padding: '8px 12px', marginBottom: 6,
                }}>
                  <span style={{ fontSize: 13 }}>📎</span>
                  <span style={{ flex: 1, fontSize: 12, color: 'var(--navy)' }}>{a.original_filename}</span>
                  <button onClick={() => removeAttachment(a.id)} style={{
                    background: 'none', border: 'none', cursor: 'pointer', color: 'var(--muted)', fontSize: 14, lineHeight: 1,
                  }}>×</button>
                </div>
              ))}
            </div>
          )}

          {/* Attach proof */}
          <input ref={fileRef} type="file" accept=".pdf,.jpg,.jpeg,.png,.docx" onChange={handleFileSelect} style={{ display: 'none' }}/>
          <button onClick={() => fileRef.current?.click()} disabled={uploading || attachments.length >= 5}
                  className="btn btn-ghost" style={{ fontSize: 12.5, width: '100%', marginBottom: 6 }}>
            {uploading ? 'Uploading…' : `+ Attach proof ${attachments.length > 0 ? `(${attachments.length}/5)` : '(optional)'}`}
          </button>
        </div>

        <div style={{ padding: '12px 20px 24px', borderTop: '1px solid var(--mist)', background: 'var(--cream)', flexShrink: 0 }}>
          <button onClick={() => setStep(5)} className="btn btn-primary" style={{ width: '100%', marginBottom: 8 }}>
            Confirm & submit →
          </button>
          <button onClick={() => setStep(3)} style={{
            background: 'none', border: 'none', color: 'var(--muted)', fontSize: 12, cursor: 'pointer', width: '100%',
          }}>
            ← Edit my statement
          </button>
        </div>
      </>
    );
  }

  // ── Step 5: Confirm / success ─────────────────────────────────────────────

  if (submitted) return (
    <>
      <Header title="Filed" back={false}/>
      <div style={{ padding: '32px 20px 100px' }}>
        <div style={{ textAlign: 'center', marginBottom: 28 }}>
          <div style={{
            width: 64, height: 64, borderRadius: 18, background: 'rgba(74,107,92,0.12)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 18px', color: 'var(--sage)',
          }}>
            <IconCheck size={30} sw={2.5}/>
          </div>
          <div className="serif" style={{ fontSize: 22, fontWeight: 600, color: 'var(--navy)', marginBottom: 8 }}>
            {template?.name} submitted
          </div>
          <div className="mono" style={{ fontSize: 12, color: 'var(--muted)' }}>
            {filing?.filing_number}
          </div>
        </div>

        {trackingCode && <TrackingCodeCard code={trackingCode}/>}

        {!trackingCode && (
          <div style={{
            background: 'rgba(74,107,92,0.08)', borderRadius: 12, padding: '14px 16px',
            textAlign: 'center', fontSize: 13, color: 'var(--ink-2)', marginTop: 8,
          }}>
            Track this filing in <strong>My Filings</strong> or the <strong>Cases</strong> tab.
          </div>
        )}

        <div style={{ marginTop: 24 }}>
          <button onClick={() => go('filing', { id: filing?.id })} className="btn btn-primary" style={{ width: '100%', marginBottom: 10 }}>
            View filing status
          </button>
          <button onClick={() => go('cases')} className="btn btn-ghost" style={{ width: '100%', marginBottom: 10 }}>
            View in Active Cases
          </button>
          <button onClick={() => go('filings')} style={{
            background: 'none', border: 'none', color: 'var(--muted)', fontSize: 12, cursor: 'pointer', width: '100%',
          }}>
            Back to My Filings
          </button>
        </div>
      </div>
    </>
  );

  // Submitting confirmation screen (step 5)
  return (
    <>
      <Header title="Submit" back={false}/>
      <StepBar step={step} labels={STEP_LABELS}/>
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px 20px', paddingBottom: 120 }}>
        {template?.requires_stepup && (
          <div style={{
            background: 'rgba(196,69,54,0.07)', border: '1px solid rgba(196,69,54,0.22)',
            borderRadius: 12, padding: '12px 16px', marginBottom: 20,
            fontSize: 12.5, color: 'var(--ember-2)', lineHeight: 1.6,
          }}>
            <strong>⚠ High-stakes filing.</strong> This routes directly to {
              template?.routing_target === 'dean' ? 'the Dean and Proctor' :
              template?.routing_target === 'provost' ? 'the Provost' : 'senior administration'
            }. Please confirm you intend to submit.
          </div>
        )}

        <div style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid var(--mist)', borderRadius: 12, padding: '14px 16px', marginBottom: 14 }}>
          <div style={{ fontSize: 10.5, color: 'var(--muted)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.1em' }}>Filing type</div>
          <div className="serif" style={{ fontSize: 15, fontWeight: 500, color: 'var(--navy)' }}>{template?.name}</div>
          <div style={{ fontSize: 11.5, color: 'var(--muted)', marginTop: 4 }}>
            → {ROUTING_LABELS[template?.routing_target] || template?.routing_target}
          </div>
        </div>

        {template?.anonymity_mode === 'anonymous' && (
          <div style={{
            fontSize: 12.5, color: 'var(--sage-2)', background: 'rgba(74,107,92,0.08)',
            borderRadius: 10, padding: '11px 14px', marginBottom: 16, lineHeight: 1.55,
          }}>
            🔒 After submitting you will receive a <strong>tracking code</strong>. Save it — it's the only way to check this anonymous filing's status.
          </div>
        )}

        {submitError && (
          <div style={{
            color: 'var(--red)', fontSize: 13, background: 'rgba(232,49,42,0.07)',
            borderRadius: 10, padding: '10px 14px', marginBottom: 16, border: '1px solid rgba(232,49,42,0.2)',
          }}>
            {submitError}
          </div>
        )}
      </div>

      <div style={{ padding: '12px 20px 24px', borderTop: '1px solid var(--mist)', background: 'var(--cream)', flexShrink: 0 }}>
        <button onClick={handleSubmit} disabled={submitting} className="btn btn-primary" style={{ width: '100%', marginBottom: 8 }}>
          {submitting ? 'Submitting…' : 'Submit filing'}
        </button>
        <button onClick={() => setStep(4)} disabled={submitting} style={{
          background: 'none', border: 'none', color: 'var(--muted)', fontSize: 12, cursor: 'pointer', width: '100%',
        }}>
          ← Back to review
        </button>
      </div>
    </>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// FilingDetailScreen — tracking & timeline
// ────────────────────────────────────────────────────────────────────────────

const TIMELINE_STEPS_ORDER = ['submitted', 'routed', 'subject_notified', 'subject_responded', 'resolved'];

const TIMELINE_STEP_LABELS = {
  submitted: 'Filed', routed: 'Routed', subject_notified: 'Notified',
  subject_responded: 'Response', resolved: 'Resolved',
};

function FilingDetailScreen({ params = {} }) {
  const { go, back } = useApp();
  const [filing, setFiling] = useState(null);
  const [timeline, setTimeline] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [withdrawing, setWithdrawing] = useState(false);

  const filingId = params.id;

  useEffect(() => {
    if (!filingId) return;
    setLoading(true);
    Promise.all([
      filingApiFetch(`/v1/filings/${filingId}`),
      filingApiFetch(`/v1/filings/${filingId}/timeline`),
    ])
      .then(([f, tl]) => { setFiling(f); setTimeline(tl); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [filingId]);

  const handleWithdraw = async () => {
    if (!window.confirm('Withdraw this filing? This cannot be undone once an admin acts on it.')) return;
    setWithdrawing(true);
    try {
      const result = await filingApiFetch(`/v1/filings/${filingId}/withdraw`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
      });
      setFiling(result);
    } catch (err) {
      alert('Could not withdraw: ' + err.message);
    } finally {
      setWithdrawing(false);
    }
  };

  if (loading) return (
    <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--cream)' }}>
      <div style={{ color: 'var(--muted)', fontSize: 13 }}>Loading…</div>
    </div>
  );

  if (error || !filing) return (
    <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--cream)', flexDirection: 'column', gap: 14 }}>
      <div style={{ color: 'var(--red)', fontSize: 13 }}>{error || 'Filing not found'}</div>
      <button onClick={back} className="btn btn-ghost" style={{ fontSize: 12 }}>Go back</button>
    </div>
  );

  const isAnonymous = filing.template?.anonymity_mode === 'anonymous';
  const canWithdraw = !filing.reviews?.length && ['draft', 'moderation_queue', 'routed'].includes(filing.state);

  // Compute progress step index
  const terminalState = ['resolved', 'dismissed', 'withdrawn', 'spam_rejected'].includes(filing.state);
  const activeIdx = terminalState ? TIMELINE_STEPS_ORDER.length - 1
    : ['moderation_queue', 'under_review'].includes(filing.state) ? 1
    : TIMELINE_STEPS_ORDER.indexOf(filing.state) >= 0 ? TIMELINE_STEPS_ORDER.indexOf(filing.state)
    : 0;

  return (
    <>
      <Header title={filing.template?.name || filing.category} back/>

      <div style={{ overflowY: 'auto', padding: '14px 20px 120px' }}>
        {/* Anonymous identity banner */}
        {isAnonymous && (
          <div style={{
            background: 'rgba(74,107,92,0.10)', border: '1px solid rgba(74,107,92,0.28)',
            borderRadius: 12, padding: '11px 14px', marginBottom: 14,
            display: 'flex', alignItems: 'center', gap: 10,
          }}>
            <IconEyeOff size={15} stroke="var(--sage)"/>
            <div style={{ fontSize: 12, color: 'var(--sage-2)', fontWeight: 600 }}>Your identity is protected throughout this filing.</div>
          </div>
        )}

        {/* ID + state */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <span className="mono" style={{ fontSize: 12, color: 'var(--muted)' }}>
            {filing.filing_number || 'Draft'}
          </span>
          <FilingStatePill state={filing.state} size="lg"/>
        </div>

        {/* Progress stepper */}
        <div style={{
          background: 'rgba(255,255,255,0.7)', border: '1px solid var(--mist)',
          borderRadius: 14, padding: '14px 16px', marginBottom: 14,
        }}>
          <div className="eyebrow" style={{ marginBottom: 14 }}>Progress</div>
          <div style={{ display: 'flex', alignItems: 'flex-start' }}>
            {TIMELINE_STEPS_ORDER.map((s, i) => {
              const done = i < activeIdx;
              const active = i === activeIdx;
              return (
                <React.Fragment key={s}>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: '0 0 auto' }}>
                    <div style={{
                      width: 22, height: 22, borderRadius: '50%',
                      background: done ? 'var(--sage)' : active ? 'var(--navy)' : 'var(--mist)',
                      color: done || active ? '#fff' : 'var(--muted)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 9, fontWeight: 700,
                      boxShadow: active ? '0 0 0 4px rgba(11,29,53,0.12)' : 'none',
                    }}>
                      {done ? <IconCheck size={9} sw={3}/> : ''}
                    </div>
                    <div style={{
                      fontSize: 8.5, color: active ? 'var(--navy)' : 'var(--muted)',
                      marginTop: 4, fontWeight: active ? 700 : 400, textAlign: 'center', maxWidth: 38,
                    }}>
                      {TIMELINE_STEP_LABELS[s]}
                    </div>
                  </div>
                  {i < TIMELINE_STEPS_ORDER.length - 1 && (
                    <div style={{
                      flex: 1, height: 1.5, background: done ? 'var(--sage)' : 'var(--mist)',
                      marginTop: 11, alignSelf: 'flex-start',
                    }}/>
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>

        {/* Moderation queue notice */}
        {filing.state === 'moderation_queue' && (
          <div style={{
            fontSize: 12.5, color: 'var(--gold)', background: 'rgba(184,137,58,0.08)',
            border: '1px solid rgba(184,137,58,0.22)', borderRadius: 10, padding: '10px 14px', marginBottom: 14,
          }}>
            Your filing is under initial review. We aim to complete this within 72 hours.
          </div>
        )}

        {/* Timeline entries from API */}
        {timeline?.entries?.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <div className="eyebrow" style={{ marginBottom: 10 }}>Timeline</div>
            {timeline.entries.map((e, i) => (
              <div key={i} className="tl-step">
                <span className={`tl-dot ${i < timeline.entries.length - 1 ? 'done' : 'active'}`}/>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--navy)', textTransform: 'capitalize' }}>
                    {e.event.replace(/_/g, ' ')}
                    {e.actor_role && <span style={{ fontWeight: 400, color: 'var(--muted)' }}> · {e.actor_role.replace(/_/g, ' ')}</span>}
                  </div>
                  {e.note && <div style={{ fontSize: 11.5, color: 'var(--ink-2)', marginTop: 2 }}>{e.note}</div>}
                  <div className="mono" style={{ fontSize: 10.5, color: 'var(--muted)', marginTop: 2 }}>
                    {new Date(e.timestamp).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                  </div>
                </div>
                {i === timeline.entries.length - 1 && (
                  <span className="pill pill-review" style={{ flexShrink: 0 }}>
                    <span className="dot pulse"/> Now
                  </span>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Final outcome */}
        {filing.final_outcome_note && (
          <div style={{
            background: 'rgba(255,255,255,0.7)', border: '1px solid var(--mist)',
            borderLeft: `3px solid ${filing.state === 'resolved' ? 'var(--sage)' : 'var(--muted)'}`,
            borderRadius: 12, padding: '14px 16px', marginBottom: 14,
          }}>
            <div className="eyebrow" style={{ marginBottom: 8 }}>
              {filing.state === 'resolved' ? 'Resolution' : 'Outcome'}
            </div>
            <div style={{ fontSize: 13.5, color: 'var(--navy)', lineHeight: 1.65, fontFamily: 'var(--font-serif)' }}>
              {filing.final_outcome_note}
            </div>
            {filing.state === 'dismissed' && !isAnonymous && (
              <div style={{ fontSize: 12, color: 'var(--muted)', marginTop: 10, lineHeight: 1.5 }}>
                If you believe this decision was made without full context, you may appeal within 30 days.
              </div>
            )}
          </div>
        )}

        {/* Your statement */}
        {filing.body && (
          <div style={{
            background: 'rgba(255,255,255,0.7)', border: '1px solid var(--mist)',
            borderRadius: 14, padding: '14px 16px', marginBottom: 14,
          }}>
            <div className="eyebrow" style={{ marginBottom: 10 }}>Your statement</div>
            <div style={{ fontSize: 13.5, color: 'var(--navy)', lineHeight: 1.65, whiteSpace: 'pre-wrap', fontFamily: 'var(--font-serif)' }}>
              "{filing.body}"
            </div>
          </div>
        )}

        {/* Attachments */}
        {filing.attachments?.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <div className="eyebrow" style={{ marginBottom: 8 }}>Proof attached</div>
            {filing.attachments.map(a => (
              <div key={a.id} style={{
                display: 'flex', alignItems: 'center', gap: 8,
                background: 'rgba(74,107,92,0.08)', borderRadius: 8, padding: '8px 12px', marginBottom: 6,
              }}>
                <span style={{ fontSize: 13 }}>📎</span>
                <span style={{ fontSize: 12, color: 'var(--sage-2)', flex: 1 }}>{a.original_filename}</span>
              </div>
            ))}
          </div>
        )}

        {/* Withdraw */}
        {canWithdraw && (
          <button onClick={handleWithdraw} disabled={withdrawing} style={{
            width: '100%', padding: '12px 16px', borderRadius: 12, cursor: 'pointer', marginBottom: 14,
            background: 'rgba(232,49,42,0.06)', border: '1px solid rgba(232,49,42,0.2)',
            color: 'var(--red)', fontSize: 13, fontFamily: 'var(--font-sans)', fontWeight: 500,
          }}>
            {withdrawing ? 'Withdrawing…' : 'Withdraw this filing'}
          </button>
        )}

        {/* Anonymous tracking code */}
        {filing.anonymous_tracking_code && (
          <TrackingCodeCard code={filing.anonymous_tracking_code}/>
        )}

        {/* View in cases */}
        <button onClick={() => go('cases')} className="btn btn-ghost" style={{ width: '100%', marginTop: 14, fontSize: 12 }}>
          ← Back to Active Cases
        </button>
      </div>
    </>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// ClassroomReportScreen
// ────────────────────────────────────────────────────────────────────────────

const ISSUE_TYPES = [
  { key: 'projector', icon: '📽', label: 'Projector' },
  { key: 'ac',        icon: '❄️',  label: 'AC / Fan' },
  { key: 'seating',   icon: '🪑', label: 'Seating' },
  { key: 'lighting',  icon: '💡', label: 'Lighting' },
  { key: 'door',      icon: '🚪', label: 'Door/Lock' },
  { key: 'cleanliness',icon: '🧹', label: 'Cleanliness' },
  { key: 'sound',     icon: '🔊', label: 'Sound' },
  { key: 'other',     icon: '❓', label: 'Other' },
];

function ClassroomReportScreen({ params = {} }) {
  const { back } = useApp();
  const [classroomRef, setClassroomRef] = useState('');
  const [issueType, setIssueType] = useState(null);
  const [notes, setNotes] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [alreadyReported, setAlreadyReported] = useState(false);
  const [error, setError] = useState(null);
  const [agg, setAgg] = useState(null);

  useEffect(() => {
    if (!classroomRef || !issueType) return;
    filingApiFetch(`/v1/classroom-reports?classroom_ref=${encodeURIComponent(classroomRef)}&issue_type=${issueType}`)
      .then(rows => setAgg(rows.find(r => r.issue_type === issueType) || null))
      .catch(() => {});
  }, [classroomRef, issueType]);

  const handleSubmit = async () => {
    if (!classroomRef.trim() || !issueType) return;
    setSubmitting(true);
    setError(null);
    try {
      await filingApiFetch('/v1/classroom-reports', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ classroom_ref: classroomRef.trim(), issue_type: issueType, notes: notes || null }),
      });
      setSubmitted(true);
    } catch (err) {
      if (err.message.toLowerCase().includes('already')) {
        setAlreadyReported(true);
      } else {
        setError(err.message);
      }
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted || alreadyReported) {
    const count = (agg?.count || 0) + (submitted ? 1 : 0);
    return (
      <>
        <Header title="Classroom report" back/>
        <div style={{ padding: '40px 20px', textAlign: 'center' }}>
          <div style={{
            width: 64, height: 64, borderRadius: 18, margin: '0 auto 18px',
            background: alreadyReported ? 'rgba(184,137,58,0.12)' : 'rgba(74,107,92,0.12)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: alreadyReported ? 'var(--gold)' : 'var(--sage)',
          }}>
            <IconCheck size={28} sw={2.5}/>
          </div>
          <div className="serif" style={{ fontSize: 19, fontWeight: 500, color: 'var(--navy)', marginBottom: 10 }}>
            {alreadyReported ? 'Already reported' : 'Report submitted'}
          </div>
          {count > 0 && (
            <div style={{
              fontSize: 13, color: 'var(--ink-2)', background: 'rgba(74,107,92,0.08)',
              borderRadius: 12, padding: '12px 18px', display: 'inline-block', marginTop: 8, lineHeight: 1.6,
            }}>
              <strong style={{ color: 'var(--navy)', fontSize: 20 }}>{count}</strong>{' '}
              {count === 1 ? 'student has' : 'students have'} reported this issue in <strong>{classroomRef}</strong>.
            </div>
          )}
          <button onClick={back} className="btn btn-ghost" style={{ marginTop: 28, width: '100%' }}>← Back</button>
        </div>
      </>
    );
  }

  return (
    <>
      <Header title="Classroom condition" subtitle="Aggregate vote · anonymous" back/>
      <div style={{ overflowY: 'auto', padding: '16px 20px', paddingBottom: 120 }}>
        <div style={{ fontSize: 13, color: 'var(--muted)', lineHeight: 1.65, marginBottom: 18 }}>
          Reports are aggregated — the room with the most issues gets prioritised. You can report each issue once per room.
        </div>

        <FField label="Classroom / room number">
          <FInput
            value={classroomRef}
            onChange={e => setClassroomRef(e.target.value)}
            placeholder="e.g. AB-301 or 8th-floor lab"
          />
        </FField>

        <FField label="What's the issue?">
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
            {ISSUE_TYPES.map(it => (
              <button key={it.key} onClick={() => setIssueType(issueType === it.key ? null : it.key)} style={{
                padding: '11px 4px', borderRadius: 12, textAlign: 'center', cursor: 'pointer',
                border: issueType === it.key ? '2px solid var(--sage)' : '1px solid var(--mist)',
                background: issueType === it.key ? 'rgba(74,107,92,0.10)' : 'rgba(255,255,255,0.7)',
                fontFamily: 'var(--font-sans)', transition: 'all 0.15s',
              }}>
                <div style={{ fontSize: 20, marginBottom: 4 }}>{it.icon}</div>
                <div style={{
                  fontSize: 10, color: 'var(--navy)',
                  fontWeight: issueType === it.key ? 700 : 400,
                }}>{it.label}</div>
              </button>
            ))}
          </div>
        </FField>

        {agg && (
          <div style={{
            fontSize: 12.5, color: 'var(--gold)', background: 'rgba(184,137,58,0.08)',
            border: '1px solid rgba(184,137,58,0.22)', borderRadius: 10, padding: '9px 13px', marginBottom: 14,
          }}>
            📊 <strong>{agg.count}</strong> {agg.count === 1 ? 'student has' : 'students have'} already reported this issue in this room.
          </div>
        )}

        <FField label="Additional notes (optional)">
          <FTextarea
            value={notes}
            onChange={e => setNotes(e.target.value)}
            placeholder="Any extra detail that might help maintenance…"
            minHeight={70}
          />
        </FField>

        {error && (
          <div style={{ color: 'var(--red)', fontSize: 12.5, marginBottom: 12, padding: '8px 12px', background: 'rgba(232,49,42,0.07)', borderRadius: 8 }}>
            {error}
          </div>
        )}
      </div>

      <div style={{ padding: '12px 20px 24px', borderTop: '1px solid var(--mist)', background: 'var(--cream)', flexShrink: 0 }}>
        <button onClick={handleSubmit} disabled={submitting || !classroomRef.trim() || !issueType}
                className="btn btn-primary" style={{ width: '100%', opacity: (!classroomRef.trim() || !issueType) ? 0.45 : 1 }}>
          {submitting ? 'Submitting…' : 'Submit report'}
        </button>
      </div>
    </>
  );
}

// Export to global scope
Object.assign(window, {
  FilingsListScreen, NewFilingScreen, FilingDetailScreen, ClassroomReportScreen,
  filingApiFetch,
});
