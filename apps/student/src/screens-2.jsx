// Anchor — Screens part 2: Cases, CaseDetail, Map, Feed, Lawyers, Notices, Profile

// ═══════════════════════════════════════════════════════════════
//  NOTIFICATIONS / SETTINGS — frontend-only, persisted to localStorage
//  (no backend exists for these; mirrors the anchor_geofence_consent pattern)
// ═══════════════════════════════════════════════════════════════

const _API = window.ANCHOR_API_URL || 'http://localhost:8000';

var NOTIF_PREF_DEFAULTS = { alerts: true, cases: true, notices: true, feed: true, marketing: false };

function loadNotifPrefs() {
  try {
    var raw = JSON.parse(localStorage.getItem('anchor_notif_prefs'));
    if (raw && typeof raw === 'object') return Object.assign({}, NOTIF_PREF_DEFAULTS, raw);
  } catch (e) { /* corrupt / unavailable */ }
  return Object.assign({}, NOTIF_PREF_DEFAULTS);
}
function saveNotifPrefs(p) {
  try { localStorage.setItem('anchor_notif_prefs', JSON.stringify(p)); } catch (e) { /* ignore */ }
}
function notifPrefsOnCount() {
  var p = loadNotifPrefs();
  return Object.keys(NOTIF_PREF_DEFAULTS).filter(function (k) { return !!p[k]; }).length;
}

function loadTrustedContacts() {
  try {
    var raw = JSON.parse(localStorage.getItem('anchor_trusted_contacts'));
    if (Array.isArray(raw)) return raw;
  } catch (e) { /* ignore */ }
  return [];
}
function saveTrustedContacts(list) {
  try { localStorage.setItem('anchor_trusted_contacts', JSON.stringify(list)); } catch (e) { /* ignore */ }
}

// ── Notification feed ─────────────────────────────────────────────────────────
function _notifKey(mode) { return mode === 'country' ? 'anchor_notif_country' : 'anchor_notif_campus'; }

function _notifSeed(mode) {
  var now = Date.now(), H = 3600 * 1000, D = 24 * H;
  if (mode === 'country') {
    return [
      { id: 'n1', type: 'lawyer', title: 'Adv. Rahman replied', body: 'Your consultation request on the tenancy dispute has a response.', ts: new Date(now - 2 * H).toISOString(), read: false, route: 'lawyers' },
      { id: 'n2', type: 'zone', title: 'Caution zone updated near you', body: 'A new red zone was added around Mirpur-10. Tap to view the safety map.', ts: new Date(now - 6 * H).toISOString(), read: false, route: 'map' },
      { id: 'n3', type: 'case', title: 'GD draft ready', body: 'Your General Diary draft has been prepared and is ready to review.', ts: new Date(now - 2 * D).toISOString(), read: true, route: 'cases' },
      { id: 'n4', type: 'notice', title: 'New legal-rights explainer', body: 'Know your rights during a police stop — a new guide is available.', ts: new Date(now - 3 * D).toISOString(), read: true, route: 'rights' },
    ];
  }
  return [
    { id: 'n1', type: 'alert', title: 'Safety alert near KT building', body: 'A nearby user triggered an emergency alert ~120m away. Stay aware.', ts: new Date(now - 1 * H).toISOString(), read: false, route: 'alert' },
    { id: 'n2', type: 'case', title: 'Case ANCHOR-2291 routed', body: "Your complaint was forwarded to the Proctor's office for review.", ts: new Date(now - 5 * H).toISOString(), read: false, route: 'cases' },
    { id: 'n3', type: 'notice', title: 'New campus notice', body: 'Mid-term routine published. Check the academic notices section.', ts: new Date(now - 26 * H).toISOString(), read: true, route: 'notices' },
    { id: 'n4', type: 'rating', title: 'Department rating posted', body: 'Your feedback on the SWE department was recorded. Thank you.', ts: new Date(now - 3 * D).toISOString(), read: true, route: 'dept-rating' },
  ];
}

function loadNotifications(mode) {
  var m = mode === 'country' ? 'country' : 'campus';
  var key = _notifKey(m);
  var list = null;
  try { list = JSON.parse(localStorage.getItem(key)); } catch (e) { list = null; }
  if (!Array.isArray(list)) {
    list = _notifSeed(m);
    saveNotifications(list, m);
  }
  return list;
}
function saveNotifications(list, mode) {
  try { localStorage.setItem(_notifKey(mode === 'country' ? 'country' : 'campus'), JSON.stringify(list)); } catch (e) { /* ignore */ }
}
function unreadCount(mode) {
  try {
    return loadNotifications(mode).filter(function (n) { return !n.read; }).length;
  } catch (e) { return 0; }
}
function markAllNotificationsRead(mode) {
  var list = loadNotifications(mode).map(function (n) { return Object.assign({}, n, { read: true }); });
  saveNotifications(list, mode);
  return list;
}
function notifRelTime(ts) {
  var d = new Date(ts).getTime();
  if (isNaN(d)) return '';
  var mins = Math.floor((Date.now() - d) / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return mins + 'm ago';
  var hrs = Math.floor(mins / 60);
  if (hrs < 24) return hrs + 'h ago';
  var days = Math.floor(hrs / 24);
  if (days < 7) return days + 'd ago';
  return new Date(ts).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
}
function notifIsToday(ts) {
  var d = new Date(ts), n = new Date();
  return d.getFullYear() === n.getFullYear() && d.getMonth() === n.getMonth() && d.getDate() === n.getDate();
}

// ── Helper: map a real Filing to the CaseCard display format ──────────────────

function mapFilingToCase(f) {
  const stateMap = {
    draft: 'submitted',
    moderation_queue: 'review',
    routed: 'review',
    subject_notified: 'review',
    subject_responded: 'review',
    under_review: 'review',
    resolved: 'resolved',
    dismissed: 'resolved',
    withdrawn: 'resolved',
    spam_rejected: 'resolved',
  };
  const routingMap = {
    dept_head: 'Department Head',
    dean: "Dean's Office",
    proctor: 'Proctor',
    provost: 'Provost',
    vc: 'Vice Chancellor',
  };
  const routing = f.template?.routing_target
    ? routingMap[f.template.routing_target] || f.template.routing_target
    : 'Administration';
  const date = f.updated_at
    ? new Date(f.updated_at).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
    : '';
  return {
    id: f.id,
    displayId: f.filing_number || 'Draft',
    title: f.template?.name || f.category,
    status: stateMap[f.state] || 'submitted',
    scope: 'campus',
    updated: date,
    anon: f.template?.anonymity_mode === 'anonymous',
    desc: f.body || '(No description)',
    routing: [routing],
    timeline: [{ t: 'Submitted', d: f.submitted_at ? new Date(f.submitted_at).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : 'Pending', done: !!f.submitted_at }],
    isRealFiling: true,
  };
}

// ═══════════════════════════════════════════════════════════════
//  CASES SCREEN
// ═══════════════════════════════════════════════════════════════
function CasesScreen() {
  const { go, mode } = useApp();
  const [tab, setTab] = React.useState('all');

  // Always fetch real filings from API — no mock data
  const [campusFilings, setCampusFilings] = React.useState([]);
  const [loadingFilings, setLoadingFilings] = React.useState(false);
  const [filingsError, setFilingsError] = React.useState(null);

  React.useEffect(() => {
    setLoadingFilings(true);
    setFilingsError(null);
    if (typeof filingApiFetch === 'function') {
      filingApiFetch('/v1/filings?page=1')
        .then(data => setCampusFilings((data || []).map(mapFilingToCase)))
        .catch(() => setFilingsError('Could not load filings — is the server running?'))
        .finally(() => setLoadingFilings(false));
    } else {
      setLoadingFilings(false);
    }
  }, [mode]);

  // Real API data for both modes
  const inMode = campusFilings;

  const filtered = inMode.filter(c =>
    tab === 'all' ? true :
    tab === 'active' ? c.status !== 'resolved' :
    /* resolved */ c.status === 'resolved'
  );

  const handleOpenCase = (c) => {
    if (c.isRealFiling) {
      go('filing', { id: c.id });
    } else {
      go('case', { id: c.id });
    }
  };

  return (
    <>
      <Header back/>
      <div style={{ padding: '4px 20px 0' }}>
        <div className="eyebrow">{mode === 'campus' ? 'Campus' : 'National'} · my cases</div>
        <h1 className="h-display" style={{ margin: '4px 0 4px', fontSize: 26, lineHeight: 1.05 }}>My Cases</h1>
        <div style={{ fontSize: 13, color: 'var(--muted)', fontFamily: 'var(--font-serif)', fontStyle: 'italic' }}>
          Your complaints, reports, and grievances — tracked in real time.
        </div>
      </div>

      <div style={{ padding: '14px 20px 8px' }}>
        <div className="tabbar">
          {[
            ['all',      `All · ${inMode.length}`],
            ['active',   `Active · ${inMode.filter(c => c.status !== 'resolved').length}`],
            ['resolved', `Resolved · ${inMode.filter(c => c.status === 'resolved').length}`],
          ].map(([k, l]) => (
            <button key={k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{l}</button>
          ))}
        </div>
      </div>

      <div style={{ padding: '8px 20px 28px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {loadingFilings && (
          <div style={{ textAlign: 'center', padding: 32, color: 'var(--muted)', fontSize: 13 }}>Loading cases…</div>
        )}
        {filingsError && !loadingFilings && (
          <div style={{
            padding: 14, background: 'rgba(232,49,42,0.06)', borderRadius: 12,
            border: '1px solid rgba(232,49,42,0.2)', color: 'var(--red)', fontSize: 12.5, textAlign: 'center',
          }}>
            {filingsError}
            <div style={{ marginTop: 8 }}>
              <button onClick={() => go('new-filing')} className="btn btn-primary" style={{ fontSize: 12 }}>
                <IconSparkles size={12}/> File a complaint
              </button>
            </div>
          </div>
        )}
        {!loadingFilings && filtered.map(c => (
          <CaseCard key={c.id} c={c} onOpen={() => handleOpenCase(c)}/>
        ))}
        {!loadingFilings && filtered.length === 0 && !filingsError && (
          <div style={{ padding: '60px 20px', textAlign: 'center' }}>
            <div className="serif" style={{ fontSize: 20, color: 'var(--navy)' }}>No cases here yet.</div>
            <div style={{ marginTop: 6, fontSize: 13, color: 'var(--muted)', fontFamily: 'var(--font-serif)', fontStyle: 'italic' }}>
              File a complaint, report, or grievance and it will appear here.
            </div>
            <button onClick={() => go('new-filing')} className="btn btn-primary" style={{ marginTop: 14 }}>
              <IconSparkles size={14}/> File a complaint
            </button>
          </div>
        )}
      </div>
    </>
  );
}

function CaseCard({ c, onOpen }) {
  // For real filings use displayId (filing number); for mock cases use id
  const displayId = c.displayId || c.id;
  return (
    <button onClick={onOpen} style={{
      width: '100%', textAlign: 'left', background: 'var(--surface)', border: '1px solid var(--mist)',
      borderRadius: 16, padding: 16, cursor: 'pointer',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="mono" style={{ fontSize: 11, color: 'var(--muted)' }}>{displayId}</span>
          {c.anon && <span className="anon"><IconEyeOff size={12}/> Anonymous</span>}
        </div>
        <StatusPill status={c.status}/>
      </div>
      <div className="serif" style={{ fontSize: 16, fontWeight: 500, lineHeight: 1.2, color: 'var(--navy)', marginBottom: 10 }}>
        {c.title}
      </div>
      <Stepper status={c.status}/>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 12 }}>
        <div style={{ fontSize: 11.5, color: 'var(--ink-2)' }}>
          {c.routed || (c.routing?.length ? `Routed to: ${c.routing[0]}` : '')}
        </div>
        <div className="serif" style={{ fontSize: 11.5, color: 'var(--muted)', fontStyle: 'italic' }}>{c.updated}</div>
      </div>
    </button>
  );
}

// ═══════════════════════════════════════════════════════════════
//  CASE DETAIL
// ═══════════════════════════════════════════════════════════════
function CaseDetailScreen({ params }) {
  const { mode } = useApp();
  const c = ACTIVE_CASES.find(x => x.id === params.id) ||
            ACTIVE_CASES.find(x => x.scope === mode) || ACTIVE_CASES[0];
  const currentLevel = c.timeline.findIndex(t => t.active);

  return (
    <>
      <Header back/>

      <div style={{ padding: '4px 20px 14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <span className="mono" style={{ fontSize: 11, color: 'var(--muted)' }}>{c.id}</span>
          {c.anon && <span className="anon"><IconEyeOff size={12}/> Anonymous</span>}
          <span style={{ flex: 1 }}/>
          <StatusPill status={c.status}/>
        </div>
        <h1 className="h-display" style={{ fontSize: 24, margin: 0, lineHeight: 1.1 }}>{c.title}</h1>
        <div style={{ marginTop: 8, fontSize: 12.5, color: 'var(--ink-2)', fontStyle: 'italic', fontFamily: 'var(--font-serif)' }}>
          {c.routed} · last updated {c.updated}
        </div>
      </div>

      {/* Routing hierarchy */}
      <div style={{ padding: '0 20px 14px' }}>
        <div className="eyebrow" style={{ marginBottom: 10 }}>Routing hierarchy</div>
        <div style={{
          padding: 14, borderRadius: 14, background: 'var(--surface)', border: '1px solid var(--mist)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {c.routing.map((step, i) => {
              const isCurr = i === Math.min(currentLevel >= 0 ? currentLevel : 0, c.routing.length - 1);
              const isPast = i < (currentLevel >= 0 ? currentLevel : 0);
              return (
                <React.Fragment key={i}>
                  <div style={{ flex: 1, textAlign: 'center' }}>
                    <div style={{
                      width: 28, height: 28, borderRadius: 999, margin: '0 auto',
                      background: isCurr ? 'var(--gold)' : isPast ? 'var(--sage)' : 'var(--mist)',
                      color: isCurr || isPast ? '#fff' : 'var(--muted)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontFamily: 'var(--font-serif)', fontSize: 12, fontWeight: 500,
                      boxShadow: isCurr ? '0 0 0 5px rgba(184,137,58,0.18)' : 'none',
                    }}>
                      {isPast ? <IconCheck size={12} sw={3}/> : i + 1}
                    </div>
                    <div style={{
                      marginTop: 6, fontSize: 10, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase',
                      color: isCurr ? 'var(--navy)' : 'var(--muted)', lineHeight: 1.2,
                    }}>{step}</div>
                  </div>
                  {i < c.routing.length - 1 && <span style={{ flex: 0.3, height: 1, background: isPast ? 'var(--sage)' : 'var(--mist-2)' }}/>}
                </React.Fragment>
              );
            })}
          </div>
        </div>
      </div>

      {/* Timeline */}
      <div style={{ padding: '4px 20px 14px' }}>
        <div className="eyebrow" style={{ marginBottom: 6 }}>Timeline</div>
        <div>
          {c.timeline.map((t, i) => (
            <div key={i} className="tl-step">
              <span className={`tl-dot ${t.done ? 'done' : t.active ? 'active' : ''}`}/>
              <div style={{ flex: 1 }}>
                <div style={{
                  fontSize: 13.5, fontWeight: 500,
                  color: t.done || t.active ? 'var(--navy)' : 'var(--muted)',
                }}>{t.t}</div>
                <div className="mono" style={{ fontSize: 10.5, color: 'var(--muted)', marginTop: 1 }}>{t.d}</div>
              </div>
              {t.active && <span className="pill pill-review"><span className="dot pulse"/> Now</span>}
            </div>
          ))}
        </div>
      </div>

      {/* Original text */}
      <div style={{ padding: '4px 20px 14px' }}>
        <div className="eyebrow" style={{ marginBottom: 6 }}>Original complaint</div>
        <div className="card" style={{ background: 'var(--surface)' }}>
          {c.anon ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <IconEyeOff size={14} stroke="var(--muted)"/>
              <div className="mono" style={{ fontSize: 11, color: 'var(--muted)' }}>From: S***** A***** (verified DIU)</div>
            </div>
          ) : null}
          <p className="serif" style={{ margin: 0, fontSize: 14, lineHeight: 1.55, color: 'var(--ink)' }}>
            “{c.desc}”
          </p>
        </div>
      </div>

      {/* Evidence */}
      <div style={{ padding: '4px 20px 14px' }}>
        <div className="eyebrow" style={{ marginBottom: 8 }}>Evidence · 3 items</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
          {[1,2,3].map(i => (
            <div key={i} style={{
              aspectRatio: '1', borderRadius: 10, background: `linear-gradient(135deg, var(--mist) 30%, var(--mist-2))`,
              border: '1px solid var(--mist-2)', position: 'relative', overflow: 'hidden',
            }}>
              <div style={{
                position: 'absolute', bottom: 6, left: 6, right: 6,
                background: 'rgba(11,29,53,0.75)', color: '#F7F3EE',
                padding: '4px 6px', borderRadius: 6,
                fontSize: 9, fontFamily: 'var(--font-mono)', lineHeight: 1.3,
              }}>
                IMG-00{i}<br/>23.78°N 90.41°E
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Dead Man's Switch — for national cases that enabled it */}
      {c.deadMan && (
        <div style={{ padding: '4px 20px 14px' }}>
          <div style={{
            padding: 14, borderRadius: 14, background: 'rgba(232,49,42,0.06)',
            border: '1px solid rgba(232,49,42,0.25)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <IconShield size={16} stroke="var(--ember)"/>
              <div className="eyebrow" style={{ color: 'var(--ember-2)' }}>Dead Man's Switch · Active</div>
            </div>
            <div style={{ fontSize: 13, color: 'var(--ink)', lineHeight: 1.4 }}>
              If you don't check in within <strong>48 hours</strong>, evidence and contacts will be released to your designated lawyer automatically.
            </div>
          </div>
        </div>
      )}

      {/* Actions */}
      <div style={{ padding: '4px 20px 28px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <button className="btn btn-primary"><IconPlus size={15}/> Add update</button>
        <button className="btn btn-ghost"><IconArrowUp size={15}/> Escalate</button>
      </div>
    </>
  );
}

// ═══════════════════════════════════════════════════════════════
//  MAP SCREEN — Leaflet + OpenStreetMap
// ═══════════════════════════════════════════════════════════════

const ZONE_COLORS = {
  campus:     '#22c55e',
  red:        '#ef4444',
  purple:     '#a855f7',
  black:      '#374151',
  // legacy
  university: '#1FA663',
  rape:       '#0B0B0B',
  murder:     '#7B2CBF',
  alert:      '#E8312A',
};
const ZONE_TYPE_LABELS = {
  campus:     'Campus (Safe Area)',
  red:        'Danger Zone',
  purple:     'Murder Report Area',
  black:      'Assault Report Area',
  // legacy
  university: 'Campus Zone',
  rape:       'Safety Advisory',
  murder:     'Safety Advisory',
  alert:      'Active Alert',
};

function haversineDistance(lat1, lng1, lat2, lng2) {
  const R  = 6371000;
  const p1 = lat1 * Math.PI / 180, p2 = lat2 * Math.PI / 180;
  const dp = (lat2 - lat1) * Math.PI / 180;
  const dl = (lng2 - lng1) * Math.PI / 180;
  const a  = Math.sin(dp/2)*Math.sin(dp/2) + Math.cos(p1)*Math.cos(p2)*Math.sin(dl/2)*Math.sin(dl/2);
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// Initial great-circle bearing (degrees, 0–360 clockwise from north) FROM point 1
// TO point 2 — i.e. the compass heading a responder must face to reach the victim.
function bearingDeg(lat1, lng1, lat2, lng2) {
  const p1 = lat1 * Math.PI / 180, p2 = lat2 * Math.PI / 180;
  const dl = (lng2 - lng1) * Math.PI / 180;
  const y = Math.sin(dl) * Math.cos(p2);
  const x = Math.cos(p1) * Math.sin(p2) - Math.sin(p1) * Math.cos(p2) * Math.cos(dl);
  return (Math.atan2(y, x) * 180 / Math.PI + 360) % 360;
}

const _CARDINAL_8       = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
const _CARDINAL_8_LONG  = ['North', 'Northeast', 'East', 'Southeast', 'South', 'Southwest', 'West', 'Northwest'];

// 0–360 bearing → one of 8 compass points. `long` gives the spelled-out form for UI copy.
function cardinal(deg, long) {
  const i = Math.round(((deg % 360) + 360) % 360 / 45) % 8;
  return (long ? _CARDINAL_8_LONG : _CARDINAL_8)[i];
}

// Human-friendly walking ETA from a straight-line distance in metres. ~1.4 m/s ≈ 5 km/h.
// The on-map line is a straight line, so this is a lower-bound "as the crow flies" estimate.
function walkEtaTxt(distanceM) {
  if (!isFinite(distanceM)) return null;
  if (distanceM < 80) return '<1 min walk';
  const mins = Math.round(distanceM / 1.4 / 60);
  return '~' + Math.max(1, mins) + ' min walk';
}

// Distance phrasing shared by the map popups and the responder sheet.
function distanceTxt(distanceM) {
  if (!isFinite(distanceM)) return null;
  return distanceM < 1000 ? Math.round(distanceM) + 'm' : (distanceM / 1000).toFixed(1) + 'km';
}


const RADIUS_OPTIONS = [
  { label: '5 km',  value: 5 },
  { label: '10 km', value: 10 },
  { label: '25 km', value: 25 },
  { label: 'All',   value: null },
];

// Zone type legend entries (student-facing types)
const LEGEND_ENTRIES = [
  ['campus',   'Campus (Safe)',     '#22c55e'],
  ['red',      'Danger Zone',       '#ef4444'],
  ['purple',   'Murder Report',     '#a855f7'],
  ['black',    'Assault Report',    '#374151'],
];

function MapScreen({ params } = {}) {
  const mapContainerRef = React.useRef(null);
  const leafletMapRef   = React.useRef(null);
  const zoneLayersRef   = React.useRef([]);
  const userMarkerRef   = React.useRef(null);
  const alertMarkerRef  = React.useRef(null);
  const dirLineRef      = React.useRef(null);   // direction line responder → victim
  const dirArrowRef     = React.useRef(null);   // rotated heading arrow near the responder
  const responderWatchRef = React.useRef(null); // navigator.geolocation.watchPosition id
  const userLocRef      = React.useRef({ lat: 23.7450, lng: 90.3718 });

  // When opened from an alert push (deep link), focus the emergency location and
  // surface the responder confirmation flow. focusAlert carries the event id; lat/lng
  // (from the push payload) may be absent/stale, so we also fetch authoritative
  // coordinates + state from the backend below.
  const eventId = params?.focusAlert || null;
  const responderToken = (typeof localStorage !== 'undefined') ? localStorage.getItem('anchor_access_token') : null;
  const [alertInfo, setAlertInfo] = React.useState(null);   // { lat, lng, state } from GET /v1/alerts/{id}
  // Responder flow state machine: idle | loading | prompt | sending | responded | cannot | closed | error
  const [respondStatus, setRespondStatus] = React.useState((eventId && responderToken) ? 'loading' : 'idle');
  const [respondError,  setRespondError]  = React.useState(null);

  // Prefer authoritative backend coordinates (full precision, and updated live as
  // the victim moves); fall back to the push params only until the backend loads.
  const pushLat = params ? parseFloat(params.lat) : NaN;
  const pushLng = params ? parseFloat(params.lng) : NaN;
  const focusLat = (alertInfo && isFinite(alertInfo.lat)) ? alertInfo.lat : (isFinite(pushLat) ? pushLat : NaN);
  const focusLng = (alertInfo && isFinite(alertInfo.lng)) ? alertInfo.lng : (isFinite(pushLng) ? pushLng : NaN);
  const hasFocus = isFinite(focusLat) && isFinite(focusLng);
  const didCenterRef = React.useRef(false);
  const didFrameBothRef = React.useRef(false);  // fitBounds(me, victim) done once
  // Treat the alert as active until the poll tells us otherwise, so the direction
  // line shows immediately on a cold deep-link before the first /v1/alerts/{id} load.
  const alertActive = !alertInfo || alertInfo.state === 'active';

  const [radiusKm,    setRadiusKm]    = React.useState(10);
  const [userLoc,     setUserLoc]     = React.useState({ lat: 23.7450, lng: 90.3718 });
  const [locStatus,   setLocStatus]   = React.useState('default');
  const [nearbyZones, setNearbyZones] = React.useState([]);
  const [zones,        setZones]       = React.useState([]);
  const [zonesLoading, setZonesLoading] = React.useState(true);
  const [zonesError,   setZonesError]   = React.useState(null);
  const [lastRefresh,  setLastRefresh]  = React.useState(null);

  function fetchZones(lat, lng, km) {
    setZonesLoading(true);
    setZonesError(null);
    let url;
    if (km && lat != null) {
      url = `${_API}/v1/zones/nearby?lat=${lat}&lng=${lng}&radius_km=${km}`;
    } else if (km == null && lat != null) {
      // "All" mode — get all active zones
      url = `${_API}/v1/zones`;
    } else {
      url = `${_API}/v1/zones`;
    }
    fetch(url)
      .then(r => { if (!r.ok) throw new Error('Server error ' + r.status); return r.json(); })
      .then(d => {
        setZones(Array.isArray(d) ? d : []);
        setZonesError(null);
        setLastRefresh(new Date());
      })
      .catch(e => setZonesError(e.message || 'Could not reach server'))
      .finally(() => setZonesLoading(false));
  }

  // Init Leaflet map once
  React.useEffect(() => {
    if (leafletMapRef.current) return;
    const map = L.map(mapContainerRef.current, { center: [23.7450, 90.3718], zoom: 13 });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19, detectRetina: true,
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    leafletMapRef.current = map;

    if (navigator.geolocation) {
      setLocStatus('locating');
      // Fast first fix to centre the map and load zones…
      navigator.geolocation.getCurrentPosition(
        pos => {
          const loc = { lat: pos.coords.latitude, lng: pos.coords.longitude };
          userLocRef.current = loc;
          setUserLoc(loc);
          // Don't yank the view away from an alert we were asked to focus.
          if (!hasFocus) map.setView([loc.lat, loc.lng], 14);
          setLocStatus('found');
          fetchZones(loc.lat, loc.lng, 10);
        },
        () => {
          setLocStatus('denied');
          fetchZones(userLocRef.current.lat, userLocRef.current.lng, null);
        },
        { timeout: 8000, enableHighAccuracy: true }
      );
      // …then, ONLY when we arrived here to navigate to an alert, keep the
      // responder's position LIVE so the direction line, distance, bearing and ETA
      // recalculate as they move toward the victim. We skip the continuous watch for
      // ordinary zone browsing to avoid draining the battery. On a transient watch
      // error we keep the last known fix rather than reverting to default.
      if (eventId) try {
        responderWatchRef.current = navigator.geolocation.watchPosition(
          pos => {
            const loc = { lat: pos.coords.latitude, lng: pos.coords.longitude };
            userLocRef.current = loc;
            setUserLoc(loc);
            setLocStatus('found');
          },
          err => {
            // Only downgrade to "denied" on a hard permission denial; ignore
            // timeouts/position-unavailable so a momentary glitch doesn't wipe the fix.
            if (err && err.code === 1) setLocStatus('denied');
          },
          { enableHighAccuracy: true, timeout: 15000, maximumAge: 5000 }
        );
      } catch (_) { /* geolocation may throw if blocked by permissions policy */ }
    } else {
      fetchZones(23.7450, 90.3718, null);
    }

    return () => {
      if (responderWatchRef.current !== null) {
        try { navigator.geolocation.clearWatch(responderWatchRef.current); } catch (_) {}
        responderWatchRef.current = null;
      }
      if (leafletMapRef.current) { leafletMapRef.current.remove(); leafletMapRef.current = null; }
    };
  }, []);

  // Drop a marker on the alert location and FOLLOW it as the victim moves (the
  // alert poll below refreshes alertInfo). Re-center the view only on first focus
  // so we don't yank the map while the responder is panning.
  React.useEffect(() => {
    const map = leafletMapRef.current;
    if (!map || !hasFocus) return;
    if (alertMarkerRef.current) {
      alertMarkerRef.current.setLatLng([focusLat, focusLng]);
    } else {
      alertMarkerRef.current = L.circleMarker([focusLat, focusLng], {
        radius: 11, color: '#E8312A', fillColor: '#E8312A', fillOpacity: 0.85, weight: 3,
      }).addTo(map)
        .bindPopup('<b style="color:#E8312A">Active alert here</b><br>Someone nearby needs help. Tap zones for details.');
    }
    if (!didCenterRef.current) {
      map.setView([focusLat, focusLng], 16);
      alertMarkerRef.current.openPopup();
      didCenterRef.current = true;
    }
  }, [focusLat, focusLng]);

  // Direction to the victim, Google-Maps style but drawn entirely in Leaflet: a
  // dashed line from the responder's LIVE position to the victim, plus a heading
  // arrow rotated to the bearing. Recomputes as either party moves; cleared when
  // we have no responder fix, no victim coords, or the alert is no longer active.
  React.useEffect(() => {
    const map = leafletMapRef.current;
    if (!map) return;

    const clearDir = () => {
      if (dirLineRef.current)  { try { map.removeLayer(dirLineRef.current); }  catch (_) {} dirLineRef.current = null; }
      if (dirArrowRef.current) { try { map.removeLayer(dirArrowRef.current); } catch (_) {} dirArrowRef.current = null; }
    };

    const haveFix = locStatus === 'found';
    const me = userLocRef.current;
    if (!eventId || !hasFocus || !alertActive || !haveFix || !me) { clearDir(); return; }

    const from = [me.lat, me.lng];
    const to   = [focusLat, focusLng];
    const brng = bearingDeg(me.lat, me.lng, focusLat, focusLng);

    // Line responder → victim
    if (dirLineRef.current) {
      dirLineRef.current.setLatLngs([from, to]);
    } else {
      dirLineRef.current = L.polyline([from, to], {
        color: '#E8312A', weight: 3, opacity: 0.85, dashArray: '6 8', interactive: false,
      }).addTo(map);
    }

    // Heading arrow anchored at the responder, rotated toward the victim.
    const arrowIcon = L.divIcon({
      className: '',
      html: '<div class="dir-arrow" style="transform:rotate(' + brng + 'deg)">'
        + '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#E8312A" '
        + 'stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">'
        + '<path d="M12 19V5"/><path d="m5 12 7-7 7 7"/></svg></div>',
      iconSize: [22, 22], iconAnchor: [11, 11],
    });
    if (dirArrowRef.current) {
      dirArrowRef.current.setLatLng(from);
      dirArrowRef.current.setIcon(arrowIcon);
    } else {
      dirArrowRef.current = L.marker(from, { icon: arrowIcon, interactive: false, zIndexOffset: 1000 }).addTo(map);
    }

    // Frame both endpoints once, so the responder sees themselves, the victim, and
    // the line between — then leave the view alone so we don't fight their panning.
    if (!didFrameBothRef.current) {
      try {
        map.fitBounds(L.latLngBounds([from, to]), { padding: [60, 60], maxZoom: 17 });
        didFrameBothRef.current = true;
      } catch (_) {}
    }

    return () => { /* layers persist across renders; cleaned on unmount below */ };
  }, [userLoc.lat, userLoc.lng, focusLat, focusLng, hasFocus, alertActive, locStatus, eventId]);

  // Remove the direction overlay on unmount (the Map screen is kept alive across nav).
  React.useEffect(() => () => {
    const map = leafletMapRef.current;
    if (!map) return;
    if (dirLineRef.current)  { try { map.removeLayer(dirLineRef.current); }  catch (_) {} dirLineRef.current = null; }
    if (dirArrowRef.current) { try { map.removeLayer(dirArrowRef.current); } catch (_) {} dirArrowRef.current = null; }
  }, []);

  // Responder flow — poll the authoritative alert location + state every 5s so the
  // map FOLLOWS the moving victim and we detect when they mark themselves safe.
  React.useEffect(() => {
    if (!eventId || !responderToken) { setRespondStatus('idle'); return; }
    let cancelled = false;
    let firstLoad = true;
    setRespondStatus('loading');
    setRespondError(null);
    const tick = async () => {
      try {
        const d = await alertApiGet('/v1/alerts/' + eventId, responderToken);
        if (cancelled) return;
        setAlertInfo({ lat: d.lat, lng: d.lng, state: d.state });
        const active = d.state === 'active';
        setRespondStatus(prev => {
          if (firstLoad) { firstLoad = false; return active ? 'prompt' : 'closed'; }
          if (active) return prev;  // keep prompt / sending / responded as-is
          // Alert resolved: if we were helping, show "they're safe"; else it closed.
          if (prev === 'responded' || prev === 'sending') return 'safe';
          if (prev === 'prompt' || prev === 'loading') return 'closed';
          return prev;
        });
      } catch (e) {
        if (cancelled) return;
        if (!firstLoad) return;  // transient poll error — keep current state
        firstLoad = false;
        const msg = String(e && e.message || '').toLowerCase();
        if (msg.includes('not found') || msg.includes('404')) setRespondStatus('closed');
        else { setRespondError('Could not load this alert.'); setRespondStatus('error'); }
      }
    };
    tick();
    const id = setInterval(tick, 5000);
    return () => { cancelled = true; clearInterval(id); };
  }, [eventId, responderToken]);

  // Distance from this responder to the person who needs help — only when we have a
  // real GPS fix (userLocRef defaults to a campus coordinate until located).
  function responderDistanceM() {
    const a = alertInfo;
    const me = userLocRef.current;
    if (a && isFinite(a.lat) && isFinite(a.lng) && me && locStatus === 'found') {
      return Math.round(haversineDistance(me.lat, me.lng, a.lat, a.lng));
    }
    return null;
  }

  // Full navigation read shared by the map overlay and the responder sheet:
  // distance + compass bearing + walking ETA, or null when we lack a fix/coords.
  function responderNav() {
    const a = alertInfo || (hasFocus ? { lat: focusLat, lng: focusLng } : null);
    const me = userLocRef.current;
    if (!(a && isFinite(a.lat) && isFinite(a.lng) && me && locStatus === 'found')) return null;
    const d = Math.round(haversineDistance(me.lat, me.lng, a.lat, a.lng));
    const brng = bearingDeg(me.lat, me.lng, a.lat, a.lng);
    return {
      distanceM:  d,
      distanceTxt: distanceTxt(d) + ' away',
      bearingTxt: cardinal(brng, true),     // "Northeast"
      bearingShort: cardinal(brng, false),  // "NE"
      etaTxt:     walkEtaTxt(d),
    };
  }

  async function handleRespondYes() {
    if (!eventId || !responderToken) return;
    setRespondError(null);
    setRespondStatus('sending');
    try {
      // Share the responder's real position so the alerting user sees who is
      // coming and from where (only when we have an actual GPS fix).
      const me = userLocRef.current;
      const haveFix = locStatus === 'found' && me && isFinite(me.lat) && isFinite(me.lng);
      await alertApiPost('/v1/alerts/' + eventId + '/respond',
        {
          response_type: 'responding',
          distance_m: responderDistanceM(),
          lat: haveFix ? me.lat : null,
          lng: haveFix ? me.lng : null,
        }, responderToken);
      setRespondStatus('responded');
    } catch (e) {
      const msg = String(e && e.message || '').toLowerCase();
      if (msg.includes('not found') || msg.includes('404')) setRespondStatus('closed');
      else { setRespondError('Could not send your response. Please try again.'); setRespondStatus('prompt'); }
    }
  }

  async function handleRespondNo() {
    if (eventId && responderToken) {
      // best-effort — record the decline so the fan-out can prioritise others
      try {
        await alertApiPost('/v1/alerts/' + eventId + '/respond',
          { response_type: 'cannot_help', distance_m: null }, responderToken);
      } catch (_) { /* non-blocking */ }
    }
    setRespondStatus('cannot');
  }

  // Re-render zones on the map whenever zones list changes
  React.useEffect(() => {
    const map = leafletMapRef.current;
    if (!map) return;

    zoneLayersRef.current.forEach(l => { try { map.removeLayer(l); } catch (_) {} });
    zoneLayersRef.current = [];

    zones.forEach(z => {
      const color = ZONE_COLORS[z.zone_type] || '#E8312A';
      const opts = {
        color, fillColor: color,
        fillOpacity: z.zone_type === 'campus' ? 0.12 : 0.22,
        weight: 2,
      };
      let layer;
      if ((z.shape_type || 'circle') === 'polygon' && Array.isArray(z.polygon_coords) && z.polygon_coords.length >= 3) {
        layer = L.polygon(z.polygon_coords, opts);
      } else {
        layer = L.circle([z.center_lat, z.center_lng], { radius: z.radius_m || 300, ...opts });
      }

      const displayName = z.name || z.label || ZONE_TYPE_LABELS[z.zone_type] || z.zone_type;
      const dist = z.center_lat
        ? haversineDistance(userLocRef.current.lat, userLocRef.current.lng, z.center_lat, z.center_lng)
        : null;
      const distTxt = dist != null
        ? (dist < 1000 ? Math.round(dist) + 'm away' : (dist / 1000).toFixed(1) + 'km away')
        : '';

      layer.bindPopup(
        '<div style="font-family:Inter Tight,sans-serif;min-width:160px">' +
        '<div style="font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.06em;color:' + color + ';margin-bottom:2px">' + (ZONE_TYPE_LABELS[z.zone_type] || z.zone_type) + '</div>' +
        '<div style="font-size:13px;font-weight:600;color:#0B1D35;margin-bottom:4px">' + displayName + '</div>' +
        (distTxt ? '<div style="font-size:11px;color:#6B7280">' + distTxt + '</div>' : '') +
        (z.description_public ? '<div style="font-size:11px;color:#374151;margin-top:4px">' + z.description_public + '</div>' : '') +
        '</div>'
      );
      layer.addTo(map);
      zoneLayersRef.current.push(layer);
    });

    // Update "nearby" list
    const nearby = zones
      .filter(z => z.center_lat != null)
      .map(z => ({ ...z, dist: haversineDistance(userLocRef.current.lat, userLocRef.current.lng, z.center_lat, z.center_lng) }))
      .sort((a, b) => a.dist - b.dist)
      .slice(0, 6);
    setNearbyZones(nearby);
  }, [JSON.stringify(zones)]);

  // User location marker
  React.useEffect(() => {
    const map = leafletMapRef.current;
    if (!map) return;
    if (userMarkerRef.current) { try { map.removeLayer(userMarkerRef.current); } catch (_) {} }
    const icon = L.divIcon({
      html: '<div style="width:14px;height:14px;border-radius:50%;background:#0B1D35;border:3px solid #fff;box-shadow:0 2px 8px rgba(11,29,53,0.4)"></div>',
      iconSize: [14, 14], iconAnchor: [7, 7], className: '',
    });
    userMarkerRef.current = L.marker([userLoc.lat, userLoc.lng], { icon }).bindPopup('You are here').addTo(map);
  }, [userLoc.lat, userLoc.lng]);

  function handleRefresh() {
    const loc = userLocRef.current;
    fetchZones(loc.lat, loc.lng, radiusKm);
  }

  function handleRadiusChange(km) {
    setRadiusKm(km);
    const loc = userLocRef.current;
    fetchZones(loc.lat, loc.lng, km);
  }

  const activeCount = zones.filter(z => z.status === 'active' || !z.status).length;
  const locHint = {
    locating: 'Locating you…',
    found:    'Using GPS location',
    denied:   'GPS unavailable — showing all zones',
    default:  'Dhaka, Bangladesh',
  }[locStatus];

  const lastRefreshTxt = lastRefresh
    ? lastRefresh.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : null;

  return (
    <>
      <Header back/>

      {/* Title */}
      <div style={{ padding: '4px 20px 10px' }}>
        <div className="eyebrow">Zone Map · Dhaka</div>
        <h1 className="h-display" style={{ fontSize: 24, margin: '4px 0 0', lineHeight: 1.1 }}>
          {zonesLoading ? '…' : activeCount} zones
        </h1>
        <div style={{ marginTop: 4, fontSize: 12, color: 'var(--muted)', fontStyle: 'italic', fontFamily: 'var(--font-serif)' }}>
          {locHint}
          {lastRefreshTxt && <span style={{ marginLeft: 8, fontStyle: 'normal' }}>· Updated {lastRefreshTxt}</span>}
        </div>
      </div>

      {/* Error banner */}
      {zonesError && (
        <div style={{ margin: '0 20px 10px', padding: '8px 12px', borderRadius: 10,
          background: '#FEE2E2', color: '#991B1B', fontSize: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ flex: 1 }}>⚠ {zonesError}</span>
          <button onClick={handleRefresh} style={{ marginLeft: 'auto', textDecoration: 'underline',
            background: 'none', border: 'none', cursor: 'pointer', color: '#991B1B', fontSize: 12 }}>Retry</button>
        </div>
      )}

      {/* Radius selector + refresh */}
      <div style={{ padding: '0 20px 10px', display: 'flex', gap: 6, alignItems: 'center', overflowX: 'auto' }} className="no-scrollbar">
        <span style={{ fontSize: 11, color: 'var(--muted)', whiteSpace: 'nowrap', marginRight: 2 }}>Radius:</span>
        {RADIUS_OPTIONS.map(({ label, value }) => (
          <button key={label} onClick={() => handleRadiusChange(value)} style={{
            padding: '6px 11px', borderRadius: 999, whiteSpace: 'nowrap', cursor: 'pointer',
            background: radiusKm === value ? 'var(--brand)' : 'var(--surface)',
            color:      radiusKm === value ? '#F7F3EE'    : 'var(--ink-2)',
            border: '1px solid ' + (radiusKm === value ? 'var(--navy)' : 'var(--mist)'),
            fontSize: 11.5, fontWeight: 500,
          }}>{label}</button>
        ))}
        <button onClick={handleRefresh} disabled={zonesLoading} style={{
          padding: '6px 10px', borderRadius: 999, whiteSpace: 'nowrap', cursor: 'pointer',
          background: 'var(--surface)', color: 'var(--ink-2)',
          border: '1px solid var(--mist)', fontSize: 11.5, fontWeight: 500,
          marginLeft: 'auto', flexShrink: 0, opacity: zonesLoading ? 0.5 : 1,
        }} title="Refresh zones">{zonesLoading ? '…' : '⟳'}</button>
      </div>

      {/* Map */}
      <div style={{ padding: '0 20px 14px' }}>
        <div style={{ borderRadius: 16, overflow: 'hidden', border: '1px solid var(--mist)' }}>
          <div ref={mapContainerRef} style={{ height: 340 }}/>
        </div>
      </div>

      {/* Color legend */}
      <div style={{ padding: '0 20px 14px' }}>
        <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--muted)', marginBottom: 8 }}>
          Legend
        </div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          {LEGEND_ENTRIES.map(([type, label, color]) => (
            <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 5, padding: '5px 10px', borderRadius: 8,
              background: 'var(--surface)', border: '1.5px solid ' + color + '60' }}>
              <span style={{ width: 10, height: 10, borderRadius: type === 'campus' ? 3 : 999, background: color, display: 'block', flexShrink: 0 }}/>
              <span style={{ fontSize: 11, color: 'var(--ink-2)', fontWeight: 500 }}>{label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Nearby zones list */}
      <div style={{ padding: '0 20px 28px' }}>
        <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--muted)', marginBottom: 10 }}>
          Zones near you
        </div>
        {zonesLoading && (
          <div style={{ fontSize: 13, color: 'var(--muted)', fontStyle: 'italic' }}>Loading zones…</div>
        )}
        {!zonesLoading && nearbyZones.length === 0 && !zonesError && (
          <div style={{ fontSize: 13, color: 'var(--muted)', fontStyle: 'italic' }}>No zones in this area.</div>
        )}
        {!zonesLoading && nearbyZones.map(z => {
          const color = ZONE_COLORS[z.zone_type] || '#E8312A';
          const displayName = z.name || z.label || ZONE_TYPE_LABELS[z.zone_type] || z.zone_type;
          return (
            <div key={z.id} className="card" style={{ marginBottom: 8, background: 'var(--surface)', padding: '10px 12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ width: 10, height: 10, borderRadius: z.zone_type === 'campus' ? 3 : 999, background: color, flexShrink: 0 }}/>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--navy)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{displayName}</div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
                    {ZONE_TYPE_LABELS[z.zone_type] || z.zone_type}
                    {z.dist != null && (
                      <> · {z.dist < 1000 ? Math.round(z.dist) + 'm' : (z.dist / 1000).toFixed(1) + 'km'} away</>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Responder confirmation sheet — shown when arriving from a nearby-alert push */}
      {eventId && respondStatus !== 'idle' && (
        <AlertRespondSheet
          status={respondStatus}
          error={respondError}
          nav={responderNav()}
          locDenied={locStatus === 'denied'}
          onYes={handleRespondYes}
          onNo={handleRespondNo}
          onClose={() => setRespondStatus('idle')}
        />
      )}
    </>
  );
}

// Bottom-sheet a nearby user sees after tapping an emergency push. Lets them confirm
// "I'm coming to help" (→ POST /respond responding) so the alerting user's live map
// shows a real responder instead of "0 responding".
function AlertRespondSheet({ status, error, nav, locDenied, onYes, onNo, onClose }) {
  const sending = status === 'sending';
  const sheet = (children) => (
    <div style={{ position:'fixed', inset:0, zIndex:9998, background:'rgba(11,29,53,0.55)',
                  backdropFilter:'blur(4px)', display:'flex', alignItems:'flex-end', justifyContent:'center' }}>
      <div style={{ background:'var(--cream)', borderRadius:'24px 24px 0 0', padding:'24px 24px 36px',
                    width:'100%', maxWidth:402, boxSizing:'border-box' }}>
        <div style={{ width:40, height:4, borderRadius:999, background:'var(--mist)', margin:'0 auto 20px' }}/>
        {children}
      </div>
    </div>
  );

  if (status === 'loading') {
    return sheet(
      <div style={{ textAlign:'center', padding:'8px 0 4px', color:'var(--muted)',
                    fontSize:14, fontFamily:'var(--font-sans)' }}>
        Loading alert…
      </div>
    );
  }

  if (status === 'safe') {
    return sheet(
      <>
        <div style={{ width:52, height:52, borderRadius:999, margin:'0 auto 14px',
                      background:'rgba(74,107,92,0.15)', border:'1px solid rgba(74,107,92,0.4)',
                      display:'flex', alignItems:'center', justifyContent:'center' }}>
          <IconCheck size={26} sw={2.4} stroke="var(--sage)"/>
        </div>
        <div style={{ fontSize:21, fontWeight:500, color:'var(--navy)', fontFamily:'var(--font-serif)',
                      textAlign:'center', marginBottom:8 }}>They're safe now</div>
        <p style={{ fontSize:13.5, color:'var(--muted)', lineHeight:1.6, textAlign:'center',
                    fontFamily:'var(--font-sans)', marginBottom:20 }}>
          The person you were helping has marked themselves safe. Thank you for responding.
        </p>
        <button onClick={onClose} className="btn btn-primary"
          style={{ width:'100%', height:48, borderRadius:12, fontSize:15, fontWeight:600 }}>Close</button>
      </>
    );
  }

  if (status === 'responded') {
    return sheet(
      <>
        <div style={{ width:52, height:52, borderRadius:999, margin:'0 auto 14px',
                      background:'rgba(74,107,92,0.15)', border:'1px solid rgba(74,107,92,0.4)',
                      display:'flex', alignItems:'center', justifyContent:'center' }}>
          <IconCheck size={26} sw={2.4} stroke="var(--sage)"/>
        </div>
        <div style={{ fontSize:21, fontWeight:500, color:'var(--navy)', fontFamily:'var(--font-serif)',
                      textAlign:'center', marginBottom:8 }}>You're on the way</div>

        {/* Live direction card — distance · compass direction · ETA. Updates as the
            responder and the victim move. Points to the on-map line for the route. */}
        {nav ? (
          <div style={{ marginBottom:16, padding:'14px 16px', borderRadius:14,
                        background:'rgba(232,49,42,0.06)', border:'1px solid rgba(232,49,42,0.22)' }}>
            <div style={{ display:'flex', alignItems:'center', gap:12 }}>
              <div style={{ width:40, height:40, borderRadius:999, flexShrink:0,
                            background:'rgba(232,49,42,0.12)', display:'flex',
                            alignItems:'center', justifyContent:'center' }}>
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#E8312A"
                     strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 11l19-9-9 19-2-8-8-2z"/></svg>
              </div>
              <div style={{ flex:1, minWidth:0 }}>
                <div style={{ fontSize:17, fontWeight:600, color:'var(--navy)', fontFamily:'var(--font-sans)' }}>
                  {nav.distanceTxt}
                </div>
                <div style={{ fontSize:12.5, color:'var(--ember)', fontWeight:600, marginTop:1,
                              fontFamily:'var(--font-sans)' }}>
                  Head {nav.bearingTxt}{nav.etaTxt ? ' · ' + nav.etaTxt : ''}
                </div>
              </div>
            </div>
            <div style={{ fontSize:12, color:'var(--muted)', lineHeight:1.5, marginTop:10,
                          fontFamily:'var(--font-sans)' }}>
              Follow the red line on the map to reach them. Head over safely — if the situation
              looks dangerous, call the authorities.
            </div>
          </div>
        ) : (
          <p style={{ fontSize:13.5, color:'var(--muted)', lineHeight:1.6, textAlign:'center',
                      fontFamily:'var(--font-sans)', marginBottom:16 }}>
            They've been told that help is coming. The map shows where they are — head over safely.
            {locDenied ? ' Turn on location to see the direction to them.' : ''}
            {' '}If the situation looks dangerous, call the authorities.
          </p>
        )}

        <a href="tel:999" style={{ display:'block', textAlign:'center', textDecoration:'none',
            marginBottom:10, padding:'13px 0', borderRadius:12, background:'var(--ember)', color:'#fff',
            fontSize:15, fontWeight:600, fontFamily:'var(--font-sans)' }}>
          Call 999 (Police)
        </a>
        <button onClick={onClose} className="btn"
          style={{ width:'100%', height:44, borderRadius:12, fontSize:14, background:'transparent',
                   border:'none', cursor:'pointer', color:'var(--muted)', fontFamily:'var(--font-sans)' }}>
          Done
        </button>
      </>
    );
  }

  if (status === 'cannot') {
    return sheet(
      <>
        <div style={{ fontSize:20, fontWeight:500, color:'var(--navy)', fontFamily:'var(--font-serif)',
                      marginBottom:8 }}>No problem</div>
        <p style={{ fontSize:13.5, color:'var(--muted)', lineHeight:1.6,
                    fontFamily:'var(--font-sans)', marginBottom:20 }}>
          Thanks for letting us know. We'll keep notifying others nearby.
        </p>
        <button onClick={onClose} className="btn btn-primary"
          style={{ width:'100%', height:48, borderRadius:12, fontSize:15, fontWeight:600 }}>Close</button>
      </>
    );
  }

  if (status === 'closed') {
    return sheet(
      <>
        <div style={{ fontSize:20, fontWeight:500, color:'var(--navy)', fontFamily:'var(--font-serif)',
                      marginBottom:8 }}>Alert no longer active</div>
        <p style={{ fontSize:13.5, color:'var(--muted)', lineHeight:1.6,
                    fontFamily:'var(--font-sans)', marginBottom:20 }}>
          This person may already be safe, or the alert has expired. No action is needed.
        </p>
        <button onClick={onClose} className="btn btn-primary"
          style={{ width:'100%', height:48, borderRadius:12, fontSize:15, fontWeight:600 }}>Close</button>
      </>
    );
  }

  if (status === 'error') {
    return sheet(
      <>
        <div style={{ fontSize:20, fontWeight:500, color:'var(--navy)', fontFamily:'var(--font-serif)',
                      marginBottom:8 }}>Couldn't load the alert</div>
        <p style={{ fontSize:13.5, color:'var(--muted)', lineHeight:1.6,
                    fontFamily:'var(--font-sans)', marginBottom:20 }}>
          {error || 'Something went wrong. Please check your connection and try again.'}
        </p>
        <button onClick={onClose} className="btn btn-primary"
          style={{ width:'100%', height:48, borderRadius:12, fontSize:15, fontWeight:600 }}>Close</button>
      </>
    );
  }

  // status === 'prompt' | 'sending'
  return sheet(
    <>
      <div style={{ display:'flex', alignItems:'center', gap:10, marginBottom:12 }}>
        <div style={{ width:44, height:44, borderRadius:999, flexShrink:0,
                      background:'rgba(232,49,42,0.14)', border:'1px solid rgba(232,49,42,0.4)',
                      display:'flex', alignItems:'center', justifyContent:'center' }}>
          <IconAlert size={20} stroke="#E8312A"/>
        </div>
        <div>
          <div style={{ fontSize:19, fontWeight:500, color:'var(--navy)', fontFamily:'var(--font-serif)', lineHeight:1.15 }}>
            Someone nearby needs help
          </div>
          {nav && (
            <div style={{ fontSize:12.5, color:'var(--ember)', fontWeight:600, marginTop:2,
                          fontFamily:'var(--font-sans)' }}>
              {nav.distanceTxt} · {nav.bearingTxt}{nav.etaTxt ? ' · ' + nav.etaTxt : ''}
            </div>
          )}
        </div>
      </div>
      <p style={{ fontSize:13.5, color:'var(--muted)', lineHeight:1.6,
                  fontFamily:'var(--font-sans)', marginBottom: error ? 14 : 22 }}>
        A nearby user just triggered an emergency alert. If you can safely reach them, let them
        know you're coming — they'll see that help is on the way.
      </p>

      {error && (
        <div style={{ marginBottom:16, padding:'11px 13px', borderRadius:12,
                      background:'rgba(196,69,54,0.08)', border:'1px solid rgba(196,69,54,0.22)',
                      color:'var(--ember)', fontSize:12.5, lineHeight:1.5, fontFamily:'var(--font-sans)' }}>
          {error}
        </div>
      )}

      <button onClick={onYes} disabled={sending}
        style={{ width:'100%', height:48, borderRadius:12, fontSize:15, fontWeight:600, marginBottom:10,
                 background:'var(--ember)', color:'#fff', border:'none',
                 cursor: sending ? 'default' : 'pointer', opacity: sending ? 0.7 : 1,
                 fontFamily:'var(--font-sans)' }}>
        {sending ? 'Sending…' : "I'm coming to help"}
      </button>
      <button onClick={onNo} disabled={sending}
        style={{ width:'100%', height:42, borderRadius:12, fontSize:14,
                 background:'transparent', border:'none', cursor: sending ? 'default' : 'pointer',
                 color:'var(--muted)', fontFamily:'var(--font-sans)' }}>
        I can't right now
      </button>
    </>
  );
}

// ═══════════════════════════════════════════════════════════════
//  FEED SCREEN — newspaper layout, live from /v1/feed
// ═══════════════════════════════════════════════════════════════
function FeedScreen() {
  const { mode } = useApp();
  // Campus students can switch editions; national-only users always see national.
  const [scope, setScope] = React.useState(mode === 'campus' ? 'campus' : 'national');
  const [tab, setTab] = React.useState('recent');
  const [posts, setPosts] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');
  const today = new Date().toLocaleDateString('en-GB', { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' });

  const ART_FOR_CATEGORY = {
    incident: 'protest', missing_person: 'building', road: 'road',
    safety: 'court', civic_event: 'building',
  };
  const KICKER_FOR_CATEGORY = {
    incident: 'Incident', missing_person: 'Missing Person',
    road: 'Road & Traffic', safety: 'Public Safety', civic_event: 'Civic Event',
  };

  function timeAgo(iso) {
    if (!iso) return '';
    const diff = (Date.now() - new Date(iso).getTime()) / 1000;
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    return Math.floor(diff / 86400) + 'd ago';
  }

  function toItem(p) {
    const scopeKey = p.scope === 'campus' ? 'campus' : 'country';
    const edition = scopeKey === 'campus' ? 'Campus' : 'National';
    const catLabel = KICKER_FOR_CATEGORY[p.category] || p.category;
    return {
      id: p.id,
      scope: scopeKey,
      art: ART_FOR_CATEGORY[p.category] || 'building',
      kicker: edition + ' · ' + catLabel,
      headline: p.title,
      byline: { author: 'Community Reporter', source: 'Anchor Verified Feed', when: timeAgo(p.created_at) },
      lead: '',
      corr: p.signal_counts?.corroborate ?? 0,
      chal: p.signal_counts?.challenge ?? 0,
      trusted: p.admin_confirmed,
    };
  }

  React.useEffect(() => {
    setLoading(true);
    setError('');
    const sort = tab === 'recent' ? 'recent' : 'corroborate';
    const token = localStorage.getItem('anchor_access_token');
    const headers = token ? { Authorization: 'Bearer ' + token } : {};
    fetch(`${_API}/v1/feed?scope=${scope}&sort=${sort}&page=1&page_size=30`, { headers })
      .then(r => {
        if (!r.ok) return r.json().then(d => { throw new Error(d.detail || 'Request failed'); });
        return r.json();
      })
      .then(data => {
        const items = Array.isArray(data) ? data : (data?.items ?? []);
        setPosts(items);
        setLoading(false);
      })
      .catch(() => { setPosts([]); setLoading(false); });
  }, [scope, tab]);

  const feedItems = posts.map(toItem);
  const visible = tab === 'trusted' ? feedItems.filter(it => it.trusted) : feedItems;
  const [hero, ...rest] = visible;

  return (
    <>
      <Header back/>

      {/* Masthead */}
      <div style={{ padding: '4px 20px 0' }}>
        <div className="masthead">
          <div>
            <div className="nameplate">
              The Anchor <em>Verified</em>
            </div>
            <div className="issue" style={{ marginTop: 2 }}>
              {scope === 'campus' ? 'Campus edition · Daffodil' : 'National edition · Bangladesh'} · {today}
            </div>
          </div>
          <div style={{ textAlign: 'right', flexShrink: 0, paddingLeft: 10 }}>
            <div className="eyebrow" style={{ fontSize: 9 }}>Vol. 1 · Live</div>
            <div className="serif" style={{ fontStyle: 'italic', fontSize: 10.5, color: 'var(--muted)', marginTop: 2 }}>
              Human-moderated
            </div>
          </div>
        </div>

        {/* Edition toggle — campus students can switch between editions */}
        {mode === 'campus' && (
          <div style={{ display: 'flex', gap: 6, margin: '8px 0 2px' }}>
            {[['national', 'National'], ['campus', 'Campus · DIU']].map(([s, l]) => (
              <button key={s} onClick={() => setScope(s)} style={{
                fontSize: 10, padding: '3px 11px', borderRadius: 999, fontWeight: 600, cursor: 'pointer',
                background: scope === s ? 'var(--brand)' : 'transparent',
                color: scope === s ? 'white' : 'var(--muted)',
                border: `1px solid ${scope === s ? 'var(--navy)' : 'var(--mist)'}`,
              }}>{l}</button>
            ))}
          </div>
        )}

        {/* Tabs */}
        <div className="tabbar" style={{ marginBottom: 4 }}>
          {[['top', 'Top stories'], ['recent', 'Latest'], ['trusted', 'Trusted only']].map(([k, l]) => (
            <button key={k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{l}</button>
          ))}
        </div>
      </div>

      <div style={{ padding: '14px 20px 28px' }}>
        {loading && (
          <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--muted)', fontSize: 13, fontFamily: 'var(--font-sans)' }}>
            Loading edition…
          </div>
        )}

        {!loading && visible.length === 0 && (
          <div style={{ textAlign: 'center', padding: '48px 0 32px', color: 'var(--muted)', fontSize: 13, fontFamily: 'var(--font-sans)' }}>
            <div style={{ fontSize: 22, marginBottom: 10 }}>📰</div>
            No published stories yet in this edition.
          </div>
        )}

        {!loading && visible.length > 0 && (
          <>
            {hero && <NewsFeature item={hero}/>}

            {rest.length > 0 && (
              <div className="news-rule">More from this edition</div>
            )}

            {rest.map(it => <NewsCard key={it.id} item={it}/>)}

            <div className="rule-fancy" style={{ marginTop: 22 }}>End of edition · {visible.length} verified items</div>
          </>
        )}
      </div>
    </>
  );
}

function useNewsSignals(item) {
  const [counts, setCounts] = React.useState({ corroborate: item.corr || 0, challenge: item.chal || 0, user_signal: null });
  const [busy, setBusy] = React.useState(false);
  const [sigErr, setSigErr] = React.useState('');

  async function signal(type) {
    if (!item.id || busy) return;
    if (!localStorage.getItem('anchor_access_token')) { setSigErr('Sign in to signal.'); return; }
    setBusy(true); setSigErr('');
    try {
      const data = await apiFetch(`/v1/feed/${item.id}/${type}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}),
      });
      if (data?.counts) setCounts(data.counts);
    } catch (e) { setSigErr(e.message || 'Could not record signal.'); }
    setBusy(false);
  }

  return { counts, busy, signal, sigErr };
}

function NewsFeature({ item }) {
  const { go } = useApp();
  const { counts, busy, signal, sigErr } = useNewsSignals(item);
  const userSig = counts.user_signal;

  const stripParts = [
    item.scope === 'campus' ? 'Anchor verified · Campus edition' : 'Anchor verified · National edition',
    item.byline.when,
    'Human-moderated',
  ];

  return (
    <article className="news-feature">
      <div className="news-strap">
        <span className="label">{stripParts[0]}</span>
        <span className="label" style={{ flex: 'none' }}>{stripParts[1].toUpperCase()}</span>
      </div>

      <div className="news-photo" onClick={() => item.id && go('feed-post', { id: item.id })} style={{ cursor: item.id ? 'pointer' : 'default' }}>
        <div className="news-photo-frame">
          <NewsArt variant={item.art}/>
        </div>
        <div className="news-photo-caption">
          <strong>Photo —</strong> {photoCaption(item)}
        </div>
      </div>

      <div className="news-decor" onClick={() => item.id && go('feed-post', { id: item.id })} style={{ cursor: item.id ? 'pointer' : 'default' }}>
        <span className="pre">{item.kicker}:</span>
        <span className="title" dangerouslySetInnerHTML={{ __html: decorateHeadline(item.headline) }}/>
      </div>

      <div className="news-byline">
        by <strong>{item.byline.author}</strong> · {item.byline.source}
      </div>

      <p className="news-lead-drop">{item.lead}</p>

      <div style={{ display: 'flex', gap: 6, marginTop: 12, flexWrap: 'wrap' }}>
        {item.trusted && <span className="pill" style={{ color: 'var(--gold)', borderColor: 'rgba(184,137,58,0.35)', background: 'rgba(184,137,58,0.08)' }}><IconBadge size={9}/> Trusted source</span>}
        <span className="pill pill-resolved"><IconCheck size={9} sw={3}/> Reviewed & published</span>
      </div>

      <div className="news-actions">
        <button
          className="news-act corr"
          onClick={() => signal('corroborate')}
          disabled={busy}
          style={{ background: userSig === 'corroborate' ? 'rgba(74,107,92,0.22)' : undefined, fontWeight: userSig === 'corroborate' ? 700 : undefined }}
        >
          <IconThumbUp size={13}/> Corroborate · {counts.corroborate}
        </button>
        <button
          className="news-act chal"
          onClick={() => signal('challenge')}
          disabled={busy}
          style={{ background: userSig === 'challenge' ? 'rgba(196,69,54,0.16)' : undefined, fontWeight: userSig === 'challenge' ? 700 : undefined }}
        >
          <IconThumbDown size={13}/> Challenge · {counts.challenge}
        </button>
      </div>
      {sigErr && <div style={{ marginTop: 6, fontSize: 11, color: 'var(--ember)' }}>{sigErr}</div>}
    </article>
  );
}

function NewsCard({ item }) {
  const { go } = useApp();
  const { counts, busy, signal, sigErr } = useNewsSignals(item);
  const userSig = counts.user_signal;

  return (
    <article className="news-card">
      <div className="news-photo" onClick={() => item.id && go('feed-post', { id: item.id })} style={{ cursor: item.id ? 'pointer' : 'default' }}>
        <div className="news-photo-frame">
          <NewsArt variant={item.art}/>
        </div>
        <div className="news-photo-caption">
          <strong>Photo —</strong> {photoCaption(item)}
        </div>
      </div>
      <div className="news-kicker" onClick={() => item.id && go('feed-post', { id: item.id })} style={{ cursor: item.id ? 'pointer' : 'default' }}>{item.kicker}</div>
      <h3 className="news-headline lg" onClick={() => item.id && go('feed-post', { id: item.id })} style={{ cursor: item.id ? 'pointer' : 'default' }}>{item.headline}</h3>
      <div className="news-byline">
        by <strong>{item.byline.author}</strong> · {item.byline.source} · {item.byline.when}
      </div>
      <p style={{ margin: 0, fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.55 }}>{item.lead}</p>
      <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
        {item.trusted && <span className="pill" style={{ color: 'var(--gold)', borderColor: 'rgba(184,137,58,0.35)', background: 'rgba(184,137,58,0.08)' }}><IconBadge size={9}/> Trusted</span>}
        <span className="pill pill-resolved"><IconCheck size={9} sw={3}/> Reviewed</span>
      </div>
      <div className="news-actions">
        <button
          className="news-act corr"
          onClick={() => signal('corroborate')}
          disabled={busy}
          style={{ background: userSig === 'corroborate' ? 'rgba(74,107,92,0.22)' : undefined, fontWeight: userSig === 'corroborate' ? 700 : undefined }}
        >
          <IconThumbUp size={13}/> Corroborate · {counts.corroborate}
        </button>
        <button
          className="news-act chal"
          onClick={() => signal('challenge')}
          disabled={busy}
          style={{ background: userSig === 'challenge' ? 'rgba(196,69,54,0.16)' : undefined, fontWeight: userSig === 'challenge' ? 700 : undefined }}
        >
          <IconThumbDown size={13}/> Challenge · {counts.challenge}
        </button>
      </div>
      {sigErr && <div style={{ marginTop: 6, fontSize: 11, color: 'var(--ember)' }}>{sigErr}</div>}
    </article>
  );
}

// Helper: photo captions matching the news art variant
function photoCaption(item) {
  const captions = {
    protest:  'crowd footage at the cordon, cross-checked against ministry briefing.',
    traffic:  'live view of the Mirpur-10 intersection during the disruption window.',
    court:    'the Cyber Tribunal building, where new fast-track hearings will be held.',
    road:     'street near the closed file location, marked on the Anchor red zone map.',
    building: 'campus administrative block — registration notice was issued from here.',
    library:  'the affected reading sections, photographed two days before closure.',
    mess:     'a recent meal at the Block C mess, used as evidence in the audit.',
  };
  return captions[item.art] || 'verified imagery from the Anchor newsroom.';
}

// Helper: wrap ampersands and em-dashes in italic spans so the display headline
// renders with mixed sizes the way a classic tabloid headline would
function decorateHeadline(text) {
  return text
    .replace(/&/g, '<span class="amp">&amp;</span>')
    .replace(/ — /g, '<span class="amp"> — </span>');
}

// ═══════════════════════════════════════════════════════════════
//  LAWYERS SCREEN
// ═══════════════════════════════════════════════════════════════
const LAWYER_AVATAR_COLORS = ['#4A6B5C', '#0B1D35', '#B8893A', '#C44536', '#5C6B4A', '#2D4A6B'];

function lawyerInitials(name) {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

function lawyerColor(id) {
  const n = parseInt(String(id).replace(/-/g, '').slice(0, 8), 16) || 0;
  return LAWYER_AVATAR_COLORS[n % LAWYER_AVATAR_COLORS.length];
}

function LawyersScreen() {
  const { go, auth } = useApp();
  const [lawyers, setLawyers] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError]   = React.useState('');
  const [starting, setStarting] = React.useState(null);

  React.useEffect(() => {
    fetch(`${_API}/v1/lawyers?verified_only=true`)
      .then(r => { if (!r.ok) throw new Error('Failed to load'); return r.json(); })
      .then(data => { setLawyers(data); setLoading(false); })
      .catch(() => { setError('Could not load lawyers. Check your connection.'); setLoading(false); });
  }, []);

  const startChat = async (l) => {
    if (!auth || !auth.isAuthenticated) { go('login'); return; }
    setStarting(l.id);
    try {
      if (window.E2EE) { try { await E2EE.ensureKeyPair(); } catch (e) {} }
      const conv = await apiFetch('/v1/conversations', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lawyer_id: l.id }),
      });
      go('chat-thread', { conv });
    } catch (e) {
      setError(e.message || 'Could not start chat.');
    } finally {
      setStarting(null);
    }
  };

  return (
    <>
      <Header back title="Find a Lawyer" subtitle="Verified · Bar-Council certified"/>

      <div style={{ padding: '14px 20px 6px' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px',
          background: 'var(--surface)', border: '1px solid var(--mist-2)', borderRadius: 999,
        }}>
          <IconSearch size={15} stroke="var(--muted)"/>
          <input placeholder="Search by name, specialty, location…" style={{
            flex: 1, border: 'none', outline: 'none', background: 'transparent',
            fontFamily: 'var(--font-sans)', fontSize: 13.5, color: 'var(--ink)',
          }}/>
        </div>

        <div style={{ display: 'flex', gap: 6, marginTop: 10, overflowX: 'auto' }} className="no-scrollbar">
          {['All', 'Criminal', 'Civil', 'Family', 'Constitutional', 'Cyber', 'DV Act'].map((f, i) => (
            <span key={f} style={{
              padding: '6px 11px', borderRadius: 999, whiteSpace: 'nowrap',
              background: i === 0 ? 'var(--brand)' : 'var(--surface)',
              color: i === 0 ? '#F7F3EE' : 'var(--ink-2)',
              border: '1px solid ' + (i === 0 ? 'var(--navy)' : 'var(--mist)'),
              fontSize: 11.5, fontWeight: 500, cursor: 'pointer',
            }}>{f}</span>
          ))}
        </div>
      </div>

      <div style={{ padding: '12px 20px 28px' }}>
        {loading && (
          <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--muted)', fontSize: 13, fontFamily: 'var(--font-sans)' }}>
            Loading lawyers…
          </div>
        )}
        {error && (
          <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--red)', fontSize: 13, fontFamily: 'var(--font-sans)' }}>
            {error}
          </div>
        )}
        {!loading && !error && lawyers.length === 0 && (
          <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--muted)', fontSize: 13, fontFamily: 'var(--font-sans)' }}>
            No lawyers found.
          </div>
        )}
        {lawyers.map((l) => (
          <div key={l.id} style={{
            padding: 14, background: 'var(--surface)',
            border: '1px solid var(--mist)', borderRadius: 14, marginBottom: 10,
          }}>
            <div style={{ display: 'flex', gap: 12 }}>
              <div style={{
                width: 52, height: 52, borderRadius: 12, flexShrink: 0,
                background: `linear-gradient(135deg, ${lawyerColor(l.id)}, ${lawyerColor(l.id)}cc)`,
                color: '#F7F3EE',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: 'var(--font-serif)', fontWeight: 500, fontSize: 18,
                border: '1px solid rgba(11,29,53,0.08)',
              }}>{lawyerInitials(l.name)}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div className="serif" style={{ fontSize: 15.5, fontWeight: 500, color: 'var(--navy)' }}>{l.name}</div>
                  {l.verified && (
                    <span title="Verified bar-council ID" style={{
                      width: 14, height: 14, borderRadius: 999, background: 'var(--gold)', color: '#fff',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}><IconCheck size={9} sw={3.2}/></span>
                  )}
                </div>
                {l.bar_number && (
                  <div className="mono" style={{ fontSize: 10.5, color: 'var(--muted)', marginTop: 1 }}>{l.bar_number}</div>
                )}
                {(l.specializations || []).length > 0 && (
                  <div style={{ display: 'flex', gap: 4, marginTop: 6, flexWrap: 'wrap' }}>
                    {l.specializations.map(s => (
                      <span key={s} style={{
                        padding: '2px 7px', borderRadius: 6, background: 'var(--cream-2)',
                        border: '1px solid var(--mist)', fontSize: 10, color: 'var(--ink-2)',
                      }}>{s}</span>
                    ))}
                  </div>
                )}
                {l.district && (
                  <div style={{ marginTop: 6, fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--font-sans)' }}>
                    {l.district}
                  </div>
                )}
              </div>
            </div>
            <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px dashed var(--mist)', display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 8 }}>
              {l.user_id ? (
                <button onClick={() => startChat(l)} disabled={starting === l.id} style={{
                  padding: '8px 12px', borderRadius: 10, background: 'var(--brand)', color: '#F7F3EE',
                  border: 'none', fontSize: 12, fontWeight: 500,
                  cursor: starting === l.id ? 'default' : 'pointer', opacity: starting === l.id ? 0.7 : 1,
                  display: 'inline-flex', alignItems: 'center', gap: 6,
                }}>
                  <IconLock size={12}/> {starting === l.id ? 'Starting…' : 'Start E2EE chat'}
                </button>
              ) : (
                <span style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--font-sans)' }}>Directory listing</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

// ═══════════════════════════════════════════════════════════════
//  NOTICES SCREEN
// ═══════════════════════════════════════════════════════════════
function NoticesScreen() {
  const TABS = ['All', 'University', 'Department', 'Batch'];
  const SCOPE_MAP = { All: null, University: 'university', Department: 'dept', Batch: 'batch' };

  const [tab, setTab] = React.useState('All');
  const [notices, setNotices] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');

  React.useEffect(() => {
    setLoading(true);
    setError('');
    const scope = SCOPE_MAP[tab];
    const qs = scope ? `?scope=${scope}&page=1` : '?page=1';
    const token = localStorage.getItem('anchor_access_token');
    const headers = token ? { Authorization: 'Bearer ' + token } : {};
    fetch(`${_API}/v1/notices${qs}`, { headers })
      .then(r => {
        if (!r.ok) return r.json().then(d => { throw new Error(d.detail || 'Request failed'); });
        return r.json();
      })
      .then(data => { setNotices(data); setLoading(false); })
      .catch(err => { setError(err.message || 'Could not load notices.'); setLoading(false); });
  }, [tab]);

  function tagLabel(n) {
    if (n.scope === 'university') return 'University-wide';
    if (n.scope === 'dept') return 'Department' + (n.dept ? ' · ' + n.dept : '');
    if (n.scope === 'batch') return 'Batch' + (n.batch ? ' · ' + n.batch : '');
    return n.scope;
  }

  function fmtDate(iso) {
    if (!iso) return '';
    try { return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' }); }
    catch { return iso; }
  }

  return (
    <>
      <Header back title="Notices" subtitle="University · Department · Batch"/>

      <div style={{ padding: '12px 20px 4px', display: 'flex', alignItems: 'center', gap: 8 }}>
        <div className="tabbar" style={{ flex: 1 }}>
          {TABS.map(t => (
            <button key={t} className={tab === t ? 'on' : ''} onClick={() => setTab(t)}>{t}</button>
          ))}
        </div>
      </div>

      <div style={{ padding: '8px 20px 28px' }}>
        {loading && (
          <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--muted)', fontSize: 13, fontFamily: 'var(--font-sans)' }}>
            Loading notices…
          </div>
        )}

        {!loading && error && (
          <div style={{ margin: '16px 0', padding: '14px 16px', background: 'rgba(232,49,42,0.06)', border: '1px solid rgba(232,49,42,0.2)', borderRadius: 12 }}>
            <div style={{ fontSize: 13, color: 'var(--red)', fontFamily: 'var(--font-sans)' }}>{error}</div>
            <div style={{ fontSize: 11.5, color: 'var(--muted)', marginTop: 4, fontFamily: 'var(--font-sans)' }}>
              Check that the backend server is running on port 8000.
            </div>
          </div>
        )}

        {!loading && !error && notices.length === 0 && (
          <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--muted)', fontSize: 13, fontFamily: 'var(--font-sans)' }}>
            No notices published yet for this category.
          </div>
        )}

        {!loading && !error && notices.map(n => (
          <div key={n.id} style={{ padding: '18px 0', borderBottom: '1px solid var(--mist)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span className="eyebrow">{tagLabel(n)}</span>
              <span style={{ width: 3, height: 3, borderRadius: 999, background: 'var(--mist-2)' }}/>
              <span className="mono" style={{ fontSize: 10.5, color: 'var(--muted)' }}>
                {fmtDate(n.published_at || n.created_at)}
              </span>
            </div>
            <div className="serif" style={{
              fontSize: 19, fontWeight: 500,
              lineHeight: 1.2, color: 'var(--navy)', letterSpacing: '-0.005em',
            }}>
              {n.title}
            </div>
            <div style={{ marginTop: 8, padding: '10px 12px', background: 'rgba(74,107,92,0.06)', border: '1px solid rgba(74,107,92,0.18)', borderRadius: 10 }}>
              <div style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.45 }}>
                {n.body.length > 280 ? n.body.slice(0, 280) + '…' : n.body}
              </div>
            </div>
            <div style={{ marginTop: 10 }}>
              <DownloadMenu
                path={`/v1/notices/${n.id}/export`}
                stem={`notice-${String(n.id).slice(0, 8)}`}
                label="Download notice"
                accent="var(--sage)"
              />
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

// ═══════════════════════════════════════════════════════════════
//  PROFILE SCREEN
// ═══════════════════════════════════════════════════════════════
function ProfileScreen() {
  const { go, logout, auth, geofenceConsent, setGeofenceConsent, login, lang, tr, theme, toggleTheme } = useApp();
  const darkOn = theme === 'dark';
  const user = auth && auth.user;
  const displayName = user ? user.name : '';
  const isStudent = user && user.role === 'student';
  const initials = displayName.split(' ').map(w => w[0]).filter(Boolean).slice(0, 2).join('').toUpperCase();

  const [editMode, setEditMode] = React.useState(false);
  const [saving, setSaving] = React.useState(false);
  const [saveError, setSaveError] = React.useState('');
  const [draftName, setDraftName] = React.useState('');
  const [draftPhone, setDraftPhone] = React.useState('');
  const [draftDept, setDraftDept] = React.useState('');

  // Push-notification opt-in. Driven by window.getPushCapability().reason so iOS /
  // insecure-context devices show actionable guidance instead of a dead-end toggle.
  // Values: 'granted'|'default'|'ok'|'denied'|'unsupported'|'ios-needs-install'|'ios-chrome'|'insecure-context'.
  const [pushState, setPushState] = React.useState(
    () => (window.getPushCapability ? window.getPushCapability().reason : 'unsupported')
  );
  const pushEnabled = pushState === 'granted';
  // Only environments where tapping can actually do something are interactive.
  const pushActionable = ['granted', 'default', 'ok', 'denied'].includes(pushState);
  const enablePush = async () => {
    if (!window.syncPushToken) { setPushState('unsupported'); return; }
    const r = await window.syncPushToken({ interactive: true });  // user-gesture call
    setPushState(
      r === 'granted' ? 'granted'
      : r === 'blocked' ? 'denied'
      : (window.getPushCapability ? window.getPushCapability().reason : r)
    );
  };
  const pushSubtext =
    pushState === 'granted'            ? 'Enabled on this device'
    : pushState === 'denied'           ? 'Blocked — allow notifications in your browser settings'
    : pushState === 'ios-needs-install' ? 'On iPhone: Share → Add to Home Screen, then open Anchor from the icon'
    : pushState === 'ios-chrome'       ? 'On iPhone, open Anchor in Safari, then Add to Home Screen'
    : pushState === 'insecure-context' ? 'Needs a secure (https) connection'
    : pushState === 'unsupported'      ? 'Not supported on this browser'
    : 'Tap to receive emergency push alerts';

  // Location consent toggle. Enabling must actually request geolocation permission
  // and post the first snapshot — otherwise the device is marked "consented" but
  // never appears in the fan-out (no fresh snapshot) and shows "no GPS" to operators.
  const [locBlocked, setLocBlocked] = React.useState(false);
  const locSubtext =
    locBlocked        ? 'Location blocked — enable it in your browser settings'
    : geofenceConsent ? 'Sharing anonymous location for alert fan-out'
    : 'Share anonymous location for alert fan-out';
  const toggleLocation = async () => {
    if (geofenceConsent) {
      localStorage.setItem('anchor_geofence_consent', 'false');
      localStorage.setItem('anchor_geofence_consent_answered', 'true');
      setGeofenceConsent(false);
      setLocBlocked(false);
      return;
    }
    const position = await new Promise((res) => {
      if (!navigator.geolocation) return res(null);
      navigator.geolocation.getCurrentPosition((p) => res(p), () => res(null),
        { timeout: 10000, maximumAge: 60000 });
    });
    if (!position) { setLocBlocked(true); return; }
    localStorage.setItem('anchor_geofence_consent', 'true');
    localStorage.setItem('anchor_geofence_consent_answered', 'true');
    setGeofenceConsent(true);
    setLocBlocked(false);
    const t = localStorage.getItem('anchor_access_token');
    if (t) {
      fetch((window.ANCHOR_API_URL || 'http://localhost:8000') + '/v1/users/me/location', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + t },
        body: JSON.stringify({ lat: position.coords.latitude, lng: position.coords.longitude, geofence_consent: true }),
      }).catch(() => {});
    }
  };

  // Per-device verification: send a real push to this account's devices and report
  // whether it was delivered, so the user can confirm push works on each one.
  const [testBusy, setTestBusy] = React.useState(false);
  const [testMsg, setTestMsg] = React.useState(null);
  const sendTestPush = async () => {
    setTestBusy(true);
    setTestMsg(null);
    try {
      // Make sure THIS device's token is freshly registered before testing —
      // self-heals a stale/never-registered token and binds the foreground
      // onMessage handler. Without this, the test could only ever reach devices
      // already in the DB (e.g. the PC), never the phone pressing the button.
      if (window.syncPushToken) {
        const sync = await window.syncPushToken({ interactive: true });
        if (sync !== 'granted') {
          const text =
            sync === 'blocked' || sync === 'denied'
              ? 'Blocked — allow notifications in your browser settings, then try again.'
            : sync === 'ios-needs-install'
              ? 'On iPhone: Share → Add to Home Screen, then open Anchor from the icon.'
            : sync === 'ios-chrome'
              ? 'On iPhone, open Anchor in Safari, then Add to Home Screen.'
            : sync === 'insecure-context'
              ? 'Needs a secure (https) connection.'
            : sync === 'unsupported'
              ? 'Notifications aren’t supported on this browser.'
              : 'Couldn’t enable notifications on this device — please try again.';
          setTestMsg({ ok: false, text });
          setTestBusy(false);
          return;
        }
      }
      const t = localStorage.getItem('anchor_access_token');
      const deviceId = localStorage.getItem('anchor_device_id');
      const url = (window.ANCHOR_API_URL || 'http://localhost:8000')
        + '/v1/users/me/fcm-token/test'
        + (deviceId ? '?device_id=' + encodeURIComponent(deviceId) : '');
      const res = await fetch(url, {
        method: 'POST',
        headers: { 'Authorization': 'Bearer ' + t },
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) setTestMsg({ ok: false, text: 'Could not send test — please try again.' });
      else if (!data.tokens) setTestMsg({ ok: false, text: 'No registered devices yet. Turn on notifications first.' });
      else if (data.delivered > 0) setTestMsg({ ok: true, text: 'Sent ✓ A notification should appear on this device.' });
      else {
        // Delivered to none — surface the actual reason the backend reported per device
        // instead of always blaming the toggle.
        const errs = (data.results || []).map(r => r.error).filter(Boolean);
        const cat = errs[0];
        const text =
          cat === 'unconfigured' ? 'Push isn’t set up on the server yet.'
          : (cat === 'unregistered' || cat === 'sender_id_mismatch')
              ? 'This device’s notification token expired — turn notifications off and on to refresh.'
          : cat === 'unavailable' ? 'Push service is busy — try again in a moment.'
          : 'Couldn’t deliver to this device — please try again.';
        setTestMsg({ ok: false, text });
      }
    } catch (_) {
      setTestMsg({ ok: false, text: 'Network error — please try again.' });
    }
    setTestBusy(false);
  };

  const enterEditMode = () => {
    setDraftName(user ? user.name || '' : '');
    setDraftPhone(user ? user.phone || '' : '');
    setDraftDept(user ? user.department || '' : '');
    setSaveError('');
    setEditMode(true);
  };

  const cancelEdit = () => {
    setEditMode(false);
    setSaveError('');
  };

  // Settings sheets + derived counts (re-read from localStorage on sheet close)
  const [sheet, setSheet] = React.useState(null); // 'notif' | 'contacts' | null
  const [prefsCount, setPrefsCount] = React.useState(() => notifPrefsOnCount());
  const [contactsCount, setContactsCount] = React.useState(() => loadTrustedContacts().length);
  const refreshCounts = () => {
    setPrefsCount(notifPrefsOnCount());
    setContactsCount(loadTrustedContacts().length);
  };
  const closeSheet = () => { setSheet(null); refreshCounts(); };

  const handleExport = () => {
    try {
      const data = {
        exported_at: new Date().toISOString(),
        app: 'Anchor AI',
        profile: user || null,
        language: lang,
        geofence_consent: geofenceConsent,
        notification_prefs: loadNotifPrefs(),
        trusted_contacts: loadTrustedContacts(),
      };
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'anchor-data-' + new Date().toISOString().slice(0, 10) + '.json';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) { console.warn('[Export] failed', e); }
  };

  const handleSave = async () => {
    const body = {};
    if (draftName.trim() && draftName.trim() !== (user && user.name)) body.full_name = draftName.trim();
    if (!(user && user.phone_verified) && draftPhone !== (user && user.phone || '')) body.phone = draftPhone || null;
    if (isStudent && draftDept !== (user && user.department || '')) body.department = draftDept || null;

    if (Object.keys(body).length === 0) {
      setEditMode(false);
      return;
    }
    setSaving(true);
    setSaveError('');
    try {
      const token = localStorage.getItem('anchor_access_token');
      const res = await fetch(`${_API}/auth/me`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': 'Bearer ' + token,
        },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) {
        setSaveError(data.detail || 'Save failed');
        return;
      }
      login({
        ...user,
        name:             data.full_name,
        phone:            data.phone,
        phone_verified:   data.phone_verified,
        email_verified:   data.email_verified,
        department:       data.department || null,
        total_filings:    data.total_filings ?? 0,
        resolved_filings: data.resolved_filings ?? 0,
      });
      setEditMode(false);
    } catch (err) {
      setSaveError(err.message || 'Network error');
    } finally {
      setSaving(false);
    }
  };

  const subtitle = isStudent
    ? (user && user.department ? `${user.department} · Daffodil International University` : 'Daffodil International University')
    : 'General Public · Bangladesh';

  const fieldStyle = {
    width: '100%', padding: '10px 13px', borderRadius: 10, border: '1px solid var(--mist-2)',
    background: 'var(--surface-solid)', fontFamily: 'var(--font-sans)', fontSize: 14, color: 'var(--navy)',
    outline: 'none', boxSizing: 'border-box',
  };
  const lockedFieldStyle = {
    padding: '10px 13px', borderRadius: 10, border: '1px solid var(--mist)',
    background: 'var(--cream-2)', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  };

  return (
    <>
      <Header back/>
      <div style={{ padding: '16px 20px 8px' }}>
        <div style={{
          padding: 18, borderRadius: 18, background: 'linear-gradient(180deg, var(--surface), var(--surface-2))',
          border: '1px solid var(--mist)',
        }}>
          {!editMode ? (
            <>
              <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
                <div style={{
                  width: 56, height: 56, borderRadius: 999, position: 'relative', flexShrink: 0,
                  background: 'linear-gradient(135deg, #C9B7A2, #8E7A60)',
                  color: '#F7F3EE', display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontFamily: 'var(--font-serif)', fontWeight: 500, fontSize: 22,
                }}>
                  {initials}
                  <span style={{
                    position: 'absolute', bottom: -2, right: -2, width: 20, height: 20, borderRadius: 999,
                    background: 'var(--gold)', color: '#fff', display: 'flex',
                    alignItems: 'center', justifyContent: 'center', border: '2.5px solid var(--cream)',
                  }}><IconCheck size={11} sw={3}/></span>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div className="serif" style={{ fontSize: 19, fontWeight: 500, color: 'var(--navy)', lineHeight: 1.1 }}>{displayName}</div>
                  <div style={{ marginTop: 4, fontSize: 12.5, color: 'var(--ink-2)' }}>{subtitle}</div>
                  <div style={{ marginTop: 6, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                    {isStudent && <span className="pill" style={{ color: 'var(--gold)', borderColor: 'rgba(184,137,58,0.35)', background: 'rgba(184,137,58,0.08)' }}><IconCheck size={9} sw={3}/> Verified DIU</span>}
                    {user && user.email_verified && <span className="pill" style={{ color: 'var(--sage)', borderColor: 'rgba(74,107,92,0.28)', background: 'rgba(74,107,92,0.07)' }}><IconCheck size={9} sw={3}/> Email verified</span>}
                  </div>
                </div>
              </div>

              {/* Stats */}
              <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px dashed var(--mist)', display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
                {[
                  { l: 'Cases filed', v: String(user && user.total_filings != null ? user.total_filings : 0) },
                  { l: 'Resolved',    v: String(user && user.resolved_filings != null ? user.resolved_filings : 0) },
                  { l: 'Trust score', v: '—' },
                ].map(s => (
                  <div key={s.l} style={{ textAlign: 'center' }}>
                    <div className="serif" style={{ fontSize: 22, fontWeight: 500, color: 'var(--navy)', letterSpacing: '-0.02em' }}>{s.v}</div>
                    <div className="eyebrow" style={{ marginTop: 2, fontSize: 9.5 }}>{s.l}</div>
                  </div>
                ))}
              </div>

              {/* Edit profile button */}
              <button
                onClick={enterEditMode}
                style={{
                  marginTop: 14, width: '100%', padding: '9px 0', borderRadius: 10,
                  border: '1px solid var(--mist-2)', background: 'rgba(11,29,53,0.04)',
                  cursor: 'pointer', fontFamily: 'var(--font-sans)', fontSize: 13.5, fontWeight: 500,
                  color: 'var(--navy)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                }}>
                Edit profile
              </button>
            </>
          ) : (
            <>
              <div style={{ marginBottom: 16, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--navy)', fontFamily: 'var(--font-sans)' }}>Edit profile</div>
                <button onClick={cancelEdit} style={{ border: 'none', background: 'none', cursor: 'pointer', color: 'var(--muted)', fontFamily: 'var(--font-sans)', fontSize: 13 }}>Cancel</button>
              </div>

              {/* Full name */}
              <div style={{ marginBottom: 12 }}>
                <div className="eyebrow" style={{ marginBottom: 5 }}>Full name</div>
                <input
                  style={fieldStyle}
                  value={draftName}
                  onChange={e => { setDraftName(e.target.value); setSaveError(''); }}
                  placeholder="Your full name"
                />
              </div>

              {/* Email — always locked */}
              <div style={{ marginBottom: 12 }}>
                <div className="eyebrow" style={{ marginBottom: 5 }}>Email</div>
                <div style={lockedFieldStyle}>
                  <div>
                    <div style={{ fontSize: 14, color: user && user.email ? 'var(--navy)' : 'var(--muted)' }}>
                      {user && user.email ? user.email : 'Not set'}
                    </div>
                    {user && user.email_verified && (
                      <div style={{ fontSize: 11, color: 'var(--sage)', marginTop: 2 }}>Verified</div>
                    )}
                  </div>
                  <IconLock size={14} stroke="var(--muted)"/>
                </div>
              </div>

              {/* Phone — locked if verified */}
              <div style={{ marginBottom: 12 }}>
                <div className="eyebrow" style={{ marginBottom: 5 }}>Phone number</div>
                {user && user.phone_verified ? (
                  <div style={lockedFieldStyle}>
                    <div>
                      <div style={{ fontSize: 14, color: 'var(--navy)' }}>{user.phone || 'Not set'}</div>
                      <div style={{ fontSize: 11, color: 'var(--sage)', marginTop: 2 }}>Verified — cannot change</div>
                    </div>
                    <IconLock size={14} stroke="var(--muted)"/>
                  </div>
                ) : (
                  <input
                    style={fieldStyle}
                    type="tel"
                    value={draftPhone}
                    onChange={e => { setDraftPhone(e.target.value); setSaveError(''); }}
                    placeholder="01XXXXXXXXX"
                  />
                )}
              </div>

              {/* Department — students only */}
              {isStudent && (
                <div style={{ marginBottom: 12 }}>
                  <div className="eyebrow" style={{ marginBottom: 5 }}>Department</div>
                  <input
                    style={fieldStyle}
                    value={draftDept}
                    onChange={e => { setDraftDept(e.target.value); setSaveError(''); }}
                    placeholder="e.g. Software Engineering"
                  />
                </div>
              )}

              {saveError && (
                <div style={{
                  marginBottom: 10, padding: '9px 12px', borderRadius: 10,
                  background: 'rgba(232,49,42,0.07)', border: '1px solid rgba(232,49,42,0.2)',
                  fontSize: 12.5, color: 'var(--red)', fontFamily: 'var(--font-sans)',
                }}>
                  {saveError}
                </div>
              )}

              <div style={{ display: 'flex', gap: 8, marginTop: 4 }}>
                <button
                  onClick={cancelEdit}
                  className="btn btn-ghost"
                  style={{ flex: 1, height: 42, borderRadius: 10, fontSize: 14 }}>
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="btn btn-primary"
                  style={{ flex: 2, height: 42, borderRadius: 10, fontSize: 14, opacity: saving ? 0.75 : 1 }}>
                  {saving ? 'Saving…' : 'Save changes'}
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Settings sections */}
      <div style={{ padding: '14px 20px 0' }}>
        <SettingsGroup title={tr('set_group_legal')} items={[
          { label: tr('set_messages'), value: tr('set_messages_val'), Icon: IconMessage, onTap: () => go('messages') },
          ...(!isStudent ? [{
            label: user && user.role === 'lawyer' ? tr('set_my_lawyer') : tr('set_apply_lawyer'),
            value: user && user.role === 'lawyer' ? tr('set_lawyer_verified') : tr('set_lawyer_pending'),
            Icon: IconScale,
            onTap: () => go('apply-lawyer'),
          }] : []),
        ]}/>
        {/* Language — upgraded to a 3-option control (Bangla / Both / English) */}
        <LanguageSetting/>
        {/* Appearance — light/dark theme toggle */}
        <div style={{ marginBottom: 16 }}>
          <div className="eyebrow" style={{ marginBottom: 8 }}>{tr('set_group_appearance')}</div>
          <div style={{ background:'var(--surface)', border:'1px solid var(--mist)',
                        borderRadius:14, padding:'12px 14px',
                        display:'flex', alignItems:'center', justifyContent:'space-between' }}>
            <div style={{ display:'flex', alignItems:'center', gap:12, minWidth:0 }}>
              <div style={{ width:30, height:30, borderRadius:8, flexShrink:0,
                            background:'var(--cream-2)', border:'1px solid var(--mist)',
                            color:'var(--navy)', display:'flex', alignItems:'center', justifyContent:'center' }}>
                {darkOn ? <IconMoon size={15}/> : <IconSun size={15}/>}
              </div>
              <div style={{ minWidth:0 }}>
                <div style={{ fontSize:14, fontWeight:500, color:'var(--navy)', fontFamily:'var(--font-sans)' }}>
                  {tr('set_dark_mode')}
                </div>
                <div style={{ fontSize:12, color:'var(--muted)', fontFamily:'var(--font-sans)', marginTop:2 }}>
                  {darkOn ? tr('set_dark_mode_on') : tr('set_dark_mode_off')}
                </div>
              </div>
            </div>
            <button onClick={toggleTheme} role="switch" aria-checked={darkOn} aria-label={tr('set_dark_mode')}
              style={{ width:44, height:26, borderRadius:999, border:'none', cursor:'pointer', flexShrink:0,
                       background: darkOn ? 'var(--sage)' : 'var(--mist)', position:'relative',
                       transition:'background 0.2s' }}>
              <span style={{ position:'absolute', top:3, left: darkOn ? 21 : 3,
                             width:20, height:20, borderRadius:999, background:'#fff',
                             boxShadow:'0 1px 3px rgba(0,0,0,0.18)', transition:'left 0.2s' }}/>
            </button>
          </div>
        </div>
        <SettingsGroup title={tr('set_group_prefs')} items={[
          { label: tr('set_notifications'),  value: prefsCount + ' of 5 on',  Icon: IconBell, onTap: () => setSheet('notif') },
          { label: tr('set_anonymity'),      value: tr('set_anonymity_val'),  Icon: IconEyeOff },
        ]}/>
        <SettingsGroup title={tr('set_group_safety')} items={[
          { label: tr('set_dms'),            value: 'Active · 48h',     Icon: IconShield, accent: 'var(--ember)' },
          { label: tr('set_2fa'),            value: user && user.mfa ? 'TOTP · enabled' : tr('set_2fa_off'),   Icon: IconLock,   onTap: () => go('mfa-setup') },
          { label: tr('set_contacts'),       value: contactsCount === 1 ? '1 set' : contactsCount + ' set', Icon: IconPhone, onTap: () => setSheet('contacts') },
        ]}/>
        <SettingsGroup title={tr('set_group_data')} items={[
          { label: tr('set_export'),         value: 'JSON',             Icon: IconUpload, onTap: handleExport },
          { label: tr('set_delete'),         value: tr('set_delete_val'),         Icon: IconX, danger: true },
        ]}/>
        {/* Location consent */}
        <div style={{ marginBottom: 16 }}>
          <div className="eyebrow" style={{ marginBottom: 8 }}>{tr('set_group_location')}</div>
          <div style={{ background:'var(--surface)', border:'1px solid var(--mist)',
                        borderRadius:14, padding:'12px 14px',
                        display:'flex', alignItems:'center', justifyContent:'space-between' }}>
            <div>
              <div style={{ fontSize:14, fontWeight:500, color:'var(--navy)', fontFamily:'var(--font-sans)' }}>
                {tr('set_nearby_alerts')}
              </div>
              <div style={{ fontSize:12, color: locBlocked ? 'var(--red)' : 'var(--muted)',
                            fontFamily:'var(--font-sans)', marginTop:2 }}>
                {locSubtext}
              </div>
            </div>
            <button onClick={toggleLocation}
              style={{ width:44, height:26, borderRadius:999, border:'none', cursor:'pointer', flexShrink:0,
                       background: geofenceConsent ? 'var(--sage)' : 'var(--mist)', position:'relative',
                       transition:'background 0.2s' }}>
              <span style={{ position:'absolute', top:3, left: geofenceConsent ? 21 : 3,
                             width:20, height:20, borderRadius:999, background:'#fff',
                             boxShadow:'0 1px 3px rgba(0,0,0,0.18)', transition:'left 0.2s' }}/>
            </button>
          </div>
        </div>
        {/* Push notifications consent */}
        <div style={{ marginBottom: 16 }}>
          <div className="eyebrow" style={{ marginBottom: 8 }}>{tr('set_group_notifications')}</div>
          <div style={{ background:'var(--surface)', border:'1px solid var(--mist)',
                        borderRadius:14, padding:'12px 14px',
                        display:'flex', alignItems:'center', justifyContent:'space-between' }}>
            <div>
              <div style={{ fontSize:14, fontWeight:500, color:'var(--navy)', fontFamily:'var(--font-sans)' }}>
                {tr('set_safety_notif')}
              </div>
              <div style={{ fontSize:12, color: pushState === 'denied' ? 'var(--red)' : 'var(--muted)',
                            fontFamily:'var(--font-sans)', marginTop:2 }}>
                {pushSubtext}
              </div>
            </div>
            <button onClick={enablePush} disabled={!pushActionable}
              style={{ width:44, height:26, borderRadius:999, border:'none', flexShrink:0,
                       cursor: !pushActionable ? 'not-allowed' : 'pointer',
                       opacity: !pushActionable ? 0.5 : 1,
                       background: pushEnabled ? 'var(--sage)' : 'var(--mist)', position:'relative',
                       transition:'background 0.2s' }}>
              <span style={{ position:'absolute', top:3, left: pushEnabled ? 21 : 3,
                             width:20, height:20, borderRadius:999, background:'#fff',
                             boxShadow:'0 1px 3px rgba(0,0,0,0.18)', transition:'left 0.2s' }}/>
            </button>
          </div>
          {/* Per-device verification */}
          {pushEnabled && (
            <div style={{ marginTop: 10, display:'flex', alignItems:'center', gap:12, flexWrap:'wrap' }}>
              <button onClick={sendTestPush} disabled={testBusy}
                style={{ height:34, padding:'0 14px', borderRadius:10, border:'1px solid var(--mist-2)',
                         background:'transparent', color:'var(--navy)', fontSize:12.5, fontWeight:600,
                         cursor: testBusy ? 'default' : 'pointer', opacity: testBusy ? 0.7 : 1,
                         fontFamily:'var(--font-sans)' }}>
                {testBusy ? 'Sending…' : 'Send test notification'}
              </button>
              {testMsg && (
                <span style={{ fontSize:12, fontFamily:'var(--font-sans)',
                               color: testMsg.ok ? 'var(--sage)' : 'var(--red)' }}>
                  {testMsg.text}
                </span>
              )}
            </div>
          )}
        </div>
        {/* Sign out */}
        <div style={{ marginBottom: 16 }}>
          <button onClick={logout} style={{
            width: '100%', padding: '13px 16px', borderRadius: 14, cursor: 'pointer',
            background: 'rgba(232,49,42,0.06)', border: '1px solid rgba(232,49,42,0.18)',
            display: 'flex', alignItems: 'center', gap: 10,
          }}>
            <div style={{
              width: 30, height: 30, borderRadius: 8, flexShrink: 0,
              background: 'rgba(232,49,42,0.08)', border: '1px solid rgba(232,49,42,0.2)',
              color: 'var(--red)', display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}><IconArrowLeft size={15}/></div>
            <div style={{ textAlign: 'left' }}>
              <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--red)', fontFamily: 'var(--font-sans)' }}>Sign out</div>
              <div style={{ fontSize: 11.5, color: 'var(--muted)', fontFamily: 'var(--font-sans)' }}>All devices will be logged out</div>
            </div>
          </button>
        </div>
      </div>

      <div style={{ padding: '6px 20px 32px', textAlign: 'center' }}>
        <div className="serif" style={{ fontStyle: 'italic', fontSize: 12, color: 'var(--muted)' }}>
          Anchor AI v0.4 · build 2026-05-23
        </div>
        <div style={{ marginTop: 4, fontSize: 10.5, color: 'var(--muted)', letterSpacing: '0.06em' }}>
          Built by Team AiVion · Daffodil International University
        </div>
      </div>

      {sheet === 'notif' && <NotifPrefsSheet onClose={closeSheet}/>}
      {sheet === 'contacts' && <TrustedContactsSheet onClose={closeSheet}/>}
    </>
  );
}

// Language picker — 3-option segmented control (Bangla / Both / English).
// "Both" (BI) is bilingual/mixed: English UI chrome + Bangla AI/content.
function LanguageSetting() {
  const { lang, setLang, tr } = useApp();
  const opts = [
    { v: 'BN', label: 'বাংলা',   sub: 'Bangla' },
    { v: 'BI', label: 'Both',    sub: 'Mixed' },
    { v: 'EN', label: 'English', sub: 'English' },
  ];
  const isBangla = (s) => /[ঀ-৿]/.test(s);
  return (
    <div style={{ marginBottom: 16 }}>
      <div className="eyebrow" style={{ marginBottom: 8 }}>{tr('lang_title')}</div>
      <div style={{ background: 'var(--surface)', border: '1px solid var(--mist)', borderRadius: 14, padding: 14 }}>
        <div className={isBangla(tr('lang_question')) ? 'serif bn' : 'serif'}
             style={{ fontSize: 15, fontWeight: 500, color: 'var(--navy)' }}>
          {tr('lang_question')}
        </div>
        <div className={isBangla(tr('lang_switch_anytime')) ? 'bn' : undefined}
             style={{ fontSize: 12, color: 'var(--muted)', marginTop: 3, fontFamily: 'var(--font-sans)' }}>
          {tr('lang_switch_anytime')}
        </div>
        <div role="radiogroup" aria-label={tr('lang_title')}
             style={{ marginTop: 12, padding: 4, borderRadius: 12, background: 'var(--cream-2)',
                      display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 4 }}>
          {opts.map(opt => {
            const active = lang === opt.v;
            return (
              <button key={opt.v} role="radio" aria-checked={active} onClick={() => setLang(opt.v)}
                style={{
                  padding: '9px 6px', borderRadius: 9, border: 'none', cursor: 'pointer',
                  background: active ? 'var(--brand)' : 'transparent',
                  color: active ? '#fff' : 'var(--navy)',
                  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
                  transition: 'background 0.18s, color 0.18s',
                }}>
                <span className={isBangla(opt.label) ? 'bn' : undefined} style={{ fontSize: 13, fontWeight: 600 }}>{opt.label}</span>
                <span style={{ fontSize: 9, opacity: active ? 0.75 : 0.5, fontWeight: 500,
                               letterSpacing: '0.04em', fontFamily: 'var(--font-sans)' }}>{opt.sub}</span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function SettingsGroup({ title, items }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div className="eyebrow" style={{ marginBottom: 8 }}>{title}</div>
      <div style={{
        background: 'var(--surface)', border: '1px solid var(--mist)',
        borderRadius: 14, overflow: 'hidden',
      }}>
        {items.map((it, i) => {
          const Ico = it.Icon;
          return (
            <div key={i} onClick={it.onTap} style={{
              display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px',
              borderBottom: i < items.length - 1 ? '1px solid var(--mist)' : 'none',
              cursor: it.onTap ? 'pointer' : 'default',
            }}>
              <div style={{
                width: 30, height: 30, borderRadius: 8,
                background: it.danger ? 'rgba(232,49,42,0.08)' : 'var(--cream-2)',
                color: it.danger ? 'var(--red)' : (it.accent || 'var(--navy)'),
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                border: '1px solid ' + (it.danger ? 'rgba(232,49,42,0.2)' : 'var(--mist)'),
              }}><Ico size={15}/></div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 500, color: it.danger ? 'var(--red)' : 'var(--navy)' }}>{it.label}</div>
                <div style={{ fontSize: 11.5, color: 'var(--muted)' }}>{it.value}</div>
              </div>
              <IconChevronRight size={14} stroke="var(--mist-2)"/>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
//  NOTIFICATIONS CENTER + SETTINGS SHEETS
// ═══════════════════════════════════════════════════════════════

var NOTIF_TYPE_META = {
  alert:  { Icon: IconShield, color: 'var(--red)',   bg: 'rgba(232,49,42,0.08)',  bd: 'rgba(232,49,42,0.2)' },
  case:   { Icon: IconFile,   color: 'var(--navy)',  bg: 'var(--cream-2)',        bd: 'var(--mist)' },
  notice: { Icon: IconNews,   color: 'var(--gold)',  bg: 'rgba(184,137,58,0.1)',  bd: 'rgba(184,137,58,0.25)' },
  rating: { Icon: IconStar,   color: 'var(--gold)',  bg: 'rgba(184,137,58,0.1)',  bd: 'rgba(184,137,58,0.25)' },
  lawyer: { Icon: IconGavel,  color: 'var(--sage)',  bg: 'rgba(74,107,92,0.08)',  bd: 'rgba(74,107,92,0.2)' },
  zone:   { Icon: IconMap,    color: 'var(--ember)', bg: 'rgba(196,69,54,0.08)',  bd: 'rgba(196,69,54,0.2)' },
};

function NotificationsScreen() {
  const { mode, go } = useApp();
  const [items, setItems] = React.useState(function () { return loadNotifications(mode); });

  React.useEffect(function () { setItems(loadNotifications(mode)); }, [mode]);

  const handleMarkAll = () => setItems(markAllNotificationsRead(mode));
  const handleTap = (n) => {
    const updated = items.map(x => x.id === n.id ? Object.assign({}, x, { read: true }) : x);
    saveNotifications(updated, mode);
    setItems(updated);
    if (n.route) go(n.route, n.params || {});
  };

  const hasUnread = items.some(n => !n.read);
  const today = items.filter(n => notifIsToday(n.ts));
  const earlier = items.filter(n => !notifIsToday(n.ts));

  const renderRow = (n, i, arr) => {
    const meta = NOTIF_TYPE_META[n.type] || NOTIF_TYPE_META.case;
    const Ico = meta.Icon;
    return (
      <div key={n.id} onClick={() => handleTap(n)} style={{
        display: 'flex', gap: 12, padding: '13px 14px', cursor: 'pointer',
        borderBottom: i < arr.length - 1 ? '1px solid var(--mist)' : 'none',
        background: n.read ? 'transparent' : 'rgba(74,107,92,0.05)',
      }}>
        <div style={{
          width: 34, height: 34, borderRadius: 9, flexShrink: 0, background: meta.bg,
          border: '1px solid ' + meta.bd, color: meta.color,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}><Ico size={16}/></div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <div style={{ fontSize: 14, fontWeight: n.read ? 500 : 600, color: 'var(--navy)',
                          fontFamily: 'var(--font-sans)', flex: 1, minWidth: 0 }}>{n.title}</div>
            {!n.read && <span style={{ width: 7, height: 7, borderRadius: 999, background: 'var(--red)', flexShrink: 0 }}/>}
          </div>
          <div style={{ fontSize: 12.5, color: 'var(--muted)', fontFamily: 'var(--font-sans)', marginTop: 3, lineHeight: 1.45 }}>{n.body}</div>
          <div style={{ fontSize: 11, color: 'var(--mist-2)', marginTop: 5, fontFamily: 'var(--font-sans)' }}>{notifRelTime(n.ts)}</div>
        </div>
      </div>
    );
  };

  return (
    <>
      <Header back/>
      <div style={{ padding: '4px 20px 8px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
        <h1 className="h-display" style={{ margin: 0, fontSize: 26, lineHeight: 1.1 }}>Notifications</h1>
        {hasUnread && (
          <button onClick={handleMarkAll} style={{
            border: 'none', background: 'none', cursor: 'pointer', color: 'var(--sage)',
            fontFamily: 'var(--font-sans)', fontSize: 13, fontWeight: 600,
            display: 'flex', alignItems: 'center', gap: 5, flexShrink: 0, whiteSpace: 'nowrap',
          }}><IconCheck size={13} sw={3}/> Mark all read</button>
        )}
      </div>

      {items.length === 0 ? (
        <div style={{ padding: '48px 28px', textAlign: 'center' }}>
          <div style={{
            width: 54, height: 54, borderRadius: 999, margin: '0 auto 14px',
            background: 'var(--cream-2)', border: '1px solid var(--mist)', color: 'var(--mist-2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}><IconBell size={24}/></div>
          <div className="serif" style={{ fontSize: 17, color: 'var(--navy)' }}>You're all caught up</div>
          <div style={{ fontSize: 13, color: 'var(--muted)', marginTop: 6, fontFamily: 'var(--font-sans)' }}>
            New alerts, case updates and notices will appear here.
          </div>
        </div>
      ) : (
        <div style={{ padding: '8px 20px 0' }}>
          {today.length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <div className="eyebrow" style={{ marginBottom: 8 }}>Today</div>
              <div style={{ background: 'var(--surface)', border: '1px solid var(--mist)', borderRadius: 14, overflow: 'hidden' }}>
                {today.map((n, i) => renderRow(n, i, today))}
              </div>
            </div>
          )}
          {earlier.length > 0 && (
            <div style={{ marginBottom: 14 }}>
              <div className="eyebrow" style={{ marginBottom: 8 }}>Earlier</div>
              <div style={{ background: 'var(--surface)', border: '1px solid var(--mist)', borderRadius: 14, overflow: 'hidden' }}>
                {earlier.map((n, i) => renderRow(n, i, earlier))}
              </div>
            </div>
          )}
        </div>
      )}
    </>
  );
}

// Bottom-sheet shell — tap-outside to close; fixed within the scaled phone frame
function BottomSheet({ title, onClose, children }) {
  return (
    <div onClick={onClose} style={{
      position: 'fixed', inset: 0, zIndex: 9999, background: 'rgba(11,29,53,0.55)',
      backdropFilter: 'blur(4px)', WebkitBackdropFilter: 'blur(4px)',
      display: 'flex', alignItems: 'flex-end', justifyContent: 'center',
    }}>
      <div onClick={e => e.stopPropagation()} style={{
        background: 'var(--cream)', borderRadius: '24px 24px 0 0', padding: '14px 22px 30px',
        width: '100%', maxWidth: 402, maxHeight: '82%', overflowY: 'auto', boxSizing: 'border-box',
      }}>
        <div style={{ width: 40, height: 4, borderRadius: 999, background: 'var(--mist)', margin: '0 auto 16px' }}/>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
          <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--navy)', fontFamily: 'var(--font-serif)' }}>{title}</div>
          <button onClick={onClose} aria-label="Close" style={{
            border: 'none', background: 'none', cursor: 'pointer', color: 'var(--muted)', padding: 4, display: 'flex',
          }}><IconX size={18}/></button>
        </div>
        {children}
      </div>
    </div>
  );
}

function ToggleRow({ label, sub, on, onToggle, accent }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 0', borderBottom: '1px solid var(--mist)' }}>
      <div style={{ flex: 1, paddingRight: 12 }}>
        <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--navy)', fontFamily: 'var(--font-sans)' }}>{label}</div>
        {sub && <div style={{ fontSize: 11.5, color: 'var(--muted)', fontFamily: 'var(--font-sans)', marginTop: 2 }}>{sub}</div>}
      </div>
      <button onClick={onToggle} aria-pressed={on} style={{
        width: 44, height: 26, borderRadius: 999, border: 'none', cursor: 'pointer', flexShrink: 0,
        background: on ? (accent || 'var(--sage)') : 'var(--mist)', position: 'relative', transition: 'background 0.2s',
      }}>
        <span style={{ position: 'absolute', top: 3, left: on ? 21 : 3, width: 20, height: 20, borderRadius: 999,
                       background: '#fff', boxShadow: '0 1px 3px rgba(0,0,0,0.18)', transition: 'left 0.2s' }}/>
      </button>
    </div>
  );
}

function NotifPrefsSheet({ onClose }) {
  const [prefs, setPrefs] = React.useState(function () { return loadNotifPrefs(); });
  const toggle = (k) => {
    const next = Object.assign({}, prefs, { [k]: !prefs[k] });
    saveNotifPrefs(next);
    setPrefs(next);
  };
  const rows = [
    { k: 'alerts',    label: 'Emergency alerts', sub: 'Nearby alerts and SOS fan-out', accent: 'var(--red)' },
    { k: 'cases',     label: 'Case updates',     sub: 'Status changes on your filings' },
    { k: 'notices',   label: 'Campus notices',   sub: 'Routines, announcements, events' },
    { k: 'feed',      label: 'Verification feed', sub: 'Replies and signals on your posts' },
    { k: 'marketing', label: 'Product news',     sub: 'Occasional updates from Anchor' },
  ];
  return (
    <BottomSheet title="Notifications" onClose={onClose}>
      <p style={{ fontSize: 12.5, color: 'var(--muted)', fontFamily: 'var(--font-sans)', lineHeight: 1.55, margin: '0 0 8px' }}>
        Choose what Anchor notifies you about.
      </p>
      {rows.map(r => (
        <ToggleRow key={r.k} label={r.label} sub={r.sub} on={!!prefs[r.k]} accent={r.accent} onToggle={() => toggle(r.k)}/>
      ))}
      <button onClick={onClose} className="btn btn-primary" style={{ marginTop: 18, width: '100%', height: 44, borderRadius: 11, fontSize: 14 }}>Done</button>
    </BottomSheet>
  );
}

function TrustedContactsSheet({ onClose }) {
  const [contacts, setContacts] = React.useState(function () { return loadTrustedContacts(); });
  const [name, setName] = React.useState('');
  const [phone, setPhone] = React.useState('');
  const [relation, setRelation] = React.useState('');
  const [err, setErr] = React.useState('');

  const fieldStyle = {
    width: '100%', padding: '10px 13px', borderRadius: 10, border: '1px solid var(--mist-2)',
    background: 'var(--surface-solid)', fontFamily: 'var(--font-sans)', fontSize: 14, color: 'var(--navy)', outline: 'none', boxSizing: 'border-box',
  };
  const persist = (list) => { saveTrustedContacts(list); setContacts(list); };

  const addContact = () => {
    const nm = name.trim(), ph = phone.trim();
    if (!nm) { setErr('Name is required'); return; }
    if (!/^01[3-9]\d{8}$/.test(ph)) { setErr('Enter a valid BD phone (01XXXXXXXXX)'); return; }
    if (contacts.some(c => c.phone === ph)) { setErr('That number is already added'); return; }
    persist(contacts.concat([{ id: 'tc_' + Date.now(), name: nm, phone: ph, relation: relation.trim() }]));
    setName(''); setPhone(''); setRelation(''); setErr('');
  };
  const removeContact = (id) => persist(contacts.filter(c => c.id !== id));

  return (
    <BottomSheet title="Trusted contacts" onClose={onClose}>
      <p style={{ fontSize: 12.5, color: 'var(--muted)', fontFamily: 'var(--font-sans)', lineHeight: 1.55, margin: '0 0 14px' }}>
        These people are notified when you trigger an emergency alert or your Dead Man's Switch fires.
      </p>
      {contacts.length === 0 ? (
        <div style={{ padding: 14, borderRadius: 12, border: '1px dashed var(--mist)', background: 'var(--cream-2)',
                      textAlign: 'center', fontSize: 13, color: 'var(--muted)', fontFamily: 'var(--font-sans)', marginBottom: 16 }}>
          No trusted contacts yet
        </div>
      ) : (
        <div style={{ marginBottom: 16, display: 'flex', flexDirection: 'column', gap: 8 }}>
          {contacts.map(c => (
            <div key={c.id} style={{ display: 'flex', alignItems: 'center', gap: 11, padding: '10px 12px', borderRadius: 12,
                                     background: 'var(--surface)', border: '1px solid var(--mist)' }}>
              <div style={{ width: 34, height: 34, borderRadius: 999, flexShrink: 0, background: 'var(--cream-2)',
                            border: '1px solid var(--mist)', color: 'var(--sage)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <IconPhone size={15}/>
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--navy)', fontFamily: 'var(--font-sans)' }}>{c.name}</div>
                <div style={{ fontSize: 12, color: 'var(--muted)', fontFamily: 'var(--font-sans)' }}>
                  {c.phone}{c.relation ? ' · ' + c.relation : ''}
                </div>
              </div>
              <button onClick={() => removeContact(c.id)} aria-label="Remove contact" style={{
                border: 'none', background: 'none', cursor: 'pointer', color: 'var(--muted)', padding: 6, flexShrink: 0, display: 'flex',
              }}><IconX size={16}/></button>
            </div>
          ))}
        </div>
      )}

      <div className="eyebrow" style={{ marginBottom: 8 }}>Add a contact</div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <input style={fieldStyle} value={name} onChange={e => { setName(e.target.value); setErr(''); }} placeholder="Full name"/>
        <input style={fieldStyle} type="tel" value={phone} onChange={e => { setPhone(e.target.value); setErr(''); }} placeholder="01XXXXXXXXX"/>
        <input style={fieldStyle} value={relation} onChange={e => setRelation(e.target.value)} placeholder="Relation (optional) — e.g. Sibling"/>
      </div>
      {err && (
        <div style={{ marginTop: 10, padding: '9px 12px', borderRadius: 10, background: 'rgba(232,49,42,0.07)',
                      border: '1px solid rgba(232,49,42,0.2)', fontSize: 12.5, color: 'var(--red)', fontFamily: 'var(--font-sans)' }}>{err}</div>
      )}
      <button onClick={addContact} className="btn btn-primary" style={{
        marginTop: 12, width: '100%', height: 44, borderRadius: 11, fontSize: 14,
        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
      }}><IconPlus size={15}/> Add contact</button>
    </BottomSheet>
  );
}

// ═══════════════════════════════════════════════════════════════
//  ROUTINES SCREEN — day-grouped cards, EN/BN, offline fallback
// ═══════════════════════════════════════════════════════════════
var _ROUTINE_DAY_ORDER = ['Sat','Sun','Mon','Tue','Wed','Thu'];
var _BN_DAYS = { Sat:'শনিবার', Sun:'রবিবার', Mon:'সোমবার', Tue:'মঙ্গলবার', Wed:'বুধবার', Thu:'বৃহস্পতিবার' };
var _ROUTINE_L = {
  EN: {
    title:'Academic Routine', subtitle:'Your class schedule',
    noData:'No routines published yet',
    noDataSub:"Your admin hasn't published a schedule yet. Check back later.",
    offline:'Offline — showing demo schedule',
    loading:'Loading…',
  },
  BN: {
    title:'শিক্ষার সময়সূচী', subtitle:'আপনার ক্লাস রুটিন',
    noData:'এখনো কোনো রুটিন প্রকাশিত হয়নি',
    noDataSub:'অ্যাডমিন এখনো সময়সূচী প্রকাশ করেননি।',
    offline:'অফলাইন — ডেমো রুটিন দেখানো হচ্ছে',
    loading:'লোড হচ্ছে…',
  },
};
var _MOCK_ROUTINE = {
  id:'mock', title:'SWE — Batch 41, Section A (Demo)',
  department:'SWE', batch:'Batch 41', semester:'Spring 2026',
  slots:[
    { day:'Sat', time:'8:30-10:00',  course:'SE223',  course_name:'Algorithm Design',      room:'KT-701A', teacher:'Dr. DEH' },
    { day:'Sat', time:'10:00-11:30', course:'CS101',  course_name:'OOP',                   room:'KT-601',  teacher:'Dr. JC'  },
    { day:'Sun', time:'8:30-10:00',  course:'ENG101', course_name:'English',                room:'KT-501',  teacher:'Ms. RA'  },
    { day:'Mon', time:'11:30-1:00',  course:'SE224',  course_name:'SE Practice (Lab)',      room:'LAB-903', teacher:'Dr. DEH' },
    { day:'Wed', time:'2:30-4:00',   course:'GE235',  course_name:'Discrete Mathematics',  room:'KT-601',  teacher:'Dr. SM'  },
  ],
};

function RoutinesScreen() {
  var appCtx = useApp ? useApp() : {};
  // Day-names / labels are content → Bangla in both BN and BI (mixed) modes.
  var lang = (typeof contentLang === 'function') ? contentLang(appCtx.lang)
                                                 : ((appCtx.lang === 'BN' || appCtx.lang === 'BI') ? 'BN' : 'EN');
  var L = _ROUTINE_L[lang];
  var fontBN = lang === 'BN' ? { fontFamily: 'var(--font-bn, inherit)' } : {};

  var [routines, setRoutines] = React.useState([]);
  var [loading, setLoading] = React.useState(true);
  var [offline, setOffline] = React.useState(false);

  React.useEffect(function() {
    setLoading(true); setOffline(false);
    var fetch$ = (typeof apiFetch === 'function')
      ? apiFetch('/v1/routines?page=1')
      : (function() {
          var token = localStorage.getItem('anchor_access_token');
          var headers = token ? { Authorization: 'Bearer ' + token } : {};
          return fetch(`${_API}/v1/routines?page=1`, { headers })
            .then(function(r) {
              if (!r.ok) return r.json().then(function(d) { throw new Error(d.detail || 'Request failed'); });
              return r.json();
            });
        })();

    fetch$
      .then(function(data) { setRoutines(Array.isArray(data) ? data : []); setLoading(false); })
      .catch(function() { setRoutines([_MOCK_ROUTINE]); setOffline(true); setLoading(false); });
  }, []);

  function groupByDay(slots) {
    var m = {};
    _ROUTINE_DAY_ORDER.forEach(function(d) { m[d] = []; });
    (slots || []).forEach(function(s) { var d = s.day || ''; if (m[d]) m[d].push(s); });
    return m;
  }

  function fmtDate(iso) {
    if (!iso) return '';
    try { return new Date(iso).toLocaleDateString('en-US', { month:'short', day:'numeric', year:'numeric' }); }
    catch(e) { return iso; }
  }

  return (
    React.createElement(React.Fragment, null,
      React.createElement(Header, { back: true, title: L.title, subtitle: L.subtitle }),
      React.createElement('div', { style: { padding: '12px 16px 36px', display: 'flex', flexDirection: 'column', gap: 16 } },

        /* Offline banner */
        offline && React.createElement('div', {
          style: { padding: '10px 14px', background: 'rgba(184,137,58,0.08)',
            border: '1px solid rgba(184,137,58,0.28)', borderRadius: 10 }
        }, React.createElement('span', {
          style: { fontSize: 12, color: 'var(--gold)', fontFamily: 'var(--font-sans)', ...fontBN }
        }, L.offline)),

        /* Loading */
        loading && React.createElement('div', {
          style: { textAlign: 'center', padding: '48px 0', color: 'var(--muted)', fontSize: 13,
            fontFamily: 'var(--font-sans)', ...fontBN }
        }, L.loading),

        /* Empty */
        !loading && !offline && routines.length === 0 && React.createElement('div', {
          style: { padding: '56px 16px', textAlign: 'center' }
        },
          React.createElement('div', {
            style: { fontFamily: 'var(--font-serif)', fontSize: 18, color: 'var(--navy)', fontWeight: 500, ...fontBN }
          }, L.noData),
          React.createElement('div', {
            style: { marginTop: 6, fontSize: 12.5, color: 'var(--muted)', fontFamily: 'var(--font-sans)', ...fontBN }
          }, L.noDataSub)
        ),

        /* Routine cards */
        !loading && routines.map(function(r) {
          var byDay = groupByDay(r.slots);
          return React.createElement('div', { key: r.id },

            /* Meta header */
            React.createElement('div', { style: { marginBottom: 10 } },
              React.createElement('div', {
                style: { fontFamily: 'var(--font-serif)', fontSize: 17, fontWeight: 500, color: 'var(--navy)', ...fontBN }
              }, r.title),
              React.createElement('div', {
                style: { display: 'flex', gap: 10, marginTop: 4, fontSize: 11.5, color: 'var(--muted)',
                  fontFamily: 'var(--font-sans)', flexWrap: 'wrap' }
              },
                r.batch    && React.createElement('span', null, r.batch),
                r.semester && React.createElement('span', null, '· ' + r.semester),
                r.published_at && React.createElement('span', {
                  style: { fontFamily: 'var(--font-mono)', fontSize: 10.5 }
                }, '· ' + fmtDate(r.published_at))
              ),
              /* Download (PDF / DOCX / CSV) */
              React.createElement('div', { style: { marginTop: 10 } },
                React.createElement(DownloadMenu, {
                  path: '/v1/routines/' + r.id + '/export',
                  stem: 'routine-' + (r.semester || String(r.id).slice(0, 8)),
                  label: 'Download routine',
                  accent: 'var(--sage)',
                })
              )
            ),

            /* Day sections */
            _ROUTINE_DAY_ORDER.map(function(day) {
              var dslots = byDay[day];
              if (!dslots || dslots.length === 0) return null;
              return React.createElement('div', { key: day, style: { marginBottom: 8 } },

                /* Day label with sage stripe */
                React.createElement('div', {
                  style: { display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }
                },
                  React.createElement('div', {
                    style: { width: 3, height: 18, borderRadius: 2, background: 'var(--sage)', flexShrink: 0 }
                  }),
                  React.createElement('span', {
                    style: { fontFamily: 'var(--font-serif)', fontSize: 14, fontWeight: 500,
                      color: 'var(--navy)', ...fontBN }
                  }, lang === 'BN' ? (_BN_DAYS[day] || day) : day)
                ),

                /* Slot rows card */
                React.createElement('div', {
                  style: { background: 'var(--surface)', border: '1px solid var(--mist)',
                    borderRadius: 12, overflow: 'hidden' }
                },
                  dslots.map(function(slot, i) {
                    return React.createElement('div', {
                      key: i,
                      style: {
                        display: 'grid',
                        gridTemplateColumns: '80px 1fr auto',
                        alignItems: 'center',
                        gap: 10,
                        padding: '10px 14px',
                        borderBottom: i < dslots.length - 1 ? '1px solid var(--mist)' : 'none',
                      }
                    },
                      /* Time */
                      React.createElement('div', {
                        style: { fontFamily: 'var(--font-mono)', fontSize: 10.5, color: 'var(--muted)', whiteSpace: 'nowrap' }
                      }, slot.time || slot.start_time || '—'),

                      /* Course code + name */
                      React.createElement('div', null,
                        React.createElement('div', {
                          style: { fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 600, color: 'var(--navy)' }
                        }, slot.course || slot.course_code || '—'),
                        slot.course_name && React.createElement('div', {
                          style: { fontSize: 11.5, color: 'var(--ink-2)', fontFamily: 'var(--font-sans)', ...fontBN }
                        }, slot.course_name)
                      ),

                      /* Room + teacher */
                      React.createElement('div', { style: { textAlign: 'right', minWidth: 0 } },
                        React.createElement('div', {
                          style: { fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--graphite)' }
                        }, slot.room || '—'),
                        React.createElement('div', {
                          style: { fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--font-sans)' }
                        }, slot.teacher || slot.instructor || '—')
                      )
                    );
                  })
                )
              );
            })
          );
        })
      )
    )
  );
}

// ═══════════════════════════════════════════════════════════════
//  DEPT RATING SCREEN
// ═══════════════════════════════════════════════════════════════
function StarPicker({ value, onChange, label, optional }) {
  const labels = ['', 'Poor', 'Fair', 'Good', 'Very good', 'Excellent'];
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--graphite)', fontFamily: 'var(--font-sans)', marginBottom: 6 }}>
        {label}{optional && <span style={{ fontWeight: 400, color: 'var(--muted)' }}> (optional)</span>}
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
        {[1, 2, 3, 4, 5].map(n => (
          <button key={n} onClick={() => onChange(value === n ? 0 : n)} style={{
            width: 34, height: 34, borderRadius: 8, border: 'none', cursor: 'pointer', fontSize: 18,
            background: n <= value ? 'rgba(184,137,58,0.12)' : 'var(--surface)',
            color: n <= value ? 'var(--gold)' : 'var(--mist-2)',
            outline: n <= value ? '1px solid rgba(184,137,58,0.4)' : '1px solid var(--mist)',
            transition: 'all 0.15s',
          }}>★</button>
        ))}
        {value > 0 && (
          <span style={{ marginLeft: 4, fontSize: 11.5, color: 'var(--muted)', fontFamily: 'var(--font-sans)' }}>
            {labels[value]}
          </span>
        )}
      </div>
    </div>
  );
}

function DeptRatingScreen() {
  const DEPTS = ['SWE', 'CSE', 'EEE', 'BBA', 'English', 'Law'];

  const [selectedDept, setSelectedDept] = React.useState('SWE');
  const [summary, setSummary] = React.useState(null);
  const [summaryLoading, setSummaryLoading] = React.useState(true);
  const [summaryError, setSummaryError] = React.useState('');

  const [overall, setOverall] = React.useState(0);
  const [teaching, setTeaching] = React.useState(0);
  const [resources, setResources] = React.useState(0);
  const [environment, setEnvironment] = React.useState(0);
  const [feedback, setFeedback] = React.useState('');
  const [anonymous, setAnonymous] = React.useState(false);
  const [period, setPeriod] = React.useState('Spring-2026');
  const [submitting, setSubmitting] = React.useState(false);
  const [submitted, setSubmitted] = React.useState(false);
  const [submitError, setSubmitError] = React.useState('');
  const [alreadyRated, setAlreadyRated] = React.useState(false);

  const isLoggedIn = !!localStorage.getItem('anchor_access_token');

  React.useEffect(() => {
    setSummaryLoading(true);
    setSummaryError('');
    setSummary(null);
    setSubmitted(false);
    setSubmitError('');
    setAlreadyRated(false);
    setOverall(0); setTeaching(0); setResources(0); setEnvironment(0); setFeedback('');

    fetch(`${_API}/v1/departments/${encodeURIComponent(selectedDept)}/summary`)
      .then(r => {
        if (!r.ok) return r.json().then(d => { throw new Error(d.detail || 'Request failed'); });
        return r.json();
      })
      .then(data => { setSummary(data); setSummaryLoading(false); })
      .catch(err => { setSummaryError(err.message || 'Could not load summary.'); setSummaryLoading(false); });
  }, [selectedDept]);

  const handleSubmit = async () => {
    if (overall === 0) { setSubmitError('Please select an overall rating.'); return; }
    setSubmitting(true);
    setSubmitError('');
    setAlreadyRated(false);
    try {
      const token = localStorage.getItem('anchor_access_token');
      const r = await fetch(`${_API}/v1/departments/ratings`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: 'Bearer ' + token } : {}),
        },
        body: JSON.stringify({
          department: selectedDept,
          period,
          overall,
          teaching_quality: teaching || undefined,
          resources: resources || undefined,
          environment: environment || undefined,
          feedback: feedback.trim() || undefined,
          anonymous,
        }),
      });
      if (!r.ok) {
        const d = await r.json().catch(() => ({}));
        if (r.status === 409) { setAlreadyRated(true); return; }
        throw new Error(d.detail || 'Submission failed.');
      }
      setSubmitted(true);
      fetch(`${_API}/v1/departments/${encodeURIComponent(selectedDept)}/summary`)
        .then(res => res.ok ? res.json() : null)
        .then(data => { if (data) setSummary(data); });
    } catch (err) {
      setSubmitError(err.message || 'Submission failed. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  function AvgBar({ val, label }) {
    if (val == null) return null;
    const pct = (val / 5) * 100;
    return (
      <div style={{ marginBottom: 10 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, fontFamily: 'var(--font-sans)', marginBottom: 4 }}>
          <span style={{ color: 'var(--ink-2)' }}>{label}</span>
          <span className="mono" style={{ color: 'var(--navy)', fontSize: 12 }}>{val.toFixed(1)} / 5</span>
        </div>
        <div style={{ height: 5, background: 'var(--mist)', borderRadius: 999, overflow: 'hidden' }}>
          <div style={{ height: '100%', width: pct + '%', background: 'var(--sage)', borderRadius: 999 }}/>
        </div>
      </div>
    );
  }

  return (
    <>
      <Header back title="Rate Your Department" subtitle="Spring 2026"/>

      <div style={{ padding: '12px 20px 0', display: 'flex', gap: 6, overflowX: 'auto' }}>
        {DEPTS.map(d => (
          <button key={d} onClick={() => setSelectedDept(d)} style={{
            padding: '7px 13px', borderRadius: 999, whiteSpace: 'nowrap', fontSize: 12.5, fontWeight: 600,
            background: d === selectedDept ? 'var(--brand)' : 'var(--surface)',
            color: d === selectedDept ? '#F7F3EE' : 'var(--ink-2)',
            border: '1px solid ' + (d === selectedDept ? 'var(--navy)' : 'var(--mist)'),
            cursor: 'pointer', fontFamily: 'var(--font-sans)',
          }}>{d}</button>
        ))}
      </div>

      <div style={{ padding: '14px 20px 32px', display: 'flex', flexDirection: 'column', gap: 14 }}>

        {/* Summary card */}
        <div style={{ background: 'var(--surface)', border: '1px solid var(--mist)', borderRadius: 14, padding: 16 }}>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', color: 'var(--sage)', fontFamily: 'var(--font-sans)', textTransform: 'uppercase', marginBottom: 10 }}>
            {selectedDept} · Community Ratings
          </div>

          {summaryLoading && (
            <div style={{ textAlign: 'center', padding: '20px 0', fontSize: 12.5, color: 'var(--muted)', fontFamily: 'var(--font-sans)' }}>
              Loading…
            </div>
          )}
          {!summaryLoading && summaryError && (
            <div style={{ fontSize: 12.5, color: 'var(--red)', fontFamily: 'var(--font-sans)' }}>{summaryError}</div>
          )}
          {!summaryLoading && !summaryError && summary && summary.total_count === 0 && (
            <div style={{ fontSize: 12.5, color: 'var(--muted)', fontFamily: 'var(--font-sans)', fontStyle: 'italic' }}>
              No ratings yet for this department. Be the first!
            </div>
          )}
          {!summaryLoading && !summaryError && summary && summary.total_count > 0 && (
            <>
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: 10, marginBottom: 16 }}>
                <div style={{ fontFamily: 'var(--font-serif)', fontSize: 52, fontWeight: 500, color: 'var(--navy)', lineHeight: 1 }}>
                  {summary.avg_overall != null ? summary.avg_overall.toFixed(1) : '—'}
                </div>
                <div style={{ paddingBottom: 6 }}>
                  <div style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--font-sans)' }}>out of 5</div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--font-sans)', marginTop: 2 }}>
                    {summary.total_count} {summary.total_count === 1 ? 'rating' : 'ratings'}
                  </div>
                </div>
              </div>
              <AvgBar val={summary.avg_teaching} label="Teaching Quality"/>
              <AvgBar val={summary.avg_resources} label="Resources"/>
              <AvgBar val={summary.avg_environment} label="Environment"/>
            </>
          )}
        </div>

        {/* Rating form */}
        {!isLoggedIn ? (
          <div style={{ padding: '18px 16px', background: 'var(--surface)', border: '1px solid var(--mist)', borderRadius: 14, textAlign: 'center' }}>
            <div style={{ fontSize: 13, color: 'var(--graphite)', fontFamily: 'var(--font-sans)' }}>
              Sign in to submit a rating
            </div>
          </div>
        ) : submitted ? (
          <div style={{ padding: '24px 16px', background: 'rgba(74,107,92,0.07)', border: '1px solid rgba(74,107,92,0.25)', borderRadius: 14, textAlign: 'center' }}>
            <div style={{ fontSize: 26, marginBottom: 8 }}>✓</div>
            <div style={{ fontFamily: 'var(--font-serif)', fontSize: 17, fontWeight: 500, color: 'var(--sage)' }}>Rating submitted</div>
            <div style={{ marginTop: 5, fontSize: 12.5, color: 'var(--muted)', fontFamily: 'var(--font-sans)' }}>
              Thank you for rating {selectedDept}.
            </div>
          </div>
        ) : (
          <div style={{ background: 'var(--surface)', border: '1px solid var(--mist)', borderRadius: 14, padding: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', color: 'var(--graphite)', fontFamily: 'var(--font-sans)', textTransform: 'uppercase', marginBottom: 14 }}>
              Submit Your Rating
            </div>

            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--graphite)', fontFamily: 'var(--font-sans)', marginBottom: 5 }}>
                Semester / Period
              </div>
              <input value={period} onChange={e => setPeriod(e.target.value)} style={{
                width: '100%', boxSizing: 'border-box', padding: '9px 12px',
                border: '1px solid var(--mist)', borderRadius: 9, fontSize: 13,
                fontFamily: 'var(--font-sans)', background: 'white', color: 'var(--ink-2)', outline: 'none',
              }}/>
            </div>

            <StarPicker value={overall} onChange={setOverall} label="Overall rating"/>
            <StarPicker value={teaching} onChange={setTeaching} label="Teaching quality" optional/>
            <StarPicker value={resources} onChange={setResources} label="Resources & facilities" optional/>
            <StarPicker value={environment} onChange={setEnvironment} label="Department environment" optional/>

            <div style={{ marginBottom: 14 }}>
              <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--graphite)', fontFamily: 'var(--font-sans)', marginBottom: 5 }}>
                Feedback <span style={{ fontWeight: 400, color: 'var(--muted)' }}>(optional)</span>
              </div>
              <textarea value={feedback} onChange={e => setFeedback(e.target.value)} rows={3} placeholder="Share your experience…" style={{
                width: '100%', boxSizing: 'border-box', padding: '9px 12px',
                border: '1px solid var(--mist)', borderRadius: 9, fontSize: 12.5, resize: 'vertical',
                fontFamily: 'var(--font-sans)', background: 'white', color: 'var(--ink-2)', outline: 'none',
              }}/>
            </div>

            <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', marginBottom: 16 }}>
              <input type="checkbox" checked={anonymous} onChange={e => setAnonymous(e.target.checked)}
                style={{ accentColor: 'var(--sage)', width: 16, height: 16 }}/>
              <span style={{ fontSize: 12.5, color: 'var(--graphite)', fontFamily: 'var(--font-sans)' }}>Submit anonymously</span>
            </label>

            {alreadyRated && (
              <div style={{ marginBottom: 12, padding: '10px 12px', background: 'rgba(184,137,58,0.08)', border: '1px solid rgba(184,137,58,0.3)', borderRadius: 9, fontSize: 12.5, color: 'var(--ink-2)', fontFamily: 'var(--font-sans)' }}>
                You've already rated {selectedDept} for {period}.
              </div>
            )}
            {submitError && (
              <div style={{ marginBottom: 12, padding: '10px 12px', background: 'rgba(232,49,42,0.06)', border: '1px solid rgba(232,49,42,0.2)', borderRadius: 9, fontSize: 12.5, color: 'var(--red)', fontFamily: 'var(--font-sans)' }}>
                {submitError}
              </div>
            )}

            <button onClick={handleSubmit} disabled={submitting} style={{
              width: '100%', padding: '13px', borderRadius: 10, cursor: submitting ? 'not-allowed' : 'pointer',
              background: submitting ? 'var(--mist)' : 'var(--sage)', color: submitting ? 'var(--muted)' : '#F7F3EE',
              border: 'none', fontSize: 14, fontWeight: 600, fontFamily: 'var(--font-sans)',
              transition: 'all 0.2s',
            }}>
              {submitting ? 'Submitting…' : 'Submit Rating'}
            </button>
          </div>
        )}
      </div>
    </>
  );
}

Object.assign(window, {
  CasesScreen, CaseDetailScreen, MapScreen, FeedScreen,
  LawyersScreen, NoticesScreen, ProfileScreen,
  RoutinesScreen, DeptRatingScreen,
  NotificationsScreen, NotifPrefsSheet, TrustedContactsSheet, BottomSheet,
  unreadCount, loadNotifications, loadNotifPrefs, loadTrustedContacts,
});
