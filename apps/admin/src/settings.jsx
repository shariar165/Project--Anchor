// Full Settings screen for both University Admin and Super Admin
var { useState, useEffect, useCallback, useRef, useMemo } = React;
function SettingsScreen({ mode='uni', dark, setDark, onGo }) {
  const [section, setSection] = useState('appearance');
  const accent = mode==='sup' ? 'ember' : 'sage';

  const NAV = mode==='uni' ? [
    { group:'Personal', items:[
      { id:'appearance', label:'Appearance', icon:'palette' },
      { id:'notifications', label:'Notifications', icon:'bell' },
      { id:'language', label:'Language & region', icon:'languages' },
      { id:'security', label:'Security & MFA', icon:'shield' },
    ]},
    { group:'University', items:[
      { id:'escalation', label:'Escalation rules', icon:'route' },
      { id:'routing', label:'Routing rules', icon:'git-fork' },
      { id:'anonymity', label:'Anonymous visibility', icon:'eye-off' },
      { id:'hierarchy', label:'Department hierarchy', icon:'building-2' },
      { id:'hours', label:'Working hours', icon:'clock' },
      { id:'audit-request', label:'Audit log access', icon:'scroll-text' },
    ]},
    { group:'Danger', items:[
      { id:'export', label:'Export & retention', icon:'download' },
    ]},
  ] : [
    { group:'Personal', items:[
      { id:'appearance', label:'Appearance', icon:'palette' },
      { id:'notifications', label:'Notifications', icon:'bell' },
      { id:'language', label:'Language & region', icon:'languages' },
      { id:'security', label:'Security & MFA', icon:'shield' },
    ]},
    { group:'Platform', items:[
      { id:'platform-escalation', label:'Default escalation timers', icon:'timer' },
      { id:'rate-limits', label:'Rate limits', icon:'gauge' },
      { id:'trust', label:'Trust ranking thresholds', icon:'award' },
      { id:'bans', label:'Ban durations', icon:'user-x' },
      { id:'ai-thresholds', label:'AI confidence thresholds', icon:'cpu' },
    ]},
    { group:'Compliance', items:[
      { id:'disclaimer', label:'Legal disclaimer', icon:'file-text' },
      { id:'retention', label:'Data retention', icon:'database' },
      { id:'pdpo', label:'Bangladesh PDP Ordinance 2025', icon:'scale' },
    ]},
  ];

  return (
    <>
      <PageHeader
        title="Settings"
        bn="সেটিংস"
        description={mode==='uni'
          ? 'Personal preferences and tenant-wide configuration. Changes to escalation, routing, and visibility are audit-logged.'
          : 'Personal preferences and platform-wide policy. All policy changes are permanently audit-logged.'}
      />

      <div className="grid gap-5" style={{ gridTemplateColumns:'240px 1fr' }}>
        {/* Sidebar */}
        <Card noPad>
          <div className="p-3">
            {NAV.map((grp, i) => (
              <div key={grp.group} className={i>0?'mt-3':''}>
                <div className="smallcaps text-[var(--muted)] px-2 pb-1.5">{grp.group}</div>
                <div className="flex flex-col gap-0.5">
                  {grp.items.map(it => (
                    <button key={it.id} onClick={()=>setSection(it.id)}
                      className={`flex items-center gap-2 px-2 py-1.5 rounded-sm text-[13px] text-left transition ${section===it.id ? (mode==='uni'?'nav-active-uni':'nav-active-sup') : 'text-[var(--graphite)] hover:bg-[var(--mist)]/40'}`}>
                      <Icon name={it.icon} size={14} />
                      <span>{it.label}</span>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Card>

        {/* Content */}
        <div>
          {section==='appearance' && <AppearanceSection dark={dark} setDark={setDark} mode={mode} accent={accent} />}
          {section==='notifications' && <NotificationsSection mode={mode} />}
          {section==='language' && <LanguageSection mode={mode} />}
          {section==='security' && <SecuritySection mode={mode} />}

          {/* university only */}
          {section==='escalation' && <EscalationRulesSection />}
          {section==='routing' && <RoutingRulesSection />}
          {section==='anonymity' && <AnonymitySection />}
          {section==='hierarchy' && <HierarchySection />}
          {section==='hours' && <HoursSection />}
          {section==='audit-request' && <AuditAccessRequestSection />}
          {section==='export' && <ExportRetentionSection />}

          {/* super admin only */}
          {section==='platform-escalation' && <PlatformEscalationSection />}
          {section==='rate-limits' && <RateLimitsSection />}
          {section==='trust' && <TrustThresholdsSection />}
          {section==='bans' && <BansSection />}
          {section==='ai-thresholds' && <AIThresholdsSection />}
          {section==='disclaimer' && <DisclaimerSection />}
          {section==='retention' && <RetentionSection />}
          {section==='pdpo' && <PDPOSection />}
        </div>
      </div>
    </>
  );
}

// ---- shared section primitives ----
function SettingRow({ title, hint, children, action }) {
  return (
    <div className="hair-b border-b last:border-b-0 py-4 flex items-start gap-6">
      <div className="flex-1 min-w-0">
        <div className="text-[13.5px] font-medium text-[var(--ink)]">{title}</div>
        {hint && <div className="text-[12px] text-[var(--muted)] mt-0.5 leading-snug">{hint}</div>}
      </div>
      <div className="shrink-0 flex items-center gap-2">{children}{action}</div>
    </div>
  );
}

function Toggle({ on, onChange }) {
  return (
    <button onClick={()=>onChange(!on)} className="relative inline-flex items-center w-10 h-6 rounded-full transition" style={{ background: on ? 'var(--sage)' : 'var(--mist)' }}>
      <span className="absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white shadow transition" style={{ transform: on ? 'translateX(16px)' : 'translateX(0)' }} />
    </button>
  );
}

function Pill({ children, on, onClick }) {
  return (
    <button onClick={onClick} className={`px-2.5 py-1 rounded-sm text-[12px] hair border ${on?'bg-[var(--sage)] text-white border-transparent':'text-[var(--graphite)] hover:bg-[var(--mist)]/40'}`}>{children}</button>
  );
}

function SaveBar({ accent='sage' }) {
  return (
    <div className="mt-4 pt-4 hair-t border-t flex items-center justify-between">
      <span className="text-[12px] text-[var(--muted)]">Changes are saved on blur and audit-logged.</span>
      <div className="flex items-center gap-2">
        <GhostButton size="sm">Discard</GhostButton>
        <PrimaryButton mode={accent} size="sm" icon="check">Save changes</PrimaryButton>
      </div>
    </div>
  );
}

// ---- Appearance ----
function AppearanceSection({ dark, setDark, mode, accent }) {
  const [density, setDensity] = useState('comfortable');
  const [sidebar, setSidebar] = useState('full');
  const [font, setFont] = useState('default');
  return (
    <Card>
      <SectionLabel>Appearance</SectionLabel>
      <SettingRow title="Theme" hint="Switch between light and dark. Your preference is remembered on this device.">
        <div className="flex hair border rounded-sm overflow-hidden">
          <button onClick={()=>setDark(false)} className={`px-3 py-1.5 text-[12px] inline-flex items-center gap-1.5 ${!dark?'bg-[var(--sage)] text-white':'text-[var(--graphite)]'}`}>
            <Icon name="sun" size={12} /> Light
          </button>
          <button onClick={()=>setDark(true)} className={`px-3 py-1.5 text-[12px] inline-flex items-center gap-1.5 ${dark?'bg-[var(--sage)] text-white':'text-[var(--graphite)]'}`}>
            <Icon name="moon" size={12} /> Dark
          </button>
          <button onClick={()=>{ try { localStorage.removeItem('anchor:dark'); } catch (e) {}; setDark(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches); }}
            className="px-3 py-1.5 text-[12px] inline-flex items-center gap-1.5 text-[var(--graphite)] hair-l border-l">
            <Icon name="monitor" size={12} /> System
          </button>
        </div>
      </SettingRow>

      <SettingRow title="Table density" hint="Comfortable matches the editorial system. Compact tightens row height for power users.">
        <div className="flex hair border rounded-sm overflow-hidden">
          {['comfortable','compact'].map(d => (
            <button key={d} onClick={()=>setDensity(d)} className={`px-3 py-1.5 text-[12px] capitalize ${density===d?'bg-[var(--sage)] text-white':'text-[var(--graphite)]'}`}>{d}</button>
          ))}
        </div>
      </SettingRow>

      <SettingRow title="Sidebar default" hint="Whether the sidebar starts expanded or collapsed when you open the admin.">
        <div className="flex hair border rounded-sm overflow-hidden">
          {[{v:'full',label:'Full'},{v:'icons',label:'Icons only'}].map(d => (
            <button key={d.v} onClick={()=>setSidebar(d.v)} className={`px-3 py-1.5 text-[12px] ${sidebar===d.v?'bg-[var(--sage)] text-white':'text-[var(--graphite)]'}`}>{d.label}</button>
          ))}
        </div>
      </SettingRow>

      <SettingRow title="Numerals" hint="Numbers default to tabular figures across the admin. Switch off if you prefer proportional.">
        <Toggle on={true} onChange={()=>{}} />
      </SettingRow>

      <SettingRow title="Reduced motion" hint="Disables non-essential transitions and the alert pulse animation.">
        <Toggle on={false} onChange={()=>{}} />
      </SettingRow>

      <SaveBar accent={accent} />
    </Card>
  );
}

// ---- Notifications ----
function NotificationsSection({ mode }) {
  const [prefs, setPrefs] = useState({
    pushNewCase: true, pushEscalation: true, pushAlert: mode==='sup',
    emailDaily: true, emailWeekly: false,
    smsCritical: true, smsRoutine: false,
    quietHours: '22:00 → 07:00',
  });
  return (
    <Card>
      <SectionLabel>Notifications</SectionLabel>
      <SettingRow title="Push · new case assigned" hint="In-app and desktop push when a complaint is routed to you.">
        <Toggle on={prefs.pushNewCase} onChange={v=>setPrefs(p=>({...p, pushNewCase:v}))} />
      </SettingRow>
      <SettingRow title="Push · escalation reminders" hint="72-hour reminder before a case auto-escalates.">
        <Toggle on={prefs.pushEscalation} onChange={v=>setPrefs(p=>({...p, pushEscalation:v}))} />
      </SettingRow>
      {mode==='sup' && (
        <SettingRow title="Push · campus alert" hint="Always-on for on-duty platform operators. Cannot be disabled while on shift.">
          <Toggle on={prefs.pushAlert} onChange={v=>setPrefs(p=>({...p, pushAlert:v}))} />
        </SettingRow>
      )}
      <SettingRow title="Email · daily digest" hint="08:00 each morning, summary of yesterday\u2019s activity in your queue.">
        <Toggle on={prefs.emailDaily} onChange={v=>setPrefs(p=>({...p, emailDaily:v}))} />
      </SettingRow>
      <SettingRow title="Email · weekly performance" hint="Sundays, performance + pattern-detection summary.">
        <Toggle on={prefs.emailWeekly} onChange={v=>setPrefs(p=>({...p, emailWeekly:v}))} />
      </SettingRow>
      <SettingRow title="SMS · critical only" hint="Rank-3 misconduct, active alerts, de-anonymization decisions.">
        <Toggle on={prefs.smsCritical} onChange={v=>setPrefs(p=>({...p, smsCritical:v}))} />
      </SettingRow>
      <SettingRow title="SMS · routine" hint="All status changes by SMS. Not recommended.">
        <Toggle on={prefs.smsRoutine} onChange={v=>setPrefs(p=>({...p, smsRoutine:v}))} />
      </SettingRow>
      <SettingRow title="Quiet hours" hint="Non-critical notifications are silenced during this window.">
        <input value={prefs.quietHours} onChange={e=>setPrefs(p=>({...p, quietHours:e.target.value}))}
          className="px-2 py-1.5 hair border rounded-sm bg-white font-mono text-[12px] w-[150px]" />
      </SettingRow>
      <SaveBar accent={mode==='sup'?'ember':'sage'} />
    </Card>
  );
}

// ---- Language & Region ----
function LanguageSection({ mode }) {
  const [lang, setLang] = useState('en');
  return (
    <Card>
      <SectionLabel>Language & region</SectionLabel>
      <SettingRow title="Interface language" hint="The admin UI text. Notice content language is configured separately per notice.">
        <div className="flex hair border rounded-sm overflow-hidden">
          {[{v:'en',label:'English'},{v:'bn',label:'বাংলা',cls:'font-bn'},{v:'auto',label:'Auto'}].map(l => (
            <button key={l.v} onClick={()=>setLang(l.v)} className={`px-3 py-1.5 text-[12px] ${l.cls||''} ${lang===l.v?'bg-[var(--sage)] text-white':'text-[var(--graphite)]'}`}>{l.label}</button>
          ))}
        </div>
      </SettingRow>
      <SettingRow title="Time zone" hint="All timestamps in the admin display in this timezone.">
        <select className="px-2 py-1.5 hair border rounded-sm bg-white text-[12.5px]"><option>(GMT+06:00) Asia / Dhaka</option><option>(GMT+05:30) Asia / Kolkata</option><option>(GMT+00:00) UTC</option></select>
      </SettingRow>
      <SettingRow title="Date format" hint="Used in tables, audit logs, and case timestamps.">
        <select className="px-2 py-1.5 hair border rounded-sm bg-white text-[12.5px] font-mono"><option>YYYY-MM-DD HH:mm</option><option>DD/MM/YYYY HH:mm</option><option>MMM D, YYYY h:mm A</option></select>
      </SettingRow>
      <SettingRow title="First day of week" hint="Used in the routine builder grid and analytics charts.">
        <select className="px-2 py-1.5 hair border rounded-sm bg-white text-[12.5px]"><option>Sunday</option><option>Monday</option><option>Saturday</option></select>
      </SettingRow>
      <SaveBar accent={mode==='sup'?'ember':'sage'} />
    </Card>
  );
}

// ---- Security ----
function SecuritySection({ mode }) {
  return (
    <Card>
      <SectionLabel>Security & MFA</SectionLabel>
      <SettingRow title="Multi-factor authentication" hint="Authenticator app — required for all admin sign-ins.">
        <Tag tone="sage" icon="shield-check">Enabled · TOTP</Tag>
      </SettingRow>
      <SettingRow title="Backup codes" hint="Single-use codes for recovery if you lose access to your authenticator.">
        <GhostButton size="sm" icon="download">Generate new set</GhostButton>
      </SettingRow>
      <SettingRow title="Session timeout" hint="Automatic sign-out after this period of inactivity.">
        <select className="px-2 py-1.5 hair border rounded-sm bg-white text-[12.5px]"><option>{mode==='sup'?'1 hour':'4 hours'}</option><option>30 minutes</option><option>8 hours</option></select>
      </SettingRow>
      <SettingRow title="Trusted devices" hint="Devices that have completed MFA in the last 30 days.">
        <span className="font-mono text-[12px] text-[var(--ink)]">3 devices</span>
        <GhostButton size="sm" danger icon="log-out">Sign out all</GhostButton>
      </SettingRow>
      <SettingRow title="Change password" hint="Last changed 47 days ago.">
        <GhostButton size="sm" icon="key-round">Change</GhostButton>
      </SettingRow>
      {mode==='sup' && (
        <SettingRow title="Hardware security key" hint="Phishing-resistant FIDO2. Recommended for super admins.">
          <PrimaryButton size="sm" mode="ember" icon="key-square">Enroll YubiKey</PrimaryButton>
        </SettingRow>
      )}
      <SaveBar accent={mode==='sup'?'ember':'sage'} />
    </Card>
  );
}

// ---- University-specific ----
function EscalationRulesSection() {
  return (
    <Card>
      <SectionLabel>Escalation rules</SectionLabel>
      <AuditNote tone="gold" icon="route">Each category has its own auto-escalation timer. Times reset on any admin action that touches the case.</AuditNote>
      <div className="mt-4">
        <DataTable
          columns={[
            { key:'cat', label:'Category' },
            { key:'l1', label:'Dept Head → Dean' },
            { key:'l2', label:'Dean → VC' },
            { key:'sev', label:'Min severity to auto-escalate' },
          ]}
          rows={[
            { cat:'Classroom', l1:'72h', l2:'7 days', sev:'Rank 2+' },
            { cat:'Teacher Conduct', l1:'48h', l2:'5 days', sev:'Rank 2+' },
            { cat:'Department', l1:'72h', l2:'7 days', sev:'Rank 2+' },
            { cat:'Hostel', l1:'72h', l2:'5 days', sev:'Rank 2+' },
            { cat:'Academic', l1:'72h', l2:'7 days', sev:'Rank 3 only' },
          ].map(r => ({...r,
            l1: <span className="font-mono text-[12px]">{r.l1}</span>,
            l2: <span className="font-mono text-[12px]">{r.l2}</span>,
            sev: <Tag tone="navy">{r.sev}</Tag>,
          }))}
        />
      </div>
      <SaveBar />
    </Card>
  );
}

function RoutingRulesSection() {
  return (
    <Card>
      <SectionLabel right={<PrimaryButton size="sm" icon="plus" mode="sage">Add rule</PrimaryButton>}>Routing rules</SectionLabel>
      <div className="space-y-2">
        {[
          { match:'Category = Hostel', to:'Provost', enabled:true },
          { match:'Category = Teacher Conduct AND Severity ≥ Rank 3', to:'Dean (bypass Dept Head)', enabled:true },
          { match:'Anonymous = true AND Severity = Rank 3', to:'Proctor (sealed queue)', enabled:true },
          { match:'Category = Classroom', to:'Dept Head', enabled:true },
          { match:'Category = Academic AND Subject contains "grade"', to:'Dept Head with copy to Registrar', enabled:false },
        ].map((r,i) => (
          <div key={i} className="hair border rounded-sm p-3 flex items-center gap-3">
            <Icon name="git-fork" size={14} className="text-[var(--graphite)]" />
            <div className="flex-1 text-[13px]">
              <span className="font-mono text-[12px] text-[var(--graphite)]">{r.match}</span>
              <span className="mx-2 text-[var(--muted)]">→</span>
              <span className="font-medium">{r.to}</span>
            </div>
            <Toggle on={r.enabled} onChange={()=>{}} />
            <button className="text-[var(--muted)] hover:text-[var(--ink)]"><Icon name="more-horizontal" size={14} /></button>
          </div>
        ))}
      </div>
      <SaveBar />
    </Card>
  );
}

function AnonymitySection() {
  return (
    <Card>
      <SectionLabel>Anonymous report visibility</SectionLabel>
      <AuditNote tone="red" icon="eye-off">These settings affect who can see anonymous reports. De-anonymization always requires a separate formal request to Super Admin.</AuditNote>
      <div className="mt-4">
        <SettingRow title="Department Head can see anonymous reports" hint="When off, anonymous reports bypass the Dept Head and go directly to the Dean.">
          <Toggle on={false} onChange={()=>{}} />
        </SettingRow>
        <SettingRow title="Dean can see anonymous Rank-3 reports" hint="Rank-3 reports always reach the Dean and Proctor by default.">
          <Toggle on={true} onChange={()=>{}} />
        </SettingRow>
        <SettingRow title="Anonymity cooling period" hint="Time a submitter must wait between anonymous reports against the same target.">
          <select className="px-2 py-1.5 hair border rounded-sm bg-white text-[12.5px]"><option>24 hours</option><option>7 days</option><option>None</option></select>
        </SettingRow>
        <SettingRow title="Show pattern-detection hints to admins" hint="When AI detects a pattern, surface that on the case detail.">
          <Toggle on={true} onChange={()=>{}} />
        </SettingRow>
      </div>
      <SaveBar />
    </Card>
  );
}

function HierarchySection() {
  return (
    <Card>
      <SectionLabel right={<GhostButton size="sm" icon="plus">Add department</GhostButton>}>Department hierarchy</SectionLabel>
      <div className="hair border rounded-sm p-3">
        <div className="text-[13.5px] font-medium mb-2">Faculty of Science & Information Technology</div>
        <div className="pl-4 space-y-1.5 text-[13px]">
          {['Department of SWE','Department of CSE','Department of EEE','Department of CIS','Department of MCT','Department of Multimedia'].map(d => (
            <div key={d} className="flex items-center justify-between hair-b border-b last:border-b-0 py-1.5">
              <span>{d}</span>
              <button className="text-[var(--muted)] hover:text-[var(--ink)]"><Icon name="more-horizontal" size={14} /></button>
            </div>
          ))}
        </div>
      </div>
      <div className="mt-3 hair border rounded-sm p-3">
        <div className="text-[13.5px] font-medium mb-2">Faculty of Business & Entrepreneurship</div>
        <div className="pl-4 space-y-1.5 text-[13px]">
          {['Department of BBA','Department of Real Estate','Department of Tourism & Hospitality'].map(d => (
            <div key={d} className="flex items-center justify-between hair-b border-b last:border-b-0 py-1.5">
              <span>{d}</span>
              <button className="text-[var(--muted)] hover:text-[var(--ink)]"><Icon name="more-horizontal" size={14} /></button>
            </div>
          ))}
        </div>
      </div>
      <SaveBar />
    </Card>
  );
}

function HoursSection() {
  const days = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  return (
    <Card>
      <SectionLabel>Working hours & holidays</SectionLabel>
      <div className="grid grid-cols-7 gap-2 mt-2">
        {days.map((d, i) => (
          <div key={d} className="hair border rounded-sm p-2.5 text-center">
            <div className="smallcaps text-[var(--muted)]">{d}</div>
            <div className="font-mono text-[11px] mt-1 text-[var(--ink)]">{i>=5?'closed':'08:00–17:00'}</div>
          </div>
        ))}
      </div>
      <div className="mt-4">
        <SectionLabel right={<GhostButton size="sm" icon="plus">Add holiday</GhostButton>}>Upcoming holidays</SectionLabel>
        <div className="space-y-1.5 text-[13px]">
          {[
            { d:'2026-06-08', n:'Buddha Purnima' },
            { d:'2026-06-12', n:'Eid-ul-Azha (begins)' },
            { d:'2026-07-29', n:'Ashura' },
            { d:'2026-08-15', n:'National Mourning Day' },
          ].map(h => (
            <div key={h.d} className="flex items-center justify-between hair-b border-b last:border-b-0 py-1.5">
              <span>{h.n}</span>
              <span className="font-mono text-[12px] text-[var(--muted)]">{h.d}</span>
            </div>
          ))}
        </div>
      </div>
      <SaveBar />
    </Card>
  );
}

function AuditAccessRequestSection() {
  return (
    <Card>
      <SectionLabel>Audit log access request</SectionLabel>
      <AuditNote tone="red" icon="shield-alert">Submit a formal request to the Super Admin for identity de-anonymization in a specific case. Two-person platform approval is required.</AuditNote>
      <div className="mt-4 space-y-3 max-w-[640px]">
        <Field label="Case ID">
          <input placeholder="CMP-2026-XXXX or ALR-2026-XXXX" className="w-full px-3 py-2 hair border rounded-sm bg-white font-mono text-[13px]" />
        </Field>
        <Field label="Legal basis" hint="Cite the section of Bangladesh statute or university policy.">
          <input placeholder="e.g. Penal Code §509" className="w-full px-3 py-2 hair border rounded-sm bg-white text-[13px]" />
        </Field>
        <Field label="Reason">
          <textarea rows={4} placeholder="Describe the formal review process this disclosure supports." className="w-full px-3 py-2 hair border rounded-sm bg-white text-[13px]" />
        </Field>
        <Field label="Supporting document">
          <div className="hair border-dashed border-2 rounded-sm p-4 text-center text-[12px] text-[var(--muted)] cursor-pointer hover:bg-[var(--mist)]/20">
            Drop the formal request letter PDF here, or click to upload.
          </div>
        </Field>
        <div className="flex items-center justify-end gap-2 pt-2">
          <GhostButton>Save draft</GhostButton>
          <PrimaryButton mode="red" icon="send">Submit to Super Admin</PrimaryButton>
        </div>
      </div>
    </Card>
  );
}

function ExportRetentionSection() {
  return (
    <Card>
      <SectionLabel>Export & retention</SectionLabel>
      <SettingRow title="Export tenant data" hint="Generate a CSV/JSON archive of all complaints, grievances, and routine data. Audit logs are excluded; request separately.">
        <GhostButton size="sm" icon="download">Generate export</GhostButton>
      </SettingRow>
      <SettingRow title="Resolved-case retention" hint="How long resolved cases remain queryable in the admin. Older cases are archived to cold storage.">
        <select className="px-2 py-1.5 hair border rounded-sm bg-white text-[12.5px]"><option>2 academic years</option><option>3 academic years</option><option>5 academic years</option></select>
      </SettingRow>
      <SettingRow title="Evidence retention" hint="Images and documents attached to cases.">
        <select className="px-2 py-1.5 hair border rounded-sm bg-white text-[12.5px]"><option>5 years</option><option>10 years</option></select>
      </SettingRow>
      <SettingRow title="Delete inactive student accounts" hint="Accounts with no activity for this period are deactivated, not deleted.">
        <select className="px-2 py-1.5 hair border rounded-sm bg-white text-[12.5px]"><option>2 years</option><option>Never</option></select>
      </SettingRow>
      <SaveBar />
    </Card>
  );
}

// ---- Super-admin specific ----
function PlatformEscalationSection() {
  return (
    <Card>
      <SectionLabel>Default escalation timers</SectionLabel>
      <AuditNote tone="red" icon="shield-alert">These are platform-wide defaults. Tenants may override per-category in their own settings — but cannot exceed the maximums set here.</AuditNote>
      <div className="mt-4 space-y-3">
        <SettingRow title="Default Level-1 → Level-2 timer" hint="Auto-escalation from Dept Head to Dean if no action is taken.">
          <input defaultValue="72" className="w-[80px] px-2 py-1.5 hair border rounded-sm bg-white font-mono text-[13px] text-right" />
          <span className="text-[12px] text-[var(--muted)]">hours</span>
        </SettingRow>
        <SettingRow title="Default Level-2 → Level-3 timer" hint="Dean to VC Office.">
          <input defaultValue="7" className="w-[80px] px-2 py-1.5 hair border rounded-sm bg-white font-mono text-[13px] text-right" />
          <span className="text-[12px] text-[var(--muted)]">days</span>
        </SettingRow>
        <SettingRow title="Active alert auto-escalation" hint="If a tenant proctor doesn\u2019t acknowledge within this window, the alert escalates to platform operators.">
          <input defaultValue="30" className="w-[80px] px-2 py-1.5 hair border rounded-sm bg-white font-mono text-[13px] text-right" />
          <span className="text-[12px] text-[var(--muted)]">minutes</span>
        </SettingRow>
        <SettingRow title="Maximum timer a tenant can configure" hint="Hard cap preventing tenants from disabling escalation by setting absurd timers.">
          <input defaultValue="14" className="w-[80px] px-2 py-1.5 hair border rounded-sm bg-white font-mono text-[13px] text-right" />
          <span className="text-[12px] text-[var(--muted)]">days</span>
        </SettingRow>
      </div>
      <SaveBar accent="ember" />
    </Card>
  );
}

function RateLimitsSection() {
  return (
    <Card>
      <SectionLabel>Rate limits</SectionLabel>
      <div className="mt-2">
        <SettingRow title="Complaint filing · per student" hint="Soft limit. Beyond this in 24h, AI screens for spam.">
          <input defaultValue="5" className="w-[80px] px-2 py-1.5 hair border rounded-sm bg-white font-mono text-[13px] text-right" />
          <span className="text-[12px] text-[var(--muted)]">/ 24h</span>
        </SettingRow>
        <SettingRow title="Active alerts · per student" hint="Hard limit per 24h. Exceeded users are auto-blocked until review.">
          <input defaultValue="3" className="w-[80px] px-2 py-1.5 hair border rounded-sm bg-white font-mono text-[13px] text-right" />
          <span className="text-[12px] text-[var(--muted)]">/ 24h</span>
        </SettingRow>
        <SettingRow title="News publishing · per user" hint="Verification feed posts before AI screening throttles.">
          <input defaultValue="2" className="w-[80px] px-2 py-1.5 hair border rounded-sm bg-white font-mono text-[13px] text-right" />
          <span className="text-[12px] text-[var(--muted)]">/ hour</span>
        </SettingRow>
        <SettingRow title="AI queries · per user" hint="Caps individual chatbot usage on the student app.">
          <input defaultValue="60" className="w-[80px] px-2 py-1.5 hair border rounded-sm bg-white font-mono text-[13px] text-right" />
          <span className="text-[12px] text-[var(--muted)]">/ hour</span>
        </SettingRow>
      </div>
      <SaveBar accent="ember" />
    </Card>
  );
}

function TrustThresholdsSection() {
  return (
    <Card>
      <SectionLabel>Trust ranking thresholds</SectionLabel>
      <p className="text-[12.5px] text-[var(--graphite)] mb-3">Publishers gain trust by submitting verified news. These thresholds map to badges in the verification feed.</p>
      <SettingRow title="Bronze · Verified" hint="Minimum correct verified posts to earn the bronze badge.">
        <input defaultValue="5" className="w-[80px] px-2 py-1.5 hair border rounded-sm bg-white font-mono text-[13px] text-right" />
        <Tag tone="mist">posts</Tag>
      </SettingRow>
      <SettingRow title="Silver · Trusted" hint="Verified posts to be marked Trusted.">
        <input defaultValue="10" className="w-[80px] px-2 py-1.5 hair border rounded-sm bg-white font-mono text-[13px] text-right" />
        <Tag tone="mist">posts</Tag>
      </SettingRow>
      <SettingRow title="Gold · Sourceful" hint="Earn the highest publisher tier.">
        <input defaultValue="15" className="w-[80px] px-2 py-1.5 hair border rounded-sm bg-white font-mono text-[13px] text-right" />
        <Tag tone="mist">posts</Tag>
      </SettingRow>
      <SettingRow title="Demotion threshold" hint="Verified false posts that demote a publisher one tier.">
        <input defaultValue="2" className="w-[80px] px-2 py-1.5 hair border rounded-sm bg-white font-mono text-[13px] text-right" />
        <Tag tone="red">false posts</Tag>
      </SettingRow>
      <SaveBar accent="ember" />
    </Card>
  );
}

function BansSection() {
  return (
    <Card>
      <SectionLabel>Ban durations</SectionLabel>
      <SettingRow title="Alert false-alarm ban" hint="When a user\u2019s alert is determined false, they cannot file new alerts for this duration.">
        <input defaultValue="30" className="w-[80px] px-2 py-1.5 hair border rounded-sm bg-white font-mono text-[13px] text-right" />
        <span className="text-[12px] text-[var(--muted)]">days</span>
      </SettingRow>
      <SettingRow title="News false-publication ban" hint="Publishing falsely verified news.">
        <input defaultValue="30" className="w-[80px] px-2 py-1.5 hair border rounded-sm bg-white font-mono text-[13px] text-right" />
        <span className="text-[12px] text-[var(--muted)]">days</span>
      </SettingRow>
      <SettingRow title="Complaint spam ban" hint="Repeated unfounded complaints flagged as spam.">
        <input defaultValue="14" className="w-[80px] px-2 py-1.5 hair border rounded-sm bg-white font-mono text-[13px] text-right" />
        <span className="text-[12px] text-[var(--muted)]">days</span>
      </SettingRow>
      <SettingRow title="Permanent ban requires" hint="Super admin approvals to make a ban permanent.">
        <select className="px-2 py-1.5 hair border rounded-sm bg-white text-[12.5px]"><option>2 super admin approvals</option><option>1 super admin approval</option><option>External oversight sign-off</option></select>
      </SettingRow>
      <SaveBar accent="ember" />
    </Card>
  );
}

function AIThresholdsSection() {
  return (
    <Card>
      <SectionLabel>AI confidence thresholds</SectionLabel>
      <SettingRow title="Auto-publish · news" hint="Minimum AI confidence to auto-approve a verification-feed post.">
        <input defaultValue="0.90" className="w-[80px] px-2 py-1.5 hair border rounded-sm bg-white font-mono text-[13px] text-right" />
      </SettingRow>
      <SettingRow title="Auto-reject · news" hint="Below this confidence, the AI rejects the post outright.">
        <input defaultValue="0.40" className="w-[80px] px-2 py-1.5 hair border rounded-sm bg-white font-mono text-[13px] text-right" />
      </SettingRow>
      <SettingRow title="Auto-flag false alarm" hint="AI confidence that the alert is false.">
        <input defaultValue="0.85" className="w-[80px] px-2 py-1.5 hair border rounded-sm bg-white font-mono text-[13px] text-right" />
      </SettingRow>
      <SettingRow title="Pattern-detection signal strength · alert">
        <select className="px-2 py-1.5 hair border rounded-sm bg-white text-[12.5px]"><option>Surface to Dean when ≥ 3 reports</option><option>Surface when ≥ 2 reports</option><option>Surface when ≥ 5 reports</option></select>
      </SettingRow>
      <SettingRow title="Self-verification minimum pass rate" hint="Below this, the output is auto-rejected and re-routed.">
        <input defaultValue="0.95" className="w-[80px] px-2 py-1.5 hair border rounded-sm bg-white font-mono text-[13px] text-right" />
      </SettingRow>
      <SaveBar accent="ember" />
    </Card>
  );
}

function DisclaimerSection() {
  const [lang, setLang] = useState('en');
  const en = 'Anchor AI provides information for educational purposes only and does not constitute legal advice. For binding guidance, consult a licensed legal practitioner. The platform routes complaints to your institution; it does not adjudicate disputes.';
  const bn = 'Anchor AI শুধুমাত্র তথ্যগত সহায়তা প্রদান করে এবং এটি কোনো আইনি পরামর্শ নয়। বাধ্যতামূলক নির্দেশনার জন্য, একজন লাইসেন্সধারী আইনজীবীর পরামর্শ নিন। এই প্ল্যাটফর্ম অভিযোগ আপনার প্রতিষ্ঠানে রাউট করে — এটি বিরোধ নিষ্পত্তি করে না।';
  return (
    <Card>
      <SectionLabel right={
        <div className="flex hair border rounded-sm overflow-hidden">
          <button onClick={()=>setLang('en')} className={`px-3 py-1 text-[12px] ${lang==='en'?'bg-[var(--ember)] text-white':'text-[var(--graphite)]'}`}>English</button>
          <button onClick={()=>setLang('bn')} className={`px-3 py-1 text-[12px] font-bn ${lang==='bn'?'bg-[var(--ember)] text-white':'text-[var(--graphite)]'}`}>বাংলা</button>
        </div>
      }>Legal disclaimer</SectionLabel>
      <p className="text-[12px] text-[var(--graphite)] mb-3">Shown to every user on first sign-in and inside the AI chat panel. Both language versions must be present before publication.</p>
      <textarea defaultValue={lang==='en'?en:bn} className={`w-full p-3 hair border rounded-sm bg-[var(--bg-input-tint)] text-[13px] min-h-[140px] ${lang==='bn'?'font-bn':''}`} />
      <SaveBar accent="ember" />
    </Card>
  );
}

function RetentionSection() {
  return (
    <Card>
      <SectionLabel>Data retention</SectionLabel>
      <AuditNote tone="navy" icon="database">Retention is set per data class. Deletion is irreversible and respects the audit-log append-only contract.</AuditNote>
      <div className="mt-4">
        <DataTable
          columns={[
            { key:'cls', label:'Data class' },
            { key:'cold', label:'Move to cold storage', align:'right' },
            { key:'purge', label:'Final purge', align:'right' },
          ]}
          rows={[
            { cls:'Resolved complaints', cold:<span className="font-mono">2y</span>, purge:<span className="font-mono">7y</span> },
            { cls:'Active alerts (after closure)', cold:<span className="font-mono">90d</span>, purge:<span className="font-mono">5y</span> },
            { cls:'Audit logs', cold:<span className="font-mono">3y</span>, purge:<MonoChip tone="navy">never</MonoChip> },
            { cls:'Evidence files', cold:<span className="font-mono">1y</span>, purge:<span className="font-mono">10y</span> },
            { cls:'Anonymous reports', cold:<span className="font-mono">2y</span>, purge:<span className="font-mono">7y</span> },
            { cls:'Notice archive', cold:<span className="font-mono">1y</span>, purge:<MonoChip tone="navy">never</MonoChip> },
          ]}
          dense
        />
      </div>
      <SaveBar accent="ember" />
    </Card>
  );
}

function PDPOSection() {
  return (
    <Card>
      <SectionLabel>Bangladesh PDP Ordinance 2025 · compliance</SectionLabel>
      <AuditNote tone="navy" icon="scale">These toggles map directly to specific sections of the Personal Data Protection Ordinance 2025. Disabling a control will fail the platform\u2019s automated compliance check.</AuditNote>
      <div className="mt-4">
        <SettingRow title="Right to access" hint="Users can request a copy of all personal data held about them within 30 days.">
          <Toggle on={true} onChange={()=>{}} />
        </SettingRow>
        <SettingRow title="Right to rectification" hint="Users can correct inaccurate personal data.">
          <Toggle on={true} onChange={()=>{}} />
        </SettingRow>
        <SettingRow title="Right to erasure" hint="Users can request deletion subject to legal hold exceptions.">
          <Toggle on={true} onChange={()=>{}} />
        </SettingRow>
        <SettingRow title="Data localization" hint="All personal data stored within Bangladesh borders.">
          <Toggle on={true} onChange={()=>{}} />
        </SettingRow>
        <SettingRow title="Cross-border transfer review" hint="Any data egress to foreign processors requires DPO sign-off.">
          <Toggle on={true} onChange={()=>{}} />
        </SettingRow>
        <SettingRow title="Breach notification window" hint="Automatic notification to Data Protection Authority on detected breach.">
          <select className="px-2 py-1.5 hair border rounded-sm bg-white text-[12.5px]"><option>72 hours (Ordinance default)</option><option>48 hours</option><option>24 hours</option></select>
        </SettingRow>
      </div>
      <div className="mt-4 hair border rounded-sm p-3 flex items-center gap-3" style={{ background:'var(--sage-tint)' }}>
        <Icon name="shield-check" size={16} style={{ color:'var(--sage)' }} />
        <div className="flex-1 text-[12.5px]" style={{ color:'var(--sage)' }}>
          <span className="font-medium">All compliance checks pass.</span> Last automated scan: 2026-05-24 02:00 BDT.
        </div>
        <GhostButton size="sm" icon="download">Compliance report</GhostButton>
      </div>
    </Card>
  );
}

Object.assign(window, { SettingsScreen });
