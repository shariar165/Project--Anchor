// Router and app root
var { useState, useEffect, useCallback, useRef, useMemo } = React;
function useHashRoute() {
  const [hash, setHash] = useState(() => window.location.hash.slice(1) || '/');
  useEffect(() => {
    const onHash = () => setHash(window.location.hash.slice(1) || '/');
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);
  const go = useCallback((route) => {
    window.location.hash = route;
    window.scrollTo(0, 0);
  }, []);
  return [hash, go];
}

const TWEAK_DEFAULS = /*EDITMODE-BEGIN*/{
  "palette": "civic",
  "voice": "serif",
  "surface": "paper"
}/*EDITMODE-END*/;

function App() {
  const [route, onGo] = useHashRoute();
  const [role, setRole] = useState('Department Head');
  const [dark, setDark] = useDark();
  const [t, setTweak] = useTweaks(TWEAK_DEFAULS);
  const [auth, setAuth] = useState(() => AnchorAPI.getStoredUser());

  const onLogin = useCallback((user) => setAuth(user), []);
  const onLogout = useCallback(() => {
    AnchorAPI.clearAuth();
    setAuth(null);
    window.location.hash = '/';
  }, []);

  // Apply tweak choices as data-attributes on <html> so global CSS rules respond.
  useEffect(() => { document.documentElement.setAttribute('data-palette', t.palette); }, [t.palette]);
  useEffect(() => { document.documentElement.setAttribute('data-voice', t.voice); }, [t.voice]);
  useEffect(() => { document.documentElement.setAttribute('data-surface', t.surface); }, [t.surface]);

  const tweaksUI = (
    <TweaksPanel>
      <TweakSection label="Palette" />
      <TweakRadio label="Story" value={t.palette}
        options={['civic','court','field','ops']}
        onChange={v => setTweak('palette', v)} />

      <TweakSection label="Voice" />
      <TweakRadio label="Heading type" value={t.voice}
        options={['serif','sans','mono']}
        onChange={v => setTweak('voice', v)} />

      <TweakSection label="Surface" />
      <TweakRadio label="Material" value={t.surface}
        options={['paper','slate','canvas']}
        onChange={v => setTweak('surface', v)} />
    </TweaksPanel>
  );

  // Route to view
  let view;
  if (route === '/' || route === '') view = <EntrySwitcher onGo={onGo} dark={dark} setDark={setDark} />;
  else if (route === '/university/login') view = <LoginScreen mode="uni" onGo={onGo} onLogin={onLogin} />;
  else if (route === '/super/login') view = <LoginScreen mode="sup" onGo={onGo} onLogin={onLogin} />;
  else if (route.startsWith('/university')) {
    if (!auth) {
      view = <LoginScreen mode="uni" onGo={onGo} onLogin={onLogin} />;
    } else {
      view = (
        <AdminShell mode="uni" route={route} onGo={onGo} role={role} setRole={setRole} dark={dark} setDark={setDark} breadcrumbs={uniCrumbs(route)} auth={auth} onLogout={onLogout}>
          {uniView(route, onGo, role, dark, setDark)}
        </AdminShell>
      );
    }
  } else if (route.startsWith('/super')) {
    if (!auth) {
      view = <LoginScreen mode="sup" onGo={onGo} onLogin={onLogin} />;
    } else {
      view = (
        <AdminShell mode="sup" route={route} onGo={onGo} role={role} setRole={setRole} dark={dark} setDark={setDark} breadcrumbs={supCrumbs(route)} auth={auth} onLogout={onLogout}>
          {supView(route, onGo, dark, setDark)}
        </AdminShell>
      );
    }
  } else {
    view = <EntrySwitcher onGo={onGo} dark={dark} setDark={setDark} />;
  }
  return <>{view}{tweaksUI}</>;
}

function uniCrumbs(route) {
  const map = {
    '/university/dashboard':['Dashboard'],
    '/university/complaints':['Complaints'],
    '/university/grievances/teachers':['Grievances','Teacher'],
    '/university/grievances/departments':['Grievances','Department'],
    '/university/classrooms':['Classroom reports'],
    '/university/hostel':['Hostel'],
    '/university/alerts':['Campus geofence'],
    '/university/geofence':['Campus geofence'],
    '/university/routine':['Routine builder'],
    '/university/timetable':['Timetable generator'],
    '/university/notices':['Notices'],
    '/university/verification-feed':['Verification feed'],
    '/university/analytics':['Analytics'],
    '/university/users':['Users'],
    '/university/settings':['Settings'],
    '/university/profile':['Profile'],
  };
  return map[route] || ['—'];
}

function supCrumbs(route) {
  const map = {
    '/super/dashboard':['Dashboard'],
    '/super/tenants':['Tenants','Universities'],
    '/super/onboard':['Tenants','Onboard'],
    '/super/audit-logs':['Operations','Audit logs'],
    '/super/alerts':['Operations','Campus alerts'],
    '/super/red-zones':['Operations','Red zone map'],
    '/super/moderation':['Operations','Content moderation'],
    '/super/deanonymization':['Operations','De-anonymization'],
    '/super/verification-feed':['Operations','Verification feed'],
    '/super/users':['Operations','Users'],
    '/super/dms':['Operations','Dead man\u2019s switch'],
    '/super/ai-health':['System','AI engine health'],
    '/super/encryption':['System','Encryption & keys'],
    '/super/analytics':['System','Analytics'],
    '/super/incidents':['System','Incidents'],
    '/super/policy':['Configuration','Policy'],
    '/super/legal-corpus':['Configuration','Legal corpus'],
    '/super/team':['Team','Members'],
    '/super/settings':['Team','Settings'],
    '/super/profile':['Team','Profile'],
  };
  if (route.startsWith('/super/tenant/')) return ['Tenants', 'Detail'];
  return map[route] || ['—'];
}

function uniView(route, onGo, role, dark, setDark) {
  switch (route) {
    case '/university/dashboard': return <UniDashboard role={role} onGo={onGo} />;
    case '/university/complaints': return <UniComplaints onGo={onGo} />;
    case '/university/routine': return <UniRoutine onGo={onGo} />;
    case '/university/timetable': return <UniTimetable onGo={onGo} />;
    case '/university/notices': return <UniNotices onGo={onGo} />;
    case '/university/geofence': return <UniGeofence onGo={onGo} />;
    case '/university/alerts': return <UniGeofence onGo={onGo} />;
    case '/university/classrooms': return <UniClassrooms onGo={onGo} />;
    case '/university/grievances/teachers': return <UniTeacherGrievances />;
    case '/university/grievances/departments': return <UniDeptGrievances />;
    case '/university/hostel': return <UniHostel />;
    case '/university/verification-feed': return <UniVerificationFeed />;
    case '/university/analytics': return <StubScreen title="Department analytics" description="Aggregate, anonymized analytics for your department." icon="bar-chart-3"
      items={['Complaint trends','Resolution rate','Escalation rate','Avg response time','Day × hour heatmap']} />;
    case '/university/users': return <StubScreen title="Users" description="Students, teachers, and admin staff in your tenant. CSV import, role assignment, deactivation." icon="users"
      items={['Students · 8,421','Teachers · 142','Admin staff · 14','Pending verification · 42']} />;
    case '/university/settings': return <SettingsScreen mode="uni" dark={dark} setDark={setDark} onGo={onGo} />;
    case '/university/profile': return <StubScreen title="My profile" description="Account, role, permissions, and MFA." icon="circle-user"
      items={['Personal info','Role & permissions','MFA settings','Recent activity']} />;
    default: return <StubScreen title="Not found" description="The page you\u2019re looking for isn\u2019t in this demo build yet." />;
  }
}

function supView(route, onGo, dark, setDark) {
  if (route.startsWith('/super/tenant/')) {
    const id = route.split('/').pop();
    return <SuperTenantDetail id={id} onGo={onGo} />;
  }
  switch (route) {
    case '/super/dashboard': return <SuperDashboard onGo={onGo} />;
    case '/super/tenants': return <SuperTenants onGo={onGo} />;
    case '/super/onboard': return <SuperOnboard onGo={onGo} />;
    case '/super/audit-logs': return <SuperAuditLogs />;
    case '/super/alerts': return <SuperAlerts onGo={onGo} />;
    case '/super/red-zones': return <SuperRedZones onGo={onGo} />;
    case '/super/moderation': return <SuperModeration />;
    case '/super/deanonymization': return <SuperDeanonymization />;
    case '/super/verification-feed': return <SuperVerificationFeed />;
    case '/super/ai-health': return <SuperAIHealth />;
    case '/super/users': return <SuperUsers />;
    case '/super/dms': return <StubScreen title="Dead Man\u2019s Switch" description="Active DMS cases per tenant, recent triggers, service health. Super Admin cannot read encrypted content." icon="lock-keyhole"
      items={['Active cases · 24','Triggered · 30d · 0','Recipient verification · 18','Service health · OK']} />;
    case '/super/encryption': return <StubScreen title="Encryption & keys" description="Master key rotation, session/chat keys count, KMS health, certificate expiry." icon="key-round"
      items={['Master key · rotated 14d ago','Active session keys · 12,847','KMS health · OK','Certificates · 3 expiring in 90d']} />;
    case '/super/analytics': return <StubScreen title="Platform-wide analytics" description="Cross-tenant aggregate dashboards. All anonymized." icon="bar-chart-3"
      items={['Complaints per week (stacked)','Resolution rates by tenant','Alert frequency heatmap (national)','Most cited laws (RAG)','Lawyer engagement','Verification feed activity']} />;
    case '/super/incidents': return <StubScreen title="Incidents" description="Ongoing technical, security and content incidents. Playbooks and post-mortems." icon="flame"
      items={['Active incidents · 1','Playbooks · 14','Post-mortems · 22']} />;
    case '/super/policy': return <StubScreen title="Policy & configuration" description="Platform-wide settings: escalation timers, rate limits, trust thresholds, ban durations." icon="scale"
      items={['Escalation timers','Rate limits','Trust thresholds (5 / 10 / 15)','Ban durations','AI confidence thresholds','Legal disclaimer (Bangla + English)','Bangladesh PDP Ordinance 2025']} />;
    case '/super/legal-corpus': return <StubScreen title="Legal corpus · RAG" description="Manage the legal corpus that feeds ChromaDB across tenant namespaces." icon="book-open"
      items={['Constitution','Laws & Acts','Court judgments','FIR / GD templates','University policies (per tenant)','Indexing jobs']} />;
    case '/super/team': return <StubScreen title="Team members" description="Super admin accounts, role assignments, MFA enforcement, access levels." icon="users"
      items={['Members · 6','MFA enforced · 6/6','Recent activity']} />;
    case '/super/profile': return <StubScreen title="My profile" description="Super admin account and security settings." icon="circle-user" />;
    case '/super/settings': return <SettingsScreen mode="sup" dark={dark} setDark={setDark} onGo={onGo} />;
    default: return <StubScreen title="Not found" description="The page you\u2019re looking for isn\u2019t in this demo build yet." />;
  }
}

class ErrorBoundary extends React.Component {
  constructor(props) { super(props); this.state = { error: null }; }
  static getDerivedStateFromError(error) { return { error }; }
  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 40, fontFamily: 'monospace', color: '#E8312A', background: '#F7F3EE', minHeight: '100vh' }}>
          <strong style={{ fontSize: 16 }}>Admin panel render error</strong>
          <pre style={{ marginTop: 12, fontSize: 13, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{String(this.state.error)}</pre>
          <p style={{ marginTop: 8, fontSize: 12, color: '#6B7785' }}>Open browser DevTools → Console for the full stack trace.</p>
        </div>
      );
    }
    return this.props.children;
  }
}

// Mount
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<ErrorBoundary><App /></ErrorBoundary>);
