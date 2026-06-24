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
    '/university/routine':['Routine editor'],
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
    '/super/verify-lawyers':['Operations','Verify lawyers'],
    '/super/officer-scorecards':['Operations','Officer scorecards'],
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
    case '/university/applications': return <UniApplications onGo={onGo} />;
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
    case '/university/analytics': return <UniAnalytics onGo={onGo} />;
    case '/university/users': return <UniUsers onGo={onGo} />;
    case '/university/settings': return <SettingsScreen mode="uni" dark={dark} setDark={setDark} onGo={onGo} />;
    case '/university/profile': return <ProfileScreen mode="uni" onGo={onGo} />;
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
    case '/super/verify-lawyers': return <SuperVerifyLawyers />;
    case '/super/officer-scorecards': return <SuperOfficerScorecards />;
    case '/super/dms': return <StubScreen title="Dead Man\u2019s Switch" description="Active DMS cases per tenant, recent triggers, service health. Super Admin cannot read encrypted content." icon="lock-keyhole"
      items={['Active cases · 24','Triggered · 30d · 0','Recipient verification · 18','Service health · OK']} />;
    case '/super/encryption': return <SuperEncryption />;
    case '/super/analytics': return <SuperAnalytics />;
    case '/super/incidents': return <SuperIncidents />;
    case '/super/policy': return <SuperPolicy />;
    case '/super/legal-corpus': return <SuperLegalCorpus />;
    case '/super/team': return <StubScreen title="Team members" description="Super admin accounts, role assignments, MFA enforcement, access levels." icon="users"
      items={['Members · 6','MFA enforced · 6/6','Recent activity']} />;
    case '/super/profile': return <ProfileScreen mode="sup" onGo={onGo} />;
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
        <div style={{ minHeight: '100vh', background: 'var(--cream)', color: 'var(--ink)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 14, padding: 40, fontFamily: "'Inter Tight', system-ui, sans-serif", textAlign: 'center' }}>
          <div style={{ fontFamily: "'Fraunces', Georgia, serif", fontWeight: 600, fontSize: 30, color: 'var(--navy)' }}>Anchor<span style={{ color: 'var(--ember)' }}>.</span></div>
          <h1 style={{ fontFamily: "'Fraunces', Georgia, serif", fontWeight: 600, fontSize: 22, color: 'var(--navy)', margin: 0 }}>Something went wrong</h1>
          <p style={{ fontSize: 13.5, color: 'var(--muted)', margin: 0, maxWidth: 460, lineHeight: 1.5 }}>The admin panel hit an unexpected error. Reloading usually fixes it.</p>
          <button type="button" onClick={() => window.location.reload()} style={{ appearance: 'none', border: 0, cursor: 'pointer', background: 'var(--navy)', color: '#fff', fontFamily: "'Inter Tight', system-ui, sans-serif", fontSize: 13, fontWeight: 600, padding: '10px 22px', borderRadius: 8 }}>Reload</button>
          <details style={{ marginTop: 6, maxWidth: 520, width: '100%', textAlign: 'left' }}>
            <summary style={{ fontSize: 12, color: 'var(--graphite)', cursor: 'pointer' }}>Technical details</summary>
            <pre style={{ marginTop: 8, fontFamily: "'JetBrains Mono', ui-monospace, monospace", fontSize: 11.5, color: 'var(--ember)', background: 'var(--paper)', border: '1px solid var(--mist)', borderRadius: 8, padding: 12, whiteSpace: 'pre-wrap', wordBreak: 'break-word', maxHeight: 200, overflow: 'auto' }}>{String(this.state.error)}</pre>
          </details>
        </div>
      );
    }
    return this.props.children;
  }
}

// Mount
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<ErrorBoundary><App /></ErrorBoundary>);
