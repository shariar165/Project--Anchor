// police-reports.jsx — National-mode FIR / GD drafting (real backend).
// Depends on: icons.jsx, app.jsx (useApp, Header), applications.jsx (apiFetch global).
// API base: http://localhost:8000  ·  routes: police-reports, new-police-report, police-report

const { useState: _prS, useEffect: _prE, useRef: _prR } = React;

const PR_BASE = window.ANCHOR_API_URL || 'http://localhost:8000';

// Reuse the shared apiFetch (single-flight refresh + soft logout). Fallback kept for safety.
const prFetch = (typeof apiFetch === 'function')
  ? apiFetch
  : async (path, opts = {}) => {
      const res = await fetch(PR_BASE + path, {
        ...opts,
        headers: { 'Authorization': 'Bearer ' + (localStorage.getItem('anchor_access_token') || ''), ...(opts.headers || {}) },
      });
      if (!res.ok) { let d = 'Request failed'; try { d = (await res.json()).detail || d; } catch {} throw new Error(d); }
      return res.status === 204 ? null : res.json();
    };

// Binary download (apiFetch returns JSON, so exports need their own fetch → blob → anchor click).
async function prDownload(path, filename) {
  const res = await fetch(PR_BASE + path, {
    headers: { 'Authorization': 'Bearer ' + (localStorage.getItem('anchor_access_token') || '') },
  });
  if (!res.ok) { let d = 'Download failed'; try { d = (await res.json()).detail || d; } catch {} throw new Error(d); }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}

const PR_STATE_META = {
  draft:         { label: 'Draft',        color: 'var(--muted)' },
  finalized:     { label: 'Ready to file',color: 'var(--gold)'  },
  filed_by_user: { label: 'Filed',        color: 'var(--sage)'  },
};

const PR_TYPE_LABEL = { gd: 'General Diary', fir: 'First Information Report' };

const PR_INCIDENT_TYPES = [
  ['theft', 'Theft'], ['snatching', 'Snatching / mugging'], ['harassment', 'Harassment'],
  ['threat', 'Threat / intimidation'], ['lost_document', 'Lost document / item'],
  ['cyber', 'Cyber / online'], ['assault', 'Assault'], ['fraud', 'Fraud'], ['other', 'Other'],
];

function PrStatePill({ state }) {
  const m = PR_STATE_META[state] || PR_STATE_META.draft;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5, background: `${m.color}1a`,
      color: m.color, border: `1px solid ${m.color}33`, borderRadius: 999,
      padding: '3px 9px 4px', fontSize: 10.5, fontWeight: 600, fontFamily: 'var(--font-sans)',
    }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: m.color }}/>
      {m.label}
    </span>
  );
}

function PrField({ label, hint, children }) {
  return (
    <div style={{ marginBottom: 13 }}>
      <div style={{
        fontSize: 10.5, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase',
        letterSpacing: '0.12em', marginBottom: 6, fontFamily: 'var(--font-sans)',
      }}>{label}</div>
      {children}
      {hint && <div style={{ fontSize: 10.5, color: 'var(--muted)', marginTop: 4 }}>{hint}</div>}
    </div>
  );
}

const PR_INPUT_STYLE = {
  width: '100%', padding: '10px 12px', borderRadius: 10, boxSizing: 'border-box',
  border: '1px solid var(--mist)', background: 'rgba(255,255,255,0.85)',
  fontFamily: 'var(--font-sans)', fontSize: 13, color: 'var(--navy)', outline: 'none',
};

function PrInput(props) {
  return <input type="text" {...props} style={{ ...PR_INPUT_STYLE, ...(props.style || {}) }}/>;
}
function PrTextarea(props) {
  return <textarea {...props} style={{ ...PR_INPUT_STYLE, minHeight: props.minHeight || 110, resize: 'vertical', ...(props.style || {}) }}/>;
}

// ────────────────────────────────────────────────────────────────────────────
// PoliceReportsListScreen
// ────────────────────────────────────────────────────────────────────────────

function PoliceReportsListScreen() {
  const { go } = useApp();
  const [reports, setReports] = _prS([]);
  const [loading, setLoading] = _prS(true);
  const [error, setError] = _prS(null);

  _prE(() => {
    prFetch('/v1/police-reports')
      .then(setReports).catch(e => setError(e.message)).finally(() => setLoading(false));
  }, []);

  return (
    <>
      <Header title="FIR / GD drafts" subtitle="Draft · print · take to thana" back/>
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 20px 100px' }}>
        <div style={{
          background: 'rgba(196,69,54,0.06)', border: '1px solid rgba(196,69,54,0.18)',
          borderRadius: 12, padding: '11px 14px', marginBottom: 14, fontSize: 12, color: 'var(--ink-2)', lineHeight: 1.55,
        }}>
          Anchor AI drafts a formal statement you can <strong>export and print</strong>. Bangladesh police
          have no online filing — submit the printed copy at the thana yourself.
        </div>

        {loading && <div style={{ textAlign: 'center', padding: 40, color: 'var(--muted)', fontSize: 13 }}>Loading…</div>}
        {!loading && error && (
          <div style={{ padding: 16, background: 'rgba(232,49,42,0.06)', borderRadius: 12, color: 'var(--red)', fontSize: 13, textAlign: 'center' }}>{error}</div>
        )}
        {!loading && !error && reports.length === 0 && (
          <div style={{ textAlign: 'center', paddingTop: 50 }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>📄</div>
            <div className="serif" style={{ fontSize: 17, fontWeight: 500, color: 'var(--navy)', marginBottom: 6 }}>No drafts yet</div>
            <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 22 }}>Draft a General Diary or FIR in minutes.</div>
            <button onClick={() => go('new-police-report', { kind: 'gd' })} className="btn btn-primary" style={{ margin: '0 auto' }}>+ New draft</button>
          </div>
        )}
        {!loading && !error && reports.map(r => {
          const date = new Date(r.updated_at || r.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
          return (
            <button key={r.id} onClick={() => go('police-report', { id: r.id })} style={{
              width: '100%', textAlign: 'left', background: 'rgba(255,255,255,0.7)', border: '1px solid var(--mist)',
              borderRadius: 14, padding: 14, marginBottom: 10, cursor: 'pointer', display: 'flex', alignItems: 'flex-start', gap: 12,
            }}>
              <div style={{
                width: 36, height: 36, borderRadius: 10, flexShrink: 0, background: 'rgba(196,69,54,0.12)',
                border: '1px solid rgba(196,69,54,0.25)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--ember)',
              }}>
                <IconGavel size={16}/>
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
                  <span className="mono" style={{ fontSize: 10, color: 'var(--muted)' }}>{r.reference_no || PR_TYPE_LABEL[r.report_type]}</span>
                  <PrStatePill state={r.state}/>
                </div>
                <div className="serif" style={{ fontSize: 14, fontWeight: 500, color: 'var(--navy)', lineHeight: 1.25, marginBottom: 4 }}>
                  {r.subject || `${PR_TYPE_LABEL[r.report_type]} (untitled)`}
                </div>
                <div style={{ fontSize: 11, color: 'var(--muted)' }}>{r.thana || 'No thana set'} · {date}</div>
              </div>
              <IconChevronRight size={14} stroke="var(--mist-2)"/>
            </button>
          );
        })}
      </div>

      <button onClick={() => go('new-police-report', { kind: 'gd' })} style={{
        position: 'fixed', bottom: 108, right: 24, width: 52, height: 52, borderRadius: '50%',
        background: 'var(--ember)', color: '#fff', border: 'none', cursor: 'pointer',
        boxShadow: '0 4px 20px rgba(196,69,54,0.35)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 20,
      }}>
        <IconPlus size={22}/>
      </button>
    </>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// NewPoliceReportScreen — wizard
// ────────────────────────────────────────────────────────────────────────────

const PR_STEPS = ['Type', 'Describe', 'Details', 'Review', 'Done'];

function PrStepBar({ step }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-start', padding: '10px 20px 6px', gap: 0 }}>
      {PR_STEPS.map((label, i) => {
        const n = i + 1, done = n < step, active = n === step;
        return (
          <React.Fragment key={n}>
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <div style={{
                width: 26, height: 26, borderRadius: '50%',
                background: done ? 'var(--sage)' : active ? 'var(--ember)' : 'var(--mist)',
                color: done || active ? '#fff' : 'var(--muted)', display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 11, fontWeight: 700,
              }}>{done ? '✓' : n}</div>
              <div style={{ fontSize: 8.5, marginTop: 4, color: active ? 'var(--navy)' : 'var(--muted)', fontWeight: active ? 700 : 400 }}>{label}</div>
            </div>
            {i < PR_STEPS.length - 1 && <div style={{ flex: 1, height: 1.5, background: done ? 'var(--sage)' : 'var(--mist)', marginTop: 13 }}/>}
          </React.Fragment>
        );
      })}
    </div>
  );
}

function NewPoliceReportScreen({ params = {} }) {
  const { go, lang } = useApp();
  const [step, setStep] = _prS(1);
  const [reportType, setReportType] = _prS(params.kind === 'fir' ? 'fir' : 'gd');
  const [situation, setSituation] = _prS('');
  const [aiBusy, setAiBusy] = _prS(false);
  const [aiNotice, setAiNotice] = _prS(null);
  const [report, setReport] = _prS(null); // created draft on backend
  const [fields, setFields] = _prS({});
  const [saving, setSaving] = _prS(false);
  const [err, setErr] = _prS(null);

  const setF = (k, v) => setFields(f => ({ ...f, [k]: v }));

  // Ensure a draft exists on the backend; returns its id.
  const ensureDraft = async () => {
    if (report) return report;
    const created = await prFetch('/v1/police-reports', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ report_type: reportType, language: lang === 'BN' ? 'bn' : 'en' }),
    });
    setReport(created);
    return created;
  };

  const runAiDraft = async () => {
    if (situation.trim().length < 10) { setErr('Describe what happened in a sentence or two.'); return; }
    setErr(null); setAiBusy(true); setAiNotice(null);
    try {
      const draft = await prFetch('/v1/police-reports/draft-with-ai', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          report_type: reportType, situation: situation.trim(), language: lang === 'BN' ? 'bn' : 'en',
          complainant_name: fields.complainant_name || null, incident_type: fields.incident_type || null,
          incident_datetime: fields.incident_datetime || null, location: fields.location || null,
        }),
      });
      setFields(f => ({ ...f, subject: draft.subject, narrative: draft.narrative }));
      setAiNotice(draft.notice || (draft.ai_assisted ? 'Drafted by Anchor AI. Review and edit before finalizing.' : null));
      await ensureDraft();
      setStep(3);
    } catch (e) {
      setErr(e.message);
    } finally {
      setAiBusy(false);
    }
  };

  const saveAndContinue = async (nextStep) => {
    setSaving(true); setErr(null);
    try {
      const d = await ensureDraft();
      const updated = await prFetch(`/v1/police-reports/${d.id}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...fields, language: lang === 'BN' ? 'bn' : 'en' }),
      });
      setReport(updated);
      setStep(nextStep);
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  const finalize = async () => {
    setSaving(true); setErr(null);
    try {
      const d = await ensureDraft();
      await prFetch(`/v1/police-reports/${d.id}`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(fields),
      });
      const finalized = await prFetch(`/v1/police-reports/${d.id}/finalize`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
      });
      setReport(finalized);
      setStep(5);
    } catch (e) {
      setErr(e.message);
    } finally {
      setSaving(false);
    }
  };

  const ErrBar = () => err ? (
    <div style={{ color: 'var(--red)', fontSize: 12.5, background: 'rgba(232,49,42,0.07)', borderRadius: 10, padding: '9px 13px', marginBottom: 12 }}>{err}</div>
  ) : null;

  // ── Step 1: type ──────────────────────────────────────────────────────────
  if (step === 1) return (
    <>
      <Header title="Draft FIR / GD" subtitle="Choose document type" back/>
      <PrStepBar step={step}/>
      <div style={{ padding: '14px 20px 100px' }}>
        <div className="eyebrow" style={{ marginBottom: 12 }}>What do you need to file?</div>
        {[
          { k: 'gd', t: 'General Diary (GD)', d: 'Record a minor incident — lost item, snatching, threat, missing document. Most common.' },
          { k: 'fir', t: 'First Information Report (FIR)', d: 'Report a cognizable offence — assault, robbery, serious crime — that police must investigate.' },
        ].map(o => (
          <button key={o.k} onClick={() => { setReportType(o.k); setStep(2); }} style={{
            width: '100%', textAlign: 'left', background: reportType === o.k ? 'rgba(196,69,54,0.06)' : 'rgba(255,255,255,0.7)',
            border: `1px solid ${reportType === o.k ? 'var(--ember)' : 'var(--mist)'}`, borderRadius: 14, padding: 16, marginBottom: 10, cursor: 'pointer',
          }}>
            <div className="serif" style={{ fontSize: 16, fontWeight: 500, color: 'var(--navy)', marginBottom: 5 }}>{o.t}</div>
            <div style={{ fontSize: 12.5, color: 'var(--muted)', lineHeight: 1.5 }}>{o.d}</div>
          </button>
        ))}
      </div>
    </>
  );

  // ── Step 2: describe + AI ─────────────────────────────────────────────────
  if (step === 2) return (
    <>
      <Header title={PR_TYPE_LABEL[reportType]} subtitle="Describe what happened" back/>
      <PrStepBar step={step}/>
      <div style={{ flex: 1, overflowY: 'auto', padding: '14px 20px 120px' }}>
        <ErrBar/>
        <div className="ai-tag" style={{ marginBottom: 10 }}><IconSparkles size={10} stroke="var(--gold)"/> Anchor AI will draft a formal statement</div>
        <PrField label="In your own words" hint="Plain language is fine — include where, when, and what happened.">
          <PrTextarea value={situation} onChange={e => setSituation(e.target.value)} minHeight={140}
            placeholder="e.g. My phone was snatched near Mirpur-10 circle around 9:30 PM by two men on a motorbike."/>
        </PrField>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <PrField label="When"><PrInput value={fields.incident_datetime || ''} onChange={e => setF('incident_datetime', e.target.value)} placeholder="18 May 2026, 9:30 PM"/></PrField>
          <PrField label="Where"><PrInput value={fields.location || ''} onChange={e => setF('location', e.target.value)} placeholder="Mirpur-10, Dhaka"/></PrField>
        </div>
      </div>
      <div style={{ padding: '12px 20px 24px', borderTop: '1px solid var(--mist)', background: 'var(--cream)' }}>
        <button onClick={runAiDraft} disabled={aiBusy} className="btn btn-primary" style={{ width: '100%', marginBottom: 8 }}>
          {aiBusy ? 'Drafting…' : '✨ Draft with Anchor AI'}
        </button>
        <button onClick={async () => { await ensureDraft(); setStep(3); }} style={{ background: 'none', border: 'none', color: 'var(--muted)', fontSize: 12, cursor: 'pointer', width: '100%' }}>
          Skip — I'll write it myself →
        </button>
      </div>
    </>
  );

  // ── Step 3: structured details ────────────────────────────────────────────
  if (step === 3) return (
    <>
      <Header title="Details" subtitle="Complete the report" back/>
      <PrStepBar step={step}/>
      <div style={{ flex: 1, overflowY: 'auto', padding: '14px 20px 120px' }}>
        <ErrBar/>
        {aiNotice && (
          <div style={{ background: 'rgba(184,137,58,0.08)', border: '1px solid rgba(184,137,58,0.25)', borderRadius: 10, padding: '10px 13px', marginBottom: 14, fontSize: 12, color: 'var(--ink-2)', lineHeight: 1.5 }}>
            {aiNotice}
          </div>
        )}
        <PrField label="Subject"><PrInput value={fields.subject || ''} onChange={e => setF('subject', e.target.value)} placeholder="Short title of the report"/></PrField>
        <PrField label="Statement"><PrTextarea value={fields.narrative || ''} onChange={e => setF('narrative', e.target.value)} minHeight={150} placeholder="The full formal statement…"/></PrField>

        <div className="eyebrow" style={{ margin: '8px 0 10px' }}>Complainant</div>
        <PrField label="Your full name"><PrInput value={fields.complainant_name || ''} onChange={e => setF('complainant_name', e.target.value)} placeholder="As on your NID"/></PrField>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <PrField label="Guardian name"><PrInput value={fields.guardian_name || ''} onChange={e => setF('guardian_name', e.target.value)} placeholder="Father / mother"/></PrField>
          <PrField label="Phone"><PrInput value={fields.phone || ''} onChange={e => setF('phone', e.target.value)} placeholder="+8801…"/></PrField>
        </div>
        <PrField label="Address"><PrInput value={fields.address || ''} onChange={e => setF('address', e.target.value)} placeholder="House, road, area, district"/></PrField>
        <PrField label="NID (optional)"><PrInput value={fields.nid || ''} onChange={e => setF('nid', e.target.value)} placeholder="National ID number"/></PrField>

        <div className="eyebrow" style={{ margin: '8px 0 10px' }}>Incident</div>
        <PrField label="Type">
          <select value={fields.incident_type || ''} onChange={e => setF('incident_type', e.target.value)} style={{ ...PR_INPUT_STYLE }}>
            <option value="">Select…</option>
            {PR_INCIDENT_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </PrField>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          <PrField label="Thana (police station)"><PrInput value={fields.thana || ''} onChange={e => setF('thana', e.target.value)} placeholder="e.g. Mirpur Model Thana"/></PrField>
          <PrField label="District"><PrInput value={fields.district || ''} onChange={e => setF('district', e.target.value)} placeholder="Dhaka"/></PrField>
        </div>
        <PrField label="Property / item details (optional)"><PrInput value={fields.property_details || ''} onChange={e => setF('property_details', e.target.value)} placeholder="e.g. Samsung A54, IMEI…"/></PrField>
        <PrField label="Accused / suspect (optional)"><PrInput value={fields.accused_details || ''} onChange={e => setF('accused_details', e.target.value)} placeholder="Description, if known"/></PrField>
        <PrField label="Witnesses (optional)"><PrInput value={fields.witnesses || ''} onChange={e => setF('witnesses', e.target.value)} placeholder="Names / contacts"/></PrField>
      </div>
      <div style={{ padding: '12px 20px 24px', borderTop: '1px solid var(--mist)', background: 'var(--cream)' }}>
        <button onClick={() => saveAndContinue(4)} disabled={saving} className="btn btn-primary" style={{ width: '100%' }}>
          {saving ? 'Saving…' : 'Review →'}
        </button>
      </div>
    </>
  );

  // ── Step 4: review ────────────────────────────────────────────────────────
  if (step === 4) return (
    <>
      <Header title="Review" subtitle="Check before finalizing" back/>
      <PrStepBar step={step}/>
      <div style={{ flex: 1, overflowY: 'auto', padding: '14px 20px 120px' }}>
        <ErrBar/>
        <div className="doc-paper">
          <div className="doc-header">
            <span>{PR_TYPE_LABEL[reportType]}</span>
            <span style={{ color: 'var(--gold)' }}>Draft · review</span>
          </div>
          <div className="doc-line lbl">To</div>
          <div className="doc-line" style={{ whiteSpace: 'pre-line' }}>{`The Officer-in-Charge\n${fields.thana || '—'}${fields.district ? ', ' + fields.district : ''}`}</div>
          <div className="doc-line subject">Subject: {fields.subject || '—'}</div>
          <div className="doc-body" style={{ whiteSpace: 'pre-wrap' }}>{fields.narrative || '—'}</div>
          <div className="doc-sig">
            <em>Sincerely,</em><br/>
            <span style={{ whiteSpace: 'pre-line' }}>{`${fields.complainant_name || '—'}${fields.phone ? '\n' + fields.phone : ''}`}</span>
          </div>
        </div>
      </div>
      <div style={{ padding: '12px 20px 24px', borderTop: '1px solid var(--mist)', background: 'var(--cream)' }}>
        <button onClick={finalize} disabled={saving} className="btn btn-primary" style={{ width: '100%', marginBottom: 8 }}>
          {saving ? 'Finalizing…' : 'Finalize report'}
        </button>
        <button onClick={() => setStep(3)} disabled={saving} style={{ background: 'none', border: 'none', color: 'var(--muted)', fontSize: 12, cursor: 'pointer', width: '100%' }}>← Edit details</button>
      </div>
    </>
  );

  // ── Step 5: done ──────────────────────────────────────────────────────────
  return (
    <>
      <Header title="Finalized" back={false}/>
      <div style={{ padding: '32px 20px 100px' }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={{ width: 64, height: 64, borderRadius: 18, background: 'rgba(74,107,92,0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px', color: 'var(--sage)' }}>
            <IconCheck size={30} sw={2.5}/>
          </div>
          <div className="serif" style={{ fontSize: 22, fontWeight: 600, color: 'var(--navy)', marginBottom: 6 }}>{PR_TYPE_LABEL[reportType]} ready</div>
          <div className="mono" style={{ fontSize: 13, color: 'var(--muted)' }}>{report?.reference_no}</div>
        </div>
        <div style={{ background: 'rgba(196,69,54,0.06)', border: '1px solid rgba(196,69,54,0.18)', borderRadius: 12, padding: '14px 16px', marginBottom: 20, fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.6 }}>
          Download the document, <strong>print and sign it</strong>, then submit it in person at {fields.thana || 'the thana'}. Keep your reference number.
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
          <button onClick={() => prDownload(`/v1/police-reports/${report.id}/export?format=pdf`, `${report.reference_no}.pdf`).catch(e => alert(e.message))} className="btn btn-primary">⬇ PDF</button>
          <button onClick={() => prDownload(`/v1/police-reports/${report.id}/export?format=docx`, `${report.reference_no}.docx`).catch(e => alert(e.message))} className="btn btn-ghost">⬇ DOCX</button>
        </div>
        <button onClick={() => go('police-report', { id: report.id })} className="btn btn-ghost" style={{ width: '100%', marginBottom: 10 }}>View report</button>
        <button onClick={() => go('police-reports')} style={{ background: 'none', border: 'none', color: 'var(--muted)', fontSize: 12, cursor: 'pointer', width: '100%' }}>Back to my drafts</button>
      </div>
    </>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// PoliceReportDetailScreen
// ────────────────────────────────────────────────────────────────────────────

function PoliceReportDetailScreen({ params = {} }) {
  const { go, back } = useApp();
  const [report, setReport] = _prS(null);
  const [loading, setLoading] = _prS(true);
  const [error, setError] = _prS(null);
  const [busy, setBusy] = _prS(false);

  const load = () => prFetch(`/v1/police-reports/${params.id}`).then(setReport).catch(e => setError(e.message)).finally(() => setLoading(false));
  _prE(() => { load(); }, [params.id]);

  const markFiled = async () => {
    if (!window.confirm('Mark this report as filed at the thana?')) return;
    setBusy(true);
    try { setReport(await prFetch(`/v1/police-reports/${params.id}/mark-filed`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })); }
    catch (e) { alert(e.message); } finally { setBusy(false); }
  };

  if (loading) return <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--cream)', color: 'var(--muted)', fontSize: 13 }}>Loading…</div>;
  if (error || !report) return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 14, alignItems: 'center', justifyContent: 'center', background: 'var(--cream)' }}>
      <div style={{ color: 'var(--red)', fontSize: 13 }}>{error || 'Report not found'}</div>
      <button onClick={back} className="btn btn-ghost" style={{ fontSize: 12 }}>Go back</button>
    </div>
  );

  const dl = (fmt) => prDownload(`/v1/police-reports/${report.id}/export?format=${fmt}`, `${report.reference_no || report.report_type}.${fmt}`).catch(e => alert(e.message));

  return (
    <>
      <Header title={PR_TYPE_LABEL[report.report_type]} back/>
      <div style={{ overflowY: 'auto', padding: '14px 20px 120px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <span className="mono" style={{ fontSize: 12, color: 'var(--muted)' }}>{report.reference_no || 'Draft'}</span>
          <PrStatePill state={report.state}/>
        </div>

        {report.state === 'draft' && (
          <div style={{ background: 'rgba(184,137,58,0.08)', border: '1px solid rgba(184,137,58,0.25)', borderRadius: 10, padding: '11px 14px', marginBottom: 14, fontSize: 12.5, color: 'var(--ink-2)' }}>
            This report is still a draft. Continue editing to finalize it.
            <div style={{ marginTop: 8 }}>
              <button onClick={() => go('new-police-report', { kind: report.report_type })} className="btn btn-ghost" style={{ fontSize: 12 }}>Continue editing</button>
            </div>
          </div>
        )}

        <div className="doc-paper">
          <div className="doc-header"><span>{PR_TYPE_LABEL[report.report_type]}</span><span>{report.reference_no || 'Draft'}</span></div>
          <div className="doc-line lbl">To</div>
          <div className="doc-line" style={{ whiteSpace: 'pre-line' }}>{`The Officer-in-Charge\n${report.thana || '—'}${report.district ? ', ' + report.district : ''}`}</div>
          <div className="doc-line subject">Subject: {report.subject || '—'}</div>
          <div className="doc-body" style={{ whiteSpace: 'pre-wrap' }}>{report.narrative || '—'}</div>
          <div className="doc-sig"><em>Sincerely,</em><br/><span style={{ whiteSpace: 'pre-line' }}>{`${report.complainant_name || '—'}${report.phone ? '\n' + report.phone : ''}`}</span></div>
        </div>

        {report.state !== 'draft' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 16 }}>
            <button onClick={() => dl('pdf')} className="btn btn-primary">⬇ PDF</button>
            <button onClick={() => dl('docx')} className="btn btn-ghost">⬇ DOCX</button>
          </div>
        )}
        {report.state === 'finalized' && (
          <button onClick={markFiled} disabled={busy} className="btn btn-ghost" style={{ width: '100%', marginTop: 10 }}>
            {busy ? '…' : '✓ I have filed this at the thana'}
          </button>
        )}
      </div>
    </>
  );
}
