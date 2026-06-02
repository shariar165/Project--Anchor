// applications.jsx — Campus Application System (student-facing)
// Depends on: icons.jsx, app.jsx (useApp, Header)
// API base: http://localhost:8000

const { useState, useEffect, useRef, useCallback } = React;

const APP_BASE = 'http://localhost:8000';

function getToken() {
  return localStorage.getItem('anchor_access_token') || '';
}

function getRefreshToken() {
  return localStorage.getItem('anchor_refresh_token') || '';
}

async function tryRefreshToken() {
  const rt = getRefreshToken();
  if (!rt) return false;
  try {
    const res = await fetch(APP_BASE + '/auth/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: rt }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    if (data.access_token) {
      localStorage.setItem('anchor_access_token', data.access_token);
      if (data.refresh_token) localStorage.setItem('anchor_refresh_token', data.refresh_token);
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

function redirectToLogin() {
  // Clear stale auth and reload — AppProvider will show LoginScreen
  localStorage.removeItem('anchor_auth');
  localStorage.removeItem('anchor_access_token');
  localStorage.removeItem('anchor_refresh_token');
  window.location.reload();
}

async function apiFetch(path, opts = {}, _retry = true) {
  const res = await fetch(APP_BASE + path, {
    ...opts,
    headers: {
      'Authorization': 'Bearer ' + getToken(),
      ...(opts.headers || {}),
    },
  });
  if (res.status === 401 && _retry) {
    const refreshed = await tryRefreshToken();
    if (refreshed) return apiFetch(path, opts, false);
    redirectToLogin();
    throw new Error('Session expired — please log in again');
  }
  if (!res.ok) {
    let detail = 'Request failed';
    try { const d = await res.json(); detail = d.detail || detail; } catch {}
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

// ── State pill ────────────────────────────────────────────────────────────────

const STATE_META = {
  draft:              { label: 'Draft',            color: 'var(--muted)',   bg: 'rgba(107,102,96,0.10)' },
  submitted:          { label: 'Submitted',        color: 'var(--gold)',    bg: 'rgba(184,137,58,0.12)' },
  in_review:          { label: 'In Review',        color: 'var(--gold)',    bg: 'rgba(184,137,58,0.12)' },
  changes_requested:  { label: 'Changes Needed',  color: 'var(--ember)',   bg: 'rgba(196,69,54,0.12)' },
  approved:           { label: 'Approved',         color: 'var(--sage)',    bg: 'rgba(74,107,92,0.12)'  },
  rejected:           { label: 'Rejected',         color: 'var(--red)',     bg: 'rgba(232,49,42,0.12)'  },
  withdrawn:          { label: 'Withdrawn',        color: 'var(--muted)',   bg: 'rgba(107,102,96,0.10)' },
  escalated:          { label: 'Escalated',        color: 'var(--ember)',   bg: 'rgba(196,69,54,0.12)' },
};

function AppStatePill({ state, size = 'sm' }) {
  const m = STATE_META[state] || STATE_META.draft;
  const fs = size === 'lg' ? 13 : 10.5;
  const px = size === 'lg' ? '10px 16px' : '3px 9px';
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      background: m.bg, color: m.color, border: `1px solid ${m.color}33`,
      borderRadius: 999, padding: px, fontSize: fs, fontWeight: 600,
      fontFamily: 'var(--font-sans)', letterSpacing: '0.02em',
    }}>
      {size === 'lg' && <span style={{ width: 7, height: 7, borderRadius: '50%', background: m.color, display: 'inline-block' }}/>}
      {m.label}
    </span>
  );
}

// ── Template icons ────────────────────────────────────────────────────────────

const TEMPLATE_ICONS = {
  'late-fee-payment': IconClock,
  'fee-installment': IconClock,
  'scholarship': IconStar,
  'medical-leave': IconHeart,
  'personal-leave': IconUser,
  'course-retake': IconBook,
  'course-withdrawal': IconX,
  'certificate-request': IconDoc,
  'exam-overlap': IconAlert,
  'id-card': IconBadge,
  'late-degree': IconGavel,
  'exam-permission': IconCheck,
  'other': IconDoc,
};

// ── Applications List Screen ──────────────────────────────────────────────────

function ApplicationsListScreen() {
  const { go, mode } = useApp();
  const [apps, setApps] = useState([]);
  const [tab, setTab] = useState('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const tabs = [
    { k: 'all', label: 'All' },
    { k: 'draft', label: 'Drafts' },
    { k: 'in_review', label: 'In Review' },
    { k: 'approved', label: 'Done' },
  ];

  const loadApps = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const stateFilter = tab === 'all' ? '' : (tab === 'in_review' ? 'in_review' : tab);
      const qs = stateFilter ? `?state=${stateFilter}` : '';
      const data = await apiFetch(`/v1/applications${qs}`);
      setApps(data || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [tab]);

  useEffect(() => { loadApps(); }, [loadApps]);

  const accent = 'var(--sage)';
  const filtered = tab === 'all' ? apps :
    tab === 'done' ? apps.filter(a => ['approved','rejected','withdrawn'].includes(a.state)) :
    apps;

  return (
    <>
      <Header title="My Applications" subtitle="Campus · Applications" back/>

      {/* Tab bar */}
      <div style={{ padding: '12px 20px 0' }}>
        <div style={{ display: 'flex', gap: 6, background: 'rgba(255,255,255,0.5)', borderRadius: 12, padding: 4 }}>
          {tabs.map(t => (
            <button key={t.k} onClick={() => setTab(t.k)} style={{
              flex: 1, padding: '7px 4px', borderRadius: 8, border: 'none', cursor: 'pointer',
              background: tab === t.k ? 'var(--navy)' : 'transparent',
              color: tab === t.k ? '#fff' : 'var(--muted)',
              fontFamily: 'var(--font-sans)', fontSize: 11.5, fontWeight: tab === t.k ? 600 : 400,
            }}>{t.label}</button>
          ))}
        </div>
      </div>

      {/* List */}
      <div style={{ padding: '12px 20px 100px' }}>
        {loading && (
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--muted)', fontSize: 13 }}>
            Loading…
          </div>
        )}
        {!loading && error && (
          <div style={{ padding: 16, background: 'rgba(232,49,42,0.06)', borderRadius: 12,
            border: '1px solid rgba(232,49,42,0.2)', color: 'var(--red)', fontSize: 13, textAlign: 'center' }}>
            {error}
          </div>
        )}
        {!loading && !error && filtered.length === 0 && (
          <div style={{ textAlign: 'center', paddingTop: 60 }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>📄</div>
            <div className="serif" style={{ fontSize: 17, fontWeight: 500, color: 'var(--navy)', marginBottom: 6 }}>
              No applications yet
            </div>
            <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 24 }}>
              Start your first application — AI will help draft it.
            </div>
            <button onClick={() => go('new-application')} className="btn btn-primary" style={{ margin: '0 auto' }}>
              + New Application
            </button>
          </div>
        )}
        {!loading && !error && filtered.map(app => {
          const TemIcon = TEMPLATE_ICONS[app.template?.key] || IconDoc;
          const short = String(app.id).slice(0, 8).toUpperCase();
          const date = new Date(app.updated_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
          return (
            <button key={app.id} onClick={() => go('application', { id: app.id })}
              style={{
                width: '100%', textAlign: 'left', background: 'rgba(255,255,255,0.7)',
                border: '1px solid var(--mist)', borderRadius: 14, padding: 14,
                marginBottom: 10, cursor: 'pointer',
                display: 'flex', alignItems: 'flex-start', gap: 12,
              }}>
              <div style={{
                width: 36, height: 36, borderRadius: 10, flexShrink: 0,
                background: `${accent}15`, border: `1px solid ${accent}30`,
                display: 'flex', alignItems: 'center', justifyContent: 'center', color: accent,
              }}>
                <TemIcon size={16}/>
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span className="mono" style={{ fontSize: 10, color: 'var(--muted)' }}>DIU-APP-{short}</span>
                  <AppStatePill state={app.state}/>
                </div>
                <div className="serif" style={{ fontSize: 14, fontWeight: 500, color: 'var(--navy)', lineHeight: 1.25, marginBottom: 4 }}>
                  {app.template?.name || 'Application'}
                </div>
                <div style={{ fontSize: 11, color: 'var(--muted)' }}>
                  {app.current_approver_level
                    ? `With ${app.current_approver_level.replace(/_/g, ' ')}`
                    : app.state === 'draft' ? 'Not submitted' : app.state}
                  {' · '}{date}
                </div>
              </div>
              <IconChevronRight size={14} stroke="var(--mist-2)"/>
            </button>
          );
        })}
      </div>

      {/* FAB */}
      <button onClick={() => go('new-application')} style={{
        position: 'fixed', bottom: 108, right: 24, width: 52, height: 52,
        borderRadius: '50%', background: 'var(--navy)', color: '#fff',
        border: 'none', cursor: 'pointer', boxShadow: '0 4px 20px rgba(11,29,53,0.35)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 20,
      }}>
        <IconPlus size={22}/>
      </button>
    </>
  );
}

// ── New Application Screen (5-step wizard) ────────────────────────────────────

const TEMPLATE_FIELDS = {
  'late-fee-payment': [
    { k: 'outstanding_amount', label: 'Outstanding Amount (BDT)', type: 'text', placeholder: 'e.g. 12,000' },
    { k: 'payment_by_date', label: 'I can pay by', type: 'text', placeholder: 'e.g. 15 June 2026' },
  ],
  'fee-installment': [
    { k: 'amount', label: 'Total Amount (BDT)', type: 'text', placeholder: 'e.g. 25,000' },
    { k: 'installment_count', label: 'Number of Installments', type: 'text', placeholder: 'e.g. 3' },
  ],
  'medical-leave': [
    { k: 'leave_from', label: 'Leave from', type: 'text', placeholder: 'e.g. 01 June 2026' },
    { k: 'leave_to', label: 'Leave until', type: 'text', placeholder: 'e.g. 07 June 2026' },
  ],
  'personal-leave': [
    { k: 'leave_from', label: 'Leave from', type: 'text', placeholder: 'e.g. 01 June 2026' },
    { k: 'leave_to', label: 'Leave until', type: 'text', placeholder: 'e.g. 07 June 2026' },
  ],
  'course-retake': [
    { k: 'course_code', label: 'Course Code', type: 'text', placeholder: 'e.g. CSE-301' },
    { k: 'semester', label: 'Semester', type: 'text', placeholder: 'e.g. Fall 2025' },
  ],
  'exam-permission': [
    { k: 'exam_type', label: 'Exam Type', type: 'text', placeholder: 'Mid / Final' },
    { k: 'course_code', label: 'Course Code', type: 'text', placeholder: 'e.g. CSE-401' },
  ],
  'exam-overlap': [
    { k: 'course_code_1', label: 'First Course', type: 'text', placeholder: 'CSE-301' },
    { k: 'course_code_2', label: 'Clashing Course', type: 'text', placeholder: 'CSE-302' },
    { k: 'exam_date', label: 'Exam Date', type: 'text', placeholder: 'e.g. 10 June 2026' },
  ],
  'scholarship': [
    { k: 'scholarship_type', label: 'Scholarship Type', type: 'text', placeholder: 'Merit / Need-based' },
  ],
  'certificate-request': [
    { k: 'document_type', label: 'Document Type', type: 'text', placeholder: 'Transcript / Certificate / Testimonial' },
    { k: 'copies', label: 'Number of Copies', type: 'text', placeholder: 'e.g. 2' },
  ],
};

function NewApplicationScreen({ params = {} }) {
  const { go, back, auth } = useApp();
  const [step, setStep] = useState(params.step || 1);
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState(null);
  const [fields, setFields] = useState({ reason: '' });
  const [lang, setLang] = useState('en');
  const [letterBody, setLetterBody] = useState('');
  const [editMode, setEditMode] = useState(false);
  const [aiDrafting, setAiDrafting] = useState(false);
  const [aiError, setAiError] = useState('');
  const [attachments, setAttachments] = useState([]);
  const [uploadingFile, setUploadingFile] = useState(false);
  const [firstApprover, setFirstApprover] = useState('department_head');
  const [settings, setSettings] = useState(null);
  const [appId, setAppId] = useState(params.id || null);
  const [submitting, setSubmitting] = useState(false);
  const [explainCache, setExplainCache] = useState({});
  const [explaining, setExplaining] = useState(null);
  const fileRef = useRef();
  const accent = 'var(--sage)';

  // Load templates
  useEffect(() => {
    apiFetch('/v1/applications/templates')
      .then(setTemplates)
      .catch(() => {});
  }, []);

  // Load campus settings (for mentor info)
  useEffect(() => {
    apiFetch('/v1/students/me/campus-settings')
      .then(setSettings)
      .catch(() => {});
  }, []);

  // If resuming a draft, load it
  useEffect(() => {
    if (!params.id) return;
    apiFetch(`/v1/applications/${params.id}`)
      .then(app => {
        const tmpl = templates.find(t => t.id === app.template_id);
        if (tmpl) setSelectedTemplate(tmpl);
        setFields(app.field_values || { reason: '' });
        setLang(app.language || 'en');
        setLetterBody(app.letter_body || '');
        setAttachments(app.attachments || []);
        setStep(params.step || 2);
      })
      .catch(() => {});
  }, [params.id, templates.length]);

  // Auto-save on field/letter change (debounced)
  const saveTimeout = useRef(null);
  const autoSave = useCallback((newFields, newLetter, newLang) => {
    if (!appId) return;
    clearTimeout(saveTimeout.current);
    saveTimeout.current = setTimeout(() => {
      apiFetch(`/v1/applications/${appId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          field_values: newFields,
          letter_body: newLetter || undefined,
          language: newLang,
        }),
      }).catch(() => {});
    }, 1500);
  }, [appId]);

  const handleFieldChange = (k, v) => {
    const nf = { ...fields, [k]: v };
    setFields(nf);
    autoSave(nf, letterBody, lang);
  };

  const handleLetterChange = (v) => {
    setLetterBody(v);
    autoSave(fields, v, lang);
  };

  // Step 1 → 2: pick template
  const handleSelectTemplate = async (tmpl) => {
    setSelectedTemplate(tmpl);
    // Create draft application
    try {
      const created = await apiFetch('/v1/applications', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template_id: tmpl.id, field_values: {}, language: lang }),
      });
      setAppId(created.id);
      setStep(2);
    } catch (e) {
      alert('Could not create application: ' + e.message);
    }
  };

  // Step 2 → 3: Draft with AI
  const handleDraftWithAI = async () => {
    if (!appId) return;
    setAiDrafting(true);
    setAiError('');
    try {
      // Save current fields first
      await apiFetch(`/v1/applications/${appId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ field_values: fields, language: lang }),
      });
      const result = await apiFetch(`/v1/applications/${appId}/draft-with-ai`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ language: lang }),
      });
      setLetterBody(result.letter_body);
      setStep(3);
    } catch (e) {
      setAiError('AI drafting unavailable. You can write the letter manually.');
      setEditMode(true);
      setStep(3);
    } finally {
      setAiDrafting(false);
    }
  };

  const handleRegenerateAI = async () => {
    if (!appId) return;
    setAiDrafting(true);
    setAiError('');
    try {
      const result = await apiFetch(`/v1/applications/${appId}/draft-with-ai`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ language: lang }),
      });
      setLetterBody(result.letter_body);
      setEditMode(false);
    } catch (e) {
      setAiError('AI regeneration failed.');
    } finally {
      setAiDrafting(false);
    }
  };

  // File upload
  const handleFileSelect = async (e) => {
    const file = e.target.files[0];
    if (!file || !appId) return;
    if (attachments.length >= 5) { alert('Maximum 5 attachments allowed.'); return; }
    if (file.size > 10 * 1024 * 1024) { alert('File must be under 10 MB.'); return; }
    setUploadingFile(true);
    try {
      const form = new FormData();
      form.append('file', file);
      let res = await fetch(`${APP_BASE}/v1/applications/${appId}/attachments`, {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + getToken() },
        body: form,
      });
      if (res.status === 401) {
        const refreshed = await tryRefreshToken();
        if (!refreshed) { redirectToLogin(); return; }
        res = await fetch(`${APP_BASE}/v1/applications/${appId}/attachments`, {
          method: 'POST',
          headers: { 'Authorization': 'Bearer ' + getToken() },
          body: form,
        });
      }
      if (!res.ok) { const d = await res.json(); throw new Error(d.detail); }
      const attach = await res.json();
      setAttachments(a => [...a, attach]);
    } catch (e) {
      alert('Upload failed: ' + e.message);
    } finally {
      setUploadingFile(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const handleRemoveAttachment = async (attachId) => {
    if (!appId) return;
    try {
      await apiFetch(`/v1/applications/${appId}/attachments/${attachId}`, { method: 'DELETE' });
      setAttachments(a => a.filter(x => x.id !== attachId));
    } catch (e) {
      alert('Could not remove: ' + e.message);
    }
  };

  const handleExplain = async (attach) => {
    if (explainCache[attach.id]) return; // already loaded
    setExplaining(attach.id);
    try {
      const result = await apiFetch(`/v1/applications/${appId}/attachments/${attach.id}/explain?lang=${lang}`, {
        method: 'POST',
      });
      setExplainCache(c => ({ ...c, [attach.id]: result.explanation }));
    } catch (e) {
      setExplainCache(c => ({ ...c, [attach.id]: 'Explanation unavailable.' }));
    } finally {
      setExplaining(null);
    }
  };

  // Submit
  const handleSubmit = async () => {
    if (!appId) return;
    setSubmitting(true);
    try {
      // Save letter body first
      await apiFetch(`/v1/applications/${appId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ letter_body: letterBody }),
      });
      await apiFetch(`/v1/applications/${appId}/submit`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ first_approver_choice: firstApprover }),
      });
      go('application', { id: appId });
    } catch (e) {
      alert('Submission failed: ' + e.message);
      setSubmitting(false);
    }
  };

  const extraFields = TEMPLATE_FIELDS[selectedTemplate?.key] || [];

  const stepLabels = ['Template', 'Details', 'Letter', 'Proof', 'Submit'];

  return (
    <>
      <Header title="New Application" subtitle="Campus · Apply" back/>

      {/* Step indicator */}
      <div style={{ padding: '8px 20px 0', display: 'flex', gap: 4, alignItems: 'center' }}>
        {stepLabels.map((label, i) => {
          const n = i + 1;
          const active = n === step;
          const done = n < step;
          return (
            <React.Fragment key={n}>
              <div style={{
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3, flex: 1,
              }}>
                <div style={{
                  width: 22, height: 22, borderRadius: '50%', fontSize: 10, fontWeight: 700,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  background: done ? accent : active ? 'var(--navy)' : 'var(--mist)',
                  color: (done || active) ? '#fff' : 'var(--muted)',
                  fontFamily: 'var(--font-sans)',
                }}>
                  {done ? '✓' : n}
                </div>
                <div style={{ fontSize: 9, color: active ? 'var(--navy)' : 'var(--muted)', fontFamily: 'var(--font-sans)', fontWeight: active ? 600 : 400 }}>
                  {label}
                </div>
              </div>
              {i < stepLabels.length - 1 && (
                <div style={{ height: 1, flex: 1, background: done ? accent : 'var(--mist)', marginBottom: 14 }}/>
              )}
            </React.Fragment>
          );
        })}
      </div>

      <div style={{ padding: '16px 20px 100px', overflowY: 'auto' }}>

        {/* ── STEP 1: Template ────────────────────────────────────── */}
        {step === 1 && (
          <>
            <div className="serif" style={{ fontSize: 18, fontWeight: 500, color: 'var(--navy)', marginBottom: 4 }}>
              What do you need?
            </div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 16 }}>
              AI will draft a professional letter for you.
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
              {(templates.length === 0 ? [] : templates).map(t => {
                const TIco = TEMPLATE_ICONS[t.key] || IconDoc;
                return (
                  <button key={t.id} onClick={() => handleSelectTemplate(t)} className="tile" style={{ textAlign: 'left' }}>
                    <div style={{
                      width: 32, height: 32, borderRadius: 9, marginBottom: 10,
                      background: `${accent}15`, border: `1px solid ${accent}25`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center', color: accent,
                    }}>
                      <TIco size={15}/>
                    </div>
                    <div className="serif" style={{ fontSize: 13, fontWeight: 500, color: 'var(--navy)', lineHeight: 1.2 }}>
                      {t.name}
                    </div>
                    {t.requires_accounts_approval && (
                      <div style={{ marginTop: 4, fontSize: 10, color: 'var(--gold)' }}>Payment route</div>
                    )}
                  </button>
                );
              })}
              {templates.length === 0 && (
                <div style={{ gridColumn: 'span 2', textAlign: 'center', padding: 24, color: 'var(--muted)', fontSize: 13 }}>
                  Loading templates…
                </div>
              )}
            </div>
          </>
        )}

        {/* ── STEP 2: Fill Details ─────────────────────────────────── */}
        {step === 2 && selectedTemplate && (
          <>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16,
              padding: '10px 14px', background: `${accent}10`, borderRadius: 12,
              border: `1px solid ${accent}20`,
            }}>
              {React.createElement(TEMPLATE_ICONS[selectedTemplate.key] || IconDoc, { size: 16, stroke: accent })}
              <div className="serif" style={{ fontSize: 14, fontWeight: 500, color: 'var(--navy)' }}>
                {selectedTemplate.name}
              </div>
            </div>

            <div style={{ marginBottom: 14 }}>
              <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--ink-2)', marginBottom: 6, fontFamily: 'var(--font-sans)' }}>
                Explain your situation *
              </label>
              <textarea
                value={fields.reason || ''}
                onChange={e => handleFieldChange('reason', e.target.value)}
                placeholder="Describe your situation in your own words. The AI will turn this into a formal letter."
                rows={4}
                style={{
                  width: '100%', boxSizing: 'border-box',
                  padding: '10px 12px', borderRadius: 10, fontSize: 13,
                  border: '1.5px solid var(--mist-2)', background: 'rgba(255,255,255,0.8)',
                  fontFamily: 'var(--font-sans)', color: 'var(--ink)', resize: 'vertical',
                  lineHeight: 1.5,
                }}
              />
            </div>

            {extraFields.map(f => (
              <div key={f.k} style={{ marginBottom: 14 }}>
                <label style={{ display: 'block', fontSize: 12, fontWeight: 600, color: 'var(--ink-2)', marginBottom: 6, fontFamily: 'var(--font-sans)' }}>
                  {f.label}
                </label>
                <input
                  type={f.type}
                  value={fields[f.k] || ''}
                  onChange={e => handleFieldChange(f.k, e.target.value)}
                  placeholder={f.placeholder}
                  style={{
                    width: '100%', boxSizing: 'border-box',
                    height: 44, padding: '0 12px', borderRadius: 10, fontSize: 13,
                    border: '1.5px solid var(--mist-2)', background: 'rgba(255,255,255,0.8)',
                    fontFamily: 'var(--font-sans)', color: 'var(--ink)',
                  }}
                />
              </div>
            ))}

            {/* Language toggle */}
            <div style={{ marginBottom: 20 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--ink-2)', marginBottom: 8, fontFamily: 'var(--font-sans)' }}>
                Letter language
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                {[['en','English'], ['bn','বাংলা']].map(([v, lbl]) => (
                  <button key={v} onClick={() => setLang(v)} style={{
                    padding: '7px 18px', borderRadius: 999, border: '1.5px solid',
                    borderColor: lang === v ? 'var(--navy)' : 'var(--mist-2)',
                    background: lang === v ? 'var(--navy)' : 'transparent',
                    color: lang === v ? '#fff' : 'var(--muted)',
                    fontFamily: lang === v ? 'var(--font-sans)' : 'var(--font-bn)',
                    fontSize: 13, cursor: 'pointer',
                  }}>{lbl}</button>
                ))}
              </div>
            </div>

            <button onClick={handleDraftWithAI} disabled={aiDrafting || !fields.reason}
              className="btn btn-primary" style={{ width: '100%', gap: 8, opacity: (!fields.reason || aiDrafting) ? 0.5 : 1 }}>
              {aiDrafting ? (
                <>Drafting…</>
              ) : (
                <><IconSparkles size={15}/> Draft with AI</>
              )}
            </button>
            <button onClick={() => { setLetterBody(''); setStep(3); }} style={{
              width: '100%', marginTop: 8, padding: '10px', borderRadius: 12, border: 'none',
              background: 'transparent', color: 'var(--muted)', fontSize: 13, cursor: 'pointer',
              fontFamily: 'var(--font-sans)',
            }}>
              Write manually instead →
            </button>
          </>
        )}

        {/* ── STEP 3: Review Letter ────────────────────────────────── */}
        {step === 3 && (
          <>
            <div className="serif" style={{ fontSize: 16, fontWeight: 500, color: 'var(--navy)', marginBottom: 4 }}>
              Review your letter
            </div>
            {aiError && (
              <div style={{ padding: '10px 14px', background: 'rgba(184,137,58,0.1)', borderRadius: 10,
                border: '1px solid rgba(184,137,58,0.3)', fontSize: 12, color: 'var(--gold)', marginBottom: 12 }}>
                ⚠ {aiError}
              </div>
            )}
            <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
              <button onClick={handleRegenerateAI} disabled={aiDrafting} className="btn btn-ghost" style={{ flex: 1, fontSize: 12 }}>
                {aiDrafting ? 'Generating…' : <><IconSparkles size={13}/> Regenerate</>}
              </button>
              <button onClick={() => setEditMode(m => !m)} className="btn btn-ghost" style={{ flex: 1, fontSize: 12 }}>
                {editMode ? 'Preview' : 'Edit manually'}
              </button>
            </div>

            {editMode ? (
              <textarea
                value={letterBody}
                onChange={e => handleLetterChange(e.target.value)}
                rows={14}
                style={{
                  width: '100%', boxSizing: 'border-box',
                  padding: '12px', borderRadius: 10, fontSize: 12.5, lineHeight: 1.7,
                  border: '1.5px solid var(--mist-2)', background: 'rgba(255,255,255,0.9)',
                  fontFamily: 'var(--font-sans)', color: 'var(--ink)', resize: 'vertical',
                }}
              />
            ) : (
              <div style={{
                background: '#fff', border: '1px solid var(--mist)', borderRadius: 12,
                padding: '16px', fontSize: 12.5, lineHeight: 1.8, fontFamily: 'var(--font-sans)',
                color: 'var(--ink)', whiteSpace: 'pre-wrap', minHeight: 200,
              }}>
                {letterBody || (
                  <span style={{ color: 'var(--muted)', fontStyle: 'italic' }}>
                    No letter yet. Click "Regenerate" or "Edit manually."
                  </span>
                )}
              </div>
            )}

            <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
              <button onClick={() => setStep(2)} className="btn btn-ghost" style={{ flex: 1 }}>← Back</button>
              <button onClick={() => setStep(4)} className="btn btn-primary" style={{ flex: 2 }}>Continue →</button>
            </div>
          </>
        )}

        {/* ── STEP 4: Attachments ──────────────────────────────────── */}
        {step === 4 && (
          <>
            <div className="serif" style={{ fontSize: 16, fontWeight: 500, color: 'var(--navy)', marginBottom: 4 }}>
              Attach proof documents
            </div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 16 }}>
              Max 5 files · 10 MB each · PDF, PNG, JPG, DOCX
            </div>

            {attachments.map(a => (
              <div key={a.id} style={{
                background: 'rgba(255,255,255,0.7)', border: '1px solid var(--mist)',
                borderRadius: 12, padding: '12px 14px', marginBottom: 10,
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: explainCache[a.id] ? 8 : 0 }}>
                  <IconPaperclip size={15} stroke="var(--sage)"/>
                  <span style={{ flex: 1, fontSize: 12.5, color: 'var(--ink)', fontFamily: 'var(--font-sans)' }}>
                    {a.original_filename}
                  </span>
                  <IconCheck size={14} stroke="var(--sage)"/>
                  <button onClick={() => handleExplain(a)} style={{
                    background: 'none', border: 'none', cursor: 'pointer',
                    fontSize: 10.5, color: 'var(--gold)', fontFamily: 'var(--font-sans)', padding: '2px 6px',
                  }}>
                    {explaining === a.id ? '…' : 'What is this?'}
                  </button>
                  <button onClick={() => handleRemoveAttachment(a.id)} style={{
                    background: 'none', border: 'none', cursor: 'pointer', color: 'var(--red)', padding: 4,
                  }}>
                    <IconX size={13}/>
                  </button>
                </div>
                {explainCache[a.id] && (
                  <div style={{
                    fontSize: 11.5, color: 'var(--ink-2)', lineHeight: 1.5, padding: '8px 10px',
                    background: 'rgba(184,137,58,0.06)', borderRadius: 8, border: '1px solid rgba(184,137,58,0.15)',
                  }}>
                    {explainCache[a.id]}
                  </div>
                )}
              </div>
            ))}

            {attachments.length < 5 && (
              <>
                <input
                  ref={fileRef} type="file" style={{ display: 'none' }}
                  accept=".pdf,.png,.jpg,.jpeg,.docx"
                  onChange={handleFileSelect}
                />
                <button onClick={() => fileRef.current?.click()} disabled={uploadingFile}
                  className="btn btn-ghost" style={{ width: '100%', gap: 8 }}>
                  {uploadingFile ? 'Uploading…' : <><IconPaperclip size={15}/> Add file</>}
                </button>
              </>
            )}

            <div style={{ display: 'flex', gap: 10, marginTop: 16 }}>
              <button onClick={() => setStep(3)} className="btn btn-ghost" style={{ flex: 1 }}>← Back</button>
              <button onClick={() => setStep(5)} className="btn btn-primary" style={{ flex: 2 }}>Continue →</button>
            </div>
          </>
        )}

        {/* ── STEP 5: Approver + Submit ────────────────────────────── */}
        {step === 5 && (
          <>
            <div className="serif" style={{ fontSize: 16, fontWeight: 500, color: 'var(--navy)', marginBottom: 4 }}>
              Pick first approver
            </div>
            <div style={{ fontSize: 12, color: 'var(--muted)', marginBottom: 16 }}>
              Your application goes to them first, then to the Dean.
            </div>

            {/* Mentor option */}
            {settings?.mentor_user_id && settings?.mentor_name && (
              <button onClick={() => setFirstApprover('mentor')} style={{
                width: '100%', textAlign: 'left', padding: '14px 16px', marginBottom: 10,
                borderRadius: 12, border: `2px solid ${firstApprover === 'mentor' ? 'var(--navy)' : 'var(--mist)'}`,
                background: firstApprover === 'mentor' ? 'rgba(11,29,53,0.04)' : 'rgba(255,255,255,0.6)',
                cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 12,
              }}>
                <div style={{
                  width: 36, height: 36, borderRadius: '50%', background: 'var(--navy)', color: '#fff',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 700,
                }}>
                  {settings.mentor_name.split(' ').map(w => w[0]).slice(0,2).join('')}
                </div>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--navy)', fontFamily: 'var(--font-sans)' }}>
                    My Mentor
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--muted)', fontFamily: 'var(--font-sans)' }}>
                    {settings.mentor_name}
                  </div>
                </div>
                {firstApprover === 'mentor' && <IconCheck size={16} stroke="var(--navy)" style={{ marginLeft: 'auto' }}/>}
              </button>
            )}

            {/* Department head option */}
            <button onClick={() => setFirstApprover('department_head')} style={{
              width: '100%', textAlign: 'left', padding: '14px 16px', marginBottom: 10,
              borderRadius: 12, border: `2px solid ${firstApprover === 'department_head' ? 'var(--navy)' : 'var(--mist)'}`,
              background: firstApprover === 'department_head' ? 'rgba(11,29,53,0.04)' : 'rgba(255,255,255,0.6)',
              cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 12,
            }}>
              <div style={{
                width: 36, height: 36, borderRadius: '50%', background: accent, color: '#fff',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <IconBuilding size={16}/>
              </div>
              <div>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--navy)', fontFamily: 'var(--font-sans)' }}>
                  My Department Head
                </div>
                <div style={{ fontSize: 12, color: 'var(--muted)', fontFamily: 'var(--font-sans)' }}>
                  {settings?.department || 'Department'}
                </div>
              </div>
              {firstApprover === 'department_head' && <IconCheck size={16} stroke="var(--navy)" style={{ marginLeft: 'auto' }}/>}
            </button>

            {!settings?.mentor_user_id && (
              <button onClick={() => go('campus-settings')} style={{
                width: '100%', marginBottom: 12, padding: '10px', background: 'none', border: 'none',
                fontSize: 12, color: 'var(--gold)', cursor: 'pointer', fontFamily: 'var(--font-sans)',
              }}>
                + Set a mentor in Settings to enable this option
              </button>
            )}

            {/* Summary */}
            <div style={{
              padding: '12px 14px', background: 'rgba(74,107,92,0.06)', borderRadius: 12,
              border: '1px solid rgba(74,107,92,0.15)', marginBottom: 16,
            }}>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--sage)', textTransform: 'uppercase',
                letterSpacing: '0.1em', marginBottom: 8, fontFamily: 'var(--font-sans)' }}>Summary</div>
              <div style={{ fontSize: 12.5, color: 'var(--ink)', fontFamily: 'var(--font-sans)', lineHeight: 1.6 }}>
                <div>Type: <strong>{selectedTemplate?.name}</strong></div>
                <div>Language: <strong>{lang === 'en' ? 'English' : 'বাংলা'}</strong></div>
                <div>Attachments: <strong>{attachments.length}</strong></div>
                <div>First approver: <strong>{firstApprover === 'mentor' ? settings?.mentor_name || 'Mentor' : 'Department Head'}</strong></div>
              </div>
            </div>

            <div style={{ display: 'flex', gap: 10 }}>
              <button onClick={() => setStep(4)} className="btn btn-ghost" style={{ flex: 1 }}>← Back</button>
              <button onClick={handleSubmit} disabled={submitting} className="btn btn-primary" style={{ flex: 2, gap: 8 }}>
                {submitting ? 'Submitting…' : <><IconSend size={15}/> Submit</>}
              </button>
            </div>
          </>
        )}
      </div>
    </>
  );
}

// ── Application Detail / Tracking Screen ──────────────────────────────────────

const APPROVER_LABELS = {
  mentor: 'Mentor',
  department_head: 'Department Head',
  dean: 'Dean',
  accounts: 'Accounts Officer',
};

function ApplicationDetailScreen({ params = {} }) {
  const { go } = useApp();
  const [app, setApp] = useState(null);
  const [timeline, setTimeline] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [showLetter, setShowLetter] = useState(false);
  const [withdrawing, setWithdrawing] = useState(false);
  const [showWithdrawConfirm, setShowWithdrawConfirm] = useState(false);
  const [pdfLoading, setPdfLoading] = useState(false);
  const sseRef = useRef(null);

  const appId = params.id;

  const loadApp = useCallback(async () => {
    if (!appId) return;
    try {
      const [appData, tlData] = await Promise.all([
        apiFetch(`/v1/applications/${appId}`),
        apiFetch(`/v1/applications/${appId}/timeline`),
      ]);
      setApp(appData);
      setTimeline(tlData);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [appId]);

  useEffect(() => { loadApp(); }, [loadApp]);

  // SSE connection
  useEffect(() => {
    if (!appId) return;
    let es;
    try {
      es = new EventSource(`${APP_BASE}/v1/applications/${appId}/stream?token=${getToken()}`);
      sseRef.current = es;
      es.onmessage = () => { loadApp(); };
      es.onerror = () => { es.close(); };
    } catch {}
    return () => { if (es) es.close(); };
  }, [appId, loadApp]);

  // Polling fallback (30s)
  useEffect(() => {
    const timer = setInterval(loadApp, 30000);
    return () => clearInterval(timer);
  }, [loadApp]);

  const handleWithdraw = async () => {
    setWithdrawing(true);
    try {
      await apiFetch(`/v1/applications/${appId}/withdraw`, { method: 'POST' });
      loadApp();
      setShowWithdrawConfirm(false);
    } catch (e) {
      alert('Withdrawal failed: ' + e.message);
    } finally {
      setWithdrawing(false);
    }
  };

  const handleDownloadPDF = async () => {
    setPdfLoading(true);
    try {
      let res = await fetch(`${APP_BASE}/v1/applications/${appId}/pdf`, {
        headers: { 'Authorization': 'Bearer ' + getToken() },
      });
      if (res.status === 401) {
        const refreshed = await tryRefreshToken();
        if (!refreshed) { redirectToLogin(); return; }
        res = await fetch(`${APP_BASE}/v1/applications/${appId}/pdf`, {
          headers: { 'Authorization': 'Bearer ' + getToken() },
        });
      }
      if (!res.ok) throw new Error('PDF not ready');
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `DIU-APP-${String(appId).slice(0,8).toUpperCase()}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert('PDF download failed: ' + e.message);
    } finally {
      setPdfLoading(false);
    }
  };

  const handleApplyAgain = async () => {
    if (!app) return;
    go('new-application');
  };

  if (loading) {
    return (
      <>
        <Header title="Application" back/>
        <div style={{ textAlign: 'center', padding: 60, color: 'var(--muted)', fontSize: 13 }}>Loading…</div>
      </>
    );
  }
  if (error || !app) {
    return (
      <>
        <Header title="Application" back/>
        <div style={{ padding: 24, color: 'var(--red)', textAlign: 'center', fontSize: 13 }}>
          {error || 'Application not found'}
        </div>
      </>
    );
  }

  const short = String(app.id).slice(0, 8).toUpperCase();
  const templateName = app.template?.name || 'Application';
  const canWithdraw = (app.state === 'in_review' || app.state === 'submitted') && (!app.reviews || app.reviews.length === 0);
  const canResubmit = app.state === 'changes_requested';
  const isApproved = app.state === 'approved';
  const isRejected = app.state === 'rejected';
  const isDraft = app.state === 'draft';

  const CHAIN_STEPS = ['draft', 'submitted', 'in_review', 'approved'];
  const stateIndex = {
    draft: 0, submitted: 1, in_review: 2,
    changes_requested: 2, escalated: 2,
    approved: 3, rejected: 3, withdrawn: 3,
  };
  const currentStep = stateIndex[app.state] ?? 0;

  const DECISION_ICON = { approved: '✓', rejected: '✗', changes_requested: '↩' };
  const DECISION_COLOR = { approved: 'var(--sage)', rejected: 'var(--red)', changes_requested: 'var(--gold)' };

  return (
    <>
      <Header title={`DIU-APP-${short}`} subtitle={templateName} back/>

      <div style={{ padding: '16px 20px 100px' }}>
        {/* State badge */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
          <AppStatePill state={app.state} size="lg"/>
          <div style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--font-sans)' }}>
            Round {app.round_count}
          </div>
        </div>

        {/* Progress stepper */}
        <div style={{
          padding: '14px 16px', background: 'rgba(255,255,255,0.6)', borderRadius: 12,
          border: '1px solid var(--mist)', marginBottom: 16,
          display: 'flex', alignItems: 'center', gap: 4,
        }}>
          {['Drafted', 'Submitted', 'In Review', 'Decision'].map((lbl, i) => (
            <React.Fragment key={i}>
              <div style={{ flex: 1, textAlign: 'center' }}>
                <div style={{
                  width: 22, height: 22, borderRadius: '50%', margin: '0 auto 4px',
                  background: i <= currentStep ? 'var(--sage)' : 'var(--mist)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 10, color: i <= currentStep ? '#fff' : 'var(--muted)',
                }}>
                  {i <= currentStep ? '●' : '○'}
                </div>
                <div style={{ fontSize: 9, color: i === currentStep ? 'var(--navy)' : 'var(--muted)', fontFamily: 'var(--font-sans)', fontWeight: i === currentStep ? 600 : 400 }}>
                  {lbl}
                </div>
              </div>
              {i < 3 && (
                <div style={{ height: 1, flex: 1, background: i < currentStep ? 'var(--sage)' : 'var(--mist)', marginBottom: 14 }}/>
              )}
            </React.Fragment>
          ))}
        </div>

        {/* Current holder */}
        {app.current_approver_level && (
          <div style={{
            padding: '10px 14px', background: 'rgba(184,137,58,0.08)', borderRadius: 10,
            border: '1px solid rgba(184,137,58,0.2)', marginBottom: 14,
            display: 'flex', alignItems: 'center', gap: 10,
          }}>
            <IconClock size={14} stroke="var(--gold)"/>
            <span style={{ fontSize: 12.5, color: 'var(--ink)', fontFamily: 'var(--font-sans)' }}>
              Currently with <strong>{APPROVER_LABELS[app.current_approver_level] || app.current_approver_level}</strong>
            </span>
          </div>
        )}

        {/* Changes requested note */}
        {app.state === 'changes_requested' && app.reviews?.length > 0 && (
          <div style={{
            padding: '12px 14px', background: 'rgba(196,69,54,0.07)', borderRadius: 10,
            border: '1px solid rgba(196,69,54,0.2)', marginBottom: 14,
          }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--ember)', textTransform: 'uppercase',
              letterSpacing: '0.08em', marginBottom: 4, fontFamily: 'var(--font-sans)' }}>
              Changes requested
            </div>
            <div style={{ fontSize: 12.5, color: 'var(--ink)', fontFamily: 'var(--font-sans)', lineHeight: 1.5 }}>
              {app.reviews[app.reviews.length - 1]?.notes || 'Please review and make the requested changes.'}
            </div>
          </div>
        )}

        {/* Timeline */}
        {timeline && timeline.entries.length > 0 && (
          <div style={{ marginBottom: 16 }}>
            <div className="eyebrow" style={{ marginBottom: 10 }}>Timeline</div>
            {[...timeline.entries].reverse().map((entry, i) => {
              const decColor = DECISION_COLOR[entry.event] || 'var(--muted)';
              const decIcon = DECISION_ICON[entry.event] || '•';
              const ts = new Date(entry.timestamp).toLocaleString('en-GB', {
                day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
              });
              return (
                <div key={i} style={{ display: 'flex', gap: 12, marginBottom: 12 }}>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                    <div style={{
                      width: 24, height: 24, borderRadius: '50%', flexShrink: 0,
                      background: `${decColor}18`, border: `1.5px solid ${decColor}50`,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 10, color: decColor, fontWeight: 700,
                    }}>{decIcon}</div>
                    {i < timeline.entries.length - 1 && (
                      <div style={{ width: 1, flex: 1, background: 'var(--mist)', margin: '3px 0' }}/>
                    )}
                  </div>
                  <div style={{ flex: 1, paddingBottom: 8 }}>
                    <div style={{ fontSize: 12.5, fontWeight: 600, color: 'var(--ink)', fontFamily: 'var(--font-sans)' }}>
                      {entry.note || entry.event}
                      {entry.actor_role && (
                        <span style={{ fontWeight: 400, color: 'var(--muted)' }}>
                          {' '}by {APPROVER_LABELS[entry.actor_role] || entry.actor_role}
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: 10.5, color: 'var(--muted)', fontFamily: 'var(--font-sans)', marginTop: 2 }}>{ts}</div>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Letter preview */}
        {app.letter_body && (
          <div style={{ marginBottom: 14 }}>
            <button onClick={() => setShowLetter(s => !s)} style={{
              width: '100%', textAlign: 'left', padding: '10px 14px',
              background: 'rgba(255,255,255,0.6)', border: '1px solid var(--mist)',
              borderRadius: 10, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8,
              fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--navy)',
            }}>
              <IconDoc size={14}/>
              {showLetter ? 'Hide letter' : 'View letter'}
              <IconChevronRight size={12} stroke="var(--muted)" style={{ marginLeft: 'auto', transform: showLetter ? 'rotate(90deg)' : '' }}/>
            </button>
            {showLetter && (
              <div style={{
                marginTop: 8, padding: '14px', background: '#fff', borderRadius: 10,
                border: '1px solid var(--mist)', fontSize: 12, lineHeight: 1.8,
                fontFamily: 'var(--font-sans)', color: 'var(--ink)', whiteSpace: 'pre-wrap',
              }}>
                {app.letter_body}
              </div>
            )}
          </div>
        )}

        {/* Attachments */}
        {app.attachments?.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <div className="eyebrow" style={{ marginBottom: 8 }}>Attachments</div>
            {app.attachments.map(a => (
              <div key={a.id} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6,
                padding: '8px 12px', background: 'rgba(255,255,255,0.6)', borderRadius: 8,
                border: '1px solid var(--mist)' }}>
                <IconPaperclip size={13} stroke="var(--sage)"/>
                <span style={{ flex: 1, fontSize: 12, color: 'var(--ink)', fontFamily: 'var(--font-sans)' }}>
                  {a.original_filename}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Actions */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {isDraft && (
            <button onClick={() => go('new-application', { id: app.id, step: 2 })} className="btn btn-primary">
              Continue editing →
            </button>
          )}
          {canResubmit && (
            <button onClick={() => go('new-application', { id: app.id, step: 3 })} className="btn btn-primary">
              Make changes & resubmit →
            </button>
          )}
          {isApproved && (
            <button onClick={handleDownloadPDF} disabled={pdfLoading} className="btn btn-primary" style={{ gap: 8 }}>
              {pdfLoading ? 'Preparing PDF…' : <><IconDownload size={15}/> Download Signed PDF</>}
            </button>
          )}
          {isRejected && (
            <button onClick={handleApplyAgain} className="btn btn-primary">Apply again →</button>
          )}
          {canWithdraw && !showWithdrawConfirm && (
            <button onClick={() => setShowWithdrawConfirm(true)} className="btn btn-ghost" style={{ color: 'var(--red)', borderColor: 'rgba(232,49,42,0.3)' }}>
              Withdraw application
            </button>
          )}
          {showWithdrawConfirm && (
            <div style={{ padding: '14px', background: 'rgba(232,49,42,0.07)', borderRadius: 12, border: '1px solid rgba(232,49,42,0.2)' }}>
              <div style={{ fontSize: 13, color: 'var(--red)', fontFamily: 'var(--font-sans)', marginBottom: 10 }}>
                Withdraw this application? This cannot be undone.
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <button onClick={() => setShowWithdrawConfirm(false)} className="btn btn-ghost" style={{ flex: 1 }}>Cancel</button>
                <button onClick={handleWithdraw} disabled={withdrawing} className="btn btn-primary"
                  style={{ flex: 1, background: 'var(--red)', borderColor: 'var(--red)' }}>
                  {withdrawing ? '…' : 'Confirm'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}

// ── Campus Settings Screen ────────────────────────────────────────────────────

function CampusSettingsScreen() {
  const { go } = useApp();
  const [settings, setSettings] = useState(null);
  const [mentors, setMentors] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showPicker, setShowPicker] = useState(false);
  const [search, setSearch] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    Promise.all([
      apiFetch('/v1/students/me/campus-settings'),
      apiFetch('/v1/students/me/available-mentors'),
    ]).then(([s, m]) => {
      setSettings(s);
      setMentors(m || []);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const handleSelectMentor = async (mentor) => {
    setSaving(true);
    try {
      const updated = await apiFetch('/v1/students/me/campus-settings', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mentor_user_id: mentor.user_id }),
      });
      setSettings(updated);
      setShowPicker(false);
    } catch (e) {
      alert('Could not update mentor: ' + e.message);
    } finally {
      setSaving(false);
    }
  };

  const filteredMentors = mentors.filter(m =>
    m.full_name.toLowerCase().includes(search.toLowerCase()) ||
    (m.email || '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <>
      <Header title="Campus Settings" subtitle="Campus · Profile" back/>

      <div style={{ padding: '16px 20px 100px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--muted)', fontSize: 13 }}>Loading…</div>
        ) : (
          <>
            {/* Department (locked) */}
            <div style={{ marginBottom: 16 }}>
              <div className="eyebrow" style={{ marginBottom: 8 }}>Department</div>
              <div style={{
                padding: '12px 14px', background: 'rgba(255,255,255,0.5)', borderRadius: 10,
                border: '1px solid var(--mist)',
              }}>
                <div style={{ fontSize: 13.5, fontWeight: 500, color: 'var(--navy)', fontFamily: 'var(--font-sans)' }}>
                  {settings?.department || 'Not set'}
                </div>
                <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 3, fontFamily: 'var(--font-sans)' }}>
                  {settings?.department_locked ? 'Locked — set from enrollment record' : 'You can update this below'}
                </div>
              </div>
            </div>

            {/* Mentor */}
            <div style={{ marginBottom: 16 }}>
              <div className="eyebrow" style={{ marginBottom: 8 }}>My Mentor</div>
              <div style={{
                padding: '12px 14px', background: 'rgba(255,255,255,0.6)', borderRadius: 10,
                border: '1px solid var(--mist)',
              }}>
                {settings?.mentor_name ? (
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <div style={{
                      width: 36, height: 36, borderRadius: '50%', background: 'var(--navy)', color: '#fff',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 700,
                    }}>
                      {settings.mentor_name.split(' ').map(w => w[0]).slice(0,2).join('')}
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontSize: 13.5, fontWeight: 500, color: 'var(--navy)', fontFamily: 'var(--font-sans)' }}>
                        {settings.mentor_name}
                      </div>
                      <div style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--font-sans)' }}>
                        Mentor
                      </div>
                    </div>
                    <button onClick={() => setShowPicker(true)} className="btn btn-ghost" style={{ fontSize: 11 }}>
                      Change
                    </button>
                  </div>
                ) : (
                  <div>
                    <div style={{ fontSize: 13, color: 'var(--muted)', fontFamily: 'var(--font-sans)', marginBottom: 10 }}>
                      No mentor set. Pick one from verified staff.
                    </div>
                    <button onClick={() => setShowPicker(true)} className="btn btn-primary" style={{ fontSize: 12 }}>
                      + Select Mentor
                    </button>
                  </div>
                )}
              </div>
            </div>

            {/* Info */}
            <div style={{ padding: '12px 14px', background: 'rgba(74,107,92,0.06)', borderRadius: 10,
              border: '1px solid rgba(74,107,92,0.15)', fontSize: 12, color: 'var(--muted)', lineHeight: 1.6,
              fontFamily: 'var(--font-sans)' }}>
              Your mentor can be the first approver for applications. Changing your mentor only affects new applications — in-flight ones keep their original selection.
            </div>

            {/* Mentor picker modal */}
            {showPicker && (
              <div style={{
                position: 'fixed', inset: 0, background: 'rgba(11,29,53,0.5)', zIndex: 50,
                display: 'flex', alignItems: 'flex-end', padding: 0,
              }}>
                <div style={{
                  width: '100%', background: 'var(--cream)', borderRadius: '20px 20px 0 0',
                  padding: '20px', maxHeight: '70%', overflowY: 'auto',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
                    <div className="serif" style={{ fontSize: 16, fontWeight: 500, color: 'var(--navy)' }}>
                      Select Mentor
                    </div>
                    <button onClick={() => setShowPicker(false)} style={{
                      background: 'none', border: 'none', cursor: 'pointer', color: 'var(--muted)',
                    }}>
                      <IconX size={18}/>
                    </button>
                  </div>

                  <input
                    type="text" value={search}
                    onChange={e => setSearch(e.target.value)}
                    placeholder="Search by name…"
                    style={{
                      width: '100%', boxSizing: 'border-box', height: 40,
                      padding: '0 12px', borderRadius: 10, fontSize: 13,
                      border: '1.5px solid var(--mist-2)', background: '#fff',
                      fontFamily: 'var(--font-sans)', marginBottom: 12,
                    }}
                  />

                  {filteredMentors.length === 0 && (
                    <div style={{ textAlign: 'center', padding: 24, color: 'var(--muted)', fontSize: 13 }}>
                      {mentors.length === 0 ? 'No staff available in your tenant.' : 'No results for your search.'}
                    </div>
                  )}

                  {filteredMentors.map(m => (
                    <button key={m.user_id} onClick={() => handleSelectMentor(m)} disabled={saving}
                      style={{
                        width: '100%', textAlign: 'left', padding: '12px 14px', marginBottom: 8,
                        background: 'rgba(255,255,255,0.7)', border: '1px solid var(--mist)',
                        borderRadius: 10, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 10,
                      }}>
                      <div style={{
                        width: 34, height: 34, borderRadius: '50%', background: 'var(--navy)', color: '#fff',
                        display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12, fontWeight: 700,
                      }}>
                        {m.full_name.split(' ').map(w => w[0]).slice(0,2).join('')}
                      </div>
                      <div>
                        <div style={{ fontSize: 13, fontWeight: 500, color: 'var(--navy)', fontFamily: 'var(--font-sans)' }}>
                          {m.full_name}
                        </div>
                        <div style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--font-sans)' }}>
                          {m.email || 'Staff'}
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </>
  );
}

Object.assign(window, {
  ApplicationsListScreen,
  NewApplicationScreen,
  ApplicationDetailScreen,
  CampusSettingsScreen,
});
