// AdminShell — sidebar + topbar layout
var { useState, useEffect, useCallback, useRef, useMemo } = React;
const ROLES = ['Department Head', 'Dean', 'Proctor', 'Provost', 'VC Office', 'IT Admin'];
const ROLE_SUBTITLE = {
  'Department Head':'SWE',
  'Dean':'Faculty of Science & IT',
  'Proctor':'Campus Safety',
  'Provost':'Hostel & Residence',
  'VC Office':'Vice-Chancellor',
  'IT Admin':'IT Operations',
};

function NavItem({ icon, label, route, active, onGo, mode='uni', badge, dot=false, collapsed }) {
  const cls = active ? (mode==='uni' ? 'nav-active-uni' : 'nav-active-sup') : 'text-[var(--graphite)] hover:bg-[var(--mist)]/40';
  return (
    <button onClick={() => onGo(route)} className={`group w-full flex items-center gap-3 px-3 py-2 rounded-sm text-[13px] transition ${cls}`}>
      <span className="relative shrink-0">
        <Icon name={icon} size={16} />
        {dot && <span className="absolute -top-0.5 -right-0.5 w-1.5 h-1.5 rounded-full pulse-dot" style={{ background:'var(--red)' }} />}
      </span>
      {!collapsed && <span className="flex-1 text-left whitespace-nowrap">{label}</span>}
      {!collapsed && badge && <span className="font-mono text-[10px] px-1.5 py-0.5 rounded-sm" style={{ background: mode==='uni'?'var(--sage)':'var(--ember)', color:'white' }}>{badge}</span>}
    </button>
  );
}

function NavGroup({ title, children, collapsed }) {
  return (
    <div className="mb-4">
      {!collapsed && <div className="smallcaps text-[var(--muted)] px-3 pb-2 pt-2">{title}</div>}
      <div className="flex flex-col gap-0.5 px-2">{children}</div>
    </div>
  );
}

// Top-level shell. Provides sidebar + topbar + main content slot.
function AdminShell({ mode='uni', route, onGo, role, setRole, dark, setDark, children, breadcrumbs=[], pageWidth='max-w-[1180px]', auth, onLogout }) {
  const [collapsed, setCollapsed] = useState(false);
  const [roleOpen, setRoleOpen] = useState(false);
  const [userOpen, setUserOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);

  const sidebarW = collapsed ? 64 : 240;

  // Keyboard cmd+k
  useEffect(() => {
    const fn = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault(); setSearchOpen(true);
      }
      if (e.key === 'Escape') { setSearchOpen(false); setRoleOpen(false); setUserOpen(false); }
    };
    window.addEventListener('keydown', fn);
    return () => window.removeEventListener('keydown', fn);
  }, []);

  // Close menus on outside click
  useEffect(() => {
    const fn = () => { setRoleOpen(false); setUserOpen(false); };
    window.addEventListener('click', fn);
    return () => window.removeEventListener('click', fn);
  }, []);

  const accent = mode==='uni' ? 'var(--sage)' : 'var(--ember)';

  // Sidebar config per mode
  const uniNav = [
    { group:'Home', items:[
      { icon:'layout-dashboard', label:'Dashboard', route:'/university/dashboard' },
    ]},
    { group:'Casework', items:[
      { icon:'message-square-warning', label:'Complaints', route:'/university/complaints', badge:'7' },
      { icon:'user-square', label:'Teacher Grievances', route:'/university/grievances/teachers' },
      { icon:'building-2', label:'Department Grievances', route:'/university/grievances/departments' },
      { icon:'door-open', label:'Classroom Reports', route:'/university/classrooms' },
      { icon:'bed', label:'Hostel', route:'/university/hostel' },
      { icon:'map', label:'Campus Geofence', route:'/university/geofence' },
    ]},
    { group:'Academic', items:[
      { icon:'calendar-clock', label:'Routine Builder', route:'/university/routine' },
      { icon:'layout-grid', label:'Timetable Generator', route:'/university/timetable' },
      { icon:'megaphone', label:'Notices', route:'/university/notices' },
    ]},
    { group:'Insights', items:[
      { icon:'newspaper', label:'Verification Feed', route:'/university/verification-feed' },
      { icon:'bar-chart-3', label:'Analytics', route:'/university/analytics' },
    ]},
    { group:'Administration', items:[
      { icon:'users', label:'Users', route:'/university/users' },
      { icon:'settings', label:'Settings', route:'/university/settings' },
      { icon:'circle-user', label:'Profile', route:'/university/profile' },
    ]},
  ];

  const supNav = [
    { group:'Overview', items:[
      { icon:'layout-dashboard', label:'Dashboard', route:'/super/dashboard' },
    ]},
    { group:'Tenants', items:[
      { icon:'graduation-cap', label:'Universities', route:'/super/tenants' },
      { icon:'plus-circle', label:'Onboard New', route:'/super/onboard' },
    ]},
    { group:'Operations', items:[
      { icon:'siren', label:'Alerts', route:'/super/alerts', dot:true },
      { icon:'map-pin', label:'Red Zone Map', route:'/super/red-zones' },
      { icon:'scroll-text', label:'Audit Logs', route:'/super/audit-logs' },
      { icon:'shield-alert', label:'De-anonymization', route:'/super/deanonymization', badge:'3' },
      { icon:'shield-x', label:'Content Moderation', route:'/super/moderation', badge:'12' },
      { icon:'newspaper', label:'Verification Feed', route:'/super/verification-feed' },
      { icon:'users-round', label:'Users', route:'/super/users' },
      { icon:'lock-keyhole', label:'Dead Man\u2019s Switch', route:'/super/dms' },
    ]},
    { group:'System', items:[
      { icon:'cpu', label:'AI Engine Health', route:'/super/ai-health' },
      { icon:'key-round', label:'Encryption & Keys', route:'/super/encryption' },
      { icon:'bar-chart-3', label:'Analytics', route:'/super/analytics' },
      { icon:'flame', label:'Incidents', route:'/super/incidents' },
    ]},
    { group:'Configuration', items:[
      { icon:'scale', label:'Policy', route:'/super/policy' },
      { icon:'book-open', label:'Legal Corpus', route:'/super/legal-corpus' },
    ]},
    { group:'Team', items:[
      { icon:'users', label:'Team Members', route:'/super/team' },
      { icon:'settings', label:'Settings', route:'/super/settings' },
      { icon:'circle-user', label:'Profile', route:'/super/profile' },
    ]},
  ];

  const nav = mode==='uni' ? uniNav : supNav;

  return (
    <div className="min-h-screen flex" style={{ background:'var(--cream)' }}>
      {/* Sidebar */}
      <aside className="hair-r border-r bg-[var(--paper)] sticky top-0 h-screen flex flex-col" style={{ width: sidebarW, transition:'width 180ms ease' }}>
        {/* Brand */}
        <div className="px-3 pt-4 pb-3 hair-b">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-sm flex items-center justify-center shrink-0 relative" style={{ background:'var(--navy)' }}>
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="white" strokeWidth="1.8">
                <path d="M12 3v18M12 7l-5 5M12 7l5 5M5 17h14" />
              </svg>
            </div>
            {!collapsed && (
              <div className="leading-tight">
                <div className="font-serif text-[16px] text-[var(--navy)]" style={{fontWeight:500}}>Anchor AI</div>
                <div className="smallcaps text-[var(--muted)]" style={{fontSize:'9.5px'}}>{mode==='uni'?'Administration':'Platform Ops'}</div>
              </div>
            )}
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto py-3 scrollbar-thin">
          {nav.map((grp, i) => (
            <NavGroup key={i} title={grp.group} collapsed={collapsed}>
              {grp.items.map(it => (
                <NavItem key={it.route} {...it} mode={mode} active={route===it.route} onGo={onGo} collapsed={collapsed} />
              ))}
            </NavGroup>
          ))}
        </nav>

        {/* Collapse toggle + back to entry */}
        <div className="hair-t border-t p-2 flex flex-col gap-1">
          <button onClick={()=>setCollapsed(c=>!c)} className="flex items-center gap-2 px-3 py-1.5 rounded-sm text-[12px] text-[var(--muted)] hover:bg-[var(--mist)]/40">
            <Icon name={collapsed?'chevrons-right':'chevrons-left'} size={14} />
            {!collapsed && <span>Collapse</span>}
          </button>
          <button onClick={()=>onLogout ? onLogout() : onGo('/')} className="flex items-center gap-2 px-3 py-1.5 rounded-sm text-[12px] text-[var(--muted)] hover:bg-[var(--mist)]/40">
            <Icon name="log-out" size={14} />
            {!collapsed && <span>Sign out</span>}
          </button>
        </div>
      </aside>

      {/* Main column */}
      <div className="flex-1 min-w-0 flex flex-col">
        {/* Top bar */}
        <header className="sticky top-0 z-20 bg-[var(--paper)] hair-b border-b">
          <div className="flex items-center gap-4 px-6 h-14">
            {/* Breadcrumbs */}
            <div className="flex items-center gap-1.5 text-[13px] text-[var(--muted)] min-w-0">
              <span className="smallcaps" style={{ color: accent }}>{mode==='uni'?'University Admin':'Super Admin'}</span>
              {breadcrumbs.map((b, i) => (
                <React.Fragment key={i}>
                  <span className="text-[var(--mist)]">/</span>
                  <span className={i===breadcrumbs.length-1?'text-[var(--ink)] font-medium':''}>{b}</span>
                </React.Fragment>
              ))}
            </div>

            <div className="flex-1" />

            {/* Search */}
            <button onClick={()=>setSearchOpen(true)} className="hidden md:inline-flex items-center gap-2 px-3 py-1.5 rounded-sm hair border bg-white text-[12px] text-[var(--muted)] hover:bg-[var(--mist)]/40 min-w-[260px]">
              <Icon name="search" size={14} />
              <span>Search complaints, users, audit logs…</span>
              <span className="ml-auto font-mono text-[10px] px-1 py-0.5 rounded-sm bg-[var(--mist)]/70 text-[var(--graphite)]">⌘K</span>
            </button>

            {/* Notifications */}
            <button className="relative w-9 h-9 rounded-sm hover:bg-[var(--mist)]/40 flex items-center justify-center">
              <Icon name="bell" size={16} />
              <span className="absolute top-1.5 right-1.5 w-1.5 h-1.5 rounded-full" style={{ background:'var(--red)' }} />
            </button>

            {/* Dark mode toggle */}
            <button onClick={()=>setDark(d=>!d)} title={dark?'Switch to light mode':'Switch to dark mode'}
              className="w-9 h-9 rounded-sm hover:bg-[var(--mist)]/40 flex items-center justify-center">
              <Icon name={dark?'sun':'moon'} size={16} />
            </button>

            {/* Role pill (university only) */}
            {mode==='uni' && (
              <div className="relative" onClick={e=>e.stopPropagation()}>
                <button onClick={()=>setRoleOpen(o=>!o)} className="inline-flex items-center gap-2 px-3 py-1.5 rounded-sm hair border bg-white whitespace-nowrap">
                  <span className="smallcaps text-[var(--muted)]">Viewing as</span>
                  <span className="text-[13px] font-medium text-[var(--ink)]">{role}</span>
                  <span className="text-[12px] text-[var(--muted)] hidden xl:inline">· {ROLE_SUBTITLE[role]}</span>
                  <Icon name="chevron-down" size={14} />
                </button>
                {roleOpen && (
                  <div className="absolute top-full mt-1 right-0 w-[280px] bg-[var(--paper)] hair border rounded-sm shadow-lg fade-in z-30">
                    <div className="px-3 py-2 hair-b smallcaps text-[var(--muted)]">Switch role · demo</div>
                    {ROLES.map(r => (
                      <button key={r} onClick={()=>{ setRole(r); setRoleOpen(false); }} className={`w-full flex items-center justify-between px-3 py-2 text-[13px] hover:bg-[var(--mist)]/40 ${r===role?'bg-[var(--sage-tint)]/60':''}`}>
                        <div className="text-left">
                          <div className="font-medium text-[var(--ink)]">{r}</div>
                          <div className="text-[11px] text-[var(--muted)]">{ROLE_SUBTITLE[r]}</div>
                        </div>
                        {r===role && <Icon name="check" size={14} style={{ color: 'var(--sage)' }} />}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {mode==='sup' && (
              <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-sm hair border bg-white">
                <span className="w-1.5 h-1.5 rounded-full" style={{ background:'var(--ember)' }} />
                <span className="smallcaps text-[var(--muted)]">Super Admin · AiVion</span>
              </span>
            )}

            {/* User avatar */}
            <div className="relative" onClick={e=>e.stopPropagation()}>
              <button onClick={()=>setUserOpen(o=>!o)} className="flex items-center gap-2 pl-1 pr-2 py-1 rounded-sm hover:bg-[var(--mist)]/40">
                <span className="w-7 h-7 rounded-full flex items-center justify-center text-white text-[11px] font-medium" style={{ background:'var(--navy)' }}>
                  {auth?.full_name ? auth.full_name.split(' ').map(w=>w[0]).join('').slice(0,2).toUpperCase() : (mode==='uni' ? 'TK' : 'AZ')}
                </span>
                <Icon name="chevron-down" size={12} />
              </button>
              {userOpen && (
                <div className="absolute top-full mt-1 right-0 w-[220px] bg-[var(--paper)] hair border rounded-sm shadow-lg fade-in z-30">
                  <div className="p-3 hair-b">
                    <div className="text-[13px] font-medium">{auth?.full_name || (mode==='uni'?'Dr. Tahmina Karim':'Asif Zaman')}</div>
                    <div className="text-[11px] text-[var(--muted)]">{auth?.email || (mode==='uni'?'tahmina@diu.edu.bd':'asif@aivion.team')}</div>
                  </div>
                  <button className="w-full text-left px-3 py-2 text-[13px] hover:bg-[var(--mist)]/40">Profile</button>
                  <button className="w-full text-left px-3 py-2 text-[13px] hover:bg-[var(--mist)]/40">Security & MFA</button>
                  <button onClick={()=>onLogout ? onLogout() : onGo('/')} className="w-full text-left px-3 py-2 text-[13px] hair-t hover:bg-[var(--mist)]/40 text-[var(--red)]">Sign out</button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 min-w-0 overflow-x-hidden">
          <div className={`mx-auto ${pageWidth} px-6 py-7`}>
            {children}
          </div>
          <footer className="px-6 pb-6 pt-2 text-[11px] text-[var(--muted)] flex items-center justify-between max-w-[1180px] mx-auto">
            <span>Anchor AI · {mode==='uni'?'University Administration Portal':'Platform Operations Console'}</span>
            <span>Authorized personnel only · All actions are audit-logged</span>
          </footer>
        </main>
      </div>

      {/* Command palette overlay */}
      {searchOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center pt-[18vh] fade-in" style={{ background:'rgba(11,29,53,0.35)' }} onClick={()=>setSearchOpen(false)}>
          <div className="bg-[var(--paper)] w-[560px] max-w-[92vw] rounded-sm hair border shadow-xl" onClick={e=>e.stopPropagation()}>
            <div className="flex items-center gap-2 px-4 py-3 hair-b">
              <Icon name="search" size={16} />
              <input autoFocus placeholder="Search complaints, users, audit logs…" className="flex-1 bg-transparent outline-none text-[14px]" />
              <span className="font-mono text-[10px] px-1.5 py-0.5 rounded-sm bg-[var(--mist)]/70 text-[var(--graphite)]">esc</span>
            </div>
            <div className="p-2">
              {[
                { icon:'message-square-warning', label:'CMP-2026-A4F2 · AC unit broken in Room 504', kbd:'open' },
                { icon:'siren', label:'ALR-2026-7C12 · Active alert · Knowledge Tower', kbd:'open' },
                { icon:'user-square', label:'Dr. Mahbub Alam · Department of SWE', kbd:'go' },
                { icon:'scroll-text', label:'Audit log: COMPLAINT_ESCALATED · 2026-05-24', kbd:'view' },
              ].map((r,i) => (
                <button key={i} className="w-full flex items-center gap-3 px-3 py-2 rounded-sm hover:bg-[var(--mist)]/40 text-left">
                  <Icon name={r.icon} size={14} />
                  <span className="flex-1 text-[13px] truncate">{r.label}</span>
                  <span className="font-mono text-[10px] text-[var(--muted)]">{r.kbd}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

Object.assign(window, { AdminShell, ROLES, ROLE_SUBTITLE });
