// University Dashboard — role-adaptive
var { useState, useEffect, useCallback, useRef, useMemo } = React;
const { LineChart, Line, AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, RadialBarChart, RadialBar, Legend } = window.Recharts || {};

const chartAxis = { stroke: '#6B7785', fontSize: 11, fontFamily: 'JetBrains Mono, monospace' };
const chartGrid = { stroke: '#E5E0D6', strokeDasharray: '0' };

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
    'Department Head':'Complaint queues, escalations, and your department\u2019s academic operations for the SWE department this week.',
    'Dean':'Cross-departmental performance, escalated grievances, and AI-flagged culture patterns across your faculty.',
    'Proctor':'Active campus alerts, serious misconduct queue, and the safety operations console.',
    'Provost':'Hostel complaints, hall tutor reports, and residence-life operations.',
    'VC Office':'Level-3 escalations and platform-wide intelligence for the Vice-Chancellor\u2019s office.',
    'IT Admin':'User management, routing configuration, and the technical health of your tenant.',
  }[role];
}

// ----- Department Head -----
function DeptHeadDashboard({ onGo }) {
  const D = window.AnchorData;
  return (
    <>
      <div className="grid grid-cols-4 gap-4 mb-6">
        <KpiCard label="Open complaints" value="23" delta="+4 this week" deltaTone="up" subtle="from 19" />
        <KpiCard label="Under review" value="11" subtle="3 awaiting your response" />
        <KpiCard label="Avg resolution" value="3.2d" delta="−0.4d" deltaTone="down" subtle="vs. last month" />
        <KpiCard label="Escalated to Dean" value="2" subtle="GRV-2026-A4F3, A4F6" accent="gold" />
      </div>

      <div className="grid grid-cols-3 gap-4 mb-6">
        {/* Inflow chart */}
        <Card className="col-span-2">
          <SectionLabel right={<div className="flex items-center gap-2 text-[11px] text-[var(--muted)]">
            <span className="inline-flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{background:'var(--sage)'}}/>this month</span>
            <span className="inline-flex items-center gap-1"><span className="w-2 h-2 rounded-full" style={{background:'var(--mist)'}}/>prev month</span>
          </div>}>Complaint inflow · last 30 days</SectionLabel>
          <div style={{ height: 240 }}>
            <ResponsiveContainer>
              <AreaChart data={D.inflow} margin={{top:5,right:8,left:-15,bottom:0}}>
                <defs>
                  <linearGradient id="sageGrad" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stopColor="#4A6B5C" stopOpacity={0.25}/>
                    <stop offset="100%" stopColor="#4A6B5C" stopOpacity={0.02}/>
                  </linearGradient>
                </defs>
                <CartesianGrid {...chartGrid} vertical={false} />
                <XAxis dataKey="day" {...chartAxis} tickLine={false} axisLine={{stroke:'#E5E0D6'}} />
                <YAxis {...chartAxis} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background:'#FDFBF7', border:'1px solid #E5E0D6', borderRadius:2, fontSize:12 }} />
                <Area type="monotone" dataKey="complaints" stroke="#4A6B5C" strokeWidth={2} fill="url(#sageGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

        {/* Category breakdown */}
        <Card>
          <SectionLabel>Category breakdown · this month</SectionLabel>
          <div className="space-y-3">
            {D.categoryBreakdown.map(c => {
              const max = Math.max(...D.categoryBreakdown.map(x=>x.value));
              return (
                <div key={c.name}>
                  <div className="flex items-center justify-between text-[12px] mb-1">
                    <span className="text-[var(--ink)]">{c.name}</span>
                    <span className="font-mono text-[var(--muted)]">{c.value}</span>
                  </div>
                  <div className="h-1.5 rounded-sm bg-[var(--mist)]/70 overflow-hidden">
                    <div className="h-full" style={{ width: `${(c.value/max)*100}%`, background:'var(--sage)' }} />
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-3 gap-4">
        {/* Recent action feed */}
        <Card className="col-span-2" noPad>
          <div className="p-5 pb-3 flex items-center justify-between">
            <SectionLabel className="mb-0">Recent activity</SectionLabel>
            <button onClick={()=>onGo('/university/complaints')} className="text-[12px] text-[var(--sage)] hover:underline">Open queue →</button>
          </div>
          <div className="hair-t border-t">
            {D.complaints.slice(0,5).map((c, i) => (
              <button key={c.id} onClick={()=>onGo('/university/complaints')} className={`w-full text-left p-4 hover:bg-[var(--mist)]/30 hair-b flex items-start gap-3 ${StatusEdgeClass(c.status)}`}>
                <Icon name={c.categoryIcon} size={16} className="mt-0.5 text-[var(--graphite)]" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <MonoChip>{c.id}</MonoChip>
                    {c.anonymous && <AnonymityBadge />}
                    <SeverityDots severity={c.severity} />
                    <span className="text-[11px] text-[var(--muted)] ml-auto">{c.lastAction}</span>
                  </div>
                  <div className="text-[13px] text-[var(--ink)] line-clamp-1">{c.title}</div>
                  <div className="text-[11px] text-[var(--muted)] mt-1 flex items-center gap-2">
                    <span>{c.category}</span>
                    <span>·</span>
                    <span>{c.routing.join(' → ')}</span>
                  </div>
                </div>
                <StatusPill status={c.status} />
              </button>
            ))}
          </div>
        </Card>

        {/* Right column: notes + AI insights */}
        <div className="flex flex-col gap-4">
          <Card>
            <SectionLabel>AI pattern insights</SectionLabel>
            <div className="space-y-3 text-[12.5px] text-[var(--graphite)] leading-relaxed">
              <div className="flex gap-2">
                <Icon name="sparkles" size={14} className="mt-0.5 shrink-0" style={{ color:'var(--gold)' }} />
                <span><span className="font-medium text-[var(--ink)]">2 classroom-cooling complaints</span> share Knowledge Tower as a hotspot.</span>
              </div>
              <div className="flex gap-2">
                <Icon name="sparkles" size={14} className="mt-0.5 shrink-0" style={{ color:'var(--gold)' }} />
                <span><span className="font-medium text-[var(--ink)]">4 anonymous reports</span> in 6 weeks reference the same lab instructor — Dean-level review suggested.</span>
              </div>
              <div className="flex gap-2">
                <Icon name="sparkles" size={14} className="mt-0.5 shrink-0" style={{ color:'var(--gold)' }} />
                <span>Resolution time on <span className="font-medium text-[var(--ink)]">Hostel category</span> has crept up by <span className="font-mono">+1.4d</span> this semester.</span>
              </div>
            </div>
            <button className="mt-4 text-[12px] text-[var(--sage)] hover:underline inline-flex items-center gap-1">Open all insights <Icon name="arrow-right" size={12} /></button>
          </Card>

          <Card>
            <SectionLabel>Next escalations</SectionLabel>
            <div className="space-y-2">
              {[
                { id:'CMP-2026-A4F2', label:'AC unit · Room 504', in:'in 18h' },
                { id:'CMP-2026-A4F8', label:'Lift · Knowledge Tower', in:'in 32h' },
              ].map(x => (
                <div key={x.id} className="flex items-center justify-between text-[12px]">
                  <div className="min-w-0">
                    <div className="truncate text-[var(--ink)]">{x.label}</div>
                    <MonoChip>{x.id}</MonoChip>
                  </div>
                  <span className="text-[var(--muted)] font-mono shrink-0 ml-2">{x.in}</span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </>
  );
}

// ----- Dean -----
function DeanDashboard({ onGo }) {
  const D = window.AnchorData;
  const dims = ['Communication','Resource Mgmt','Responsiveness','Fairness','Events'];
  const cellClass = (v) => v >= 4.2 ? 'hm-good' : v >= 3.7 ? 'hm-okay' : 'hm-poor';
  return (
    <>
      <div className="grid grid-cols-4 gap-4 mb-6">
        <KpiCard label="Escalated cases" value="5" delta="+2" deltaTone="up" subtle="awaiting your review" accent="gold" />
        <KpiCard label="Departments tracked" value="6" subtle="of 6 in faculty" />
        <KpiCard label="Anonymous reports" value="3" delta="new" deltaTone="up" subtle="not visible to dept heads" accent="ember" />
        <KpiCard label="Avg dept rating" value="3.96" subtle="Spring 2026 mid-sem" />
      </div>

      {/* Heatmap */}
      <Card className="mb-6">
        <SectionLabel right={<div className="flex items-center gap-3 text-[11px] text-[var(--muted)]">
          <span className="inline-flex items-center gap-1"><span className="w-2 h-2 hm-good" /> ≥ 4.2 strong</span>
          <span className="inline-flex items-center gap-1"><span className="w-2 h-2 hm-okay" /> 3.7–4.1</span>
          <span className="inline-flex items-center gap-1"><span className="w-2 h-2 hm-poor" /> &lt; 3.7</span>
        </div>}>Department performance heatmap · Spring 2026</SectionLabel>
        <div className="grid" style={{ gridTemplateColumns: `120px repeat(${dims.length}, 1fr)` }}>
          <div />
          {dims.map(d => <div key={d} className="text-[11px] text-[var(--muted)] px-2 pb-2 text-center">{d}</div>)}
          {D.deptPerf.map(row => (
            <React.Fragment key={row.dept}>
              <div className="text-[13px] font-medium text-[var(--ink)] py-2 hair-t border-t flex items-center">{row.dept}</div>
              {dims.map(d => (
                <div key={d} className={`hair-t border-t p-1.5`}>
                  <div className={`rounded-sm py-2.5 text-center font-mono text-[12px] text-[var(--ink)] ${cellClass(row[d])}`}>{row[d].toFixed(1)}</div>
                </div>
              ))}
            </React.Fragment>
          ))}
        </div>
      </Card>

      <div className="grid grid-cols-3 gap-4">
        <Card className="col-span-2">
          <SectionLabel right={<MonoChip tone="navy">Dean-only</MonoChip>}>Pattern detection alerts</SectionLabel>
          <div className="space-y-3">
            {[
              { dept:'SWE', text:'3 anonymous reports mention favoritism in SWE-405 lab access — pattern detected.', strength:'High' },
              { dept:'EEE', text:'Project group assignments appear biased toward students attending instructor coaching.', strength:'Medium' },
              { dept:'Law', text:'2 culture reports about delayed grading for non-traditional research formats.', strength:'Low' },
            ].map((p,i) => (
              <div key={i} className="hair border rounded-sm p-3 edge-gold flex items-start gap-3">
                <Icon name="sparkles" size={16} className="mt-0.5" style={{ color:'var(--gold)' }} />
                <div className="flex-1">
                  <div className="text-[13px] text-[var(--ink)] leading-snug">{p.text}</div>
                  <div className="mt-1.5 flex items-center gap-2 text-[11px] text-[var(--muted)]">
                    <Tag tone="sage">{p.dept}</Tag>
                    <span>·</span>
                    <span>Signal strength: <span className="font-medium" style={{ color:'var(--ink)' }}>{p.strength}</span></span>
                  </div>
                </div>
                <GhostButton size="sm" icon="arrow-right">Review</GhostButton>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <SectionLabel>Escalated to your desk</SectionLabel>
          <div className="space-y-2">
            {D.complaints.filter(c=>c.level===2).map(c => (
              <button key={c.id} onClick={()=>onGo('/university/complaints')} className={`w-full text-left p-3 rounded-sm hair border hover:bg-[var(--mist)]/30 ${StatusEdgeClass(c.status)}`}>
                <div className="flex items-center gap-2 mb-1">
                  <MonoChip>{c.id}</MonoChip>
                  {c.anonymous && <AnonymityBadge />}
                </div>
                <div className="text-[13px] line-clamp-2">{c.title}</div>
              </button>
            ))}
          </div>
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
  return (
    <>
      <div className="grid grid-cols-4 gap-4 mb-6">
        <KpiCard label="Hostel complaints · open" value="14" delta="+3" deltaTone="up" subtle="this week" />
        <KpiCard label="Seat allocation queue" value="22" subtle="pending review" />
        <KpiCard label="Hall tutor reports" value="6" subtle="3 require response" />
        <KpiCard label="Warden misconduct" value="1" subtle="Rank-3, sealed" accent="ember" />
      </div>

      <div className="grid grid-cols-2 gap-4 mb-6">
        {['Female Hall 1','Female Hall 2','Male Hall A','Male Hall B'].map(h => (
          <Card key={h}>
            <div className="flex items-center justify-between mb-3">
              <div>
                <div className="font-serif text-[18px] text-[var(--navy)]" style={{fontWeight:500}}>{h}</div>
                <div className="text-[12px] text-[var(--muted)]">Tutor: Mr. Saiful Islam · 312 residents</div>
              </div>
              <StatusPill status={h.includes('Female Hall 2')?'Escalated':'Under Review'} />
            </div>
            <div className="grid grid-cols-4 gap-3 text-center">
              {[
                { k:'Seat', v:'4' },
                { k:'Curfew', v:'2' },
                { k:'Roommate', v:'3' },
                { k:'Warden', v:'0' },
              ].map(x => (
                <div key={x.k}>
                  <div className="font-mono text-[20px] text-[var(--ink)]">{x.v}</div>
                  <div className="smallcaps text-[var(--muted)]" style={{fontSize:'9.5px'}}>{x.k}</div>
                </div>
              ))}
            </div>
          </Card>
        ))}
      </div>
    </>
  );
}

// ----- VC -----
function VCDashboard({ onGo }) {
  return (
    <>
      <AuditNote tone="navy" icon="shield-check">
        You are viewing Level-3 escalations and platform-wide intelligence. All views of this content are audit-logged.
      </AuditNote>
      <div className="grid grid-cols-4 gap-4 my-6">
        <KpiCard label="Level-3 escalations" value="3" subtle="awaiting your sign-off" accent="ember" />
        <KpiCard label="Open across faculties" value="612" subtle="university-wide" />
        <KpiCard label="Active alerts" value="2" subtle="campus safety" accent="ember" />
        <KpiCard label="Avg resolution" value="4.1d" delta="−0.2d" deltaTone="down" />
      </div>
      <Card>
        <SectionLabel>Level-3 escalations on your desk</SectionLabel>
        <EmptyState icon="check-circle" title="Caught up." body="No Level-3 escalations require your sign-off right now. Dean and Proctor are handling current cases." />
      </Card>
    </>
  );
}

// ----- IT Admin -----
function ITDashboard({ onGo }) {
  return (
    <>
      <div className="grid grid-cols-4 gap-4 mb-6">
        <KpiCard label="Active users · 30d" value="8,421" delta="+126" deltaTone="up" />
        <KpiCard label="Pending verifications" value="42" subtle="email + ID check" />
        <KpiCard label="Open routing rules" value="14" subtle="across 6 departments" />
        <KpiCard label="System health" value="99.94%" delta="OK" deltaTone="up" subtle="uptime · 30d" />
      </div>
      <Card>
        <SectionLabel>Recent admin actions in your tenant</SectionLabel>
        <DataTable
          columns={[
            { key:'t', label:'Time', render:r=><span className="font-mono text-[12px] text-[var(--muted)]">{r.t}</span> },
            { key:'actor', label:'Actor' },
            { key:'action', label:'Action', render:r=><MonoChip>{r.action}</MonoChip> },
            { key:'target', label:'Target' },
            { key:'outcome', label:'Outcome', render:r=><span className="text-[12px]">{r.outcome}</span> },
          ]}
          rows={window.AnchorData.audit.filter(a=>a.tenant==='diu').slice(0,6)}
          dense
        />
      </Card>
    </>
  );
}

Object.assign(window, { UniDashboard });
