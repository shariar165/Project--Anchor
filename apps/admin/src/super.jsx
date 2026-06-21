// Super Admin screens
var { useState, useEffect, useCallback, useRef, useMemo } = React;

// Map a free-form RAG/component health string to a StatusPill tone.
function _ragHealthTone(status) {
  const s = String(status || '').toLowerCase();
  if (/(unavailable|down|error|fail|offline|false)/.test(s)) return 'down';
  if (/(ok|healthy|up|ready|loaded|online|reachable|true)/.test(s)) return 'healthy';
  return 'degraded';
}
// Average MTTR across incidents, formatted as "Xm" / "X.Yh".
function _avgMttr(items) {
  const vals = (items || []).map(i => i.mttr_seconds).filter(v => v != null && v > 0);
  if (!vals.length) return null;
  const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
  const m = Math.round(avg / 60);
  return m >= 60 ? `${(m / 60).toFixed(1)}h` : `${m}m`;
}
// Convert a [{date,count}] series into a plain number[] for <Sparkline>.
function _sparkVals(series) {
  if (!Array.isArray(series)) return null;
  return series.map(pt => (pt && typeof pt === 'object') ? (pt.count || 0) : (pt || 0));
}

function SuperDashboard({ onGo }) {
  const [recentAudit, setRecentAudit] = useState([]);
  const [tenants, setTenants] = useState([]);
  const [deanonStats, setDeanonStats] = useState(null);
  const [analytics, setAnalytics] = useState(null);
  const [aiHealth, setAiHealth] = useState(null);
  const [incidents, setIncidents] = useState(null);
  useEffect(() => {
    AnchorAPI.apiGet('/v1/admin/audit?limit=5').then(d => setRecentAudit(d.items || [])).catch(() => {});
    AnchorAPI.apiGet('/v1/super-admin/tenants').then(d => setTenants(d.items || [])).catch(() => {});
    AnchorAPI.apiGet('/v1/admin/deanonymization/stats').then(setDeanonStats).catch(() => {});
    AnchorAPI.apiGet('/v1/super-admin/analytics').then(setAnalytics).catch(() => {});
    AnchorAPI.apiGet('/v1/super-admin/ai-health').then(setAiHealth).catch(() => {});
    AnchorAPI.apiGet('/v1/super-admin/incidents?limit=20').then(setIncidents).catch(() => {});
  }, []);
  const a = analytics || {};
  const aTenants = a.tenants || {};
  const aUsers = a.users || {};
  const aAlerts = a.alerts || {};
  const aContent = a.content || {};
  const aSeries = a.series || {};
  const pilotCount = aTenants.pilot != null ? aTenants.pilot : tenants.filter(t => t.tier === 'pilot').length;
  const suspendedCount = aTenants.suspended != null ? aTenants.suspended : tenants.filter(t => !t.active).length;
  const activeUserCount = (aUsers.by_status && aUsers.by_status.active) || null;
  const healthComponents = (aiHealth && aiHealth.components) || null;
  const healthOk = aiHealth ? aiHealth.rag_reachable : null;
  const openIncidents = incidents ? incidents.open_count : null;
  const mttr = incidents ? _avgMttr(incidents.items) : null;
  return (
    <>
      <PageHeader
        title="Platform operations"
        bn="প্ল্যাটফর্ম অপারেশনস"
        description="System-wide health, anonymized aggregate metrics, and critical actions across all university tenants."
        actions={<>
          <GhostButton icon="download" size="sm">Status report</GhostButton>
          <PrimaryButton icon="plus" mode="ember" size="sm" onClick={()=>onGo('/super/onboard')}>Onboard university</PrimaryButton>
        </>}
      />

      {deanonStats && deanonStats.open_total > 0 && (
        <AuditNote tone="red" icon="shield-alert" className="mb-4">
          <span>
            {deanonStats.open_total} de-anonymization {deanonStats.open_total === 1 ? 'request is' : 'requests are'} awaiting review
            {deanonStats.awaiting_second_approval > 0 && <> — {deanonStats.awaiting_second_approval} awaiting a second approval</>}.
          </span>
          <button onClick={()=>onGo('/super/deanonymization')} className="underline font-medium ml-1">Review →</button>
        </AuditNote>
      )}

      <div className="grid grid-cols-5 gap-4 mb-6">
        <KpiCard label="Universities" value={(aTenants.total != null ? aTenants.total : tenants.length).toLocaleString()} subtle={`${pilotCount} pilot · ${suspendedCount} suspended`} accent="navy" />
        <KpiCard label="Active users" value={aUsers.total != null ? aUsers.total.toLocaleString() : '—'} subtle={activeUserCount != null ? `${activeUserCount.toLocaleString()} active` : 'all tenants'} />
        <KpiCard label="Open cases" value={aContent.filings != null ? ((aContent.filings || 0) + (aContent.applications || 0)).toLocaleString() : '—'} subtle="filings + applications" accent="ember" />
        <KpiCard label="Active alerts" value={aAlerts.active != null ? aAlerts.active.toLocaleString() : '—'} subtle="platform-wide" accent="ember" />
        <KpiCard label="AI / RAG" value={healthOk == null ? '…' : (healthOk ? 'Operational' : 'Degraded')} delta={healthOk ? 'OK' : null} deltaTone={healthOk ? 'up' : undefined} subtle="live health" />
      </div>

      <div className="grid gap-4" style={{ gridTemplateColumns: '1.4fr 1fr' }}>
        <Card>
          <SectionLabel right={<MonoChip>health</MonoChip>}>System health · AI subsystem</SectionLabel>
          {!aiHealth
            ? <div className="text-[12px] text-[var(--muted)] py-6 text-center">Loading health…</div>
            : <div className="grid grid-cols-2 gap-2">
                {Object.entries(healthComponents || {}).map(([name, status]) => {
                  const tone = _ragHealthTone(status);
                  return (
                    <div key={name} className="hair border rounded-sm p-3 flex items-center gap-3">
                      <span className="w-2 h-2 rounded-full shrink-0" style={{ background: tone==='healthy'?'#4A6B5C':tone==='degraded'?'#B8893A':'#E8312A' }} />
                      <div className="flex-1 min-w-0">
                        <div className="text-[13px] text-[var(--ink)] truncate capitalize">{name}</div>
                        <div className="text-[11px] text-[var(--muted)] font-mono truncate">{String(status)}</div>
                      </div>
                      <StatusPill status={tone} dot={false} />
                    </div>
                  );
                })}
                {(aiHealth.namespaces || []).map(ns => (
                  <div key={ns.namespace} className="hair border rounded-sm p-3 flex items-center gap-3">
                    <span className="w-2 h-2 rounded-full shrink-0" style={{ background:'#4A6B5C' }} />
                    <div className="flex-1 min-w-0">
                      <div className="text-[13px] text-[var(--ink)] truncate">corpus · {ns.namespace}</div>
                      <div className="text-[11px] text-[var(--muted)] font-mono truncate">{(ns.documents||0).toLocaleString()} docs · {(ns.dense_chunks||0).toLocaleString()} chunks</div>
                    </div>
                  </div>
                ))}
              </div>}
          <div className="mt-4 hair-t pt-3 text-[12px] text-[var(--muted)] flex items-center justify-between">
            <span>Open incidents</span>
            <span className="font-mono">{openIncidents == null ? '—' : `${openIncidents} open${mttr ? ` · MTTR ${mttr}` : ''}`}</span>
          </div>
        </Card>

        <Card>
          <SectionLabel right={<MonoChip>anonymized</MonoChip>}>Platform activity · last 14 days</SectionLabel>
          {!analytics
            ? <div className="text-[12px] text-[var(--muted)] py-6 text-center">Loading activity…</div>
            : <div className="space-y-3">
                {[
                  { k:'Alerts triggered', v:aAlerts.total, spark:_sparkVals(aSeries.alerts_14d) },
                  { k:'Filings submitted', v:aContent.filings, spark:_sparkVals(aSeries.filings_14d) },
                  { k:'Feed posts', v:aContent.feed_posts, spark:_sparkVals(aSeries.feed_14d) },
                  { k:'Applications', v:aContent.applications, spark:null },
                  { k:'AI queries · 24h', v:(aiHealth && aiHealth.usage && aiHealth.usage.ai_chat_24h), spark:null },
                ].map(r => (
                  <div key={r.k} className="flex items-center gap-3 hair-b border-b last:border-b-0 pb-2">
                    <div className="flex-1">
                      <div className="text-[13px] text-[var(--ink)]">{r.k}</div>
                      <div className="font-mono text-[18px] text-[var(--navy)] leading-tight">{r.v == null ? '—' : r.v.toLocaleString()}</div>
                    </div>
                    {r.spark && r.spark.length > 1 && <Sparkline values={r.spark} />}
                  </div>
                ))}
              </div>}
        </Card>
      </div>

      <div className="grid grid-cols-2 gap-4 mt-4">
        <Card noPad>
          <div className="p-4 hair-b flex items-center justify-between">
            <SectionLabel className="mb-0">Tenants</SectionLabel>
            <button onClick={()=>onGo('/super/tenants')} className="text-[12px] text-[var(--ember)] hover:underline">All tenants →</button>
          </div>
          {tenants.length === 0
            ? <div className="p-4 text-[12px] text-[var(--muted)]">No universities onboarded yet.</div>
            : <DataTable
                columns={[
                  { key:'name', label:'University' },
                  { key:'status', label:'Status', render:r=><StatusPill status={r.status} /> },
                  { key:'user_count', label:'Users', align:'right', render:r=><span className="font-mono">{(r.user_count||0).toLocaleString()}</span> },
                ]}
                rows={tenants}
                onRowClick={(r)=>onGo(`/super/tenant/${r.id}`)}
                dense
              />}
        </Card>
        <Card noPad>
          <div className="p-4 hair-b flex items-center justify-between">
            <SectionLabel className="mb-0">Recent audit events</SectionLabel>
            <button onClick={()=>onGo('/super/audit-logs')} className="text-[12px] text-[var(--ember)] hover:underline">Open log explorer →</button>
          </div>
          <DataTable
            columns={[
              { key:'created_at', label:'Time', render:r=><span className="font-mono text-[11px] text-[var(--muted)]">{new Date(r.created_at).toLocaleString('en-GB',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'})}</span> },
              { key:'event_type', label:'Action', render:r=><MonoChip>{r.event_type}</MonoChip> },
              { key:'actor', label:'Actor', render:r=><span>{(r.actor && r.actor.masked_email) || 'system'}</span> },
            ]}
            rows={recentAudit}
            dense
          />
        </Card>
      </div>
    </>
  );
}

function Sparkline({ values, color='var(--ember)' }) {
  const w = 60, h = 24, max = Math.max(...values), min = Math.min(...values);
  const pts = values.map((v, i) => {
    const x = (i/(values.length-1))*w;
    const y = h - ((v-min)/(max-min||1))*(h-4) - 2;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  return (
    <svg width={w} height={h}>
      <polyline points={pts} fill="none" stroke={color} strokeWidth="1.5" />
    </svg>
  );
}

// ---- Tenants ----
function fmtDate(s) {
  if (!s) return '—';
  try { return new Date(s).toLocaleDateString('en-GB', { day:'2-digit', month:'short', year:'numeric' }); }
  catch { return '—'; }
}

function SuperTenants({ onGo }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    AnchorAPI.apiGet('/v1/super-admin/tenants')
      .then(d => setRows(d.items || []))
      .catch(e => setError(e.message || 'Failed to load tenants'))
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  return (
    <>
      <PageHeader
        title="University tenants"
        description="All onboarded universities. Click a row to view detail. Onboarding provisions a tenant with its own verified email domain(s) and an initial admin account."
        actions={<PrimaryButton icon="plus" mode="ember" onClick={()=>onGo('/super/onboard')}>Onboard new</PrimaryButton>}
      />
      {error && (
        <div className="mb-4">
          <AuditNote tone="red" icon="alert-triangle">
            <span>{error} </span>
            <button onClick={load} className="underline font-medium ml-1">Retry →</button>
          </AuditNote>
        </div>
      )}
      <Card noPad>
        {loading
          ? <div className="p-10 text-center text-[13px] text-[var(--muted)]">Loading universities…</div>
          : rows.length === 0 && !error
            ? <EmptyState icon="building-2" title="No universities yet"
                body="Onboard your first university to provision its tenant, email domains, and an initial admin account."
                action={<PrimaryButton icon="plus" mode="ember" onClick={()=>onGo('/super/onboard')}>Onboard new</PrimaryButton>} />
            : <DataTable
                columns={[
                  { key:'name', label:'University', render:r=><div><div className="font-medium text-[var(--ink)]">{r.name}</div><div className="text-[11px] text-[var(--muted)] font-mono">{(r.domains||[]).map(d=>'@'+d.domain).join(', ') || '—'}</div></div> },
                  { key:'status', label:'Status', render:r=><StatusPill status={r.status} /> },
                  { key:'user_count', label:'Users', align:'right', render:r=><span className="font-mono">{(r.user_count||0).toLocaleString()}</span> },
                  { key:'vector_namespace', label:'Vector ns', render:r=><MonoChip>{r.vector_namespace || r.slug}</MonoChip> },
                  { key:'contact_name', label:'Primary contact', render:r=>r.contact_name || <span className="text-[var(--muted)]">—</span> },
                  { key:'created_at', label:'Onboarded', render:r=><span className="font-mono text-[12px] text-[var(--muted)]">{fmtDate(r.created_at)}</span> },
                ]}
                rows={rows}
                onRowClick={(r)=>onGo(`/super/tenant/${r.id}`)}
              />}
      </Card>
    </>
  );
}

const INPUT_CLS = "w-full px-3 py-2 hair border rounded-sm bg-white text-[13px]";

function slugify(s) {
  return (s || '').toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40);
}

function SuperOnboard({ onGo }) {
  const steps = ['University info','Initial admin','Confirmation'];
  const [step, setStep] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [slugTouched, setSlugTouched] = useState(false);
  const [f, setF] = useState({
    name: '', slug: '', domains: '', country: 'Bangladesh', tier: 'pilot',
    contact_name: '', vector_namespace: '',
    admin_name: '', admin_email: '', admin_password: '',
  });
  const set = (k, v) => setF(prev => ({ ...prev, [k]: v }));

  // Auto-derive slug from name until the user edits the slug directly.
  const onName = (v) => setF(prev => ({ ...prev, name: v, slug: slugTouched ? prev.slug : slugify(v) }));

  const domainList = f.domains.split(',').map(d => d.trim().replace(/^@/, '').toLowerCase()).filter(Boolean);

  const stepValid = (s) => {
    if (s === 0) return f.name.trim() && f.slug.trim() && domainList.length > 0;
    if (s === 1) return f.admin_name.trim() && /.+@.+\..+/.test(f.admin_email) && f.admin_password.length >= 8;
    return true;
  };
  const canSubmit = stepValid(0) && stepValid(1);

  const submit = async () => {
    setError(null);
    setSubmitting(true);
    try {
      const payload = {
        name: f.name.trim(),
        slug: f.slug.trim(),
        email_domains: domainList,
        tier: f.tier,
        country: f.country.trim() || null,
        contact_name: f.contact_name.trim() || null,
        vector_namespace: f.vector_namespace.trim() || null,
        initial_admin: {
          full_name: f.admin_name.trim(),
          email: f.admin_email.trim(),
          password: f.admin_password,
        },
      };
      const created = await AnchorAPI.apiPostAuth('/v1/super-admin/tenants', payload);
      onGo(`/super/tenant/${created.id}`);
    } catch (e) {
      setError(e.message || 'Onboarding failed');
      setSubmitting(false);
    }
  };

  return (
    <>
      <PageHeader
        title="Onboard new university"
        description="Provision a new tenant with its own verified email domain(s), RAG vector namespace, and an initial university admin account."
      />
      {error && (
        <div className="mb-4"><AuditNote tone="red" icon="alert-triangle">{error}</AuditNote></div>
      )}
      <div className="grid gap-5" style={{ gridTemplateColumns: '260px 1fr' }}>
        <Card noPad>
          <ol>
            {steps.map((s, i) => (
              <li key={s} className={`p-3 hair-b last:border-b-0 flex items-center gap-3 ${i===step?'bg-[var(--ember-tint)]/40':''}`}>
                <div className="w-6 h-6 rounded-full flex items-center justify-center font-mono text-[11px]" style={{ background: i<step?'var(--ember)':'var(--mist)', color: i<step?'white':'var(--graphite)'}}>
                  {i<step ? <Icon name="check" size={11} /> : i+1}
                </div>
                <span className={`text-[13px] ${i===step?'font-medium text-[var(--ember)]':'text-[var(--ink)]'}`}>{s}</span>
              </li>
            ))}
          </ol>
        </Card>
        <Card>
          <SectionLabel>Step {step+1} · {steps[step]}</SectionLabel>

          {step===0 && (
            <div className="grid grid-cols-2 gap-3">
              <Field label="University name"><input value={f.name} onChange={e=>onName(e.target.value)} placeholder="Bangladesh University of Engineering & Technology" className={INPUT_CLS} /></Field>
              <Field label="Slug (unique)" hint="Used as the tenant key and default vector namespace."><input value={f.slug} onChange={e=>{setSlugTouched(true); set('slug', slugify(e.target.value));}} placeholder="buet" className={INPUT_CLS + ' font-mono'} /></Field>
              <Field label="Verified email domain(s)" hint="Comma-separate multiple. The leading @ is optional."><input value={f.domains} onChange={e=>set('domains', e.target.value)} placeholder="buet.ac.bd, eee.buet.ac.bd" className={INPUT_CLS + ' font-mono'} /></Field>
              <Field label="Primary contact (optional)"><input value={f.contact_name} onChange={e=>set('contact_name', e.target.value)} placeholder="Dr. Anwar Hossain" className={INPUT_CLS} /></Field>
              <Field label="Country"><input value={f.country} onChange={e=>set('country', e.target.value)} className={INPUT_CLS} /></Field>
              <Field label="Tier">
                <select value={f.tier} onChange={e=>set('tier', e.target.value)} className={INPUT_CLS}>
                  <option value="pilot">Pilot</option>
                  <option value="active">Active</option>
                </select>
              </Field>
              <Field label="Vector namespace (optional)" hint="Defaults to the slug if left blank."><input value={f.vector_namespace} onChange={e=>set('vector_namespace', e.target.value)} placeholder={f.slug || 'buet'} className={INPUT_CLS + ' font-mono'} /></Field>
            </div>
          )}

          {step===1 && (
            <div className="grid grid-cols-2 gap-3">
              <Field label="Admin full name"><input value={f.admin_name} onChange={e=>set('admin_name', e.target.value)} placeholder="Registrar Office" className={INPUT_CLS} /></Field>
              <Field label="Admin email"><input value={f.admin_email} onChange={e=>set('admin_email', e.target.value)} placeholder="admin@buet.ac.bd" className={INPUT_CLS + ' font-mono'} /></Field>
              <Field label="Temporary password" hint="At least 8 characters. The admin should change it after first login."><input type="password" value={f.admin_password} onChange={e=>set('admin_password', e.target.value)} className={INPUT_CLS} /></Field>
              <div className="col-span-2"><AuditNote tone="navy" icon="info">This creates one active <span className="font-mono">admin</span> account scoped to the new tenant. Add more staff later from User management.</AuditNote></div>
            </div>
          )}

          {step===2 && (
            <div className="space-y-2 text-[13px]">
              <div className="grid grid-cols-2 gap-y-2 gap-x-4">
                <div><span className="text-[var(--muted)]">University:</span> <span className="text-[var(--ink)] font-medium">{f.name || '—'}</span></div>
                <div><span className="text-[var(--muted)]">Slug:</span> <MonoChip>{f.slug || '—'}</MonoChip></div>
                <div><span className="text-[var(--muted)]">Domains:</span> <span className="font-mono">{domainList.map(d=>'@'+d).join(', ') || '—'}</span></div>
                <div><span className="text-[var(--muted)]">Tier:</span> <StatusPill status={f.tier==='pilot'?'Pilot':'Active'} /></div>
                <div><span className="text-[var(--muted)]">Namespace:</span> <MonoChip>{f.vector_namespace || f.slug || '—'}</MonoChip></div>
                <div><span className="text-[var(--muted)]">Contact:</span> {f.contact_name || '—'}</div>
                <div><span className="text-[var(--muted)]">Admin:</span> {f.admin_name || '—'} <span className="font-mono text-[var(--muted)]">{f.admin_email || ''}</span></div>
              </div>
              {!canSubmit && <AuditNote tone="red" icon="alert-triangle">Some required fields are missing — go back and complete University info and Initial admin.</AuditNote>}
            </div>
          )}

          <div className="mt-5 flex items-center justify-between">
            <GhostButton onClick={()=> step===0 ? onGo('/super/tenants') : setStep(s=>s-1)}>{step===0 ? 'Cancel' : 'Back'}</GhostButton>
            {step < steps.length-1
              ? <PrimaryButton mode="ember" icon="arrow-right" onClick={()=>setStep(s=>s+1)} disabled={!stepValid(step)} className={!stepValid(step)?'opacity-50 pointer-events-none':''}>Continue</PrimaryButton>
              : <PrimaryButton mode="ember" icon="check" onClick={submit} disabled={!canSubmit || submitting} className={(!canSubmit||submitting)?'opacity-50 pointer-events-none':''}>{submitting ? 'Provisioning…' : 'Finish onboarding'}</PrimaryButton>}
          </div>
        </Card>
      </div>
    </>
  );
}

function SuperTenantDetail({ id, onGo }) {
  const [tenant, setTenant] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionError, setActionError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [confirmSuspend, setConfirmSuspend] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [configOpen, setConfigOpen] = useState(false);
  const [newDomain, setNewDomain] = useState('');

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    AnchorAPI.apiGet(`/v1/super-admin/tenants/${id}`)
      .then(setTenant)
      .catch(e => setError(e.message || 'Failed to load tenant'))
      .finally(() => setLoading(false));
  }, [id]);
  useEffect(() => { load(); }, [load]);

  const run = async (fn) => {
    setActionError(null);
    setBusy(true);
    try { await fn(); }
    catch (e) { setActionError(e.message || 'Action failed'); }
    finally { setBusy(false); }
  };

  const setActive = (active) => run(async () => {
    const updated = await AnchorAPI.apiPatch(`/v1/super-admin/tenants/${id}`, { active });
    setTenant(updated);
  });

  const addDomain = () => run(async () => {
    const updated = await AnchorAPI.apiPostAuth(`/v1/super-admin/tenants/${id}/domains`, { domain: newDomain });
    setNewDomain('');
    setTenant(updated);
  });

  const removeDomain = (domainId) => run(async () => {
    await AnchorAPI.apiDelete(`/v1/super-admin/tenants/${id}/domains/${domainId}`);
    load();
  });

  const doDelete = () => run(async () => {
    await AnchorAPI.apiDelete(`/v1/super-admin/tenants/${id}`);
    onGo('/super/tenants');
  });

  if (loading) return <div className="p-10 text-center text-[13px] text-[var(--muted)]">Loading tenant…</div>;
  if (error) return (
    <>
      <PageHeader title="University tenant" description="" actions={<GhostButton icon="arrow-left" onClick={()=>onGo('/super/tenants')}>Back</GhostButton>} />
      <AuditNote tone="red" icon="alert-triangle"><span>{error} </span><button onClick={load} className="underline font-medium ml-1">Retry →</button></AuditNote>
    </>
  );
  if (!tenant) return null;

  return (
    <>
      <PageHeader
        title={tenant.name}
        description={`Tenant ID: ${tenant.id} · Namespace ${tenant.vector_namespace || tenant.slug}`}
        actions={
          <>
            <StatusPill status={tenant.status} />
            <GhostButton size="sm" icon="settings" onClick={()=>setConfigOpen(true)}>Configure</GhostButton>
            {tenant.active
              ? <GhostButton size="sm" icon="pause" danger onClick={()=>setConfirmSuspend(true)}>Suspend</GhostButton>
              : <PrimaryButton size="sm" icon="play" mode="sage" onClick={()=>setActive(true)}>Activate</PrimaryButton>}
            <GhostButton size="sm" icon="trash-2" danger onClick={()=>setConfirmDelete(true)}>Delete</GhostButton>
          </>
        }
      />

      {actionError && <div className="mb-4"><AuditNote tone="red" icon="alert-triangle">{actionError}</AuditNote></div>}

      <div className="grid grid-cols-4 gap-4 mb-4">
        <KpiCard label="Users" value={(tenant.user_count||0).toLocaleString()} subtle="attached to tenant" accent="navy" />
        <KpiCard label="Status" value={tenant.status} mono={false} accent={tenant.active ? 'sage' : 'ember'} />
        <KpiCard label="Tier" value={tenant.tier==='pilot'?'Pilot':'Active'} mono={false} />
        <KpiCard label="Onboarded" value={fmtDate(tenant.created_at)} mono={false} />
      </div>

      <div className="grid gap-4" style={{ gridTemplateColumns: '1fr 1fr' }}>
        <Card>
          <SectionLabel>Details</SectionLabel>
          <dl className="space-y-2 text-[13px]">
            <div className="flex justify-between gap-4"><dt className="text-[var(--muted)]">Slug</dt><dd><MonoChip>{tenant.slug}</MonoChip></dd></div>
            <div className="flex justify-between gap-4"><dt className="text-[var(--muted)]">Country</dt><dd>{tenant.country || '—'}</dd></div>
            <div className="flex justify-between gap-4"><dt className="text-[var(--muted)]">Primary contact</dt><dd>{tenant.contact_name || '—'}</dd></div>
            <div className="flex justify-between gap-4"><dt className="text-[var(--muted)]">Vector namespace</dt><dd><MonoChip>{tenant.vector_namespace || tenant.slug}</MonoChip></dd></div>
          </dl>
        </Card>

        <Card>
          <SectionLabel right={<MonoChip>{(tenant.domains||[]).length}</MonoChip>}>Verified email domains</SectionLabel>
          <div className="space-y-2 mb-3">
            {(tenant.domains||[]).map(d => (
              <div key={d.id} className="flex items-center justify-between hair border rounded-sm px-3 py-2">
                <span className="font-mono text-[13px]">@{d.domain}</span>
                <button onClick={()=>removeDomain(d.id)} disabled={busy || (tenant.domains||[]).length<=1}
                  className={`text-[var(--red)] ${(busy||(tenant.domains||[]).length<=1)?'opacity-40':'hover:opacity-70'}`} title={(tenant.domains||[]).length<=1?'A tenant must keep at least one domain':'Remove domain'}>
                  <Icon name="x" size={14} />
                </button>
              </div>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <input value={newDomain} onChange={e=>setNewDomain(e.target.value)} placeholder="add.edu.bd" className={INPUT_CLS + ' font-mono'} />
            <PrimaryButton size="sm" mode="ember" icon="plus" onClick={addDomain} disabled={busy || !newDomain.trim()} className={(busy||!newDomain.trim())?'opacity-50 pointer-events-none':''}>Add</PrimaryButton>
          </div>
        </Card>
      </div>

      <div className="mt-4">
        <AuditNote tone="navy" icon="lock">
          Super Admin cannot read individual case content from this tenant — only aggregate metrics and configuration. Identity de-anonymization requires a formal request via the workflow.
        </AuditNote>
      </div>

      <ConfirmModal open={confirmSuspend} onClose={()=>setConfirmSuspend(false)} onConfirm={()=>setActive(false)}
        title="Suspend tenant" tone="red" confirmWord="SUSPEND" confirmLabel="Suspend"
        body={`Suspending ${tenant.name} disables sign-in resolution for its email domains. You can reactivate it at any time.`} />

      <ConfirmModal open={confirmDelete} onClose={()=>setConfirmDelete(false)} onConfirm={doDelete}
        title="Delete tenant" tone="red" confirmWord="DELETE" confirmLabel="Delete"
        body={`Permanently delete ${tenant.name} and its email domains. This is only allowed when no users are attached to the tenant.`} />

      <ConfigureSlideOver open={configOpen} onClose={()=>setConfigOpen(false)} tenant={tenant}
        onSaved={(updated)=>{ setTenant(updated); setConfigOpen(false); }} onError={setActionError} />
    </>
  );
}

function ConfigureSlideOver({ open, onClose, tenant, onSaved, onError }) {
  const [f, setF] = useState({ name:'', tier:'active', country:'', contact_name:'', vector_namespace:'' });
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (open && tenant) setF({
      name: tenant.name || '', tier: tenant.tier || 'active', country: tenant.country || '',
      contact_name: tenant.contact_name || '', vector_namespace: tenant.vector_namespace || '',
    });
  }, [open, tenant]);
  const set = (k, v) => setF(prev => ({ ...prev, [k]: v }));

  const save = async () => {
    setSaving(true);
    try {
      const updated = await AnchorAPI.apiPatch(`/v1/super-admin/tenants/${tenant.id}`, {
        name: f.name.trim(), tier: f.tier, country: f.country.trim() || null,
        contact_name: f.contact_name.trim() || null, vector_namespace: f.vector_namespace.trim() || null,
      });
      onSaved(updated);
    } catch (e) {
      onError(e.message || 'Save failed');
      onClose();
    } finally { setSaving(false); }
  };

  return (
    <SlideOver open={open} onClose={onClose}>
      <div className="p-5 hair-b flex items-center justify-between">
        <h3 className="font-serif text-[20px] text-[var(--navy)]">Configure tenant</h3>
        <button onClick={onClose} className="text-[var(--muted)] hover:text-[var(--ink)]"><Icon name="x" size={18} /></button>
      </div>
      <div className="p-5 space-y-3">
        <Field label="University name"><input value={f.name} onChange={e=>set('name', e.target.value)} className={INPUT_CLS} /></Field>
        <Field label="Tier">
          <select value={f.tier} onChange={e=>set('tier', e.target.value)} className={INPUT_CLS}>
            <option value="pilot">Pilot</option>
            <option value="active">Active</option>
          </select>
        </Field>
        <Field label="Country"><input value={f.country} onChange={e=>set('country', e.target.value)} className={INPUT_CLS} /></Field>
        <Field label="Primary contact"><input value={f.contact_name} onChange={e=>set('contact_name', e.target.value)} className={INPUT_CLS} /></Field>
        <Field label="Vector namespace"><input value={f.vector_namespace} onChange={e=>set('vector_namespace', e.target.value)} className={INPUT_CLS + ' font-mono'} /></Field>
      </div>
      <div className="p-4 hair-t flex items-center justify-end gap-2">
        <GhostButton onClick={onClose}>Cancel</GhostButton>
        <PrimaryButton mode="ember" icon="check" onClick={save} disabled={saving || !f.name.trim()} className={(saving||!f.name.trim())?'opacity-50 pointer-events-none':''}>{saving ? 'Saving…' : 'Save changes'}</PrimaryButton>
      </div>
    </SlideOver>
  );
}

// ---- Audit Logs ----
const AUDIT_ACTION_PREFIXES = [
  ['', 'All actions'],
  ['login', 'Login'],
  ['mfa_', 'MFA'],
  ['alert_', 'Alerts'],
  ['complaint_', 'Complaints'],
  ['filing_', 'Filings'],
  ['feed_', 'Feed'],
  ['zone_', 'Zones'],
  ['deanonymize_', 'De-anonymization'],
  ['user_', 'User management'],
];
const AUDIT_ROLES = [
  ['', 'All roles'],
  ['super_admin', 'Super Admin'],
  ['admin', 'Admin'],
  ['moderator', 'Moderator'],
  ['student', 'Student'],
  ['user', 'User'],
];
const AUDIT_RANGES = [
  ['', 'All time'],
  ['24h', 'Last 24h'],
  ['7d', 'Last 7 days'],
  ['30d', 'Last 30 days'],
];
const AUDIT_ROLE_TONE = { super_admin:'red', admin:'sage', moderator:'gold', student:'navy', user:'navy' };

function _auditDateFrom(range) {
  const DAY = 864e5;
  const ms = range === '24h' ? DAY : range === '7d' ? 7*DAY : range === '30d' ? 30*DAY : 0;
  return ms ? new Date(Date.now() - ms).toISOString() : null;
}
function _auditFmtTs(iso) {
  try { return new Date(iso).toLocaleString('en-GB', { day:'2-digit', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit', second:'2-digit' }); }
  catch { return iso; }
}

function SuperAuditLogs() {
  const PAGE = 50;
  const [rows, setRows]         = useState([]);
  const [total, setTotal]       = useState(0);
  const [offset, setOffset]     = useState(0);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState('');
  const [selected, setSelected] = useState(null);

  const [q, setQ]               = useState('');
  const [qDebounced, setQDebounced] = useState('');
  const [prefix, setPrefix]     = useState('');
  const [role, setRole]         = useState('');
  const [range, setRange]       = useState('');

  const [verifying, setVerifying]       = useState(false);
  const [verifyResult, setVerifyResult] = useState(null);
  const [exporting, setExporting]       = useState(false);

  // Debounce the free-text search so we don't fire a request per keystroke.
  useEffect(() => {
    const t = setTimeout(() => setQDebounced(q.trim()), 350);
    return () => clearTimeout(t);
  }, [q]);

  // Any filter change resets to the first page.
  useEffect(() => { setOffset(0); }, [qDebounced, prefix, role, range]);

  function buildParams(extra) {
    const p = new URLSearchParams();
    if (qDebounced) p.set('q', qDebounced);
    if (prefix) p.set('prefix', prefix);
    if (role) p.set('role', role);
    const df = _auditDateFrom(range);
    if (df) p.set('date_from', df);
    Object.entries(extra || {}).forEach(([k, v]) => p.set(k, v));
    return p;
  }

  // Fetch with a cancellation guard so a slow earlier request can't overwrite a
  // newer one (e.g. when changing a filter resets the page and refires).
  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError('');
    AnchorAPI.apiGet(`/v1/admin/audit?${buildParams({ limit: PAGE, offset })}`)
      .then(data => { if (cancelled) return; setRows(data.items || []); setTotal(data.total || 0); })
      .catch(e => { if (cancelled) return; setError(e.message); setRows([]); setTotal(0); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [qDebounced, prefix, role, range, offset]);

  async function verifyChain() {
    setVerifying(true); setVerifyResult(null);
    try { setVerifyResult(await AnchorAPI.apiGet('/v1/admin/audit/verify?limit=5000')); }
    catch (e) { setVerifyResult({ error: e.message }); }
    finally { setVerifying(false); }
  }

  async function exportCsv() {
    setExporting(true);
    try {
      const stamp = new Date().toISOString().slice(0, 19).replace(/[-:T]/g, '');
      await AnchorAPI.apiDownload(`/v1/admin/audit/export?${buildParams({ limit: 50000 })}`, `anchor-audit-${stamp}.csv`);
    } catch (e) { alert(e.message); }
    finally { setExporting(false); }
  }

  return (
    <>
      <PageHeader
        title="Audit log explorer"
        description="Every significant action across the platform is permanently logged in an append-only SHA-256 hash chain. Logs cannot be edited or deleted."
        actions={<>
          <GhostButton icon="shield-check" size="sm" onClick={verifyChain} disabled={verifying}>{verifying ? 'Verifying…' : 'Verify integrity'}</GhostButton>
          <GhostButton icon="download" size="sm" onClick={exportCsv} disabled={exporting}>{exporting ? 'Exporting…' : 'Export CSV'}</GhostButton>
        </>}
      />

      {verifyResult && (
        <div className="mb-4">
          {verifyResult.error
            ? <AuditNote tone="red" icon="shield-alert">Could not verify chain: {verifyResult.error}</AuditNote>
            : verifyResult.ok
              ? <AuditNote tone="sage" icon="shield-check">Hash chain verified — {verifyResult.checked} rows intact, no tampering detected.</AuditNote>
              : <AuditNote tone="red" icon="shield-alert">Tampering detected — chain breaks at row <span className="font-mono">{verifyResult.first_tampered_id}</span> (checked {verifyResult.checked} rows).</AuditNote>}
        </div>
      )}

      <Card noPad className="mb-4">
        <div className="p-4 grid gap-3 hair-b" style={{ gridTemplateColumns:'2fr 1fr 1fr 1fr' }}>
          <div className="flex items-center gap-2 hair border rounded-sm px-2 bg-white">
            <Icon name="search" size={14} className="text-[var(--muted)]" />
            <input value={q} onChange={e=>setQ(e.target.value)} placeholder="Search action or metadata…" className="flex-1 py-2 outline-none bg-transparent text-[13px]" />
          </div>
          <select value={prefix} onChange={e=>setPrefix(e.target.value)} className="hair border rounded-sm px-2 py-2 bg-white text-[12.5px]">
            {AUDIT_ACTION_PREFIXES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <select value={role} onChange={e=>setRole(e.target.value)} className="hair border rounded-sm px-2 py-2 bg-white text-[12.5px]">
            {AUDIT_ROLES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <select value={range} onChange={e=>setRange(e.target.value)} className="hair border rounded-sm px-2 py-2 bg-white text-[12.5px]">
            {AUDIT_RANGES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>

        {loading ? (
          <div className="px-5 py-12 text-center text-[13px] text-[var(--muted)]">Loading audit events…</div>
        ) : error ? (
          <div className="px-5 py-12 text-center text-[13px]" style={{ color:'var(--red)' }}>{error}</div>
        ) : rows.length === 0 ? (
          <EmptyState icon="search" title="No matching events" body="No audit events match the current filters." />
        ) : (
          <DataTable
            columns={[
              { key:'created_at', label:'Timestamp', render:r=><span className="font-mono text-[11.5px] text-[var(--muted)]">{_auditFmtTs(r.created_at)}</span> },
              { key:'actor', label:'Actor (masked)', render:r=><span>{(r.actor && r.actor.masked_email) || 'system'}</span> },
              { key:'event_type', label:'Action', render:r=><MonoChip>{r.event_type}</MonoChip> },
              { key:'role', label:'Role', render:r=> (r.actor && r.actor.role) ? <Tag tone={AUDIT_ROLE_TONE[r.actor.role] || 'navy'}>{r.actor.role}</Tag> : <span className="text-[var(--muted)]">—</span> },
              { key:'ip', label:'IP', render:r=><span className="font-mono text-[11.5px]">{r.ip_address || '—'}</span> },
            ]}
            rows={rows}
            dense
            onRowClick={setSelected}
          />
        )}

        {!loading && !error && total > 0 && (
          <div className="p-3 hair-t flex items-center justify-between text-[12px] text-[var(--muted)]">
            <span>Showing {rows.length ? offset + 1 : 0}–{offset + rows.length} of {total}</span>
            <div className="flex items-center gap-2">
              <GhostButton size="sm" disabled={offset === 0} onClick={()=>setOffset(Math.max(0, offset - PAGE))}>Prev</GhostButton>
              <GhostButton size="sm" disabled={offset + PAGE >= total} onClick={()=>setOffset(offset + PAGE)}>Next</GhostButton>
            </div>
          </div>
        )}
      </Card>

      <SlideOver open={!!selected} onClose={()=>setSelected(null)} width={520}>
        {selected && (
          <div className="p-5 space-y-3">
            <div className="flex items-center justify-between">
              <SectionLabel className="mb-0">Audit event</SectionLabel>
              <button onClick={()=>setSelected(null)} className="w-7 h-7 rounded-sm hover:bg-[var(--mist)]/40 flex items-center justify-center"><Icon name="x" size={14} /></button>
            </div>
            <MonoChip tone="navy">{selected.event_type}</MonoChip>
            <div className="hair border rounded-sm p-3 bg-[#FBF9F2] font-mono text-[12px] space-y-1 break-all">
              <div><span className="text-[var(--muted)]">timestamp:</span> {_auditFmtTs(selected.created_at)}</div>
              <div><span className="text-[var(--muted)]">actor:</span> {(selected.actor && selected.actor.masked_email) || 'system'}</div>
              <div><span className="text-[var(--muted)]">role:</span> {(selected.actor && selected.actor.role) || '—'}</div>
              <div><span className="text-[var(--muted)]">user_id:</span> {(selected.actor && selected.actor.user_id) || '—'}</div>
              <div><span className="text-[var(--muted)]">tenant_id:</span> {(selected.actor && selected.actor.tenant_id) || '—'}</div>
              <div><span className="text-[var(--muted)]">ip:</span> {selected.ip_address || '—'}</div>
              <div><span className="text-[var(--muted)]">row_hash:</span> {selected.row_hash}</div>
            </div>
            {selected.metadata && Object.keys(selected.metadata).length > 0 && (
              <div>
                <SectionLabel>Metadata</SectionLabel>
                <pre className="hair border rounded-sm p-3 bg-[#FBF9F2] font-mono text-[11.5px] whitespace-pre-wrap break-all">{JSON.stringify(selected.metadata, null, 2)}</pre>
              </div>
            )}
            <AuditNote tone="navy" icon="shield-check">
              This event is part of an append-only SHA-256 hash chain. Tampering would invalidate every downstream hash — use “Verify integrity” to re-check.
            </AuditNote>
          </div>
        )}
      </SlideOver>
    </>
  );
}

// ---- De-anonymization ----
const DEANON_STATUS_LABEL = {
  pending_review: 'Pending review',
  awaiting_second_approval: 'Awaiting 2nd approval',
  approved: 'Approved',
  denied: 'Denied',
  expired: 'Expired',
};

function _deanonFmt(iso) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }); }
  catch { return iso; }
}

function SuperDeanonymization() {
  const [rows, setRows]         = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [selectedId, setSelectedId]     = useState(null);
  const [busy, setBusy]         = useState(false);
  const [actionMsg, setActionMsg] = useState('');
  const [denying, setDenying]   = useState(false);
  const [denyReason, setDenyReason] = useState('');
  const [reveal, setReveal]     = useState(null);

  async function load() {
    setLoading(true); setError('');
    try {
      const params = new URLSearchParams();
      if (statusFilter) params.set('status', statusFilter);
      const data = await AnchorAPI.apiGet(`/v1/admin/deanonymization?${params}`);
      setRows(data.items || []);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, [statusFilter]);

  const selected = rows.find(r => r.id === selectedId) || null;

  // Reset transient panel state when switching requests.
  useEffect(() => { setActionMsg(''); setReveal(null); setDenying(false); setDenyReason(''); }, [selectedId]);

  async function refreshSelected() {
    await load();
  }

  async function handleApprove() {
    if (!selected) return;
    setBusy(true); setActionMsg('');
    try {
      await AnchorAPI.apiPostAuth(`/v1/admin/deanonymization/${selected.id}/approve`, {});
      await refreshSelected();
    } catch (e) { setActionMsg(e.message); }
    finally { setBusy(false); }
  }

  async function handleDeny() {
    if (!selected || !denyReason.trim()) return;
    setBusy(true); setActionMsg('');
    try {
      await AnchorAPI.apiPostAuth(`/v1/admin/deanonymization/${selected.id}/deny`, { reason: denyReason.trim() });
      setDenying(false); setDenyReason('');
      await refreshSelected();
    } catch (e) { setActionMsg(e.message); }
    finally { setBusy(false); }
  }

  async function handleReveal() {
    if (!selected) return;
    setBusy(true); setActionMsg('');
    try {
      const data = await AnchorAPI.apiPostAuth(`/v1/admin/deanonymization/${selected.id}/reveal`, {});
      setReveal(data);
    } catch (e) { setActionMsg(e.message); await refreshSelected(); }
    finally { setBusy(false); }
  }

  const decisions = rows
    .filter(r => r.status === 'approved' || r.status === 'denied' || r.status === 'expired')
    .sort((a, b) => new Date(b.decided_at || b.created_at) - new Date(a.decided_at || a.created_at))
    .slice(0, 6);

  const FILTERS = [
    ['', 'All'],
    ['pending_review', 'Pending'],
    ['awaiting_second_approval', 'Awaiting 2nd'],
    ['approved', 'Approved'],
    ['denied', 'Denied'],
  ];

  return (
    <>
      <PageHeader
        title="De-anonymization queue"
        bn="পরিচয় উন্মোচন অনুরোধ"
        description="Identity disclosure requests from university admins. Every approval is permanently logged and reviewable by external oversight."
      />

      <AuditNote tone="red" icon="shield-alert" className="mb-4">
        De-anonymization requests must be reviewed against formal legal grounds. Approval releases the identity mapping to the requesting admin only, with time-limited access. Releasing an identity requires two distinct super admins.
      </AuditNote>

      <div className="flex items-center gap-1.5 mb-3">
        {FILTERS.map(([val, lbl]) => (
          <button key={val||'all'} onClick={()=>setStatusFilter(val)}
            className="px-2.5 py-1 rounded-sm text-[12px] border hair transition-colors"
            style={statusFilter===val
              ? { background:'var(--navy)', color:'#fff', borderColor:'var(--navy)' }
              : { color:'var(--muted)' }}>
            {lbl}
          </button>
        ))}
        <button onClick={load} className="ml-auto text-[12px] text-[var(--muted)] hover:text-[var(--ink)] underline">refresh</button>
      </div>

      <div className="grid gap-4" style={{ gridTemplateColumns: '1fr 360px' }}>
        <Card noPad>
          {loading ? (
            <div className="p-8 text-center text-[13px] text-[var(--muted)]">Loading requests…</div>
          ) : error ? (
            <div className="p-6 text-[12.5px]" style={{ color:'var(--ember)' }}>{error}</div>
          ) : rows.length === 0 ? (
            <div className="p-6"><EmptyState icon="shield-check" title="Queue is clear" body="No de-anonymization requests match this filter." /></div>
          ) : (
            <DataTable
              columns={[
                { key:'request_number', label:'Request ID', render:r=><MonoChip tone="navy">{r.request_number}</MonoChip> },
                { key:'target_ref', label:'Case', render:r=><MonoChip>{r.target_ref}</MonoChip> },
                { key:'requester_label', label:'Requester' },
                { key:'legal_basis', label:'Legal basis' },
                { key:'created_at', label:'Requested', render:r=><span className="font-mono text-[11.5px] text-[var(--muted)]">{_deanonFmt(r.created_at)}</span> },
                { key:'status', label:'Status', render:r=><StatusPill status={DEANON_STATUS_LABEL[r.status] || r.status} /> },
              ]}
              rows={rows}
              onRowClick={r=>setSelectedId(r.id)}
            />
          )}
        </Card>

        <div className="space-y-4">
          {selected ? (
            <Card>
              <div className="flex items-center justify-between mb-2">
                <SectionLabel className="mb-0">Review</SectionLabel>
                <button onClick={()=>setSelectedId(null)} className="text-[12px] text-[var(--muted)] hover:text-[var(--ink)]">close</button>
              </div>
              <div className="flex items-center gap-2">
                <MonoChip tone="navy">{selected.request_number}</MonoChip>
                <StatusPill status={DEANON_STATUS_LABEL[selected.status] || selected.status} />
              </div>
              <h3 className="font-serif text-[20px] text-[var(--navy)] mt-2" style={{fontWeight:500, textWrap:'pretty'}}>{selected.target_ref}</h3>
              <div className="text-[12px] text-[var(--muted)] mt-0.5">{selected.requester_label}</div>

              <div className="mt-4 hair border rounded-sm p-3 bg-[#FBF9F2]">
                <div className="smallcaps text-[var(--muted)] mb-1">Reason cited</div>
                <p className="text-[12.5px] text-[var(--ink)]" style={{textWrap:'pretty'}}>{selected.reason}</p>
                {selected.formal_letter_ref && (
                  <div className="mt-2 text-[11.5px] text-[var(--muted)]">Formal letter: <span className="font-mono text-[var(--ink)]">{selected.formal_letter_ref}</span></div>
                )}
              </div>

              <div className="mt-3 grid grid-cols-2 gap-2">
                <KpiCard label="Legal basis" value={selected.legal_basis} mono={false} accent="ember" />
                <KpiCard label="Target" value={selected.target_type} accent="navy" />
              </div>

              {/* Two-person control trail */}
              <div className="mt-4 space-y-2">
                <div className="smallcaps text-[var(--muted)]">Two-person control</div>
                <div className="flex items-start gap-2 text-[12.5px]">
                  <Icon name={selected.first_approval ? 'check-circle' : 'circle'} size={14}
                    className="mt-0.5 shrink-0" style={{ color: selected.first_approval ? 'var(--sage)' : 'var(--muted)' }} />
                  <span>
                    First approval{selected.first_approval
                      ? <> — <span className="font-mono">{selected.first_approval.masked_email}</span> · {_deanonFmt(selected.first_approval.at)}</>
                      : ' — pending'}
                  </span>
                </div>
                <div className="flex items-start gap-2 text-[12.5px]">
                  <Icon name={selected.second_approval ? 'check-circle' : 'circle'} size={14}
                    className="mt-0.5 shrink-0" style={{ color: selected.second_approval ? 'var(--sage)' : 'var(--muted)' }} />
                  <span>
                    Second approval (different admin){selected.second_approval
                      ? <> — <span className="font-mono">{selected.second_approval.masked_email}</span> · {_deanonFmt(selected.second_approval.at)}</>
                      : ' — pending'}
                  </span>
                </div>
              </div>

              {actionMsg && (
                <div className="mt-3 px-3 py-2 rounded-sm text-[12px] flex items-start gap-2" style={{ background:'var(--ember-tint, #F6E5E2)', color:'var(--ember)' }}>
                  <Icon name="circle-alert" size={13} className="mt-0.5 shrink-0" /><span>{actionMsg}</span>
                </div>
              )}

              {/* Released identity */}
              {reveal && (
                <div className="mt-4 hair border rounded-sm p-3" style={{ background:'#FBF1EE', borderColor:'var(--ember)' }}>
                  <div className="smallcaps mb-1" style={{ color:'var(--ember)' }}>Released identity</div>
                  <div className="text-[14px] font-medium text-[var(--ink)]">{reveal.full_name || '—'}</div>
                  <div className="text-[12.5px] font-mono text-[var(--ink)]">{reveal.email || reveal.masked_email || '—'}</div>
                  <div className="text-[11.5px] text-[var(--muted)] mt-1">Role: {reveal.role || '—'} · Access expires {_deanonFmt(reveal.access_expires_at)}</div>
                </div>
              )}

              {/* Actions by status */}
              <div className="mt-4 flex flex-wrap items-center gap-2">
                {(selected.status === 'pending_review' || selected.status === 'awaiting_second_approval') && !denying && (
                  <>
                    <PrimaryButton mode="ember" icon="check" onClick={handleApprove} disabled={busy}>
                      {selected.status === 'awaiting_second_approval' ? 'Give 2nd approval' : 'Approve'}
                    </PrimaryButton>
                    <GhostButton icon="x" danger onClick={()=>setDenying(true)} disabled={busy}>Deny</GhostButton>
                  </>
                )}
                {selected.status === 'approved' && (
                  <PrimaryButton mode="ember" icon="eye" onClick={handleReveal} disabled={busy}>
                    {reveal ? 'Re-reveal identity' : 'Reveal identity'}
                  </PrimaryButton>
                )}
                {selected.status === 'denied' && (
                  <div className="text-[12.5px] text-[var(--muted)]">Denied{selected.denied_reason ? ` — ${selected.denied_reason}` : ''}.</div>
                )}
                {selected.status === 'expired' && (
                  <div className="text-[12.5px] text-[var(--muted)]">Reveal window expired. A new request is required.</div>
                )}
              </div>

              {/* Deny form */}
              {denying && (
                <div className="mt-3 space-y-2">
                  <textarea value={denyReason} onChange={e=>setDenyReason(e.target.value)}
                    placeholder="Reason for denial (recorded in the audit log)…"
                    className="w-full px-2.5 py-2 hair border rounded-sm bg-white text-[12.5px]" rows={2} />
                  <div className="flex items-center gap-2">
                    <PrimaryButton mode="ember" icon="x" onClick={handleDeny} disabled={busy || !denyReason.trim()}>Confirm deny</PrimaryButton>
                    <GhostButton onClick={()=>{ setDenying(false); setDenyReason(''); }} disabled={busy}>Cancel</GhostButton>
                  </div>
                </div>
              )}
            </Card>
          ) : (
            <Card>
              <EmptyState icon="shield-alert" title="Select a request" body="Open any request from the table to review the case, legal basis, and approve or deny." />
            </Card>
          )}

          <Card>
            <SectionLabel>Recent decisions</SectionLabel>
            {decisions.length === 0 ? (
              <div className="text-[12.5px] text-[var(--muted)]">No decisions yet.</div>
            ) : (
              <div className="space-y-2 text-[12.5px]">
                {decisions.map(d => (
                  <div key={d.id} className="flex items-center justify-between">
                    <span>{d.request_number} · {DEANON_STATUS_LABEL[d.status] || d.status}</span>
                    <span className="font-mono text-[var(--muted)]">{_deanonFmt(d.decided_at).split(',')[0]}</span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}

// ---- Verification feed (super) ----
function FeedPostCard({ v, onDefer, onConfirm, busy, isDone, msg }) {
  const sc = v.signal_counts || {};
  const corrob = sc.corroborate ?? 0;
  const chall = sc.challenge ?? 0;
  const flags = sc.flags ?? 0;
  const isStepUpErr = msg && (msg.toLowerCase().includes('step') || msg.includes('401') || msg.includes('403'));

  return (
    <div className={`hair border rounded-sm p-4 space-y-3 ${isDone ? 'opacity-60' : ''}`}
      style={isDone ? { background:'var(--mist)' } : { background:'var(--paper)' }}>
      {/* Top row: meta tags + date */}
      <div className="flex items-center gap-2 flex-wrap">
        <MonoChip tone="navy">#{v.post_number}</MonoChip>
        <Tag tone="navy">{v.scope}</Tag>
        <Tag tone="mist">{v.category}</Tag>
        {v.admin_confirmed && <Tag tone="sage">Confirmed</Tag>}
        <span className="ml-auto text-[11px] text-[var(--muted)] font-mono">{new Date(v.created_at).toLocaleDateString()}</span>
      </div>

      {/* Title */}
      <h3 className="text-[15px] font-medium leading-snug" style={{textWrap:'pretty'}}>{v.title}</h3>

      {/* Signal pills */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-[11.5px] font-medium"
          style={{ background:'rgba(74,107,92,0.10)', color:'var(--sage)' }}>
          <Icon name="check-circle" size={11} />{corrob} corroborate
        </span>
        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-[11.5px] font-medium"
          style={{ background:'rgba(196,69,54,0.10)', color:'var(--ember)' }}>
          <Icon name="x-circle" size={11} />{chall} challenge
        </span>
        {flags > 0 && (
          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-[11.5px] font-medium"
            style={{ background:'rgba(184,137,58,0.12)', color:'var(--gold)' }}>
            <Icon name="flag" size={11} />{flags} flag{flags > 1 ? 's' : ''}
          </span>
        )}
      </div>

      {/* Feedback row */}
      {isStepUpErr && (
        <div className="px-3 py-2 rounded-sm text-[12px]" style={{ background:'rgba(184,137,58,0.10)', color:'#8A6520', border:'1px solid rgba(184,137,58,0.25)' }}>
          <Icon name="shield-alert" size={12} className="inline mr-1" />
          Step-up authentication required. Re-authenticate with your password in the Anchor mobile app to unlock sensitive moderation actions.
        </div>
      )}
      {msg && !isDone && !isStepUpErr && (
        <div className="text-[11.5px]" style={{color:'var(--red)'}}>{msg}</div>
      )}
      {isDone && (
        <div className="inline-flex items-center gap-1 text-[11.5px]" style={{color:'var(--sage)'}}>
          <Icon name="check" size={11} />Action recorded: {msg}
        </div>
      )}

      {/* Action row */}
      <div className="flex items-center justify-end gap-2 pt-1">
        <GhostButton size="sm" icon="rotate-ccw" disabled={busy || isDone} onClick={onDefer}>
          {busy ? '…' : 'Send back'}
        </GhostButton>
        <PrimaryButton size="sm" mode="ember" icon="check" disabled={busy || isDone} onClick={onConfirm}>
          {busy ? '…' : 'Approve'}
        </PrimaryButton>
      </div>
    </div>
  );
}

function SuperVerificationFeed() {
  const TAB_API = { 'Pending': 'flagged', 'Confirmation': 'confirmation', 'Pre-publish': 'pre_publish' };
  const TABS = ['Pending', 'Confirmation', 'Pre-publish'];
  const [tab, setTab] = useState('Pending');
  const [posts, setPosts] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionMsg, setActionMsg] = useState({});
  const [actionLoading, setActionLoading] = useState({});

  function loadPosts(activeTab) {
    setLoading(true); setError('');
    const apiTab = TAB_API[activeTab] || 'flagged';
    Promise.all([
      AnchorAPI.apiGet(`/v1/feed/admin/queue?tab=${apiTab}&page=1&page_size=20`),
      AnchorAPI.apiGet('/v1/feed/admin/stats'),
    ]).then(([queue, s]) => {
      setPosts(Array.isArray(queue) ? queue : []);
      setStats(s);
      setLoading(false);
    }).catch(err => { setError(err.message || 'Could not load feed queue.'); setLoading(false); });
  }

  useEffect(() => { loadPosts(tab); }, [tab]);

  async function handleDefer(postId) {
    setActionLoading(a => ({...a, [postId]: true})); setActionMsg(m => ({...m, [postId]: ''}));
    try {
      await AnchorAPI.apiPostAuth(`/v1/feed/admin/${postId}/defer`, { internal_note: 'Deferred by super admin.' });
      setActionMsg(m => ({...m, [postId]: 'deferred'}));
      loadPosts(tab);
    } catch (err) {
      setActionMsg(m => ({...m, [postId]: err.message || 'Failed'}));
    } finally { setActionLoading(a => ({...a, [postId]: false})); }
  }

  async function handleConfirm(postId) {
    setActionLoading(a => ({...a, [postId]: true})); setActionMsg(m => ({...m, [postId]: ''}));
    try {
      await AnchorAPI.apiPostAuth(`/v1/feed/admin/${postId}/confirm`, { internal_note: 'Confirmed by super admin.' });
      setActionMsg(m => ({...m, [postId]: 'confirmed'}));
      loadPosts(tab);
    } catch (err) {
      const msg = err.message || '';
      setActionMsg(m => ({...m, [postId]: msg || 'Confirm failed'}));
    } finally { setActionLoading(a => ({...a, [postId]: false})); }
  }

  return (
    <>
      <PageHeader
        title="Verification feed"
        description="Posts escalated by university admins for platform-public visibility. Approve, deny, or send back."
        actions={stats && (
          <div className="flex items-center gap-2">
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-sm text-[12px] font-medium"
              style={{ background:'rgba(196,69,54,0.10)', color:'var(--ember)' }}>
              <Icon name="flag" size={11} />{stats.flagged ?? '—'} flagged
            </span>
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-sm text-[12px] font-medium"
              style={{ background:'rgba(74,107,92,0.10)', color:'var(--sage)' }}>
              <Icon name="check-circle" size={11} />{stats.confirmed ?? '—'} confirmed
            </span>
            <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-sm text-[12px] font-medium"
              style={{ background:'var(--mist)', color:'var(--graphite)' }}>
              <Icon name="layers" size={11} />{stats.total ?? '—'} total
            </span>
          </div>
        )}
      />

      <Card noPad>
        <div className="p-4 hair-b flex items-center gap-1">
          {TABS.map(t => (
            <button key={t} onClick={() => setTab(t)} className={`px-3 py-1.5 text-[13px] rounded-sm ${tab===t?'bg-[var(--navy)] text-white':'hair border text-[var(--graphite)]'}`}>{t}</button>
          ))}
        </div>

        {loading && (
          <div className="p-4 space-y-3">
            {[1,2,3].map(i => (
              <div key={i} className="hair border rounded-sm p-4 animate-pulse space-y-2">
                <div className="flex gap-2"><div className="h-5 w-20 bg-[var(--mist)] rounded-sm" /><div className="h-5 w-16 bg-[var(--mist)] rounded-sm" /></div>
                <div className="h-4 bg-[var(--mist)] rounded-sm w-3/4" />
                <div className="flex gap-2"><div className="h-5 w-24 bg-[var(--mist)] rounded-sm" /><div className="h-5 w-24 bg-[var(--mist)] rounded-sm" /></div>
              </div>
            ))}
          </div>
        )}
        {error && (
          <div className="p-4 text-[13px]" style={{color:'var(--red)'}}>
            {error} — <button className="underline" onClick={() => loadPosts(tab)}>Retry</button>
          </div>
        )}
        {!loading && !error && posts.length === 0 && (
          <div className="p-8 text-center text-[13px] text-[var(--muted)]">No posts in this queue.</div>
        )}

        {!loading && !error && posts.length > 0 && (
          <div className="p-4 space-y-3">
            {posts.map(v => (
              <FeedPostCard
                key={v.id}
                v={v}
                onDefer={() => handleDefer(v.id)}
                onConfirm={() => handleConfirm(v.id)}
                busy={actionLoading[v.id] || false}
                isDone={(actionMsg[v.id] === 'deferred' || actionMsg[v.id] === 'confirmed')}
                msg={actionMsg[v.id] || ''}
              />
            ))}
          </div>
        )}
      </Card>
    </>
  );
}

// ---- System · shared fetch helpers ----
function _useSysFetch(path) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const load = useCallback(() => {
    setLoading(true); setError('');
    AnchorAPI.apiGet(path)
      .then(d => setData(d))
      .catch(e => setError(e.message || 'Failed to load'))
      .finally(() => setLoading(false));
  }, [path]);
  useEffect(() => { load(); }, [load]);
  return { data, loading, error, reload: load };
}

function _SysState({ loading, error, onRetry, children }) {
  if (loading) return <div className="p-10 text-center text-[13px] text-[var(--muted)]">Loading…</div>;
  if (error) return (
    <AuditNote tone="red" icon="alert-triangle">
      <span>{error} </span><button onClick={onRetry} className="underline font-medium ml-1">Retry →</button>
    </AuditNote>
  );
  return children;
}

function _svcTone(v) {
  const s = (v || '').toString().toLowerCase();
  if (s === 'ok' || s === 'healthy') return { c: '#4A6B5C', label: 'healthy' };
  if (s.startsWith('degraded')) return { c: '#B8893A', label: 'degraded' };
  return { c: '#E8312A', label: s || 'down' };
}

function _fmtUptime(s) {
  if (s == null) return '—';
  if (s < 60) return s + 's';
  if (s < 3600) return Math.floor(s / 60) + 'm';
  if (s < 86400) return Math.floor(s / 3600) + 'h ' + Math.floor((s % 3600) / 60) + 'm';
  return Math.floor(s / 86400) + 'd ' + Math.floor((s % 86400) / 3600) + 'h';
}

// ---- System · AI Engine Health ----
function SuperAIHealth() {
  const { data, loading, error, reload } = _useSysFetch('/v1/super-admin/ai-health');
  return (
    <>
      <PageHeader title="AI engine health"
        description="Live status of the RAG pipeline, vector store, and language models — with real per-namespace corpus health. Powered by services/rag."
        actions={<GhostButton size="sm" icon="refresh-cw" onClick={reload}>Refresh</GhostButton>} />
      <_SysState loading={loading} error={error} onRetry={reload}>
        {data && (() => {
          const c = data.components || {};
          const comps = [['Pipeline', c.pipeline], ['Embedder', c.embedder], ['Vector store (Chroma)', c.chromadb], ['LLM (Ollama)', c.ollama]];
          const host = data.host || {};
          const usage = data.usage || {};
          return (
            <>
              {!data.rag_reachable && (
                <div className="mb-4"><AuditNote tone="gold" icon="plug-zap">RAG service is unreachable — component status shows as unavailable. Start <span className="font-mono">services/rag</span> to see live data.</AuditNote></div>
              )}
              <div className="grid grid-cols-4 gap-4 mb-4">
                {comps.map(([label, val]) => {
                  const t = _svcTone(val);
                  return (
                    <div key={label} className="bg-[var(--paper)] hair border rounded-sm p-4">
                      <div className="flex items-center justify-between">
                        <span className="smallcaps text-[var(--muted)]">{label}</span>
                        <span className="w-2 h-2 rounded-full" style={{ background: t.c }} />
                      </div>
                      <div className="mt-2 text-[15px] text-[var(--ink)] capitalize">{t.label}</div>
                      <div className="text-[11px] text-[var(--muted)] font-mono truncate">{(val == null || val === '') ? '—' : val}</div>
                    </div>
                  );
                })}
              </div>

              <div className="grid grid-cols-4 gap-4 mb-4">
                <KpiCard label="AI chats · 24h" value={usage.ai_chat_24h != null ? usage.ai_chat_24h.toLocaleString() : '—'} accent="navy" />
                <KpiCard label="CPU" value={host.cpu_percent != null ? host.cpu_percent + '%' : '—'} subtle="API host" />
                <KpiCard label="Memory" value={host.mem_percent != null ? host.mem_percent + '%' : '—'} subtle={host.mem_used_mb != null ? `${host.mem_used_mb} / ${host.mem_total_mb} MB` : ''} accent="ember" />
                <KpiCard label="API uptime" value={_fmtUptime(host.process_uptime_s)} mono={false} />
              </div>

              <Card>
                <SectionLabel right={<MonoChip>chromadb</MonoChip>}>Vector DB · per-namespace corpus health</SectionLabel>
                {(!data.namespaces || data.namespaces.length === 0)
                  ? <div className="text-[12.5px] text-[var(--muted)]">{data.corpus_error ? `Corpus stats unavailable (${data.corpus_error}).` : 'No namespaces reported by RAG.'}</div>
                  : <DataTable
                      columns={[
                        { key: 'namespace', label: 'Namespace', render: r => <MonoChip>{r.namespace}</MonoChip> },
                        { key: 'documents', label: 'Documents', align: 'right', render: r => <span className="font-mono">{r.documents != null ? r.documents.toLocaleString() : '—'}</span> },
                        { key: 'dense_chunks', label: 'Dense chunks', align: 'right', render: r => <span className="font-mono">{r.dense_chunks != null ? r.dense_chunks.toLocaleString() : '—'}</span> },
                        { key: 'sparse_chunks', label: 'Sparse chunks', align: 'right', render: r => <span className="font-mono">{r.sparse_chunks != null ? r.sparse_chunks.toLocaleString() : '—'}</span> },
                      ]}
                      rows={data.namespaces}
                    />}
              </Card>
              <div className="mt-3 text-[11px] text-[var(--muted)] font-mono">checked {data.checked_at ? new Date(data.checked_at).toLocaleString() : '—'}</div>
            </>
          );
        })()}
      </_SysState>
    </>
  );
}

// ---- System · Encryption & Keys (read-only) ----
function SuperEncryption() {
  const { data, loading, error, reload } = _useSysFetch('/v1/super-admin/keys/health');
  return (
    <>
      <PageHeader title="Encryption & keys"
        description="Read-only health of the platform's cryptographic material — JWT signing keys, password hashing, MFA secrets, the audit hash chain, and end-to-end keys. No secret material is ever exposed."
        actions={<GhostButton size="sm" icon="refresh-cw" onClick={reload}>Refresh</GhostButton>} />
      <_SysState loading={loading} error={error} onRetry={reload}>
        {data && (() => {
          const jwt = data.jwt || {}, ac = data.audit_chain || {}, totp = data.totp || {}, e2ee = data.e2ee || {}, pw = data.password || {}, dl = data.token_denylist || {}, push = data.push || {};
          return (
            <>
              <div className="grid grid-cols-4 gap-4 mb-4">
                <KpiCard label="JWT algorithm" value={jwt.algorithm || '—'} mono={false} accent="navy" subtle={jwt.curve || ''} />
                <KpiCard label="Signing key age" value={jwt.age_days != null ? jwt.age_days + 'd' : '—'} subtle={jwt.source || ''} />
                <KpiCard label="Audit chain" value={ac.ok === true ? 'Verified' : ac.ok === false ? 'TAMPERED' : '—'} mono={false} accent={ac.ok === false ? 'ember' : 'sage'} subtle={ac.checked != null ? `${ac.checked} rows` : ''} />
                <KpiCard label="E2EE public keys" value={e2ee.stored_public_keys != null ? e2ee.stored_public_keys.toLocaleString() : '—'} accent="navy" />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <Card>
                  <SectionLabel right={<MonoChip>ed25519</MonoChip>}>JWT signing key</SectionLabel>
                  <dl className="space-y-2 text-[13px]">
                    <div className="flex justify-between gap-4"><dt className="text-[var(--muted)]">Algorithm</dt><dd>{jwt.algorithm || '—'} · {jwt.curve || '—'}</dd></div>
                    <div className="flex justify-between gap-4"><dt className="text-[var(--muted)]">Fingerprint</dt><dd className="font-mono text-[11.5px] break-all text-right">{jwt.fingerprint || '—'}</dd></div>
                    <div className="flex justify-between gap-4"><dt className="text-[var(--muted)]">Source</dt><dd>{jwt.source || '—'}</dd></div>
                    <div className="flex justify-between gap-4"><dt className="text-[var(--muted)]">Rotation</dt><dd>{jwt.rotation || '—'}</dd></div>
                  </dl>
                </Card>
                <Card>
                  <SectionLabel>Audit hash chain</SectionLabel>
                  {ac.ok === true && <AuditNote tone="sage" icon="shield-check">Chain verified — {ac.checked} rows intact, no tampering detected.</AuditNote>}
                  {ac.ok === false && <AuditNote tone="red" icon="shield-alert">Tampering detected at row <span className="font-mono">{ac.first_tampered_id}</span> ({ac.checked} checked).</AuditNote>}
                  {ac.ok == null && <AuditNote tone="gold" icon="alert-triangle">Could not verify chain{ac.error ? `: ${ac.error}` : ''}.</AuditNote>}
                  <p className="mt-3 text-[12.5px] text-[var(--graphite)]">Every privileged action appends to an append-only SHA-256 chain. Tampering invalidates all downstream hashes.</p>
                </Card>
              </div>

              <Card className="mt-4">
                <SectionLabel>Secrets &amp; configuration</SectionLabel>
                <DataTable dense
                  columns={[{ key: 'k', label: 'Control' }, { key: 'v', label: 'Status', render: r => r.v }]}
                  rows={[
                    { k: 'Password hashing', v: <Tag tone="sage">{pw.algorithm || 'Argon2id'}</Tag> },
                    { k: 'Password pepper', v: pw.pepper_configured ? <Tag tone="sage" icon="check">Configured</Tag> : <Tag tone="red" icon="x">Default / unset</Tag> },
                    { k: 'TOTP secrets at rest', v: totp.encrypted_at_rest ? <Tag tone="sage" icon="check">Encrypted</Tag> : <Tag tone="red" icon="alert-triangle">Plaintext (SEC-12)</Tag> },
                    { k: 'Revoked tokens (deny-list)', v: <span className="font-mono text-[12px]">{dl.revoked_jti_count != null ? dl.revoked_jti_count : '—'} <span className="text-[var(--muted)]">/ {dl.backend || 'redis'}</span></span> },
                    { k: 'Push (FCM) credentials', v: push.fcm_configured ? <Tag tone="sage" icon="check">Configured</Tag> : <Tag tone="gold">Not configured</Tag> },
                  ]} />
                {!totp.encrypted_at_rest && <div className="mt-3"><AuditNote tone="red" icon="shield-alert">{totp.note || 'TOTP secrets are stored unencrypted (SEC-12).'}</AuditNote></div>}
              </Card>
              <div className="mt-3 text-[11px] text-[var(--muted)] font-mono">checked {data.checked_at ? new Date(data.checked_at).toLocaleString() : '—'}</div>
            </>
          );
        })()}
      </_SysState>
    </>
  );
}

// ---- System · Platform Analytics ----
function SuperAnalytics() {
  const { data, loading, error, reload } = _useSysFetch('/v1/super-admin/analytics');
  return (
    <>
      <PageHeader title="Platform analytics"
        description="Cross-tenant, anonymized aggregates across all universities — users, tenants, alerts, content, and 14-day activity trends."
        actions={<GhostButton size="sm" icon="refresh-cw" onClick={reload}>Refresh</GhostButton>} />
      <_SysState loading={loading} error={error} onRetry={reload}>
        {data && (() => {
          const t = data.tenants || {}, u = data.users || {}, a = data.alerts || {}, ct = data.content || {}, dn = data.deanonymization || {}, corp = data.corpus || {}, host = data.host || {}, series = data.series || {};
          const spark = (arr) => (arr || []).map(p => p.count);
          const roleRows = Object.entries(u.by_role || {}).map(([k, v]) => ({ k, v }));
          const statusRows = Object.entries(u.by_status || {}).map(([k, v]) => ({ k, v }));
          return (
            <>
              <div className="grid grid-cols-5 gap-4 mb-4">
                <KpiCard label="Users" value={(u.total || 0).toLocaleString()} accent="navy" />
                <KpiCard label="Universities" value={t.total || 0} subtle={`${t.pilot || 0} pilot · ${t.suspended || 0} suspended`} />
                <KpiCard label="Active alerts" value={a.active || 0} accent="ember" />
                <KpiCard label="Filings" value={(ct.filings || 0).toLocaleString()} />
                <KpiCard label="De-anon · open" value={dn.open || 0} accent="ember" subtle={`${dn.total || 0} total`} />
              </div>

              <div className="grid gap-4 mb-4" style={{ gridTemplateColumns: '1fr 1fr' }}>
                <Card>
                  <SectionLabel right={<MonoChip>14d</MonoChip>}>Activity trends</SectionLabel>
                  <div className="space-y-3">
                    {[['Alerts', series.alerts_14d, 'var(--ember)'], ['Filings', series.filings_14d, 'var(--navy)'], ['Feed posts', series.feed_14d, 'var(--sage)']].map(([label, arr, color]) => (
                      <div key={label} className="flex items-center gap-3 hair-b border-b last:border-b-0 pb-2">
                        <div className="flex-1">
                          <div className="text-[13px] text-[var(--ink)]">{label}</div>
                          <div className="font-mono text-[18px] text-[var(--navy)] leading-tight">{(arr || []).reduce((s, p) => s + p.count, 0)}</div>
                        </div>
                        <Sparkline values={spark(arr).length ? spark(arr) : [0, 0]} color={color} />
                      </div>
                    ))}
                  </div>
                </Card>
                <Card>
                  <SectionLabel>Users by role</SectionLabel>
                  {roleRows.length === 0 ? <div className="text-[12.5px] text-[var(--muted)]">No users.</div>
                    : <DataTable dense
                        columns={[{ key: 'k', label: 'Role', render: r => <Tag tone="navy">{r.k}</Tag> }, { key: 'v', label: 'Count', align: 'right', render: r => <span className="font-mono">{r.v.toLocaleString()}</span> }]}
                        rows={roleRows} />}
                  <div className="mt-3">
                    <SectionLabel>By status</SectionLabel>
                    <div className="flex flex-wrap gap-2">
                      {statusRows.map(r => <span key={r.k} className="text-[12px] hair border rounded-sm px-2 py-1"><span className="text-[var(--muted)]">{r.k}:</span> <span className="font-mono">{r.v}</span></span>)}
                    </div>
                  </div>
                </Card>
              </div>

              <div className="grid grid-cols-4 gap-4">
                <KpiCard label="Feed posts" value={(ct.feed_posts || 0).toLocaleString()} accent="sage" />
                <KpiCard label="Applications" value={(ct.applications || 0).toLocaleString()} />
                <KpiCard label="Corpus documents" value={corp.documents != null ? corp.documents.toLocaleString() : '—'} subtle={corp.dense_chunks != null ? `${corp.dense_chunks.toLocaleString()} chunks` : ''} accent="gold" />
                <KpiCard label="API memory" value={host.mem_percent != null ? host.mem_percent + '%' : '—'} subtle="host" accent="ember" />
              </div>
              <div className="mt-3 text-[11px] text-[var(--muted)] font-mono">generated {data.generated_at ? new Date(data.generated_at).toLocaleString() : '—'}</div>
            </>
          );
        })()}
      </_SysState>
    </>
  );
}

// ---- System · Incidents ----
const _INC_SEV = [['sev1', 'SEV1 · Critical'], ['sev2', 'SEV2 · High'], ['sev3', 'SEV3 · Moderate'], ['sev4', 'SEV4 · Low']];
const _INC_STATUS = ['investigating', 'identified', 'monitoring', 'resolved'];
function _incSevTone(s) { return (s === 'sev1' || s === 'sev2') ? 'red' : s === 'sev3' ? 'gold' : 'navy'; }
function _incStatusTone(s) { return s === 'resolved' ? 'sage' : s === 'monitoring' ? 'navy' : s === 'identified' ? 'gold' : 'red'; }
function _incStatusLabel(s) { return { investigating: 'Investigating', identified: 'Identified', monitoring: 'Monitoring', resolved: 'Resolved' }[s] || s; }
function _fmtMttr(secs) { if (secs == null) return '—'; const h = Math.floor(secs / 3600), m = Math.floor((secs % 3600) / 60); return h > 0 ? `${h}h ${m}m` : `${m}m`; }
function _incFmt(iso) { if (!iso) return '—'; try { return new Date(iso).toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }); } catch { return iso; } }

function SuperIncidents() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [filter, setFilter] = useState('');
  const [selId, setSelId] = useState(null);
  const [creating, setCreating] = useState(false);

  const load = useCallback(() => {
    setLoading(true); setError('');
    const q = filter ? (filter === 'open' ? '?open_only=true' : `?status=${filter}`) : '';
    AnchorAPI.apiGet(`/v1/super-admin/incidents${q}`)
      .then(d => setRows(d.items || []))
      .catch(e => setError(e.message || 'Failed to load'))
      .finally(() => setLoading(false));
  }, [filter]);
  useEffect(() => { load(); }, [load]);

  const openCount = rows.filter(r => r.is_open).length;
  const FILTERS = [['', 'All'], ['open', 'Open'], ['investigating', 'Investigating'], ['identified', 'Identified'], ['monitoring', 'Monitoring'], ['resolved', 'Resolved']];

  return (
    <>
      <PageHeader title="Incidents"
        description="Operational incident log — declare, track, and resolve platform incidents. Every change is recorded in the audit trail."
        actions={<PrimaryButton mode="ember" icon="plus" onClick={() => setCreating(true)}>Declare incident</PrimaryButton>} />

      <div className="grid grid-cols-4 gap-4 mb-4">
        <KpiCard label="Open incidents" value={openCount} accent="ember" />
        <KpiCard label="Total (shown)" value={rows.length} />
        <KpiCard label="SEV1/2 open" value={rows.filter(r => r.is_open && (r.severity === 'sev1' || r.severity === 'sev2')).length} accent="ember" />
        <KpiCard label="Resolved (shown)" value={rows.filter(r => r.status === 'resolved').length} accent="sage" />
      </div>

      <div className="flex items-center gap-1.5 mb-3">
        {FILTERS.map(([v, l]) => (
          <button key={v || 'all'} onClick={() => setFilter(v)} className="px-2.5 py-1 rounded-sm text-[12px] border hair transition-colors"
            style={filter === v ? { background: 'var(--ember)', color: '#fff', borderColor: 'var(--ember)' } : { color: 'var(--muted)' }}>{l}</button>
        ))}
        <button onClick={load} className="ml-auto text-[12px] text-[var(--muted)] hover:text-[var(--ink)] underline">refresh</button>
      </div>

      <Card noPad>
        {loading ? <div className="p-10 text-center text-[13px] text-[var(--muted)]">Loading incidents…</div>
          : error ? <div className="p-6"><AuditNote tone="red" icon="alert-triangle"><span>{error} </span><button onClick={load} className="underline ml-1">Retry →</button></AuditNote></div>
          : rows.length === 0 ? <EmptyState icon="shield-check" title="No incidents" body="Nothing matches this filter. Declare an incident to start tracking." />
          : <DataTable
              columns={[
                { key: 'severity', label: 'Severity', render: r => <Tag tone={_incSevTone(r.severity)}>{r.severity.toUpperCase()}</Tag> },
                { key: 'title', label: 'Incident', render: r => <div><div className="font-medium text-[var(--ink)]">{r.title}</div>{r.component && <div className="text-[11px] text-[var(--muted)] font-mono">{r.component}</div>}</div> },
                { key: 'status', label: 'Status', render: r => <Tag tone={_incStatusTone(r.status)}>{_incStatusLabel(r.status)}</Tag> },
                { key: 'started_at', label: 'Started', render: r => <span className="font-mono text-[11.5px] text-[var(--muted)]">{_incFmt(r.started_at)}</span> },
                { key: 'mttr', label: 'MTTR', align: 'right', render: r => <span className="font-mono text-[12px]">{_fmtMttr(r.mttr_seconds)}</span> },
              ]}
              rows={rows} onRowClick={r => setSelId(r.id)} />}
      </Card>

      <IncidentDetail id={selId} onClose={() => setSelId(null)} onChanged={load} />
      <IncidentCreate open={creating} onClose={() => setCreating(false)} onCreated={() => { setCreating(false); load(); }} />
    </>
  );
}

function IncidentCreate({ open, onClose, onCreated }) {
  const [f, setF] = useState({ title: '', description: '', severity: 'sev3', component: '', status: 'investigating' });
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState('');
  useEffect(() => { if (open) { setF({ title: '', description: '', severity: 'sev3', component: '', status: 'investigating' }); setErr(''); } }, [open]);
  const set = (k, v) => setF(p => ({ ...p, [k]: v }));
  const submit = async () => {
    setSaving(true); setErr('');
    try {
      await AnchorAPI.apiPostAuth('/v1/super-admin/incidents', {
        title: f.title.trim(), description: f.description.trim() || null,
        severity: f.severity, component: f.component.trim() || null, status: f.status,
      });
      onCreated();
    } catch (e) { setErr(e.message || 'Failed to declare incident'); setSaving(false); }
  };
  return (
    <SlideOver open={open} onClose={onClose}>
      <div className="p-5 hair-b flex items-center justify-between">
        <h3 className="font-serif text-[20px] text-[var(--navy)]">Declare incident</h3>
        <button onClick={onClose} className="text-[var(--muted)] hover:text-[var(--ink)]"><Icon name="x" size={18} /></button>
      </div>
      <div className="p-5 space-y-3">
        {err && <AuditNote tone="red" icon="alert-triangle">{err}</AuditNote>}
        <Field label="Title"><input value={f.title} onChange={e => set('title', e.target.value)} placeholder="RAG latency spike" className={INPUT_CLS} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Severity"><select value={f.severity} onChange={e => set('severity', e.target.value)} className={INPUT_CLS}>{_INC_SEV.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field>
          <Field label="Component"><input value={f.component} onChange={e => set('component', e.target.value)} placeholder="RAG / API / Push" className={INPUT_CLS} /></Field>
        </div>
        <Field label="Initial status"><select value={f.status} onChange={e => set('status', e.target.value)} className={INPUT_CLS}>{_INC_STATUS.map(s => <option key={s} value={s}>{_incStatusLabel(s)}</option>)}</select></Field>
        <Field label="Description"><textarea value={f.description} onChange={e => set('description', e.target.value)} rows={4} className={INPUT_CLS} placeholder="What's happening, impact, scope…" /></Field>
      </div>
      <div className="p-4 hair-t flex items-center justify-end gap-2">
        <GhostButton onClick={onClose}>Cancel</GhostButton>
        <PrimaryButton mode="ember" icon="check" onClick={submit} disabled={saving || f.title.trim().length < 3} className={(saving || f.title.trim().length < 3) ? 'opacity-50 pointer-events-none' : ''}>{saving ? 'Declaring…' : 'Declare'}</PrimaryButton>
      </div>
    </SlideOver>
  );
}

function IncidentDetail({ id, onClose, onChanged }) {
  const [inc, setInc] = useState(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [note, setNote] = useState('');
  const [pm, setPm] = useState('');

  const load = useCallback(() => {
    if (!id) return;
    setLoading(true);
    AnchorAPI.apiGet(`/v1/super-admin/incidents/${id}`)
      .then(d => { setInc(d); setPm(d.postmortem || ''); })
      .catch(e => setMsg(e.message))
      .finally(() => setLoading(false));
  }, [id]);
  useEffect(() => { setInc(null); setMsg(''); setNote(''); if (id) load(); }, [id, load]);

  const patch = async (body) => {
    setBusy(true); setMsg('');
    try { const d = await AnchorAPI.apiPatch(`/v1/super-admin/incidents/${id}`, body); setInc(d); setPm(d.postmortem || ''); onChanged && onChanged(); }
    catch (e) { setMsg(e.message || 'Update failed'); }
    finally { setBusy(false); }
  };
  const addNote = async () => {
    if (!note.trim()) return;
    setBusy(true); setMsg('');
    try { const d = await AnchorAPI.apiPostAuth(`/v1/super-admin/incidents/${id}/updates`, { note: note.trim() }); setInc(d); setNote(''); onChanged && onChanged(); }
    catch (e) { setMsg(e.message || 'Failed to add note'); }
    finally { setBusy(false); }
  };

  return (
    <SlideOver open={!!id} onClose={onClose} width={560}>
      {loading && !inc ? <div className="p-10 text-center text-[13px] text-[var(--muted)]">Loading…</div> : inc && (
        <div className="p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2"><Tag tone={_incSevTone(inc.severity)}>{inc.severity.toUpperCase()}</Tag><Tag tone={_incStatusTone(inc.status)}>{_incStatusLabel(inc.status)}</Tag></div>
            <button onClick={onClose} className="w-7 h-7 rounded-sm hover:bg-[var(--mist)]/40 flex items-center justify-center"><Icon name="x" size={14} /></button>
          </div>
          <h3 className="font-serif text-[22px] text-[var(--navy)]" style={{ fontWeight: 500, textWrap: 'pretty' }}>{inc.title}</h3>
          {inc.component && <div className="text-[12px] text-[var(--muted)]">Component: <span className="font-mono">{inc.component}</span></div>}
          {inc.description && <p className="text-[13px] text-[var(--graphite)]" style={{ textWrap: 'pretty' }}>{inc.description}</p>}

          <div className="grid grid-cols-3 gap-2">
            <KpiCard label="Started" value={_incFmt(inc.started_at)} mono={false} />
            <KpiCard label="Resolved" value={inc.resolved_at ? _incFmt(inc.resolved_at) : '—'} mono={false} accent="sage" />
            <KpiCard label="MTTR" value={_fmtMttr(inc.mttr_seconds)} accent="ember" />
          </div>

          {msg && <AuditNote tone="red" icon="alert-triangle">{msg}</AuditNote>}

          <div>
            <SectionLabel>Update status</SectionLabel>
            <div className="flex flex-wrap gap-1.5">
              {_INC_STATUS.map(s => (
                <button key={s} onClick={() => patch({ status: s })} disabled={busy || s === inc.status}
                  className="px-2.5 py-1 rounded-sm text-[12px] border hair disabled:opacity-100"
                  style={s === inc.status ? { background: 'var(--navy)', color: '#fff', borderColor: 'var(--navy)' } : { color: 'var(--muted)' }}>
                  {_incStatusLabel(s)}
                </button>
              ))}
            </div>
          </div>

          <div>
            <SectionLabel right={<MonoChip>{(inc.updates || []).length}</MonoChip>}>Timeline</SectionLabel>
            {(inc.updates || []).length === 0 ? <div className="text-[12.5px] text-[var(--muted)]">No updates yet.</div>
              : <Timeline items={(inc.updates || []).map(u => ({ t: _incFmt(u.created_at), who: u.status ? _incStatusLabel(u.status) : 'note', what: u.note }))} />}
            <div className="mt-3 flex items-center gap-2">
              <input value={note} onChange={e => setNote(e.target.value)} placeholder="Add a timeline note…" className={INPUT_CLS} />
              <PrimaryButton size="sm" mode="navy" icon="plus" onClick={addNote} disabled={busy || !note.trim()} className={(busy || !note.trim()) ? 'opacity-50 pointer-events-none' : ''}>Add</PrimaryButton>
            </div>
          </div>

          <div>
            <SectionLabel>Post-mortem</SectionLabel>
            <textarea value={pm} onChange={e => setPm(e.target.value)} rows={4} className={INPUT_CLS} placeholder="Root cause, remediation, follow-ups…" />
            <div className="mt-2 flex justify-end"><GhostButton size="sm" icon="save" onClick={() => patch({ postmortem: pm })} disabled={busy}>Save post-mortem</GhostButton></div>
          </div>
        </div>
      )}
    </SlideOver>
  );
}

// ---- SUPER ADMIN · Campus Alerts Console ----

function _fmtElapsed(createdAt, now) {
  const secs = Math.max(0, Math.floor((now - new Date(createdAt).getTime()) / 1000));
  const h = String(Math.floor(secs / 3600)).padStart(2, '0');
  const m = String(Math.floor((secs % 3600) / 60)).padStart(2, '0');
  const s = String(secs % 60).padStart(2, '0');
  return `${h}:${m}:${s}`;
}

function _fmtLocation(lat, lng) {
  return (lat != null && lng != null) ? `${lat.toFixed(4)}, ${lng.toFixed(4)}` : 'No GPS data';
}

function _fmtSecs(secs) {
  if (secs == null) return '—';
  const m = Math.floor(secs / 60), s = Math.round(secs % 60);
  return `${m}m ${String(s).padStart(2, '0')}s`;
}

const ALERT_STATE_LABEL = {
  active:      'Active',
  user_safe:   'User Safe',
  closed:      'Closed',
  false_alert: 'False Alarm',
  resolved:    'Resolved',
};

function SuperAlerts({ onGo }) {
  const [tab, setTab] = useState('active');
  const [alerts, setAlerts] = useState([]);
  const [stats, setStats] = useState(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [histState, setHistState] = useState('');
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState({});
  const [actionMsg, setActionMsg] = useState({});
  const [confirmAction, setConfirmAction] = useState(null);
  const [now, setNow] = useState(Date.now());

  // Live clock for elapsed display on active tab
  useEffect(() => {
    if (tab !== 'active') return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [tab]);

  function loadAlerts() {
    if (tab === 'analytics') return;
    setLoading(true); setError('');
    const params = new URLSearchParams({ limit: 50, offset: (page - 1) * 50 });
    if (tab === 'active') params.set('state', 'active');
    if (tab === 'false')  params.set('state', 'active');
    if (tab === 'history' && histState) params.set('state', histState);
    AnchorAPI.apiGet(`/v1/admin/alerts?${params}`)
      .then(d => { setAlerts(d.items || []); setTotal(d.total || 0); setLoading(false); })
      .catch(e => { setError(e.message || 'Failed to load alerts'); setLoading(false); });
  }

  function loadStats() {
    setStatsLoading(true);
    AnchorAPI.apiGet('/v1/admin/alerts/stats')
      .then(d => setStats(d))
      .catch(() => setStats(null))
      .finally(() => setStatsLoading(false));
  }

  useEffect(() => {
    loadAlerts();
    if (tab === 'active' || tab === 'analytics') loadStats();
  }, [tab, page, histState]);

  async function handleAck(eventId) {
    setActionLoading(a => ({ ...a, [eventId]: 'ack' }));
    try {
      await AnchorAPI.apiPostAuth(`/v1/admin/alerts/${eventId}/ack`, {});
      setActionMsg(m => ({ ...m, [eventId]: 'Acknowledged' }));
    } catch (e) {
      setActionMsg(m => ({ ...m, [eventId]: e.message || 'Failed' }));
    } finally {
      setActionLoading(a => ({ ...a, [eventId]: null }));
    }
  }

  async function handleResolve(eventId) {
    setActionLoading(a => ({ ...a, [eventId]: 'resolve' }));
    try {
      await AnchorAPI.apiPostAuth(`/v1/admin/alerts/${eventId}/resolve`, {});
      setConfirmAction(null);
      loadAlerts();
    } catch (e) {
      setActionMsg(m => ({ ...m, [eventId]: e.message || 'Resolve failed' }));
      setConfirmAction(null);
    } finally {
      setActionLoading(a => ({ ...a, [eventId]: null }));
    }
  }

  async function handleFalse(eventId) {
    setActionLoading(a => ({ ...a, [eventId]: 'false' }));
    try {
      await AnchorAPI.apiPostAuth(`/v1/admin/alerts/${eventId}/false`, {});
      setConfirmAction(null);
      loadAlerts();
    } catch (e) {
      setActionMsg(m => ({ ...m, [eventId]: e.message || 'Failed' }));
      setConfirmAction(null);
    } finally {
      setActionLoading(a => ({ ...a, [eventId]: null }));
    }
  }

  async function openDetail(eventId) {
    setSelected(eventId); setDetailLoading(true); setDetail(null);
    try   { setDetail(await AnchorAPI.apiGet(`/v1/admin/alerts/${eventId}`)); }
    catch (e) { setDetail({ _error: e.message || 'Could not load alert detail' }); }
    finally { setDetailLoading(false); }
  }

  const activeCount = tab === 'active' ? total : alerts.filter(a => a.state === 'active').length;

  const LoadingRows = () => (
    <div className="p-6 space-y-3">
      {[1,2,3].map(i => <div key={i} className="h-6 bg-[var(--mist)] rounded-sm animate-pulse" />)}
    </div>
  );

  const ErrorBanner = () => (
    <div className="p-4 text-[13px]" style={{ color:'var(--red)' }}>
      {error} — <button className="underline" onClick={loadAlerts}>Retry</button>
    </div>
  );

  return (
    <>
      <PageHeader
        title="Campus alerts · platform console"
        bn="ক্যাম্পাস সতর্কতা"
        description="Cross-tenant alert operations. Acknowledge active events, dispatch response, moderate false alarms, and review the platform-wide history."
        actions={
          <>
            <span className="text-[12.5px] text-[var(--muted)] px-2">Cross-tenant view</span>
            <GhostButton size="sm" icon="download">Export 24h log</GhostButton>
          </>
        }
      />

      <AuditNote tone="red" icon="shield-alert" className="mb-4">
        Alert event data is stored with anonymous event IDs only. Identity de-anonymization is a separate workflow and requires formal legal grounds.
      </AuditNote>

      {/* Tabs */}
      <div className="flex items-center gap-1 mb-4">
        {[
          { v:'active',    label:`Active (${tab==='active' ? total : '…'})`, dot: tab==='active' && total > 0 },
          { v:'history',   label:'Historical' },
          { v:'false',     label:'False-alarm moderation' },
          { v:'analytics', label:'Analytics' },
        ].map(t => (
          <button key={t.v} onClick={() => { setTab(t.v); setPage(1); setAlerts([]); }}
            className={`px-3 py-1.5 text-[13px] rounded-sm ${tab===t.v?'bg-[var(--ember)] text-white':'hair border text-[var(--graphite)] hover:bg-[var(--mist)]/40'}`}>
            <span className="inline-flex items-center gap-1.5">
              {t.dot && <span className="w-1.5 h-1.5 rounded-full pulse-dot" style={{ background:'var(--red)' }} />}
              {t.label}
            </span>
          </button>
        ))}
      </div>

      {/* ── Active tab ── */}
      {tab==='active' && (
        <>
          <div className="grid grid-cols-4 gap-4 mb-4">
            <KpiCard label="Active alerts" value={loading ? '…' : total} subtle="across all tenants" accent="ember" />
            <KpiCard label="Avg response · 24h" value={statsLoading ? '…' : _fmtSecs(stats?.avg_response_secs_24h)} subtle="responding type" />
            <KpiCard label="False alarms · 30d" value={statsLoading ? '…' : (stats?.false_alarms_30d ?? '—')} accent="ember" />
            <KpiCard label="Resolved · 24h" value={statsLoading ? '…' : (stats?.resolved_24h ?? '—')} />
          </div>

          <Card noPad>
            <div className="p-4 hair-b" style={{ background:'#F6E5E2' }}>
              <div className="flex items-center gap-2 text-[var(--red)]">
                <Icon name="siren" size={16} />
                <span className="font-medium">{loading ? '…' : total} active alerts</span>
                <span className="text-[12px]" style={{ color:'#A2362B' }}>· dispatched response will be permanently logged</span>
              </div>
            </div>

            {loading && <LoadingRows />}
            {!loading && error && <ErrorBanner />}
            {!loading && !error && (
              <div className="divide-y" style={{ borderColor:'var(--mist)' }}>
                {alerts.map(a => (
                  <div key={a.event_id} className="p-5 grid gap-4" style={{ gridTemplateColumns:'1fr 220px' }}>
                    <div>
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <MonoChip tone="navy">{a.event_id.slice(0, 13)}…</MonoChip>
                        {a.tenant_id && <Tag tone="navy">{a.tenant_id.slice(0, 6)}…</Tag>}
                        <span className="smallcaps" style={{ color:'var(--red)' }}>
                          {a.responder_count} responding
                        </span>
                        <span className="text-[11px] text-[var(--muted)] font-mono">
                          triggered {new Date(a.created_at).toLocaleString()}
                        </span>
                      </div>
                      <h3 className="font-serif text-[20px] text-[var(--navy)]" style={{fontWeight:500}}>
                        {_fmtLocation(a.lat, a.lng)}
                      </h3>
                      <div className="text-[12.5px] text-[var(--muted)] mt-0.5">
                        GPS: {a.gps_status} · {a.notification_count} notifications sent
                      </div>

                      {actionMsg[a.event_id] && (
                        <div className="mt-2 text-[12px]" style={{ color: actionMsg[a.event_id] === 'Acknowledged' ? 'var(--sage)' : 'var(--red)' }}>
                          {actionMsg[a.event_id]}
                        </div>
                      )}

                      <div className="mt-4 flex flex-wrap items-center gap-2">
                        <PrimaryButton size="sm" mode="red" icon="bell-ring"
                          disabled={!!actionLoading[a.event_id]}
                          onClick={() => handleAck(a.event_id)}>
                          {actionLoading[a.event_id] === 'ack' ? '…' : 'Acknowledge'}
                        </PrimaryButton>
                        <PrimaryButton size="sm" mode="navy" icon="users">Dispatch response</PrimaryButton>
                        <GhostButton size="sm" icon="phone">Anonymous call</GhostButton>
                        <GhostButton size="sm" icon="building-2">Notify university</GhostButton>
                        <GhostButton size="sm" icon="check-circle"
                          disabled={!!actionLoading[a.event_id]}
                          onClick={() => setConfirmAction({ type: 'resolve', eventId: a.event_id })}>
                          Resolve →
                        </GhostButton>
                      </div>
                    </div>
                    <div className="hair border rounded-sm p-3 text-center" style={{ background:'#FBF9F2' }}>
                      <div className="font-mono text-[28px] text-[var(--ink)]">
                        {_fmtElapsed(a.created_at, now)}
                      </div>
                      <div className="smallcaps text-[var(--muted)] mt-1">elapsed</div>
                      <div className="mt-3 text-[11px] text-[var(--graphite)]">
                        Auto-closes after <span className="font-mono">24h</span>
                      </div>
                    </div>
                  </div>
                ))}
                {alerts.length === 0 && (
                  <EmptyState icon="check-circle" title="No active alerts" body="The platform is currently quiet across all tenants." />
                )}
              </div>
            )}
          </Card>
        </>
      )}

      {/* ── History tab ── */}
      {tab==='history' && (
        <>
          <div className="flex items-center gap-2 mb-3">
            <SectionLabel className="mb-0">Filter by state</SectionLabel>
            <select value={histState} onChange={e => { setHistState(e.target.value); setPage(1); }}
              className="hair border rounded-sm px-2 py-1.5 bg-white text-[12.5px]">
              <option value="">All states</option>
              {Object.entries(ALERT_STATE_LABEL).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
            <span className="ml-auto font-mono text-[12px] text-[var(--muted)]">{total} total</span>
          </div>
          <Card noPad>
            {loading && <LoadingRows />}
            {!loading && error && <ErrorBanner />}
            {!loading && !error && (
              <DataTable
                columns={[
                  { key:'event_id', label:'Event ID', render:r=><MonoChip>{r.event_id.slice(0,13)}…</MonoChip> },
                  { key:'tenant_id', label:'Tenant', render:r=> r.tenant_id ? <Tag tone="navy">{r.tenant_id.slice(0,6)}…</Tag> : <span className="text-[var(--muted)] text-[11px]">—</span> },
                  { key:'state', label:'Status', render:r=><StatusPill status={ALERT_STATE_LABEL[r.state] || r.state} /> },
                  { key:'lat', label:'Location', render:r=><span className="font-mono text-[11.5px]">{_fmtLocation(r.lat, r.lng)}</span> },
                  { key:'responder_count', label:'Responders', align:'right', render:r=><span className="font-mono">{r.responder_count}</span> },
                  { key:'created_at', label:'Triggered', render:r=><span className="font-mono text-[11.5px] text-[var(--muted)]">{new Date(r.created_at).toLocaleString()}</span> },
                  { key:'', label:'', render:r=><GhostButton size="sm" onClick={()=>openDetail(r.event_id)}>Open</GhostButton> },
                ]}
                rows={alerts}
                dense
              />
            )}
            {!loading && !error && alerts.length === 0 && (
              <div className="p-8 text-center text-[13px] text-[var(--muted)]">No alerts found.</div>
            )}
          </Card>
          {total > 50 && (
            <div className="flex items-center gap-2 mt-4 justify-end">
              <GhostButton size="sm" icon="chevron-left" onClick={() => setPage(p => Math.max(1, p-1))} disabled={page===1}>Prev</GhostButton>
              <span className="text-[12px] text-[var(--muted)]">Page {page} / {Math.ceil(total/50)}</span>
              <GhostButton size="sm" icon="chevron-right" onClick={() => setPage(p => p+1)} disabled={page >= Math.ceil(total/50)}>Next</GhostButton>
            </div>
          )}
        </>
      )}

      {/* ── False-alarm moderation tab ── */}
      {tab==='false' && (
        <Card>
          <SectionLabel right={<MonoChip tone="navy">active alerts pending review</MonoChip>}>
            False-alarm moderation
          </SectionLabel>
          {loading && <LoadingRows />}
          {!loading && error && <div className="text-[13px]" style={{color:'var(--red)'}}>{error} — <button className="underline" onClick={loadAlerts}>Retry</button></div>}
          {!loading && !error && (
            <div className="space-y-2">
              {alerts.map(a => (
                <div key={a.event_id} className="hair border rounded-sm p-3 flex items-center gap-3">
                  <Icon name="alert-triangle" size={16} className="text-[var(--muted)]" />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <MonoChip>{a.event_id.slice(0,13)}…</MonoChip>
                      {a.tenant_id && <Tag tone="navy">{a.tenant_id.slice(0,6)}…</Tag>}
                      <span className="text-[13px] text-[var(--ink)]">{_fmtLocation(a.lat, a.lng)}</span>
                    </div>
                    <div className="text-[11.5px] text-[var(--muted)] mt-0.5">
                      {new Date(a.created_at).toLocaleString()} · GPS: {a.gps_status} · {a.responder_count} responders
                    </div>
                    {actionMsg[a.event_id] && (
                      <div className="text-[11.5px] mt-1" style={{color:'var(--red)'}}>{actionMsg[a.event_id]}</div>
                    )}
                  </div>
                  <GhostButton size="sm" danger icon="user-x"
                    disabled={!!actionLoading[a.event_id]}
                    onClick={() => setConfirmAction({ type: 'false', eventId: a.event_id })}>
                    {actionLoading[a.event_id] === 'false' ? '…' : 'Mark false alarm'}
                  </GhostButton>
                  <GhostButton size="sm" icon="check"
                    disabled={!!actionLoading[a.event_id]}
                    onClick={() => setConfirmAction({ type: 'resolve', eventId: a.event_id })}>
                    {actionLoading[a.event_id] === 'resolve' ? '…' : 'Resolve genuine'}
                  </GhostButton>
                </div>
              ))}
              {alerts.length === 0 && (
                <EmptyState icon="shield-check" title="No active alerts pending moderation"
                  body="There are no active alerts to review right now." />
              )}
            </div>
          )}
        </Card>
      )}

      {/* ── Analytics tab ── */}
      {tab==='analytics' && (
        <div className="grid grid-cols-3 gap-4">
          <Card>
            <SectionLabel>Alerts by tenant · 30d</SectionLabel>
            {statsLoading && <div className="text-[12px] text-[var(--muted)]">Loading…</div>}
            {!statsLoading && !(stats?.by_tenant_30d?.length) && (
              <div className="text-[12px] text-[var(--muted)]">No data in the last 30 days</div>
            )}
            {!statsLoading && (stats?.by_tenant_30d || []).length > 0 && (
              <div className="space-y-2 text-[12px]">
                {(() => {
                  const max = Math.max(...stats.by_tenant_30d.map(x => x.count), 1);
                  return stats.by_tenant_30d.map(({ tenant_id, count }) => (
                    <div key={tenant_id ?? 'none'}>
                      <div className="flex justify-between mb-1">
                        <span className="font-mono text-[11px] truncate max-w-[120px]">
                          {tenant_id ? tenant_id.slice(0, 8) + '…' : '(none)'}
                        </span>
                        <span className="font-mono">{count}</span>
                      </div>
                      <div className="h-1.5 bg-[var(--mist)] rounded-sm overflow-hidden">
                        <div className="h-full bg-[var(--ember)]" style={{ width: `${(count / max) * 100}%` }} />
                      </div>
                    </div>
                  ));
                })()}
              </div>
            )}
          </Card>
          <Card>
            <SectionLabel>By zone type · 30d</SectionLabel>
            {statsLoading && <div className="text-[12px] text-[var(--muted)]">Loading…</div>}
            {!statsLoading && !(stats?.by_zone_type_30d?.length) && (
              <div className="text-[12px] text-[var(--muted)]">No data in the last 30 days</div>
            )}
            {!statsLoading && (stats?.by_zone_type_30d || []).length > 0 && (
              <div className="space-y-2 text-[12px]">
                {(() => {
                  const max = Math.max(...stats.by_zone_type_30d.map(x => x.count), 1);
                  return stats.by_zone_type_30d.map(({ zone_type, count }) => (
                    <div key={zone_type}>
                      <div className="flex justify-between mb-1">
                        <span className="capitalize">{zone_type}</span>
                        <span className="font-mono">{count}</span>
                      </div>
                      <div className="h-1.5 bg-[var(--mist)] rounded-sm overflow-hidden">
                        <div className="h-full bg-[var(--navy)]" style={{ width: `${(count / max) * 100}%` }} />
                      </div>
                    </div>
                  ));
                })()}
              </div>
            )}
          </Card>
          <Card>
            <SectionLabel>Resolution time histogram</SectionLabel>
            {statsLoading && <div className="text-[11px] text-[var(--muted)]">Loading…</div>}
            {!statsLoading && (
              <div className="space-y-1.5 text-[11px] font-mono">
                {(() => {
                  const hist = stats?.resolution_histogram_30d || [];
                  const max = Math.max(...hist.map(x => x.count), 1);
                  return hist.map(({ bucket, count }) => (
                    <div key={bucket} className="flex items-center gap-2">
                      <span className="w-20 text-[var(--muted)]">{bucket}</span>
                      <div className="flex-1 h-3 bg-[var(--mist)] rounded-sm overflow-hidden">
                        <div className="h-full bg-[var(--sage)]" style={{ width: `${(count / max) * 100}%` }} />
                      </div>
                      <span className="w-6 text-right">{count}</span>
                    </div>
                  ));
                })()}
                {!(stats?.resolution_histogram_30d?.some(b => b.count > 0)) && (
                  <div className="text-[var(--muted)] text-center pt-1">No closed alerts in 30 days</div>
                )}
              </div>
            )}
          </Card>
        </div>
      )}

      {/* ── Alert detail slide-over (opened from history tab) ── */}
      <SlideOver open={!!selected} onClose={() => { setSelected(null); setDetail(null); }} width={560}>
        {detailLoading && <div className="p-5 text-[13px] text-[var(--muted)]">Loading…</div>}
        {detail && detail._error && <div className="p-5 text-[13px]" style={{color:'var(--red)'}}>{detail._error}</div>}
        {detail && !detail._error && !detailLoading && (
          <div className="p-5 space-y-4">
            <div className="flex items-center justify-between">
              <SectionLabel className="mb-0">Alert detail</SectionLabel>
              <button onClick={() => { setSelected(null); setDetail(null); }}
                className="w-7 h-7 rounded-sm hover:bg-[var(--mist)]/40 flex items-center justify-center">
                <Icon name="x" size={14} />
              </button>
            </div>

            <div className="flex items-center gap-2 flex-wrap">
              <MonoChip tone="navy">{detail.event_id.slice(0,13)}…</MonoChip>
              <StatusPill status={ALERT_STATE_LABEL[detail.state] || detail.state} />
              <span className="ml-auto font-mono text-[11px] text-[var(--muted)]">
                {new Date(detail.created_at).toLocaleString()}
              </span>
            </div>

            <div className="hair border rounded-sm p-3 font-mono text-[12px] space-y-1 bg-[#FBF9F2]">
              <div><span className="text-[var(--muted)]">location:</span> {_fmtLocation(detail.lat, detail.lng)}</div>
              <div><span className="text-[var(--muted)]">gps:</span> {detail.gps_status}</div>
              <div><span className="text-[var(--muted)]">evidence:</span> {detail.evidence_count} items</div>
              {detail.closed_at && <div><span className="text-[var(--muted)]">closed:</span> {new Date(detail.closed_at).toLocaleString()} by {detail.closed_by}</div>}
            </div>

            {detail.zone && (
              <>
                <SectionLabel>Zone</SectionLabel>
                <div className="hair border rounded-sm p-3 font-mono text-[12px] space-y-1">
                  <div><span className="text-[var(--muted)]">type:</span> {detail.zone.zone_type}</div>
                  <div><span className="text-[var(--muted)]">center:</span> {detail.zone.center_lat?.toFixed(4)}, {detail.zone.center_lng?.toFixed(4)}</div>
                  <div><span className="text-[var(--muted)]">radius:</span> {detail.zone.radius_m}m</div>
                  <div><span className="text-[var(--muted)]">status:</span> {detail.zone.status}</div>
                </div>
              </>
            )}

            {detail.notifications && detail.notifications.length > 0 && (
              <>
                <SectionLabel>Notifications ({detail.notifications.length})</SectionLabel>
                <div className="space-y-1.5 max-h-40 overflow-y-auto">
                  {detail.notifications.map((n, i) => (
                    <div key={i} className="hair border rounded-sm px-3 py-2 text-[12px] flex items-center gap-2">
                      <Tag tone="mist">{n.recipient_type}</Tag>
                      <Tag tone="mist">{n.channel}</Tag>
                      <StatusPill status={n.status === 'sent' || n.status === 'delivered' ? 'Resolved' : n.status === 'failed' ? 'Escalated' : 'Submitted'} dot={false} />
                      {n.sent_at && <span className="ml-auto font-mono text-[10.5px] text-[var(--muted)]">{new Date(n.sent_at).toLocaleTimeString()}</span>}
                    </div>
                  ))}
                </div>
              </>
            )}

            {detail.responses && detail.responses.length > 0 && (
              <>
                <SectionLabel>Responder actions ({detail.responses.length})</SectionLabel>
                <div className="space-y-1.5">
                  {detail.responses.map((r, i) => (
                    <div key={i} className="hair border rounded-sm px-3 py-2 text-[12px] flex items-center gap-2">
                      <Tag tone={r.response_type === 'responding' ? 'sage' : r.response_type === 'flagged_fake' ? 'red' : 'mist'}>{r.response_type}</Tag>
                      {r.distance_m != null && <span className="text-[var(--muted)]">{r.distance_m}m away</span>}
                      <span className="ml-auto font-mono text-[10.5px] text-[var(--muted)]">{new Date(r.created_at).toLocaleTimeString()}</span>
                    </div>
                  ))}
                </div>
              </>
            )}

            {detail.state === 'active' && (
              <div className="flex gap-2 pt-2">
                <PrimaryButton mode="ember" icon="check-circle" size="sm"
                  disabled={!!actionLoading[detail.event_id]}
                  onClick={() => setConfirmAction({ type: 'resolve', eventId: detail.event_id })}>
                  Resolve
                </PrimaryButton>
                <GhostButton danger icon="user-x" size="sm"
                  disabled={!!actionLoading[detail.event_id]}
                  onClick={() => setConfirmAction({ type: 'false', eventId: detail.event_id })}>
                  Mark false alarm
                </GhostButton>
                <GhostButton icon="bell-ring" size="sm"
                  disabled={!!actionLoading[detail.event_id]}
                  onClick={() => handleAck(detail.event_id)}>
                  {actionLoading[detail.event_id] === 'ack' ? '…' : 'Ack'}
                </GhostButton>
              </div>
            )}
          </div>
        )}
      </SlideOver>

      {/* ── Confirm modal for destructive actions ── */}
      <ConfirmModal
        open={!!confirmAction}
        onClose={() => setConfirmAction(null)}
        onConfirm={() => {
          if (!confirmAction) return;
          if (confirmAction.type === 'resolve') handleResolve(confirmAction.eventId);
          if (confirmAction.type === 'false')   handleFalse(confirmAction.eventId);
        }}
        title={confirmAction?.type === 'false' ? 'Mark as false alarm?' : 'Resolve this alert?'}
        body={
          confirmAction?.type === 'false'
            ? 'This will mark the alert as a confirmed false alarm and apply a 30-day ban on the triggering device. This action is permanent and audit-logged.'
            : 'This will mark the alert as formally resolved. The linked zone will be archived. This action is audit-logged.'
        }
        confirmWord={confirmAction?.type === 'false' ? 'BAN' : 'RESOLVE'}
        confirmLabel={confirmAction?.type === 'false' ? 'Mark false & ban device' : 'Resolve alert'}
        tone="red"
      />
    </>
  );
}

// ---- SUPER ADMIN · Content Moderation (removal authority) ----
function SuperModeration() {
  const [tab, setTab] = useState('news');
  const [confirm, setConfirm] = useState(null);

  const news = [
    { id:'VP-2026-0144', tenant:'diu', publisher:'Trust 14 · publisher_a4f1', title:'Suspected adulterated cooking oil at Mirpur 10', filed:'2026-05-24 09:11', flags:'2 challenges · pattern: false-info' },
    { id:'VP-2026-0143', tenant:'du', publisher:'Trust 9 · publisher_b22a', title:'Police-uniform impersonators in Dhanmondi area', filed:'2026-05-23 18:20', flags:'AI: review carefully' },
    { id:'VP-2026-0142', tenant:'diu', publisher:'Trust 18 · publisher_c019', title:'Severe water-logging on Ashulia road', filed:'2026-05-23 07:00', flags:'OK' },
    { id:'VP-2026-0140', tenant:'buet', publisher:'Trust 4 · publisher_d901', title:'(Claim) Power outage scheduled for Friday', filed:'2026-05-22 13:05', flags:'8 challenges · likely false' },
  ];
  const applications = [
    { id:'APP-2026-0091', tenant:'diu', kind:'FIR draft', subject:'Vehicle theft · Ashulia Thana', filed:'2026-05-22 14:00', flags:'duplicate of APP-0085' },
    { id:'APP-2026-0084', tenant:'du', kind:'Lawyer chat request', subject:'Tenancy dispute · Dhanmondi', filed:'2026-05-20 11:20', flags:'spam pattern' },
    { id:'APP-2026-0072', tenant:'diu', kind:'GD draft', subject:'Lost ID card', filed:'2026-05-18 09:00', flags:'incomplete' },
  ];
  const reports = [
    { id:'CMP-2026-A4F9', tenant:'diu', kind:'Complaint', subject:'Grade dispute · SWE-405 midterm', filed:'2026-05-15 12:00', flags:'student banned for spam · keep or purge?' },
    { id:'GRV-2026-CR03', tenant:'du', kind:'Anonymous culture report', subject:'(content sealed)', filed:'2026-05-10 21:00', flags:'AI pattern: extortion attempt' },
    { id:'CMP-2026-A3K1', tenant:'nsu', kind:'Complaint', subject:'(content sealed — NSU suspended)', filed:'2026-04-30 10:00', flags:'tenant suspended' },
  ];

  return (
    <>
      <PageHeader
        title="Content moderation"
        bn="বিষয়বস্তু মডারেশন"
        description="Cross-platform removal authority. Take down news posts, applications, and reports that violate policy or threaten platform integrity."
      />

      <AuditNote tone="red" icon="shield-alert" className="mb-4">
        Removal is permanent and logged in the append-only audit chain. Use only against confirmed policy violations: false information, impersonation, abuse, spam, or content from a suspended tenant. Every action is reviewable by external oversight.
      </AuditNote>

      <div className="grid grid-cols-4 gap-4 mb-5">
        <KpiCard label="Pending review · news" value={news.length} accent="ember" />
        <KpiCard label="Pending · applications" value={applications.length} accent="navy" />
        <KpiCard label="Pending · reports" value={reports.length} accent="navy" />
        <KpiCard label="Removed · 30d" value="48" subtle="all audit-logged" />
      </div>

      <div className="flex items-center gap-1 mb-4">
        {[
          { v:'news', label:'News · Verification feed', icon:'newspaper', count:news.length },
          { v:'apps', label:'Applications', icon:'file-text', count:applications.length },
          { v:'reports', label:'Reports & complaints', icon:'message-square-warning', count:reports.length },
          { v:'history', label:'Removal history', icon:'history' },
        ].map(t => (
          <button key={t.v} onClick={()=>setTab(t.v)} className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-[13px] rounded-sm ${tab===t.v?'bg-[var(--ember)] text-white':'hair border text-[var(--graphite)]'}`}>
            <Icon name={t.icon} size={12} />
            {t.label}
            {t.count!==undefined && <span className={`font-mono text-[10px] ml-1 px-1 rounded-sm ${tab===t.v?'bg-white/20':'bg-[var(--mist)]/60'}`}>{t.count}</span>}
          </button>
        ))}
      </div>

      {tab==='news' && (
        <ModerationList items={news} kind="news" onRemove={item=>setConfirm({item, kind:'news'})} />
      )}
      {tab==='apps' && (
        <ModerationList items={applications} kind="app" onRemove={item=>setConfirm({item, kind:'application'})} />
      )}
      {tab==='reports' && (
        <ModerationList items={reports} kind="report" onRemove={item=>setConfirm({item, kind:'report'})} />
      )}
      {tab==='history' && (
        <Card noPad>
          <DataTable
            columns={[
              { key:'t', label:'Removed at', render:r=><span className="font-mono text-[11.5px] text-[var(--muted)]">{r.t}</span> },
              { key:'id', label:'Content ID', render:r=><MonoChip>{r.id}</MonoChip> },
              { key:'kind', label:'Kind' },
              { key:'tenant', label:'Tenant', render:r=><Tag tone="navy">{r.tenant}</Tag> },
              { key:'reason', label:'Reason' },
              { key:'actor', label:'By' },
            ]}
            rows={[
              { t:'2026-05-23 22:11', id:'VP-2026-0089', kind:'News post', tenant:'du', reason:'False information · 12 challenges', actor:'super_z01' },
              { t:'2026-05-22 11:14', id:'APP-2026-0078', kind:'FIR draft', tenant:'diu', reason:'Spam pattern · same submitter ×8', actor:'super_z02' },
              { t:'2026-05-21 09:00', id:'VP-2026-0081', kind:'News post', tenant:'buet', reason:'Impersonation of authority', actor:'super_z01' },
              { t:'2026-05-19 16:40', id:'CMP-2026-A2K0', kind:'Complaint', tenant:'nsu', reason:'Tenant suspended · routine purge', actor:'super_z01' },
              { t:'2026-05-18 08:33', id:'VP-2026-0076', kind:'News post', tenant:'diu', reason:'Doxxing risk · identifying info', actor:'super_z02' },
            ]}
            dense
          />
        </Card>
      )}

      <ConfirmModal
        open={!!confirm} onClose={()=>setConfirm(null)} onConfirm={()=>{}}
        title={confirm ? `Remove this ${confirm.kind}?` : ''}
        body={confirm ? `Permanently removing ${confirm.item.id} will tombstone it in the originating tenant and notify the publisher. The action is permanent, audit-logged, and reviewable by external oversight.` : ''}
        confirmWord="REMOVE" confirmLabel="Remove permanently" tone="red"
      />
    </>
  );
}

function ModerationList({ items, kind, onRemove }) {
  return (
    <Card noPad>
      <div className="divide-y" style={{ borderColor:'var(--mist)' }}>
        {items.map(it => (
          <div key={it.id} className="p-4 flex items-start gap-3">
            <div className="w-9 h-9 rounded-sm bg-[var(--mist)] flex items-center justify-center shrink-0">
              <Icon name={kind==='news'?'newspaper':kind==='app'?'file-text':'message-square-warning'} size={14} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-1 flex-wrap">
                <MonoChip>{it.id}</MonoChip>
                <Tag tone="navy">{it.tenant}</Tag>
                {it.kind && <Tag tone="mist">{it.kind}</Tag>}
                <span className="ml-auto font-mono text-[11px] text-[var(--muted)]">{it.filed}</span>
              </div>
              <div className="text-[14px] text-[var(--ink)] font-medium" style={{textWrap:'pretty'}}>{it.title || it.subject}</div>
              <div className="text-[11.5px] text-[var(--muted)] mt-1 flex items-center gap-2">
                {it.publisher && <span><Icon name="user" size={11} className="inline mr-1" />{it.publisher}</span>}
                {it.flags && <span><Icon name="flag" size={11} className="inline mr-1" />{it.flags}</span>}
              </div>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <GhostButton size="sm" icon="eye">Open</GhostButton>
              <GhostButton size="sm" icon="rotate-ccw">Return to tenant</GhostButton>
              <PrimaryButton size="sm" mode="red" icon="trash-2" onClick={()=>onRemove(it)}>Remove</PrimaryButton>
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

// ---- User Management ----
const ROLE_TAG = {
  super_admin: { label: 'Super Admin', tone: 'red' },
  admin:       { label: 'Admin',       tone: 'sage' },
  moderator:   { label: 'Moderator',   tone: 'gold' },
  student:     { label: 'Student',     tone: 'navy' },
  user:        { label: 'User',        tone: 'muted' },
};

function SuperUsers() {
  const [users, setUsers]           = useState([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState('');
  const [page, setPage]             = useState(1);
  const [pages, setPages]           = useState(1);
  const [total, setTotal]           = useState(0);
  const [roleFilter, setRoleFilter] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm]             = useState({ full_name: '', email: '', password: '', role: 'admin', staff_position: '' });
  const [creating, setCreating]     = useState(false);
  const [createError, setCreateError] = useState('');

  async function load() {
    setLoading(true); setError('');
    try {
      const params = new URLSearchParams({ page });
      if (roleFilter) params.set('role', roleFilter);
      const data = await AnchorAPI.apiGet(`/v1/admin/users?${params}`);
      setUsers(data.items);
      setTotal(data.total);
      setPages(data.pages);
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); }, [page, roleFilter]);

  async function handleCreate(e) {
    e.preventDefault(); setCreating(true); setCreateError('');
    try {
      const payload = { ...form, staff_position: form.staff_position || null };
      await AnchorAPI.apiPostAuth('/v1/admin/users', payload);
      setShowCreate(false);
      setForm({ full_name: '', email: '', password: '', role: 'admin', staff_position: '' });
      load();
    } catch (e) { setCreateError(e.message); }
    finally { setCreating(false); }
  }

  async function patchStatus(userId, newStatus) {
    try {
      await AnchorAPI.apiPatch(`/v1/admin/users/${userId}/status`, { status: newStatus });
      load();
    } catch (e) { alert(e.message); }
  }

  async function patchRole(userId, newRole) {
    try {
      await AnchorAPI.apiPatch(`/v1/admin/users/${userId}/role`, { role: newRole });
      load();
    } catch (e) { alert(e.message); }
  }

  async function patchPosition(userId, newPosition) {
    try {
      await AnchorAPI.apiPatch(`/v1/admin/users/${userId}/position`, { staff_position: newPosition || null });
      load();
    } catch (e) { alert(e.message); }
  }

  const rt = ROLE_TAG;

  return (
    <>
      <PageHeader
        title="Users"
        bn="ব্যবহারকারী"
        description="All registered accounts across the platform. Super Admin can create admin and moderator accounts directly — no email verification required."
        actions={
          <PrimaryButton icon="plus" mode="ember" size="sm" onClick={() => setShowCreate(true)}>
            Create admin
          </PrimaryButton>
        }
      />

      {/* Filters */}
      <div className="flex items-center gap-2 mb-4">
        {['', 'super_admin', 'admin', 'moderator', 'student', 'user'].map(r => (
          <button
            key={r}
            onClick={() => { setRoleFilter(r); setPage(1); }}
            className={`px-3 py-1.5 rounded-sm text-[12px] hair border transition ${roleFilter === r ? 'bg-[var(--navy)] text-white border-[var(--navy)]' : 'text-[var(--graphite)] hover:bg-[var(--mist)]/40'}`}
          >
            {r ? (rt[r]?.label || r) : 'All roles'}
          </button>
        ))}
        <span className="ml-auto font-mono text-[12px] text-[var(--muted)]">{total} users</span>
      </div>

      <Card noPad>
        {loading && <div className="p-8 text-center text-[13px] text-[var(--muted)]">Loading…</div>}
        {error && <div className="p-4 text-[13px] text-[var(--red)]">{error}</div>}
        {!loading && !error && (
          <DataTable
            columns={[
              { key: 'full_name', label: 'Name', render: r => (
                <div>
                  <div className="text-[13px] font-medium text-[var(--ink)]">{r.full_name}</div>
                  <div className="text-[11px] text-[var(--muted)] font-mono">{r.email || r.phone || '—'}</div>
                </div>
              )},
              { key: 'role', label: 'Role', render: r => {
                const info = rt[r.role] || { label: r.role, tone: 'muted' };
                return <Tag tone={info.tone}>{info.label}</Tag>;
              }},
              { key: 'status', label: 'Status', render: r => <StatusPill status={r.status} /> },
              { key: 'staff_position', label: 'App. stage', render: r => (
                (r.role === 'admin' || r.role === 'moderator')
                  ? (
                    <select
                      value={r.staff_position || ''}
                      onClick={e => e.stopPropagation()}
                      onChange={e => patchPosition(r.id, e.target.value)}
                      className="text-[11px] px-1.5 py-1 hair border rounded-sm bg-white text-[var(--graphite)]"
                    >
                      <option value="">— none —</option>
                      {['mentor', 'department_head', 'dean', 'accounts'].map(p => (
                        <option key={p} value={p}>{p}</option>
                      ))}
                    </select>
                  )
                  : <span className="text-[11px] text-[var(--muted)]">—</span>
              )},
              { key: 'mfa_enabled', label: 'MFA', render: r => (
                <span className={`font-mono text-[11px] ${r.mfa_enabled ? 'text-[var(--sage)]' : 'text-[var(--muted)]'}`}>
                  {r.mfa_enabled ? 'ON' : 'off'}
                </span>
              )},
              { key: 'actions', label: '', render: r => (
                <div className="flex items-center gap-1.5 justify-end" onClick={e => e.stopPropagation()}>
                  {/* Role selector (super_admin only) */}
                  <select
                    value={r.role}
                    onChange={e => patchRole(r.id, e.target.value)}
                    className="text-[11px] px-1.5 py-1 hair border rounded-sm bg-white text-[var(--graphite)]"
                  >
                    {['admin', 'moderator', 'user', 'student'].map(ro => (
                      <option key={ro} value={ro}>{ro}</option>
                    ))}
                  </select>
                  {/* Suspend / activate */}
                  {r.status === 'active'
                    ? <button onClick={() => patchStatus(r.id, 'suspended')} className="text-[11px] px-2 py-1 hair border rounded-sm text-[var(--red)] hover:bg-[var(--ember-tint)]/40">Suspend</button>
                    : <button onClick={() => patchStatus(r.id, 'active')} className="text-[11px] px-2 py-1 hair border rounded-sm text-[var(--sage)] hover:bg-[var(--sage-tint)]/40">Activate</button>
                  }
                </div>
              )},
            ]}
            rows={users}
            dense
          />
        )}
      </Card>

      {/* Pagination */}
      {pages > 1 && (
        <div className="flex items-center gap-2 mt-4 justify-end">
          <GhostButton size="sm" icon="chevron-left" onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}>Prev</GhostButton>
          <span className="text-[12px] text-[var(--muted)]">Page {page} / {pages}</span>
          <GhostButton size="sm" icon="chevron-right" onClick={() => setPage(p => Math.min(pages, p + 1))} disabled={page === pages}>Next</GhostButton>
        </div>
      )}

      {/* Create admin modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center fade-in" style={{ background: 'var(--overlay)' }} onClick={() => setShowCreate(false)}>
          <div className="bg-[var(--paper)] w-[480px] rounded-sm hair border shadow-xl p-6" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-serif text-[22px] text-[var(--navy)]" style={{ fontWeight: 500 }}>Create admin account</h2>
              <button onClick={() => setShowCreate(false)} className="w-7 h-7 rounded-sm hover:bg-[var(--mist)]/40 flex items-center justify-center">
                <Icon name="x" size={14} />
              </button>
            </div>

            <AuditNote tone="navy" icon="shield-check" className="mb-4">
              Account will be immediately active — no email verification required. Action is audit-logged.
            </AuditNote>

            {createError && (
              <div className="mb-3 px-3 py-2 rounded-sm text-[12px] flex items-center gap-2" style={{ background: 'var(--ember-tint)', color: 'var(--ember)' }}>
                <Icon name="circle-alert" size={13} />
                {createError}
              </div>
            )}

            <form onSubmit={handleCreate} className="space-y-3">
              <Field label="Full name">
                <input value={form.full_name} onChange={e => setForm(f => ({ ...f, full_name: e.target.value }))}
                  required className="w-full px-3 py-2.5 hair border rounded-sm bg-white text-[13px]" />
              </Field>
              <Field label="Email address">
                <input type="email" value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))}
                  required className="w-full px-3 py-2.5 hair border rounded-sm bg-white text-[13px]" />
              </Field>
              <Field label="Password" hint="Min 8 characters. Must not appear in breach databases.">
                <input type="password" value={form.password} onChange={e => setForm(f => ({ ...f, password: e.target.value }))}
                  required minLength={8} className="w-full px-3 py-2.5 hair border rounded-sm bg-white text-[13px]" />
              </Field>
              <Field label="Role">
                <select value={form.role} onChange={e => setForm(f => ({ ...f, role: e.target.value }))}
                  className="w-full px-3 py-2 hair border rounded-sm bg-white text-[13px]">
                  <option value="admin">Admin</option>
                  <option value="moderator">Moderator</option>
                </select>
              </Field>
              <Field label="Application stage" hint="Which approval stage this staff member handles. Leave as none for general admins.">
                <select value={form.staff_position} onChange={e => setForm(f => ({ ...f, staff_position: e.target.value }))}
                  className="w-full px-3 py-2 hair border rounded-sm bg-white text-[13px]">
                  <option value="">— none —</option>
                  <option value="mentor">Mentor</option>
                  <option value="department_head">Department Head</option>
                  <option value="dean">Dean</option>
                  <option value="accounts">Accounts</option>
                </select>
              </Field>
              <div className="flex gap-2 pt-2">
                <PrimaryButton as="button" type="submit" mode="ember" icon="user-plus" disabled={creating} className="flex-1 justify-center">
                  {creating ? 'Creating…' : 'Create account'}
                </PrimaryButton>
                <GhostButton type="button" onClick={() => setShowCreate(false)}>Cancel</GhostButton>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}

// ─── Red Zone Map ─────────────────────────────────────────────────────────────

const ZONE_COLORS = {
  red:    '#ef4444',
  purple: '#a855f7',
  black:  '#374151',
};

const ZONE_TYPE_LABELS = {
  red:    'Danger Zone',
  purple: 'Murder Report Area',
  black:  'Assault Report Area',
};

function SuperRedZones({ onGo }) {
  const [zones, setZones] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [mapError, setMapError] = useState(null);
  const [statusFilter, setStatusFilter] = useState('active');
  const [typeFilters, setTypeFilters] = useState({ red: true, purple: true, black: true });

  // 'list' = zone roster, 'form' = create/edit — both inside the right panel, no overlay
  const [panelMode, setPanelMode] = useState('list');
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ zone_type: 'red', center_lat: '', center_lng: '', radius_m: 300, name: '', description_public: '', expires_at: '' });
  const [formError, setFormError] = useState(null);
  const [saving, setSaving] = useState(false);

  const [confirmArchive, setConfirmArchive] = useState(null);
  const [archiving, setArchiving] = useState(false);

  const [clickMode, setClickMode] = useState(false);
  const clickModeRef = useRef(false);

  const mapDivRef = useRef(null);
  const leafletMapRef = useRef(null);
  const circleLayersRef = useRef({});

  function load() {
    setLoading(true);
    setLoadError(null);
    AnchorAPI.apiGet('/v1/super-admin/zones?limit=200')
      .then(data => { setZones(data); setLoading(false); })
      .catch(err => {
        const msg = err.message || 'Failed to load zones';
        setLoadError(msg.includes('Session expired') ? 'Session expired — please sign in again.' : msg);
        setLoading(false);
      });
  }

  useEffect(() => { load(); }, []);

  useEffect(() => { clickModeRef.current = clickMode; }, [clickMode]);

  // Init Leaflet once — guard against CDN not loading
  useEffect(() => {
    if (!mapDivRef.current || leafletMapRef.current) return;
    if (!window.L) {
      setMapError('Map library failed to load. Please refresh the page.');
      return;
    }
    try {
      const map = window.L.map(mapDivRef.current, { zoomControl: true }).setView([23.7450, 90.3718], 12);
      window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19,
      }).addTo(map);
      leafletMapRef.current = map;
      // Fix black tiles — container may not have final size at mount time
      setTimeout(() => map.invalidateSize(), 100);

      map.on('click', (e) => {
        if (!clickModeRef.current) return;
        setClickMode(false);
        setForm(f => ({
          ...f,
          center_lat: String(e.latlng.lat.toFixed(6)),
          center_lng: String(e.latlng.lng.toFixed(6)),
        }));
        setEditing(null);
        setFormError(null);
        setPanelMode('form');
      });
    } catch (err) {
      setMapError('Map failed to initialise: ' + (err.message || 'unknown error'));
    }

    return () => {
      if (leafletMapRef.current) { leafletMapRef.current.remove(); leafletMapRef.current = null; }
      circleLayersRef.current = {};
    };
  }, []);

  // Redraw circles whenever zones list changes
  useEffect(() => {
    const map = leafletMapRef.current;
    if (!map || !window.L) return;
    Object.values(circleLayersRef.current).forEach(c => c.remove());
    circleLayersRef.current = {};

    zones.forEach(zone => {
      const color = ZONE_COLORS[zone.zone_type] || '#E8312A';
      const isArchived = zone.status === 'archived';
      const circle = window.L.circle([zone.center_lat, zone.center_lng], {
        radius: zone.radius_m,
        color,
        fillColor: color,
        fillOpacity: isArchived ? 0.06 : 0.15,
        weight: isArchived ? 1 : 2,
        dashArray: isArchived ? '5 5' : null,
      });
      const popupLabel = zone.name || ZONE_TYPE_LABELS[zone.zone_type] || zone.zone_type;
      circle.bindPopup(`<strong>${popupLabel}</strong><br/>${zone.zone_type} · ${zone.radius_m}m · ${zone.status}`);
      circle.on('click', (ev) => {
        window.L.DomEvent.stopPropagation(ev);
        openEdit(zone);
      });
      circle.addTo(map);
      circleLayersRef.current[zone.id] = circle;
    });
  }, [zones]);

  function openEdit(zone) {
    setForm({
      zone_type: zone.zone_type,
      center_lat: String(zone.center_lat),
      center_lng: String(zone.center_lng),
      radius_m: zone.radius_m,
      name: zone.name || '',
      description_public: zone.description_public || '',
      expires_at: zone.expires_at ? zone.expires_at.slice(0, 10) : '',
    });
    setEditing(zone);
    setFormError(null);
    setPanelMode('form');
  }

  function closeForm() {
    setPanelMode('list');
    setEditing(null);
    setFormError(null);
    setClickMode(false);
  }

  async function handleSave(e) {
    e.preventDefault();
    const lat = parseFloat(form.center_lat);
    const lng = parseFloat(form.center_lng);
    const radius = parseInt(form.radius_m, 10);
    if (!editing) {
      if (isNaN(lat) || lat < -90 || lat > 90) { setFormError('Latitude must be between -90 and 90'); return; }
      if (isNaN(lng) || lng < -180 || lng > 180) { setFormError('Longitude must be between -180 and 180'); return; }
    }
    if (isNaN(radius) || radius < 50 || radius > 10000) { setFormError('Radius must be between 50 and 10 000 m'); return; }

    setSaving(true);
    setFormError(null);
    try {
      if (editing) {
        await AnchorAPI.apiPatch(`/v1/super-admin/zones/${editing.id}`, {
          name: form.name || null,
          description: form.description_public || null,
          radius_m: radius,
          expires_at: form.expires_at ? new Date(form.expires_at + 'T00:00:00Z').toISOString() : null,
        });
      } else {
        if (!form.name.trim()) { setFormError('Zone name is required'); setSaving(false); return; }
        await AnchorAPI.apiPostAuth('/v1/super-admin/zones', {
          zone_type: form.zone_type,
          shape_type: 'circle',
          center_lat: lat,
          center_lng: lng,
          radius_m: radius,
          name: form.name.trim(),
          description: form.description_public || null,
          expires_at: form.expires_at ? new Date(form.expires_at + 'T00:00:00Z').toISOString() : null,
        });
      }
      closeForm();
      load();
    } catch (err) {
      setFormError(err.message || 'Save failed — please try again');
    } finally {
      setSaving(false);
    }
  }

  async function handleArchive() {
    if (!confirmArchive) return;
    setArchiving(true);
    try {
      await AnchorAPI.apiDelete(`/v1/super-admin/zones/${confirmArchive.id}`);
    } catch (_) {
      // swallow — reload reflects reality
    } finally {
      setArchiving(false);
      load();
    }
  }

  const filteredZones = zones.filter(z => {
    if (statusFilter !== 'all' && z.status !== statusFilter) return false;
    if (!typeFilters[z.zone_type]) return false;
    return true;
  });

  // ── List panel ────────────────────────────────────────────────────────────
  function renderList() {
    return (
      <>
        <div className="px-4 py-3 hair-b flex items-center justify-between shrink-0">
          <div>
            <div className="text-[13px] font-semibold text-[var(--graphite)]">Red Zone Map</div>
            <div className="text-[10px] text-[var(--muted)] mt-0.5">Super Admin · Platform-wide</div>
          </div>
          <button
            onClick={() => setClickMode(true)}
            className="px-2.5 py-1 text-[12px] font-medium rounded-sm flex items-center gap-1.5 text-white"
            style={{ background: 'var(--ember)' }}
          >
            <Icon name="plus" size={12} />
            New
          </button>
        </div>

        {loadError && (
          <div className="mx-3 mt-3 px-3 py-2 rounded-sm text-[12px] flex items-start gap-2 shrink-0" style={{ background: 'var(--ember-tint)', color: 'var(--ember)' }}>
            <Icon name="circle-alert" size={13} className="mt-0.5 shrink-0" />
            <span className="flex-1 leading-snug">{loadError}</span>
            <button onClick={load} className="underline ml-1 shrink-0">Retry</button>
          </div>
        )}

        <div className="px-4 py-2 hair-b flex items-center gap-1.5 flex-wrap shrink-0">
          {['active', 'archived', 'all'].map(s => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className="px-2.5 py-0.5 rounded-full text-[11px] font-medium capitalize"
              style={
                statusFilter === s
                  ? { background: 'var(--ember)', color: 'white' }
                  : { background: 'var(--mist)', color: 'var(--muted)' }
              }
            >
              {s}
            </button>
          ))}
          <div className="ml-auto flex gap-2 items-center">
            {Object.entries(typeFilters).map(([type, on]) => (
              <button
                key={type}
                onClick={() => setTypeFilters(f => ({ ...f, [type]: !f[type] }))}
                title={ZONE_TYPE_LABELS[type]}
                className="w-3 h-3 rounded-full border-2"
                style={{
                  borderColor: ZONE_COLORS[type],
                  background: on ? ZONE_COLORS[type] : 'transparent',
                  opacity: on ? 1 : 0.3,
                }}
              />
            ))}
          </div>
        </div>

        <div className="flex-1 overflow-y-auto scrollbar-none">
          {loading && (
            <div className="flex items-center justify-center py-10 gap-2 text-[var(--muted)] text-[13px]">
              <Icon name="loader-circle" size={15} />
              Loading…
            </div>
          )}
          {!loading && !loadError && filteredZones.length === 0 && (
            <div className="flex flex-col items-center justify-center py-10 px-4 text-center">
              <Icon name="map-pin-off" size={26} className="mb-2 text-[var(--muted)]" />
              <p className="text-[12px] text-[var(--muted)]">No zones match this filter.</p>
              <button
                onClick={() => setClickMode(true)}
                className="mt-3 text-[12px] underline"
                style={{ color: 'var(--ember)' }}
              >
                Create the first zone
              </button>
            </div>
          )}
          {!loading && filteredZones.map(zone => (
            <div
              key={zone.id}
              className="px-4 py-3 hair-b last:border-0 hover:bg-[var(--mist)]/20 group cursor-pointer"
              onClick={() => openEdit(zone)}
            >
              <div className="flex items-start gap-2.5">
                <span
                  className="mt-1 w-2.5 h-2.5 rounded-full shrink-0"
                  style={{ background: ZONE_COLORS[zone.zone_type] }}
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="text-[12px] font-semibold text-[var(--graphite)] truncate">
                      {zone.name || ZONE_TYPE_LABELS[zone.zone_type]}
                    </span>
                    {zone.status === 'archived' && (
                      <span
                        className="text-[10px] px-1.5 py-0.5 rounded-full font-medium shrink-0"
                        style={{ background: 'var(--mist)', color: 'var(--muted)' }}
                      >
                        archived
                      </span>
                    )}
                  </div>
                  <div className="flex gap-1.5 mt-0.5 flex-wrap">
                    <span className="text-[11px] text-[var(--muted)]">{zone.zone_type}</span>
                    <span className="text-[11px] text-[var(--muted)]">·</span>
                    <span className="text-[11px] text-[var(--muted)]">{zone.radius_m}m</span>
                    <span className="text-[11px] text-[var(--muted)]">·</span>
                    <span className="text-[11px] text-[var(--muted)] font-mono">
                      {parseFloat(zone.center_lat).toFixed(4)}, {parseFloat(zone.center_lng).toFixed(4)}
                    </span>
                  </div>
                </div>
                <Icon name="chevron-right" size={14} className="text-[var(--mist)] group-hover:text-[var(--muted)] shrink-0 mt-0.5" />
              </div>
            </div>
          ))}
        </div>
      </>
    );
  }

  // ── Form panel ────────────────────────────────────────────────────────────
  function renderForm() {
    return (
      <div className="flex flex-col h-full">
        <div className="px-4 py-3 hair-b flex items-center gap-2 shrink-0">
          <button
            onClick={closeForm}
            className="flex items-center gap-1 text-[12px] text-[var(--muted)] hover:text-[var(--graphite)] transition-colors"
          >
            <Icon name="chevron-left" size={14} />
            Zones
          </button>
          <span className="text-[var(--mist)]">/</span>
          <span className="text-[13px] font-semibold text-[var(--graphite)]">
            {editing ? 'Edit Zone' : 'New Zone'}
          </span>
        </div>

        <div className="flex-1 overflow-y-auto scrollbar-none px-4 py-4 space-y-4">

          {!editing && (
            <AuditNote tone="red" icon="map-pin">
              Zone appears immediately on the public Anchor map.
            </AuditNote>
          )}

          {formError && (
            <div className="px-3 py-2 rounded-sm text-[12px] flex items-start gap-2" style={{ background: 'var(--ember-tint)', color: 'var(--ember)' }}>
              <Icon name="circle-alert" size={13} className="mt-0.5 shrink-0" />
              <span>{formError}</span>
            </div>
          )}

          <form id="zone-form" onSubmit={handleSave} className="space-y-4">

            <div>
              <label className="block text-[11px] font-semibold text-[var(--graphite)] uppercase tracking-wide mb-2">Zone Type</label>
              <div className="grid grid-cols-2 gap-1.5">
                {Object.entries(ZONE_TYPE_LABELS).map(([type, lbl]) => {
                  const active = form.zone_type === type;
                  const color = ZONE_COLORS[type];
                  return (
                    <button
                      key={type}
                      type="button"
                      disabled={!!editing}
                      onClick={() => !editing && setForm(f => ({ ...f, zone_type: type }))}
                      className="px-2.5 py-2 rounded-sm border text-left text-[11px] flex items-center gap-2 transition-all"
                      style={
                        active
                          ? { borderColor: color, background: color + '18', color: color === '#0B0B0B' ? '#1a1a1a' : color, fontWeight: 600 }
                          : editing
                            ? { borderColor: 'var(--mist)', color: 'var(--muted)', opacity: 0.5, cursor: 'not-allowed' }
                            : { borderColor: 'var(--mist)', color: 'var(--graphite)' }
                      }
                    >
                      <span className="w-2 h-2 rounded-full shrink-0" style={{ background: color }} />
                      <span className="leading-tight">{lbl}</span>
                    </button>
                  );
                })}
              </div>
              {editing && <p className="text-[11px] mt-1" style={{ color: 'var(--muted)' }}>Type is fixed after creation.</p>}
            </div>

            {!editing ? (
              <div>
                <label className="block text-[11px] font-semibold text-[var(--graphite)] uppercase tracking-wide mb-1">Location</label>
                <div className="grid grid-cols-2 gap-2 mb-1">
                  <input
                    type="number" step="any" value={form.center_lat}
                    onChange={e => setForm(f => ({ ...f, center_lat: e.target.value }))}
                    required placeholder="Latitude"
                    className="w-full px-2.5 py-2 hair border rounded-sm bg-white text-[12px]"
                  />
                  <input
                    type="number" step="any" value={form.center_lng}
                    onChange={e => setForm(f => ({ ...f, center_lng: e.target.value }))}
                    required placeholder="Longitude"
                    className="w-full px-2.5 py-2 hair border rounded-sm bg-white text-[12px]"
                  />
                </div>
                <p className="text-[11px]" style={{ color: 'var(--muted)' }}>
                  Or{' '}
                  <button
                    type="button"
                    onClick={() => { closeForm(); setClickMode(true); }}
                    className="underline"
                    style={{ color: 'var(--ember)' }}
                  >
                    click the map
                  </button>
                  {' '}to pin a location.
                </p>
              </div>
            ) : (
              <div>
                <label className="block text-[11px] font-semibold text-[var(--graphite)] uppercase tracking-wide mb-1">Location (fixed)</label>
                <div className="px-2.5 py-2 rounded-sm text-[12px] font-mono" style={{ background: 'var(--mist)', color: 'var(--graphite)' }}>
                  {parseFloat(form.center_lat).toFixed(5)}, {parseFloat(form.center_lng).toFixed(5)}
                </div>
              </div>
            )}

            <div>
              <label className="block text-[11px] font-semibold text-[var(--graphite)] uppercase tracking-wide mb-1">
                Radius — <span className="font-mono">{form.radius_m} m</span>
              </label>
              <div className="flex gap-2 items-center">
                <input
                  type="range" min={50} max={5000} step={50}
                  value={form.radius_m}
                  onChange={e => setForm(f => ({ ...f, radius_m: parseInt(e.target.value, 10) }))}
                  className="flex-1"
                />
                <input
                  type="number" min={50} max={10000}
                  value={form.radius_m}
                  onChange={e => setForm(f => ({ ...f, radius_m: Math.max(50, parseInt(e.target.value, 10) || 50) }))}
                  className="w-20 px-2 py-1.5 hair border rounded-sm bg-white text-[12px] text-right"
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-[var(--graphite)] uppercase tracking-wide mb-1">
                Zone name <span className="text-[var(--muted)] normal-case font-normal">(required)</span>
              </label>
              <input
                value={form.name}
                onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                placeholder={ZONE_TYPE_LABELS[form.zone_type]}
                className="w-full px-2.5 py-2 hair border rounded-sm bg-white text-[12px]"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-[var(--graphite)] uppercase tracking-wide mb-1">
                Public description <span className="text-[var(--muted)] normal-case font-normal">(optional)</span>
              </label>
              <textarea
                rows={3}
                value={form.description_public}
                onChange={e => setForm(f => ({ ...f, description_public: e.target.value }))}
                placeholder="Shown in the zone popup on the public map."
                className="w-full px-2.5 py-2 hair border rounded-sm bg-white text-[12px] resize-none"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-[var(--graphite)] uppercase tracking-wide mb-1">
                Expires on <span className="text-[var(--muted)] normal-case font-normal">(blank = no expiry)</span>
              </label>
              <input
                type="date"
                value={form.expires_at}
                onChange={e => setForm(f => ({ ...f, expires_at: e.target.value }))}
                className="w-full px-2.5 py-2 hair border rounded-sm bg-white text-[12px]"
              />
            </div>
          </form>

          {/* Archive danger section — only shown when editing an active zone */}
          {editing && editing.status === 'active' && (
            <div className="pt-2 mt-2 border-t hair">
              <p className="text-[11px] font-semibold uppercase tracking-wide mb-2" style={{ color: 'var(--ember)' }}>Danger zone</p>
              <button
                type="button"
                onClick={() => setConfirmArchive(editing)}
                className="w-full flex items-center gap-2 px-3 py-2 rounded-sm border text-[12px] transition-colors"
                style={{ borderColor: 'var(--ember)', color: 'var(--ember)', background: 'var(--ember-tint)' }}
              >
                <Icon name="archive" size={13} />
                Archive this zone
              </button>
              <p className="text-[11px] mt-1" style={{ color: 'var(--muted)' }}>
                Removes zone from the public map immediately.
              </p>
            </div>
          )}
        </div>

        <div className="px-4 py-3 hair-t flex gap-2 shrink-0">
          <PrimaryButton
            as="button"
            type="submit"
            form="zone-form"
            mode="ember"
            icon={editing ? 'save' : 'map-pin'}
            disabled={saving}
            className="flex-1 justify-center"
          >
            {saving ? 'Saving…' : editing ? 'Save changes' : 'Create zone'}
          </PrimaryButton>
          <GhostButton type="button" onClick={closeForm}>Cancel</GhostButton>
        </div>
      </div>
    );
  }

  return (
    <div className="flex gap-4" style={{ height: 'calc(100vh - 84px)', minHeight: 500 }}>

      {/* ── Leaflet map (left, fills remaining space) ── */}
      <div className="flex-1 rounded-sm overflow-hidden border hair relative" style={{ minWidth: 0 }}>
        {mapError ? (
          <div className="w-full h-full flex flex-col items-center justify-center p-6 text-center" style={{ background: 'var(--mist)' }}>
            <Icon name="map-off" size={32} className="mb-3 text-[var(--muted)]" />
            <p className="text-[13px] text-[var(--graphite)]">{mapError}</p>
          </div>
        ) : (
          <>
            {clickMode && (
              <div
                className="absolute top-3 z-[1000] px-3 py-1.5 rounded text-[12px] font-medium flex items-center gap-2"
                style={{
                  left: '50%', transform: 'translateX(-50%)',
                  background: 'var(--ember)', color: 'white',
                  boxShadow: 'var(--shadow)', pointerEvents: 'all',
                }}
              >
                <Icon name="map-pin" size={13} />
                Click map to place zone
                <button
                  onClick={() => setClickMode(false)}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, opacity: 0.8, display: 'flex' }}
                >
                  <Icon name="x" size={12} />
                </button>
              </div>
            )}
            <div
              ref={mapDivRef}
              className="w-full h-full"
              style={{ cursor: clickMode ? 'crosshair' : undefined }}
            />
          </>
        )}
      </div>

      {/* ── Right panel: list or form, no overlay ── */}
      <div
        className="flex flex-col rounded-sm border hair bg-[var(--paper)] overflow-hidden"
        style={{ width: 340, flexShrink: 0 }}
      >
        {panelMode === 'list' ? renderList() : renderForm()}
      </div>

      {/* ── Archive confirm modal ── */}
      <ConfirmModal
        open={!!confirmArchive}
        onClose={() => { setConfirmArchive(null); }}
        onConfirm={handleArchive}
        title="Archive this zone?"
        body={confirmArchive
          ? `"${confirmArchive.name || ZONE_TYPE_LABELS[confirmArchive.zone_type]}" will be removed from the public map immediately. The record is preserved in audit history.`
          : ''}
        confirmWord="ARCHIVE"
        confirmLabel={archiving ? 'Archiving…' : 'Archive zone'}
        tone="red"
      />
    </div>
  );
}


// ---- Policy & configuration ----
const _PERMA_BAN_OPTS = ['2 super admin approvals', '1 super admin approval', 'External oversight sign-off'];
const _PATTERN_OPTS = ['Surface to Dean when ≥ 3 reports', 'Surface when ≥ 2 reports', 'Surface when ≥ 5 reports'];
const _BREACH_OPTS = ['72 hours (Ordinance default)', '48 hours', '24 hours'];

function SuperPolicy() {
  const [cfg, setCfg]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]   = useState('');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved]   = useState(false);
  const [dirty, setDirty]   = useState({});
  const [discLang, setDiscLang] = useState('en');

  useEffect(() => {
    let cancelled = false;
    setLoading(true); setError('');
    AnchorAPI.apiGet('/v1/super-admin/config')
      .then(d => { if (!cancelled) setCfg(d); })
      .catch(e => { if (!cancelled) setError(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  function set(section, key, value) {
    setCfg(c => ({ ...c, [section]: { ...(c[section] || {}), [key]: value } }));
    setDirty(d => ({ ...d, [section]: true }));
    setSaved(false);
  }
  const hasDirty = Object.keys(dirty).some(s => dirty[s]);

  async function save() {
    const sections = {};
    Object.keys(dirty).forEach(s => { if (dirty[s] && cfg[s]) sections[s] = cfg[s]; });
    if (Object.keys(sections).length === 0) return;
    setSaving(true); setError('');
    try {
      const updated = await AnchorAPI.apiPatch('/v1/super-admin/config', { sections });
      setCfg(updated); setDirty({}); setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch (e) { setError(e.message); }
    finally { setSaving(false); }
  }

  // Field renderers (closures over cfg/set)
  function numRow(section, key, title, hint, suffix, step) {
    const v = (cfg[section] || {})[key];
    return (
      <SettingRow title={title} hint={hint}>
        <input type="number" step={step || 1} value={v ?? ''}
          onChange={e => set(section, key, e.target.value === '' ? '' : Number(e.target.value))}
          className="w-[90px] px-2 py-1.5 hair border rounded-sm bg-white font-mono text-[13px] text-right" />
        {suffix && <span className="text-[12px] text-[var(--muted)]">{suffix}</span>}
      </SettingRow>
    );
  }
  function selRow(section, key, title, hint, options) {
    const v = (cfg[section] || {})[key];
    return (
      <SettingRow title={title} hint={hint}>
        <select value={v ?? ''} onChange={e => set(section, key, e.target.value)}
          className="px-2 py-1.5 hair border rounded-sm bg-white text-[12.5px]">
          {options.map(o => <option key={o} value={o}>{o}</option>)}
        </select>
      </SettingRow>
    );
  }
  function toggleRow(section, key, title, hint) {
    const v = !!(cfg[section] || {})[key];
    return (
      <SettingRow title={title} hint={hint}>
        <Toggle on={v} onChange={nv => set(section, key, nv)} />
      </SettingRow>
    );
  }

  return (
    <>
      <PageHeader title="Policy & configuration" bn="নীতি ও কনফিগারেশন"
        description="Platform-wide defaults: escalation timers, rate limits, trust thresholds, ban durations, AI confidence gates, the legal disclaimer, retention, and PDP Ordinance controls. All changes are audit-logged."
        actions={
          <PrimaryButton mode="ember" size="sm" icon={saving ? 'loader' : 'check'} onClick={save}
            disabled={saving || !hasDirty}
            className={(saving || !hasDirty) ? 'opacity-60 pointer-events-none' : ''}>
            {saving ? 'Saving…' : 'Save changes'}
          </PrimaryButton>
        }
      />

      {error && <AuditNote tone="red" icon="alert-triangle">{error}</AuditNote>}
      {saved && <div className="mb-4"><AuditNote tone="sage" icon="check-circle">Configuration saved and audit-logged.</AuditNote></div>}
      {hasDirty && !saving && <div className="mb-4"><AuditNote tone="gold" icon="pencil">You have unsaved changes.</AuditNote></div>}

      {loading || !cfg ? (
        <Card><EmptyState icon="loader" title="Loading configuration…" /></Card>
      ) : (
        <div className="space-y-5">
          <Card>
            <SectionLabel>Default escalation timers</SectionLabel>
            <AuditNote tone="red" icon="shield-alert">Platform-wide defaults. Tenants may override per-category in their own settings — but cannot exceed the maximums set here.</AuditNote>
            <div className="mt-2">
              {numRow('escalation', 'level1_to_level2_hours', 'Default Level-1 → Level-2 timer', 'Auto-escalation from Dept Head to Dean if no action is taken.', 'hours')}
              {numRow('escalation', 'level2_to_level3_days', 'Default Level-2 → Level-3 timer', 'Dean to VC Office.', 'days')}
              {numRow('escalation', 'alert_auto_escalation_minutes', 'Active alert auto-escalation', 'If a tenant proctor doesn’t acknowledge within this window, the alert escalates to platform operators.', 'minutes')}
              {numRow('escalation', 'max_tenant_timer_days', 'Maximum timer a tenant can configure', 'Hard cap preventing tenants from disabling escalation by setting absurd timers.', 'days')}
            </div>
          </Card>

          <Card>
            <SectionLabel>Rate limits</SectionLabel>
            {numRow('rate_limits', 'complaint_filing_per_24h', 'Complaint filing · per student', 'Soft limit. Beyond this in 24h, AI screens for spam.', '/ 24h')}
            {numRow('rate_limits', 'active_alerts_per_24h', 'Active alerts · per student', 'Hard limit per 24h. Exceeded users are auto-blocked until review.', '/ 24h')}
            {numRow('rate_limits', 'news_publishing_per_hour', 'News publishing · per user', 'Verification feed posts before AI screening throttles.', '/ hour')}
            {numRow('rate_limits', 'ai_queries_per_hour', 'AI queries · per user', 'Caps individual chatbot usage on the student app.', '/ hour')}
          </Card>

          <Card>
            <SectionLabel>Trust ranking thresholds</SectionLabel>
            <p className="text-[12.5px] text-[var(--graphite)] mb-1">Publishers gain trust by submitting verified news. These thresholds map to badges in the verification feed.</p>
            {numRow('trust_thresholds', 'bronze_verified_posts', 'Bronze · Verified', 'Minimum correct verified posts to earn the bronze badge.', 'posts')}
            {numRow('trust_thresholds', 'silver_trusted_posts', 'Silver · Trusted', 'Verified posts to be marked Trusted.', 'posts')}
            {numRow('trust_thresholds', 'gold_sourceful_posts', 'Gold · Sourceful', 'Earn the highest publisher tier.', 'posts')}
            {numRow('trust_thresholds', 'demotion_false_posts', 'Demotion threshold', 'Verified false posts that demote a publisher one tier.', 'false posts')}
          </Card>

          <Card>
            <SectionLabel>Ban durations</SectionLabel>
            {numRow('bans', 'alert_false_alarm_days', 'Alert false-alarm ban', 'When a user’s alert is determined false, they cannot file new alerts for this duration.', 'days')}
            {numRow('bans', 'news_false_publication_days', 'News false-publication ban', 'Publishing falsely verified news.', 'days')}
            {numRow('bans', 'complaint_spam_days', 'Complaint spam ban', 'Repeated unfounded complaints flagged as spam.', 'days')}
            {selRow('bans', 'permanent_ban_requires', 'Permanent ban requires', 'Super admin approvals to make a ban permanent.', _PERMA_BAN_OPTS)}
          </Card>

          <Card>
            <SectionLabel>AI confidence thresholds</SectionLabel>
            {numRow('ai_thresholds', 'auto_publish_news', 'Auto-publish · news', 'Minimum AI confidence to auto-approve a verification-feed post.', '', 0.01)}
            {numRow('ai_thresholds', 'auto_reject_news', 'Auto-reject · news', 'Below this confidence, the AI rejects the post outright.', '', 0.01)}
            {numRow('ai_thresholds', 'auto_flag_false_alarm', 'Auto-flag false alarm', 'AI confidence that the alert is false.', '', 0.01)}
            {selRow('ai_thresholds', 'pattern_detection_signal', 'Pattern-detection signal strength · alert', '', _PATTERN_OPTS)}
            {numRow('ai_thresholds', 'self_verification_min', 'Self-verification minimum pass rate', 'Below this, the output is auto-rejected and re-routed.', '', 0.01)}
          </Card>

          <Card>
            <SectionLabel right={
              <div className="flex hair border rounded-sm overflow-hidden">
                <button onClick={()=>setDiscLang('en')} className={`px-3 py-1 text-[12px] ${discLang==='en'?'bg-[var(--ember)] text-white':'text-[var(--graphite)]'}`}>English</button>
                <button onClick={()=>setDiscLang('bn')} className={`px-3 py-1 text-[12px] font-bn ${discLang==='bn'?'bg-[var(--ember)] text-white':'text-[var(--graphite)]'}`}>বাংলা</button>
              </div>
            }>Legal disclaimer</SectionLabel>
            <p className="text-[12px] text-[var(--graphite)] mb-3">Shown to every user on first sign-in and inside the AI chat panel. Both language versions must be present.</p>
            <textarea value={(cfg.disclaimer || {})[discLang] || ''} onChange={e => set('disclaimer', discLang, e.target.value)}
              className={`w-full p-3 hair border rounded-sm bg-[var(--bg-input-tint)] text-[13px] min-h-[140px] ${discLang==='bn'?'font-bn':''}`} />
          </Card>

          <Card>
            <SectionLabel>Data retention</SectionLabel>
            <AuditNote tone="navy" icon="database">Retention is set per data class. Deletion is irreversible and respects the audit-log append-only contract.</AuditNote>
            <div className="mt-2">
              {selRow('retention', 'resolved_case', 'Resolved-case retention', 'How long resolved cases remain queryable in the admin.', ['2 academic years','3 academic years','5 academic years'])}
              {selRow('retention', 'evidence', 'Evidence retention', 'Images and documents attached to cases.', ['5 years','10 years'])}
              {selRow('retention', 'delete_inactive_accounts', 'Delete inactive student accounts', 'Accounts with no activity for this period are deactivated, not deleted.', ['2 years','Never'])}
            </div>
          </Card>

          <Card>
            <SectionLabel>Bangladesh PDP Ordinance 2025 · compliance</SectionLabel>
            <AuditNote tone="navy" icon="scale">These toggles map directly to sections of the Personal Data Protection Ordinance 2025. Disabling a control will fail the platform’s automated compliance check.</AuditNote>
            <div className="mt-2">
              {toggleRow('pdpo', 'right_to_access', 'Right to access', 'Users can request a copy of all personal data held about them within 30 days.')}
              {toggleRow('pdpo', 'right_to_rectification', 'Right to rectification', 'Users can correct inaccurate personal data.')}
              {toggleRow('pdpo', 'right_to_erasure', 'Right to erasure', 'Users can request deletion subject to legal hold exceptions.')}
              {toggleRow('pdpo', 'data_localization', 'Data localization', 'All personal data stored within Bangladesh borders.')}
              {toggleRow('pdpo', 'cross_border_transfer_review', 'Cross-border transfer review', 'Any data egress to foreign processors requires DPO sign-off.')}
              {selRow('pdpo', 'breach_notification_window', 'Breach notification window', 'Automatic notification to the Data Protection Authority on a detected breach.', _BREACH_OPTS)}
            </div>
          </Card>
        </div>
      )}
    </>
  );
}

// ---- Legal corpus · RAG ----
const _DOC_TYPES = ['statute', 'rule', 'regulation', 'circular', 'judgment', 'commentary', 'template', 'university_policy', 'workflow'];

function _healthTone(v) { return v === 'ok' ? 'sage' : v === 'disabled' ? 'mist' : 'red'; }

function SuperLegalCorpus() {
  const [namespace, setNamespace] = useState('national');
  const [namespaces, setNamespaces] = useState(['national', 'diu']);
  const [docs, setDocs]       = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');
  const [health, setHealth]   = useState(null);
  const [addOpen, setAddOpen] = useState(false);
  const [confirmDel, setConfirmDel] = useState(null);
  const [reloading, setReloading]   = useState(false);
  const [notice, setNotice]   = useState('');

  const blank = { title: '', document_type: 'statute', section: '', language: 'en', effective_date: '', text: '' };
  const [form, setForm] = useState(blank);
  const [submitting, setSubmitting] = useState(false);
  const [formErr, setFormErr] = useState('');

  const fetchDocs = useCallback(() => {
    setLoading(true); setError('');
    AnchorAPI.apiGet(`/v1/super-admin/corpus/documents?namespace=${encodeURIComponent(namespace)}`)
      .then(d => setDocs(d.documents || []))
      .catch(e => { setError(e.message); setDocs([]); })
      .finally(() => setLoading(false));
  }, [namespace]);

  useEffect(() => { fetchDocs(); }, [fetchDocs]);

  useEffect(() => {
    AnchorAPI.apiGet('/ai/health').then(setHealth).catch(() => setHealth({ pipeline: 'unavailable' }));
    AnchorAPI.apiGet('/v1/super-admin/tenants')
      .then(d => {
        const ns = ['national', 'diu'];
        (d.items || []).forEach(t => {
          const v = t.vector_namespace || t.slug;
          if (v && !ns.includes(v)) ns.push(v);
        });
        setNamespaces(ns);
      })
      .catch(() => {});
  }, []);

  async function submitDoc() {
    if (!form.title.trim() || !form.text.trim()) { setFormErr('Title and document text are required.'); return; }
    setSubmitting(true); setFormErr('');
    try {
      const res = await AnchorAPI.apiPostAuth('/v1/super-admin/corpus/documents', {
        namespace,
        title: form.title.trim(),
        document_type: form.document_type,
        language: form.language,
        metadata: { section: form.section.trim(), effective_date: form.effective_date.trim() },
        text: form.text,
      });
      setAddOpen(false); setForm(blank);
      setNotice(`Indexed “${form.title.trim()}” — ${res.chunks_loaded} chunk${res.chunks_loaded === 1 ? '' : 's'}.`);
      setTimeout(() => setNotice(''), 4000);
      fetchDocs();
    } catch (e) { setFormErr(e.message); }
    finally { setSubmitting(false); }
  }

  async function doDelete() {
    if (!confirmDel) return;
    try {
      await AnchorAPI.apiDelete(`/v1/super-admin/corpus/documents/${encodeURIComponent(confirmDel.document_id)}?namespace=${encodeURIComponent(namespace)}`);
      setNotice(`Removed “${confirmDel.title}” from the ${namespace} corpus.`);
      setTimeout(() => setNotice(''), 4000);
      fetchDocs();
    } catch (e) { setError(e.message); }
  }

  async function reloadSample() {
    setReloading(true); setError('');
    try {
      await AnchorAPI.apiPostAuth('/ai/ingest', {});
      setNotice('Sample corpus reloaded into ChromaDB.');
      setTimeout(() => setNotice(''), 4000);
      fetchDocs();
    } catch (e) { setError(e.message); }
    finally { setReloading(false); }
  }

  const ragDown = health && (health.pipeline === 'unavailable' || health.chromadb && String(health.chromadb).startsWith('error'));

  const columns = [
    { key: 'title', label: 'Document', render: r => (
      <div className="min-w-0">
        <div className="text-[13px] text-[var(--ink)] font-medium truncate">{r.title}</div>
        {r.section && <div className="text-[11.5px] text-[var(--muted)]">{r.section}</div>}
      </div>
    )},
    { key: 'document_type', label: 'Type', render: r => <Tag tone="navy">{String(r.document_type).replace(/_/g, ' ')}</Tag> },
    { key: 'language', label: 'Lang', render: r => <span className="font-mono text-[12px] uppercase">{r.language}</span> },
    { key: 'effective_date', label: 'Effective', render: r => <span className="text-[12px] text-[var(--graphite)]">{r.effective_date || '—'}</span> },
    { key: 'chunk_count', label: 'Chunks', align: 'right', render: r => <MonoChip>{r.chunk_count}</MonoChip> },
    { key: 'actions', label: '', align: 'right', render: r => (
      <GhostButton size="sm" danger icon="trash-2" onClick={() => setConfirmDel(r)}>Delete</GhostButton>
    )},
  ];

  return (
    <>
      <PageHeader title="Legal corpus · RAG" bn="আইনি কর্পাস"
        description="Manage the documents that feed ChromaDB across tenant namespaces. Adding a document chunks it, generates contextual prefixes, and indexes it for hybrid retrieval."
        actions={<>
          <GhostButton size="sm" icon={reloading ? 'loader' : 'refresh-cw'} onClick={reloadSample}
            disabled={reloading} className={reloading ? 'opacity-60 pointer-events-none' : ''}>
            {reloading ? 'Reloading…' : 'Reload sample corpus'}
          </GhostButton>
          <PrimaryButton mode="ember" size="sm" icon="plus" onClick={() => { setForm(blank); setFormErr(''); setAddOpen(true); }}>Add document</PrimaryButton>
        </>}
      />

      {notice && <div className="mb-4"><AuditNote tone="sage" icon="check-circle">{notice}</AuditNote></div>}

      {/* RAG health banner */}
      <div className="mb-4">
        {ragDown ? (
          <AuditNote tone="red" icon="server-off">
            RAG service is unreachable — corpus operations are unavailable. The pipeline runs separately (see services/rag). Start it and refresh.
          </AuditNote>
        ) : health ? (
          <Card className="flex items-center gap-4 flex-wrap" >
            <span className="smallcaps text-[var(--muted)]">RAG engine</span>
            {['embedder', 'chromadb', 'ollama'].map(k => (
              <span key={k} className="inline-flex items-center gap-1.5 text-[12.5px]">
                <span className="text-[var(--muted)] capitalize">{k}:</span>
                <Tag tone={_healthTone(health[k])}>{health[k] || 'unknown'}</Tag>
              </span>
            ))}
          </Card>
        ) : null}
      </div>

      {/* Namespace selector */}
      <div className="mb-4 flex items-center gap-2 flex-wrap">
        <span className="smallcaps text-[var(--muted)] mr-1">Namespace</span>
        {namespaces.map(ns => (
          <button key={ns} onClick={() => setNamespace(ns)}
            className={`px-3 py-1.5 rounded-sm text-[12.5px] hair border ${namespace===ns ? 'bg-[var(--ember)] text-white border-transparent' : 'text-[var(--graphite)] hover:bg-[var(--mist)]/40'}`}>
            {ns}
          </button>
        ))}
      </div>

      {error && <div className="mb-4"><AuditNote tone="red" icon="alert-triangle">{error}</AuditNote></div>}

      <Card noPad>
        {loading ? (
          <EmptyState icon="loader" title="Loading corpus…" />
        ) : docs.length === 0 ? (
          <EmptyState icon="book-open" title="No documents in this namespace"
            body="Add a legal document to index it for retrieval, or reload the built-in sample corpus."
            action={<PrimaryButton mode="ember" size="sm" icon="plus" onClick={() => setAddOpen(true)}>Add document</PrimaryButton>} />
        ) : (
          <div className="p-2">
            <DataTable columns={columns} rows={docs} />
          </div>
        )}
      </Card>

      {/* Add document slide-over */}
      <SlideOver open={addOpen} onClose={() => setAddOpen(false)} width={560}>
        <div className="p-5 space-y-4">
          <div className="flex items-center justify-between">
            <SectionLabel className="mb-0">Add corpus document · {namespace}</SectionLabel>
            <button onClick={() => setAddOpen(false)} className="w-7 h-7 rounded-sm hover:bg-[var(--mist)]/40 flex items-center justify-center"><Icon name="x" size={14} /></button>
          </div>
          {formErr && <AuditNote tone="red" icon="alert-triangle">{formErr}</AuditNote>}
          <div>
            <label className="smallcaps text-[var(--muted)]">Title / Act name</label>
            <input value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))}
              className="mt-1 w-full px-3 py-2 hair border rounded-sm bg-white text-[13px]" placeholder="e.g. Penal Code 1860 — Section 354" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="smallcaps text-[var(--muted)]">Document type</label>
              <select value={form.document_type} onChange={e => setForm(f => ({ ...f, document_type: e.target.value }))}
                className="mt-1 w-full px-2 py-2 hair border rounded-sm bg-white text-[12.5px]">
                {_DOC_TYPES.map(t => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
              </select>
            </div>
            <div>
              <label className="smallcaps text-[var(--muted)]">Language</label>
              <select value={form.language} onChange={e => setForm(f => ({ ...f, language: e.target.value }))}
                className="mt-1 w-full px-2 py-2 hair border rounded-sm bg-white text-[12.5px]">
                <option value="en">English</option>
                <option value="bn">Bangla</option>
              </select>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="smallcaps text-[var(--muted)]">Section / clause</label>
              <input value={form.section} onChange={e => setForm(f => ({ ...f, section: e.target.value }))}
                className="mt-1 w-full px-3 py-2 hair border rounded-sm bg-white text-[13px]" placeholder="Section 3.4" />
            </div>
            <div>
              <label className="smallcaps text-[var(--muted)]">Effective date</label>
              <input value={form.effective_date} onChange={e => setForm(f => ({ ...f, effective_date: e.target.value }))}
                className="mt-1 w-full px-3 py-2 hair border rounded-sm bg-white text-[13px]" placeholder="2023-09-18" />
            </div>
          </div>
          <div>
            <label className="smallcaps text-[var(--muted)]">Document text</label>
            <textarea value={form.text} onChange={e => setForm(f => ({ ...f, text: e.target.value }))}
              className={`mt-1 w-full p-3 hair border rounded-sm bg-white text-[13px] min-h-[220px] ${form.language==='bn'?'font-bn':''}`}
              placeholder="Paste the document body. Blank lines separate it into retrieval chunks." />
            <p className="text-[11.5px] text-[var(--muted)] mt-1">Long text is split on blank lines into retrieval-sized chunks; each chunk gets an AI-generated contextual prefix before embedding.</p>
          </div>
          <div className="flex items-center justify-end gap-2 pt-1">
            <GhostButton onClick={() => setAddOpen(false)}>Cancel</GhostButton>
            <PrimaryButton mode="ember" icon={submitting ? 'loader' : 'upload'} onClick={submitDoc}
              disabled={submitting} className={submitting ? 'opacity-60 pointer-events-none' : ''}>
              {submitting ? 'Indexing…' : 'Ingest document'}
            </PrimaryButton>
          </div>
        </div>
      </SlideOver>

      <ConfirmModal
        open={!!confirmDel}
        onClose={() => setConfirmDel(null)}
        onConfirm={doDelete}
        title="Delete this document?"
        body={confirmDel ? `All ${confirmDel.chunk_count} chunk${confirmDel.chunk_count===1?'':'s'} of “${confirmDel.title}” will be removed from the ${namespace} corpus and the retrieval index.` : ''}
        confirmWord="DELETE"
        confirmLabel="Delete document"
        tone="red"
      />
    </>
  );
}

Object.assign(window, { SuperDashboard, SuperTenants, SuperOnboard, SuperTenantDetail, SuperAuditLogs, SuperDeanonymization, SuperVerificationFeed, SuperAIHealth, SuperEncryption, SuperAnalytics, SuperIncidents, SuperAlerts, SuperModeration, SuperUsers, SuperRedZones, SuperPolicy, SuperLegalCorpus });
