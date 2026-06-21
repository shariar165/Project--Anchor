// University Dashboard — role-adaptive, backend-connected
var { useState, useEffect, useCallback, useRef, useMemo } = React;
const { LineChart, Line, AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, RadialBarChart, RadialBar, Legend } = window.Recharts || {};

const chartAxis = { stroke: '#6B7785', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' };
const chartGrid = { stroke: '#E5E0D6', strokeDasharray: '0' };

// ── Shared helpers ────────────────────────────────────────────────────────────

function _cap(s) { return String(s || '').replace(/^\w/, c => c.toUpperCase()); }

// Average resolution seconds → "3.2d" / "5.4h" / "—".
function _fmtResolution(secs) {
  if (!secs || secs <= 0) return '—';
  const days = secs / 86400;
  if (days >= 1) return `${days.toFixed(1)}d`;
  return `${(secs / 3600).toFixed(1)}h`;
}

// Map a Filing.state to a StatusPill status label.
const _FILING_STATUS = {
  draft: 'Submitted', moderation_queue: 'Submitted', routed: 'Submitted',
  subject_notified: 'Under Review', subject_responded: 'Under Review', under_review: 'Under Review',
  resolved: 'Resolved', dismissed: 'Rejected', withdrawn: 'Closed', spam_rejected: 'Rejected',
};
function _filingStatus(state) { return _FILING_STATUS[state] || 'Submitted'; }

// Render a labelled horizontal bar breakdown from a {key: count} map.
function BreakdownBars({ data, color = 'var(--sage)', labelMap }) {
  const entries = Object.entries(data || {}).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]);
  if (!entries.length) return <div className="text-[12px] text-[var(--muted)] py-2">No data yet.</div>;
  const max = Math.max(...entries.map(([, v]) => v));
  return (
    <div className="space-y-3">
      {entries.map(([k, v]) => (
        <div key={k}>
          <div className="flex items-center justify-between text-[12px] mb-1">
            <span className="text-[var(--ink)]">{labelMap ? (labelMap[k] || _cap(k.replace(/_/g, ' '))) : _cap(k.replace(/_/g, ' '))}</span>
            <span className="font-mono text-[var(--muted)]">{v}</span>
          </div>
          <div className="h-1.5 rounded-sm bg-[var(--mist)]/70 overflow-hidden">
            <div className="h-full" style={{ width: `${(v / max) * 100}%`, background: color }} />
          </div>
        </div>
      ))}
    </div>
  );
}

// Shared fetch of the admin filing stats + a small recent-filings list.
function useFilingData() {
  const [stats, setStats] = useState(null);
  const [filings, setFilings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  useEffect(() => {
    let alive = true;
    setLoading(true);
    Promise.all([
      AnchorAPI.apiGet('/v1/admin/filings/stats'),
      AnchorAPI.apiGet('/v1/admin/filings?page=1').catch(() => []),
    ])
      .then(([s, list]) => { if (!alive) return; setStats(s); setFilings(Array.isArray(list) ? list : (list.items || [])); })
      .catch(e => { if (alive) setError(e.message || 'Failed to load'); })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, []);
  return { stats, filings, loading, error };
}

function RecentFilings({ filings, onGo, limit = 5 }) {
  if (!filings.length) return <EmptyState icon="inbox" title="No filings yet." body="Submitted complaints, reports, and grievances appear here." />;
  return (
    <div className="hair-t border-t">
      {filings.slice(0, limit).map(f => (
        <button key={f.id} onClick={() => onGo('/university/complaints')} className={`w-full text-left p-4 hover:bg-[var(--mist)]/30 hair-b flex items-start gap-3 ${StatusEdgeClass(_filingStatus(f.state))}`}>
          <Icon name="file-text" size={16} className="mt-0.5 text-[var(--graphite)]" />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <MonoChip>{f.filing_number || (f.id ? f.id.slice(0, 8) : '—')}</MonoChip>
              <span className="text-[11px] text-[var(--muted)] ml-auto">{f.created_at ? new Date(f.created_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' }) : ''}</span>
            </div>
            <div className="text-[13px] text-[var(--ink)] line-clamp-1">{(f.template && f.template.name) || _cap(f.category)}</div>
            <div className="text-[11px] text-[var(--muted)] mt-1">{_cap(f.category)}</div>
          </div>
          <StatusPill status={_filingStatus(f.state)} />
        </button>
      ))}
    </div>
  );
}

function UniDashboard({ role, onGo }) {
  return (
    <>
      <PageHeader
        title={`Hello, Dr. Tahmina.`}
        bn="শুভ অপরাহ্ন"
        description={dashboardDescription(role)}
        actions={
          <>
            <GhostButton icon="download" size="sm">Export</GhostButton>
            <PrimaryButton icon="plus" size="sm" mode="sage" onClick={()=>onGo('/university/notices')}>New notice</PrimaryButton>
          </>
        }
      />

      {role === 'Department Head' && <DeptHeadDashboard onGo={onGo} />}
      {role === 'Dean' && <DeanDashboard onGo={onGo} />}
      {role === 'Proctor' && <ProctorDashboard onGo={onGo} />}
      {role === 'Provost' && <ProvostDashboard onGo={onGo} />}
      {role === 'VC Office' && <VCDashboard onGo={onGo} />}
      {role === 'IT Admin' && <ITDashboard onGo={onGo} />}
    </>
  );
}

function dashboardDescription(role) {
  return {
    'Department Head':'Complaint queues, escalations, and your department’s academic operations this week.',
    'Dean':'Cross-departmental performance, escalated grievances, and faculty-wide caseload.',
    'Proctor':'Active campus alerts, serious misconduct queue, and the safety operations console.',
    'Provost':'Hostel complaints, hall tutor reports, and residence-life operations.',
    'VC Office':'Level-3 escalations and platform-wide intelligence for the Vice-Chancellor’s office.',
    'IT Admin':'User management, routing configuration, and the technical health of your tenant.',
  }[role];
}

// ----- Department Head -----
function DeptHeadDashboard({ onGo }) {
  const { stats, filings, loading } = useFilingData();
  const inflow = (stats?.inflow_30d || []).map(p => ({ day: p.date ? p.date.slice(8, 10) : '', complaints: p.count }));
  const categories = Object.entries(stats?.by_category || {}).map(([name, value]) => ({ name: _cap(name), value }));
  const catMax = Math.max(1, ...categories.map(c => c.value));

  return (
    <>
      <div className="grid grid-cols-4 gap-4 mb-6">
        <KpiCard label="Open complaints" value={loading ? '…' : (stats?.open ?? '—')} subtle="in the pipeline" />
        <KpiCard label="Under review" value={loading ? '…' : (stats?.under_review ?? '—')} subtle="awaiting decision" />
        <KpiCard label="Avg resolution" value={loading ? '…' : _fmtResolution(stats?.avg_resolution_secs)} subtle="submit → resolve" />
        <KpiCard label="Escalated" value={loading ? '…' : (stats?.escalated ?? '—')} subtle="raised a level" accent="gold" />
      </div>

      <div className="grid grid-cols-3 gap-4 mb-6">
        {/* Inflow chart */}
        <Card className="col-span-2">
          <SectionLabel right={<MonoChip>30d</MonoChip>}>Complaint inflow · last 30 days</SectionLabel>
          <div style={{ height: 240 }}>
            {loading
              ? <div className="h-full grid place-items-center text-[13px] text-[var(--muted)]">Loading…</div>
              : <ResponsiveContainer>
                  <AreaChart data={inflow} margin={{top:5,right:8,left:-15,bottom:0}}>
                    <defs>
                      <linearGradient id="sageGrad" x1="0" x2="0" y1="0" y2="1">
                        <stop offset="0%" stopColor="#4A6B5C" stopOpacity={0.25}/>
                        <stop offset="100%" stopColor="#4A6B5C" stopOpacity={0.02}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid {...chartGrid} vertical={false} />
                    <XAxis dataKey="day" {...chartAxis} tickLine={false} axisLine={{stroke:'#E5E0D6'}} interval={4} />
                    <YAxis {...chartAxis} tickLine={false} axisLine={false} allowDecimals={false} />
                    <Tooltip contentStyle={{ background:'#FDFBF7', border:'1px solid #E5E0D6', borderRadius:2, fontSize:12 }} />
                    <Area type="monotone" dataKey="complaints" stroke="#4A6B5C" strokeWidth={2} fill="url(#sageGrad)" />
                  </AreaChart>
                </ResponsiveContainer>}
          </div>
        </Card>

        {/* Category breakdown */}
        <Card>
          <SectionLabel>Category breakdown</SectionLabel>
          {loading
            ? <div className="text-[12px] text-[var(--muted)] py-2">Loading…</div>
            : categories.length === 0
              ? <div className="text-[12px] text-[var(--muted)] py-2">No complaints filed yet.</div>
              : <div className="space-y-3">
                  {categories.map(c => (
                    <div key={c.name}>
                      <div className="flex items-center justify-between text-[12px] mb-1">
                        <span className="text-[var(--ink)]">{c.name}</span>
                        <span className="font-mono text-[var(--muted)]">{c.value}</span>
                      </div>
                      <div className="h-1.5 rounded-sm bg-[var(--mist)]/70 overflow-hidden">
                        <div className="h-full" style={{ width: `${(c.value/catMax)*100}%`, background:'var(--sage)' }} />
                      </div>
                    </div>
                  ))}
                </div>}
        </Card>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {/* Recent action feed */}
        <Card className="col-span-2" noPad>
          <div className="p-5 pb-3 flex items-center justify-between">
            <SectionLabel className="mb-0">Recent activity</SectionLabel>
            <button onClick={()=>onGo('/university/complaints')} className="text-[12px] text-[var(--sage)] hover:underline">Open queue →</button>
          </div>
          {loading ? <div className="px-5 py-4 text-[13px] text-[var(--muted)]">Loading…</div> : <RecentFilings filings={filings} onGo={onGo} />}
        </Card>

        {/* Right column: real breakdowns */}
        <div className="flex flex-col gap-4">
          <Card>
            <SectionLabel>Caseload by status</SectionLabel>
            <BreakdownBars data={stats?.by_state} color="var(--sage)" />
          </Card>
          <Card>
            <SectionLabel>By priority</SectionLabel>
            <BreakdownBars data={stats?.by_priority} color="var(--gold)" />
          </Card>
        </div>
      </div>
    </>
  );
}

// ----- Dean -----
const DEAN_DEPTS = ['SWE', 'CSE', 'EEE', 'BBA', 'English', 'Law'];

function DeanDashboard({ onGo }) {
  const { stats, filings, loading } = useFilingData();
  const [deptRows, setDeptRows] = useState(null);
  useEffect(() => {
    Promise.all(DEAN_DEPTS.map(d =>
      AnchorAPI.apiGet(`/v1/departments/${encodeURIComponent(d)}/summary`).catch(() => null)
    )).then(rows => setDeptRows(rows.map((r, i) => r || { department: DEAN_DEPTS[i], total_count: 0 })));
  }, []);
  const cellClass = (v) => v == null ? '' : v >= 4.2 ? 'hm-good' : v >= 3.7 ? 'hm-okay' : 'hm-poor';
  const dims = [['avg_overall', 'Overall'], ['avg_teaching', 'Teaching'], ['avg_resources', 'Resources'], ['avg_environment', 'Environment']];

  return (
    <>
      <div className="grid grid-cols-4 gap-4 mb-6">
        <KpiCard label="Escalated cases" value={loading ? '…' : (stats?.escalated ?? '—')} subtle="awaiting your review" accent="gold" />
        <KpiCard label="Open across faculty" value={loading ? '…' : (stats?.open ?? '—')} subtle="active filings" />
        <KpiCard label="Resolved" value={loading ? '…' : (stats?.resolved ?? '—')} subtle="closed out" />
        <KpiCard label="Avg resolution" value={loading ? '…' : _fmtResolution(stats?.avg_resolution_secs)} subtle="submit → resolve" />
      </div>

      {/* Department ratings (real data from /v1/departments/{dept}/summary) */}
      <Card className="mb-6">
        <SectionLabel right={<div className="flex items-center gap-3 text-[11px] text-[var(--muted)]">
          <span className="inline-flex items-center gap-1"><span className="w-2 h-2 hm-good" /> ≥ 4.2</span>
          <span className="inline-flex items-center gap-1"><span className="w-2 h-2 hm-okay" /> 3.7–4.1</span>
          <span className="inline-flex items-center gap-1"><span className="w-2 h-2 hm-poor" /> &lt; 3.7</span>
        </div>}>Department ratings · student feedback</SectionLabel>
        {!deptRows
          ? <div className="text-[12px] text-[var(--muted)] py-4">Loading ratings…</div>
          : <div className="grid" style={{ gridTemplateColumns: `140px repeat(${dims.length}, 1fr) 90px` }}>
              <div />
              {dims.map(([, label]) => <div key={label} className="text-[11px] text-[var(--muted)] px-2 pb-2 text-center">{label}</div>)}
              <div className="text-[11px] text-[var(--muted)] px-2 pb-2 text-center">Ratings</div>
              {deptRows.map(row => (
                <React.Fragment key={row.department}>
                  <div className="text-[13px] font-medium text-[var(--ink)] py-2 hair-t border-t flex items-center">{row.department}</div>
                  {dims.map(([key, label]) => (
                    <div key={label} className="hair-t border-t p-1.5">
                      <div className={`rounded-sm py-2.5 text-center font-mono text-[12px] text-[var(--ink)] ${cellClass(row[key])}`}>{row[key] != null ? Number(row[key]).toFixed(1) : '—'}</div>
                    </div>
                  ))}
                  <div className="hair-t border-t flex items-center justify-center font-mono text-[12px] text-[var(--muted)]">{row.total_count || 0}</div>
                </React.Fragment>
              ))}
            </div>}
      </Card>

      <div className="grid grid-cols-3 gap-4">
        <Card className="col-span-2" noPad>
          <div className="p-5 pb-3 flex items-center justify-between">
            <SectionLabel className="mb-0">Recent filings across faculty</SectionLabel>
            <button onClick={()=>onGo('/university/complaints')} className="text-[12px] text-[var(--sage)] hover:underline">Open queue →</button>
          </div>
          {loading ? <div className="px-5 py-4 text-[13px] text-[var(--muted)]">Loading…</div> : <RecentFilings filings={filings} onGo={onGo} />}
        </Card>
        <Card>
          <SectionLabel>Caseload by category</SectionLabel>
          <BreakdownBars data={stats?.by_category} color="var(--sage)" />
        </Card>
      </div>
    </>
  );
}

// ----- Proctor -----
function _fmtSecs(secs) {
  if (!secs) return '—';
  const m = Math.floor(secs / 60), s = Math.round(secs % 60);
  return `${m}m ${String(s).padStart(2, '0')}s`;
}

function ProctorDashboard({ onGo }) {
  const [stats, setStats] = useState(null);
  const [alertRows, setAlertRows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      AnchorAPI.apiGet('/v1/admin/alerts/stats'),
      AnchorAPI.apiGet('/v1/admin/alerts?state=active&limit=10'),
    ])
      .then(([s, a]) => {
        setStats(s);
        const items = a.items ?? [];
        setAlertRows(items.map(ev => ({
          id: ev.event_id ? ev.event_id.slice(0, 13) + '…' : '—',
          kind: 'Alert',
          location: ev.lat && ev.lng ? `${Number(ev.lat).toFixed(4)}, ${Number(ev.lng).toFixed(4)}` : '—',
          triggeredAt: ev.created_at ? new Date(ev.created_at).toLocaleString('en-BD') : '—',
          status: ev.state === 'active' ? 'Active' : ev.state === 'resolved' ? 'Resolved' : (ev.state ?? '—'),
        })));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <AuditNote tone="navy" icon="shield-check" className="mb-4">
        Campus alerts are now operated by the AiVion Trust &amp; Safety team at the platform level. Your role here covers Rank-3 misconduct, hostel safety reports, and maintaining the campus geofence boundary.
      </AuditNote>

      <div className="grid grid-cols-4 gap-4 mb-6">
        <KpiCard label="Alerts inside zone · 24h" value={loading ? '…' : (stats?.active_count ?? '—')} subtle="live" accent="ember" />
        <KpiCard label="Resolved · 24h" value={loading ? '…' : (stats?.resolved_24h ?? '—')} subtle={stats ? `avg ${_fmtSecs(stats.avg_response_secs_24h)}` : ''} />
        <KpiCard label="False alarms · 30d" value={loading ? '…' : (stats?.false_alarms_30d ?? '—')} subtle="AI-flagged" />
        <KpiCard label="Rank-3 misconduct queue" value="—" subtle="sealed; restricted access" accent="ember" />
      </div>

      <div className="grid grid-cols-3 gap-4 mb-4">
        <Card className="col-span-2" noPad>
          <div className="p-5 pb-3 flex items-center justify-between">
            <SectionLabel className="mb-0">Recent alerts inside your zone</SectionLabel>
            <button onClick={()=>onGo('/university/geofence')} className="text-[12px] text-[var(--sage)] hover:underline">Open geofence →</button>
          </div>
          <div className="hair-t border-t">
            {loading
              ? <div className="px-5 py-4 text-[13px] text-[var(--muted)]">Loading…</div>
              : <DataTable
                  columns={[
                    { key:'id', label:'Event ID', render:r=><MonoChip>{r.id}</MonoChip> },
                    { key:'kind', label:'Kind' },
                    { key:'location', label:'Location' },
                    { key:'triggeredAt', label:'Triggered', render:r=><span className="font-mono text-[12px] text-[var(--muted)]">{r.triggeredAt}</span> },
                    { key:'status', label:'Status', render:r=><StatusPill status={r.status} /> },
                  ]}
                  rows={alertRows}
                  dense
                />
            }
            <div className="px-3 py-2 hair-t text-[11px] text-[var(--muted)] flex items-center gap-2">
              <Icon name="info" size={11} /> Read-only summary. Active alert response is operated by Super Admin.
            </div>
          </div>
        </Card>

        <Card>
          <SectionLabel>Campus zone</SectionLabel>
          <div className="aspect-square rounded-sm hair border relative overflow-hidden dot-grid" style={{ background:'#F1EFE8' }}>
            <svg viewBox="0 0 200 200" className="absolute inset-0 w-full h-full">
              <path d="M20 60 L60 30 L150 40 L180 90 L160 160 L80 175 L30 140 Z" fill="rgba(74,107,92,0.08)" stroke="#4A6B5C" strokeDasharray="3 3" />
              <text x="100" y="103" textAnchor="middle" fontSize="9" fill="#345249" fontFamily="JetBrains Mono">Campus geofence</text>
              <g transform="translate(110, 88)">
                <circle r="6" fill="#4A6B5C" />
              </g>
              <g transform="translate(60, 130)">
                <circle r="6" fill="#4A6B5C" />
              </g>
              <g transform="translate(155, 130)">
                <circle r="5" fill="#B8893A" />
                <text x="0" y="-10" textAnchor="middle" fontSize="7" fill="#52555C">Proctor Office</text>
              </g>
            </svg>
          </div>
          <button onClick={()=>onGo('/university/geofence')} className="mt-3 inline-flex items-center gap-1 text-[12px] text-[var(--sage)] hover:underline">
            <Icon name="map" size={12} /> Manage geofence
          </button>
        </Card>
      </div>
    </>
  );
}

// ----- Provost -----
function ProvostDashboard({ onGo }) {
  const { stats, filings, loading } = useFilingData();
  return (
    <>
      <div className="grid grid-cols-4 gap-4 mb-6">
        <KpiCard label="Open complaints" value={loading ? '…' : (stats?.open ?? '—')} subtle="residence + campus" />
        <KpiCard label="Under review" value={loading ? '…' : (stats?.under_review ?? '—')} subtle="awaiting decision" />
        <KpiCard label="Resolved" value={loading ? '…' : (stats?.resolved ?? '—')} subtle="closed out" />
        <KpiCard label="Escalated" value={loading ? '…' : (stats?.escalated ?? '—')} subtle="raised a level" accent="ember" />
      </div>

      <div className="grid grid-cols-3 gap-4">
        <Card className="col-span-2" noPad>
          <div className="p-5 pb-3 flex items-center justify-between">
            <SectionLabel className="mb-0">Recent residence-life filings</SectionLabel>
            <button onClick={()=>onGo('/university/complaints')} className="text-[12px] text-[var(--sage)] hover:underline">Open queue →</button>
          </div>
          {loading ? <div className="px-5 py-4 text-[13px] text-[var(--muted)]">Loading…</div> : <RecentFilings filings={filings} onGo={onGo} />}
        </Card>
        <Card>
          <SectionLabel>Caseload by status</SectionLabel>
          <BreakdownBars data={stats?.by_state} color="var(--sage)" />
        </Card>
      </div>
    </>
  );
}

// ----- VC -----
function VCDashboard({ onGo }) {
  const { stats, loading } = useFilingData();
  const [alertStats, setAlertStats] = useState(null);
  useEffect(() => {
    AnchorAPI.apiGet('/v1/admin/alerts/stats').then(setAlertStats).catch(() => {});
  }, []);
  return (
    <>
      <AuditNote tone="navy" icon="shield-check">
        You are viewing Level-3 escalations and platform-wide intelligence. All views of this content are audit-logged.
      </AuditNote>
      <div className="grid grid-cols-4 gap-4 my-6">
        <KpiCard label="Escalated cases" value={loading ? '…' : (stats?.escalated ?? '—')} subtle="awaiting your sign-off" accent="ember" />
        <KpiCard label="Open across faculties" value={loading ? '…' : (stats?.open ?? '—')} subtle="university-wide" />
        <KpiCard label="Active alerts" value={alertStats?.active_count ?? '—'} subtle="campus safety" accent="ember" />
        <KpiCard label="Avg resolution" value={loading ? '…' : _fmtResolution(stats?.avg_resolution_secs)} subtle="submit → resolve" />
      </div>
      <Card>
        <SectionLabel>Level-3 escalations on your desk</SectionLabel>
        {loading
          ? <div className="text-[13px] text-[var(--muted)] py-4">Loading…</div>
          : (stats?.escalated ?? 0) > 0
            ? <div className="text-[13px] text-[var(--ink)] py-2">
                <span className="font-mono text-[18px] text-[var(--ember)]">{stats.escalated}</span> escalated case{stats.escalated === 1 ? '' : 's'} awaiting review.
                <button onClick={()=>onGo('/university/complaints')} className="ml-2 text-[var(--sage)] hover:underline">Open queue →</button>
              </div>
            : <EmptyState icon="check-circle" title="Caught up." body="No Level-3 escalations require your sign-off right now." />}
      </Card>
    </>
  );
}

// ----- IT Admin -----
function ITDashboard({ onGo }) {
  const [users, setUsers] = useState(null);
  const [stats, setStats] = useState(null);
  const [alertStats, setAlertStats] = useState(null);
  const [aiOk, setAiOk] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    setLoading(true);
    Promise.all([
      AnchorAPI.apiGet('/v1/admin/users?page=1'),
      AnchorAPI.apiGet('/v1/admin/filings/stats').catch(() => null),
      AnchorAPI.apiGet('/v1/admin/alerts/stats').catch(() => null),
      AnchorAPI.apiGet('/ai/health').then(d => !!d && !d.error).catch(() => false),
    ])
      .then(([u, s, a, ok]) => { setUsers(u); setStats(s); setAlertStats(a); setAiOk(ok); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);
  const items = users?.items || [];
  const unverified = items.filter(u => u.email_verified === false).length;

  return (
    <>
      <div className="grid grid-cols-4 gap-4 mb-6">
        <KpiCard label="Users · tenant" value={loading ? '…' : (users?.total?.toLocaleString() ?? '—')} subtle="registered" />
        <KpiCard label="Unverified · page" value={loading ? '…' : unverified} subtle="email not confirmed" />
        <KpiCard label="Open filings" value={loading ? '…' : (stats?.open ?? '—')} subtle="across tenant" />
        <KpiCard label="AI subsystem" value={aiOk == null ? '…' : (aiOk ? 'Operational' : 'Down')} delta={aiOk ? 'OK' : null} deltaTone={aiOk ? 'up' : undefined} subtle="RAG health" accent={aiOk ? undefined : 'ember'} />
      </div>
      <Card noPad>
        <div className="p-5 pb-3 flex items-center justify-between">
          <SectionLabel className="mb-0">Users in your tenant</SectionLabel>
          <button onClick={()=>onGo('/university/users')} className="text-[12px] text-[var(--sage)] hover:underline">Manage users →</button>
        </div>
        {loading
          ? <div className="px-5 py-4 text-[13px] text-[var(--muted)]">Loading…</div>
          : <DataTable
              columns={[
                { key:'full_name', label:'Name' },
                { key:'email', label:'Email', render:r=><span className="font-mono text-[12px] text-[var(--muted)]">{r.email}</span> },
                { key:'role', label:'Role', render:r=><MonoChip>{r.role}</MonoChip> },
                { key:'status', label:'Status', render:r=><StatusPill status={_cap(r.status)} dot={false} /> },
                { key:'email_verified', label:'Verified', render:r=><span className="text-[12px]">{r.email_verified ? '✓' : '—'}</span> },
              ]}
              rows={items.slice(0, 8)}
              dense
            />}
      </Card>
    </>
  );
}

Object.assign(window, { UniDashboard });
