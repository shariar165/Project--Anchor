// Anchor — Screens part 2: Cases, CaseDetail, Map, Feed, Lawyers, Notices, Profile

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
      width: '100%', textAlign: 'left', background: 'rgba(255,255,255,0.7)', border: '1px solid var(--mist)',
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
          padding: 14, borderRadius: 14, background: 'rgba(255,255,255,0.65)', border: '1px solid var(--mist)',
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
        <div className="card" style={{ background: 'rgba(255,255,255,0.7)' }}>
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
  university: '#1FA663',
  rape:       '#0B0B0B',
  murder:     '#7B2CBF',
  alert:      '#E8312A',
};
const ZONE_TYPE_LABELS = {
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


function MapScreen() {
  const mapContainerRef = React.useRef(null);
  const leafletMapRef   = React.useRef(null);
  const zoneLayersRef   = React.useRef([]);
  const userMarkerRef   = React.useRef(null);

  const [filter,      setFilter]      = React.useState('all');
  const [typeFilters, setTypeFilters] = React.useState({ rape:true, murder:true, alert:true, university:true });
  const [userLoc,     setUserLoc]     = React.useState({ lat:23.7450, lng:90.3718 });
  const [locStatus,   setLocStatus]   = React.useState('default');
  const [nearbyZones, setNearbyZones] = React.useState([]);
  const [zones,        setZones]        = React.useState([]);
  const [zonesLoading, setZonesLoading] = React.useState(true);
  const [zonesError,   setZonesError]   = React.useState(null);

  const fetchZones = React.useCallback(() => {
    fetch('http://localhost:8000/v1/zones')
      .then(r => { if (!r.ok) throw new Error('Server error ' + r.status); return r.json(); })
      .then(d => { setZones(Array.isArray(d) ? d : []); setZonesError(null); })
      .catch(e => setZonesError(e.message || 'Could not reach server'))
      .finally(() => setZonesLoading(false));
  }, []);

  // Fetch zones on mount, then poll every 30 s so new admin-created zones appear automatically
  React.useEffect(() => {
    fetchZones();
    const id = setInterval(fetchZones, 30000);
    return () => clearInterval(id);
  }, [fetchZones]);

  // Init Leaflet map once on mount
  React.useEffect(() => {
    if (leafletMapRef.current) return;
    const map = L.map(mapContainerRef.current, { center:[23.7450, 90.3718], zoom:13 });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      detectRetina: true,
      attribution: '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
    leafletMapRef.current = map;

    if (navigator.geolocation) {
      setLocStatus('locating');
      navigator.geolocation.getCurrentPosition(
        pos => {
          const loc = { lat: pos.coords.latitude, lng: pos.coords.longitude };
          setUserLoc(loc);
          map.setView([loc.lat, loc.lng], 14);
          setLocStatus('found');
        },
        () => setLocStatus('denied'),
        { timeout: 8000 }
      );
    }
    return () => {
      if (leafletMapRef.current) { leafletMapRef.current.remove(); leafletMapRef.current = null; }
    };
  }, []);

  // Re-render zones whenever filter, type toggles, or user location changes
  React.useEffect(() => {
    const map = leafletMapRef.current;
    if (!map) return;

    zoneLayersRef.current.forEach(l => map.removeLayer(l));
    zoneLayersRef.current = [];

    const STATUS_LABEL = { active:'Active', under_investigation:'Under investigation', resolved:'Resolved' };

    const visible = zones.filter(z =>
      z.status !== 'archived' &&
      typeFilters[z.zone_type] &&
      (filter === 'all' || z.status === filter)
    );

    visible.forEach(z => {
      const color       = ZONE_COLORS[z.zone_type];
      const fillOpacity = z.status === 'resolved' ? 0.1 : 0.25;
      const dashArray   = z.status === 'under_investigation' ? '6 6' : null;

      let layer;
      if (z.shape_type === 'polygon' && z.polygon_geojson) {
        layer = L.geoJSON(z.polygon_geojson, {
          style: { color, fillColor: color, fillOpacity: 0.15, weight: 2 },
        });
      } else {
        layer = L.circle([z.center_lat, z.center_lng], {
          radius: z.radius_m, color, fillColor: color, fillOpacity, weight: 2, dashArray,
        });
      }

      const dist    = z.center_lat ? haversineDistance(userLoc.lat, userLoc.lng, z.center_lat, z.center_lng) : null;
      const distTxt = dist ? (dist < 1000 ? Math.round(dist) + 'm away' : (dist / 1000).toFixed(1) + 'km away') : '';

      layer.bindPopup(
        '<div class="anchor-popup">' +
        '<div class="anchor-popup-type" style="color:' + color + '">' + ZONE_TYPE_LABELS[z.zone_type] + '</div>' +
        '<div class="anchor-popup-label">' + z.label + '</div>' +
        '<div class="anchor-popup-meta">' + z.created_at + (distTxt ? ' · ' + distTxt : '') + '</div>' +
        '<div class="anchor-popup-desc">' + z.description_public + '</div>' +
        '<div class="anchor-popup-status">' + (STATUS_LABEL[z.status] || z.status) + '</div>' +
        '</div>'
      );

      layer.addTo(map);
      zoneLayersRef.current.push(layer);
    });

    // Update nearby list (circle zones only, sorted by distance)
    const nearby = zones
      .filter(z => z.status !== 'archived' && z.center_lat && typeFilters[z.zone_type] && (filter === 'all' || z.status === filter))
      .map(z => ({ ...z, dist: haversineDistance(userLoc.lat, userLoc.lng, z.center_lat, z.center_lng) }))
      .sort((a, b) => a.dist - b.dist)
      .slice(0, 5);
    setNearbyZones(nearby);
  }, [filter, JSON.stringify(typeFilters), userLoc.lat, userLoc.lng, JSON.stringify(zones)]);

  // User location marker
  React.useEffect(() => {
    const map = leafletMapRef.current;
    if (!map) return;
    if (userMarkerRef.current) map.removeLayer(userMarkerRef.current);
    const icon = L.divIcon({
      html: '<div style="width:14px;height:14px;border-radius:50%;background:#0B1D35;border:3px solid #fff;box-shadow:0 2px 8px rgba(11,29,53,0.4)"></div>',
      iconSize: [14, 14], iconAnchor: [7, 7], className: '',
    });
    userMarkerRef.current = L.marker([userLoc.lat, userLoc.lng], { icon })
      .bindPopup('You are here')
      .addTo(map);
  }, [userLoc.lat, userLoc.lng]);

  const activeCount = zones.filter(z => z.status === 'active').length;
  const locHint = {
    locating: 'Locating you…',
    found:    'Using your location',
    denied:   'Showing Dhaka default',
    default:  'Dhaka, Bangladesh',
  }[locStatus];

  return (
    <>
      <Header back/>

      {/* Title */}
      <div style={{ padding: '4px 20px 12px' }}>
        <div className="eyebrow">Red Zone Map · Dhaka</div>
        <h1 className="h-display" style={{ fontSize: 24, margin: '4px 0 0', lineHeight: 1.1 }}>
          {zonesLoading ? '…' : activeCount} active zones
        </h1>
        <div style={{ marginTop: 4, fontSize: 12, color: 'var(--muted)', fontStyle: 'italic', fontFamily: 'var(--font-serif)' }}>
          {locHint}
        </div>
      </div>

      {/* Error banner — shown when zone fetch fails */}
      {zonesError && (
        <div style={{ margin: '0 20px 10px', padding: '8px 12px', borderRadius: 10,
          background: '#FEE2E2', color: '#991B1B', fontSize: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ flex: 1 }}>⚠ {zonesError}</span>
          <button onClick={fetchZones} style={{ marginLeft: 'auto', textDecoration: 'underline',
            background: 'none', border: 'none', cursor: 'pointer', color: '#991B1B', fontSize: 12 }}>
            Retry
          </button>
        </div>
      )}

      {/* Status filter tabs */}
      <div style={{ padding: '0 20px 10px', display: 'flex', gap: 6, overflowX: 'auto' }} className="no-scrollbar">
        {[['all','All'],['active','Active'],['under_investigation','Investigating'],['resolved','Resolved']].map(([k, l]) => (
          <button key={k} onClick={() => setFilter(k)} style={{
            padding: '7px 12px', borderRadius: 999, whiteSpace: 'nowrap', cursor: 'pointer',
            background: filter === k ? 'var(--navy)' : 'rgba(255,255,255,0.7)',
            color:      filter === k ? '#F7F3EE'    : 'var(--ink-2)',
            border: '1px solid ' + (filter === k ? 'var(--navy)' : 'var(--mist)'),
            fontSize: 11.5, fontWeight: 500,
          }}>{l}</button>
        ))}
        <button onClick={fetchZones} style={{
          padding: '7px 10px', borderRadius: 999, whiteSpace: 'nowrap', cursor: 'pointer',
          background: 'rgba(255,255,255,0.7)', color: 'var(--ink-2)',
          border: '1px solid var(--mist)', fontSize: 11.5, fontWeight: 500,
          marginLeft: 'auto', flexShrink: 0,
        }} title="Refresh zones">⟳</button>
      </div>

      {/* Map */}
      <div style={{ padding: '0 20px 14px' }}>
        <div style={{ borderRadius: 16, overflow: 'hidden', border: '1px solid var(--mist)' }}>
          <div ref={mapContainerRef} style={{ height: 360 }}/>
        </div>
      </div>

      {/* Zone type toggles / legend */}
      <div style={{ padding: '0 20px 14px' }}>
        <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--muted)', marginBottom: 8 }}>
          Zone types
        </div>
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {[['rape','Sexual Assault','#0B0B0B'],['murder','Homicide','#7B2CBF'],['alert','Alert','#E8312A'],['university','Campus','#1FA663']].map(([type, label, color]) => (
            <button key={type} onClick={() => setTypeFilters(f => ({ ...f, [type]: !f[type] }))} style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '6px 10px', borderRadius: 8, cursor: 'pointer',
              background: typeFilters[type] ? 'rgba(255,255,255,0.85)' : 'rgba(255,255,255,0.4)',
              border: '1.5px solid ' + (typeFilters[type] ? color : 'var(--mist)'),
              opacity: typeFilters[type] ? 1 : 0.5,
            }}>
              <span style={{ width: 10, height: 10, borderRadius: 999, background: color, display: 'block' }}/>
              <span style={{ fontSize: 11.5, color: 'var(--ink-2)', fontWeight: 500 }}>{label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Nearby zones list */}
      <div style={{ padding: '0 20px 28px' }}>
        <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--muted)', marginBottom: 10 }}>
          Zones near you
        </div>
        {nearbyZones.length === 0
          ? <div style={{ fontSize: 13, color: 'var(--muted)', fontStyle: 'italic' }}>No zones match current filters.</div>
          : nearbyZones.map(z => (
            <div key={z.id} className="card" style={{ marginBottom: 8, background: 'rgba(255,255,255,0.8)', padding: '10px 12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <span style={{ width: 10, height: 10, borderRadius: 999, background: ZONE_COLORS[z.zone_type], flexShrink: 0 }}/>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--navy)' }}>{z.label}</div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 1 }}>
                    {ZONE_TYPE_LABELS[z.zone_type]} · {z.dist < 1000 ? Math.round(z.dist) + 'm' : (z.dist / 1000).toFixed(1) + 'km'} away
                  </div>
                </div>
                <span className={'pill ' + (z.status === 'resolved' ? 'pill-resolved' : z.status === 'active' ? 'pill-escalated' : 'pill-review')} style={{ fontSize: 10 }}>
                  {z.status === 'under_investigation' ? 'Investigating' : z.status[0].toUpperCase() + z.status.slice(1)}
                </span>
              </div>
            </div>
          ))
        }
      </div>
    </>
  );
}

// ═══════════════════════════════════════════════════════════════
//  FEED SCREEN — newspaper layout, live from /v1/feed
// ═══════════════════════════════════════════════════════════════
function FeedScreen() {
  const { mode } = useApp();
  const [tab, setTab] = React.useState('top');
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
    const apiScope = mode === 'campus' ? 'campus' : 'national';
    const sort = tab === 'recent' ? 'recent' : 'corroborate';
    const token = localStorage.getItem('anchor_access_token');
    const headers = token ? { Authorization: 'Bearer ' + token } : {};
    fetch(`http://localhost:8000/v1/feed?scope=${apiScope}&sort=${sort}&page=1&page_size=30`, { headers })
      .then(r => {
        if (!r.ok) return r.json().then(d => { throw new Error(d.detail || 'Request failed'); });
        return r.json();
      })
      .then(data => {
        const items = Array.isArray(data) ? data : (data?.items ?? []);
        setPosts(items);
        setLoading(false);
      })
      .catch(err => { setError(err.message || 'Could not load feed.'); setLoading(false); });
  }, [mode, tab]);

  const items = posts.map(toItem);
  const visible = tab === 'trusted' ? items.filter(it => it.trusted) : items;
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
              {mode === 'campus' ? 'Campus edition · Daffodil' : 'National edition · Bangladesh'} · {today}
            </div>
          </div>
          <div style={{ textAlign: 'right', flexShrink: 0, paddingLeft: 10 }}>
            <div className="eyebrow" style={{ fontSize: 9 }}>Vol. 1 · Live</div>
            <div className="serif" style={{ fontStyle: 'italic', fontSize: 10.5, color: 'var(--muted)', marginTop: 2 }}>
              Human-moderated
            </div>
          </div>
        </div>

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

        {!loading && error && (
          <div style={{ margin: '16px 0', padding: '14px 16px', background: 'rgba(232,49,42,0.06)', border: '1px solid rgba(232,49,42,0.2)', borderRadius: 12 }}>
            <div style={{ fontSize: 13, color: 'var(--red)', fontFamily: 'var(--font-sans)' }}>{error}</div>
            <div style={{ fontSize: 11.5, color: 'var(--muted)', marginTop: 4, fontFamily: 'var(--font-sans)' }}>
              Check that the backend server is running on port 8000.
            </div>
          </div>
        )}

        {!loading && !error && (
          <>
            {hero && <NewsFeature item={hero}/>}

            {rest.length > 0 && (
              <div className="news-rule">More from this edition</div>
            )}

            {rest.map(it => <NewsCard key={it.id} item={it}/>)}

            {visible.length === 0 && (
              <div style={{ padding: '60px 20px', textAlign: 'center' }}>
                <div className="serif" style={{ fontSize: 20, color: 'var(--navy)' }}>Nothing in this section yet.</div>
                <div style={{ marginTop: 6, fontSize: 13, color: 'var(--muted)', fontFamily: 'var(--font-serif)', fontStyle: 'italic' }}>
                  Switch tab to see other stories.
                </div>
              </div>
            )}

            {visible.length > 0 && (
              <div className="rule-fancy" style={{ marginTop: 22 }}>End of edition · {visible.length} verified items</div>
            )}
          </>
        )}
      </div>
    </>
  );
}

function NewsFeature({ item }) {
  // Split kicker into "Section · Story": use as a teaser line
  const stripParts = [
    item.scope === 'campus' ? 'Anchor verified · Campus edition' : 'Anchor verified · National edition',
    item.byline.when,
    'Human-moderated',
  ];

  // Build a tabloid headline — italic display with mixed sizes
  return (
    <article className="news-feature">
      {/* Promotional red strap */}
      <div className="news-strap">
        <span className="label">{stripParts[0]}</span>
        <span className="label" style={{ flex: 'none' }}>{stripParts[1].toUpperCase()}</span>
      </div>

      {/* Big photo, framed */}
      <div className="news-photo">
        <div className="news-photo-frame">
          <NewsArt variant={item.art}/>
        </div>
        <div className="news-photo-caption">
          <strong>Photo —</strong> {photoCaption(item)}
        </div>
      </div>

      {/* Decorative italic headline */}
      <div className="news-decor">
        <span className="pre">{item.kicker}:</span>
        <span className="title" dangerouslySetInnerHTML={{ __html: decorateHeadline(item.headline) }}/>
      </div>

      {/* Byline */}
      <div className="news-byline">
        by <strong>{item.byline.author}</strong> · {item.byline.source}
      </div>

      {/* Drop-cap lead */}
      <p className="news-lead-drop">{item.lead}</p>

      {/* Trust badges */}
      <div style={{ display: 'flex', gap: 6, marginTop: 12, flexWrap: 'wrap' }}>
        {item.trusted && <span className="pill" style={{ color: 'var(--gold)', borderColor: 'rgba(184,137,58,0.35)', background: 'rgba(184,137,58,0.08)' }}><IconBadge size={9}/> Trusted source</span>}
        <span className="pill pill-resolved"><IconCheck size={9} sw={3}/> Reviewed & published</span>
      </div>

      <div className="news-actions">
        <button className="news-act corr"><IconThumbUp size={13}/> Corroborate · {item.corr}</button>
        <button className="news-act chal"><IconThumbDown size={13}/> Challenge · {item.chal}</button>
      </div>
    </article>
  );
}

function NewsCard({ item }) {
  return (
    <article className="news-card">
      <div className="news-photo">
        <div className="news-photo-frame">
          <NewsArt variant={item.art}/>
        </div>
        <div className="news-photo-caption">
          <strong>Photo —</strong> {photoCaption(item)}
        </div>
      </div>
      <div className="news-kicker">{item.kicker}</div>
      <h3 className="news-headline lg">{item.headline}</h3>
      <div className="news-byline">
        by <strong>{item.byline.author}</strong> · {item.byline.source} · {item.byline.when}
      </div>
      <p style={{ margin: 0, fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.55 }}>{item.lead}</p>
      <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
        {item.trusted && <span className="pill" style={{ color: 'var(--gold)', borderColor: 'rgba(184,137,58,0.35)', background: 'rgba(184,137,58,0.08)' }}><IconBadge size={9}/> Trusted</span>}
        <span className="pill pill-resolved"><IconCheck size={9} sw={3}/> Reviewed</span>
      </div>
      <div className="news-actions">
        <button className="news-act corr"><IconThumbUp size={13}/> Corroborate · {item.corr}</button>
        <button className="news-act chal"><IconThumbDown size={13}/> Challenge · {item.chal}</button>
      </div>
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
  const [lawyers, setLawyers] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError]   = React.useState('');

  React.useEffect(() => {
    fetch('http://localhost:8000/v1/lawyers')
      .then(r => { if (!r.ok) throw new Error('Failed to load'); return r.json(); })
      .then(data => { setLawyers(data); setLoading(false); })
      .catch(() => { setError('Could not load lawyers. Check your connection.'); setLoading(false); });
  }, []);

  return (
    <>
      <Header back title="Find a Lawyer" subtitle="Verified · Bar-Council certified"/>

      <div style={{ padding: '14px 20px 6px' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px',
          background: 'rgba(255,255,255,0.7)', border: '1px solid var(--mist-2)', borderRadius: 999,
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
              background: i === 0 ? 'var(--navy)' : 'rgba(255,255,255,0.7)',
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
            padding: 14, background: 'rgba(255,255,255,0.7)',
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
            <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px dashed var(--mist)', display: 'flex', justifyContent: 'flex-end' }}>
              <button style={{
                padding: '8px 12px', borderRadius: 10, background: 'var(--navy)', color: '#F7F3EE',
                border: 'none', fontSize: 12, fontWeight: 500, cursor: 'pointer',
                display: 'inline-flex', alignItems: 'center', gap: 6,
              }}>
                <IconLock size={12}/> Start E2EE chat
              </button>
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
    fetch('http://localhost:8000/v1/notices' + qs, { headers })
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
  const { go, logout, auth, geofenceConsent, setGeofenceConsent } = useApp();
  const user = auth && auth.user;
  const displayName = user ? user.name : 'Sadia Akter';
  const isStudent = user && user.role === 'student';
  const initials = displayName.split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase();
  return (
    <>
      <Header back/>
      <div style={{ padding: '16px 20px 8px' }}>
        <div style={{
          padding: 18, borderRadius: 18, background: 'linear-gradient(180deg, rgba(255,255,255,0.85), rgba(255,255,255,0.55))',
          border: '1px solid var(--mist)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{
              width: 56, height: 56, borderRadius: 999, position: 'relative',
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
              <div style={{ marginTop: 4, fontSize: 12.5, color: 'var(--ink-2)' }}>
                {isStudent ? 'SWE · 4th year · Daffodil International University' : 'General Public · Bangladesh'}
              </div>
              <div style={{ marginTop: 6, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {isStudent && <span className="pill" style={{ color: 'var(--gold)', borderColor: 'rgba(184,137,58,0.35)', background: 'rgba(184,137,58,0.08)' }}><IconCheck size={9} sw={3}/> Verified DIU</span>}
                <span className="pill"><IconClock size={10}/> Since Jan 2024</span>
              </div>
            </div>
          </div>

          {/* Stats */}
          <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px dashed var(--mist)', display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
            {[
              { l: 'Cases filed', v: '7' },
              { l: 'Resolved', v: '4' },
              { l: 'Trust score', v: '92' },
            ].map(s => (
              <div key={s.l} style={{ textAlign: 'center' }}>
                <div className="serif" style={{ fontSize: 22, fontWeight: 500, color: 'var(--navy)', letterSpacing: '-0.02em' }}>{s.v}</div>
                <div className="eyebrow" style={{ marginTop: 2, fontSize: 9.5 }}>{s.l}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Settings sections */}
      <div style={{ padding: '14px 20px 0' }}>
        <SettingsGroup title="Preferences" items={[
          { label: 'Language',            value: 'English · বাংলা', Icon: IconGlobe },
          { label: 'Notifications',       value: 'On · selective',  Icon: IconBell },
          { label: 'Default anonymity',   value: 'Always ask',       Icon: IconEyeOff },
        ]}/>
        <SettingsGroup title="Safety" items={[
          { label: "Dead Man's Switch",   value: 'Active · 48h',     Icon: IconShield, accent: 'var(--ember)' },
          { label: 'Two-factor auth',     value: 'TOTP · enabled',   Icon: IconLock,   onTap: () => go('mfa-setup') },
          { label: 'Trusted contacts',    value: '3 set',             Icon: IconPhone },
        ]}/>
        <SettingsGroup title="Data" items={[
          { label: 'Export my data',      value: 'JSON · PDF',       Icon: IconUpload },
          { label: 'Delete account',      value: 'Permanent',         Icon: IconX, danger: true },
        ]}/>
        {/* Location consent */}
        <div style={{ marginBottom: 16 }}>
          <div className="eyebrow" style={{ marginBottom: 8 }}>Location</div>
          <div style={{ background:'rgba(255,255,255,0.7)', border:'1px solid var(--mist)',
                        borderRadius:14, padding:'12px 14px',
                        display:'flex', alignItems:'center', justifyContent:'space-between' }}>
            <div>
              <div style={{ fontSize:14, fontWeight:500, color:'var(--navy)', fontFamily:'var(--font-sans)' }}>
                Nearby alerts
              </div>
              <div style={{ fontSize:12, color:'var(--muted)', fontFamily:'var(--font-sans)', marginTop:2 }}>
                Share anonymous location for alert fan-out
              </div>
            </div>
            <button onClick={() => {
                const next = !geofenceConsent;
                localStorage.setItem('anchor_geofence_consent', String(next));
                localStorage.setItem('anchor_geofence_consent_answered', 'true');
                setGeofenceConsent(next);
              }}
              style={{ width:44, height:26, borderRadius:999, border:'none', cursor:'pointer', flexShrink:0,
                       background: geofenceConsent ? 'var(--sage)' : 'var(--mist)', position:'relative',
                       transition:'background 0.2s' }}>
              <span style={{ position:'absolute', top:3, left: geofenceConsent ? 21 : 3,
                             width:20, height:20, borderRadius:999, background:'#fff',
                             boxShadow:'0 1px 3px rgba(0,0,0,0.18)', transition:'left 0.2s' }}/>
            </button>
          </div>
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
    </>
  );
}

function SettingsGroup({ title, items }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div className="eyebrow" style={{ marginBottom: 8 }}>{title}</div>
      <div style={{
        background: 'rgba(255,255,255,0.7)', border: '1px solid var(--mist)',
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
//  ROUTINES SCREEN
// ═══════════════════════════════════════════════════════════════
function RoutinesScreen() {
  const [routines, setRoutines] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');

  React.useEffect(() => {
    setLoading(true);
    setError('');
    const token = localStorage.getItem('anchor_access_token');
    const headers = token ? { Authorization: 'Bearer ' + token } : {};
    fetch('http://localhost:8000/v1/routines?page=1', { headers })
      .then(r => {
        if (!r.ok) return r.json().then(d => { throw new Error(d.detail || 'Request failed'); });
        return r.json();
      })
      .then(data => { setRoutines(data); setLoading(false); })
      .catch(err => { setError(err.message || 'Could not load routines.'); setLoading(false); });
  }, []);

  function fmtDate(iso) {
    if (!iso) return '';
    try { return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }); }
    catch { return iso; }
  }

  return (
    <>
      <Header back title="Academic Routine" subtitle="Your class schedule"/>
      <div style={{ padding: '16px 20px 28px', display: 'flex', flexDirection: 'column', gap: 14 }}>

        {loading && (
          <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--muted)', fontSize: 13, fontFamily: 'var(--font-sans)' }}>
            Loading routines…
          </div>
        )}

        {!loading && error && (
          <div style={{ padding: '14px 16px', background: 'rgba(232,49,42,0.06)', border: '1px solid rgba(232,49,42,0.2)', borderRadius: 12 }}>
            <div style={{ fontSize: 13, color: 'var(--red)', fontFamily: 'var(--font-sans)' }}>{error}</div>
            <div style={{ fontSize: 11.5, color: 'var(--muted)', marginTop: 4, fontFamily: 'var(--font-sans)' }}>
              Check that the backend server is running on port 8000.
            </div>
          </div>
        )}

        {!loading && !error && routines.length === 0 && (
          <div style={{ padding: '48px 16px', textAlign: 'center' }}>
            <div style={{ fontFamily: 'var(--font-serif)', fontSize: 18, color: 'var(--navy)', fontWeight: 500 }}>
              No routines published yet
            </div>
            <div style={{ marginTop: 6, fontSize: 12.5, color: 'var(--muted)', fontFamily: 'var(--font-sans)' }}>
              Your admin hasn't published a class schedule yet. Check back later.
            </div>
          </div>
        )}

        {!loading && !error && routines.map(r => (
          <div key={r.id} style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid var(--mist)', borderRadius: 14, overflow: 'hidden' }}>
            <div style={{ padding: '14px 16px 10px', borderBottom: '1px solid var(--mist)' }}>
              <div style={{ fontFamily: 'var(--font-serif)', fontSize: 17, fontWeight: 500, color: 'var(--navy)', lineHeight: 1.2 }}>
                {r.title}
              </div>
              <div style={{ display: 'flex', gap: 12, marginTop: 5, fontSize: 11.5, color: 'var(--muted)', fontFamily: 'var(--font-sans)', flexWrap: 'wrap' }}>
                {r.department && <span>Dept: <strong style={{ color: 'var(--ink-2)' }}>{r.department}</strong></span>}
                {r.batch && <span>Batch: <strong style={{ color: 'var(--ink-2)' }}>{r.batch}</strong></span>}
                {r.semester && <span>Semester: <strong style={{ color: 'var(--ink-2)' }}>{r.semester}</strong></span>}
                {r.published_at && (
                  <span className="mono" style={{ fontSize: 10.5 }}>Published {fmtDate(r.published_at)}</span>
                )}
              </div>
            </div>

            {Array.isArray(r.slots) && r.slots.length > 0 ? (
              <div style={{ overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12, fontFamily: 'var(--font-sans)' }}>
                  <thead>
                    <tr style={{ background: 'rgba(74,107,92,0.07)' }}>
                      {['Day', 'Time', 'Course', 'Room', 'Teacher'].map(h => (
                        <th key={h} style={{
                          padding: '7px 12px', textAlign: 'left', fontWeight: 600,
                          color: 'var(--graphite)', fontSize: 10.5, letterSpacing: '0.05em',
                          textTransform: 'uppercase', borderBottom: '1px solid var(--mist)', whiteSpace: 'nowrap',
                        }}>{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {r.slots.map((slot, i) => (
                      <tr key={i} style={{ borderBottom: i < r.slots.length - 1 ? '1px solid var(--mist)' : 'none' }}>
                        <td style={{ padding: '8px 12px', color: 'var(--ink-2)', whiteSpace: 'nowrap' }}>{slot.day || '—'}</td>
                        <td style={{ padding: '8px 12px', color: 'var(--ink-2)', fontFamily: 'var(--font-mono)', fontSize: 11, whiteSpace: 'nowrap' }}>{slot.time || slot.start_time || '—'}</td>
                        <td style={{ padding: '8px 12px', color: 'var(--navy)', fontWeight: 500 }}>{slot.course || slot.course_code || '—'}</td>
                        <td style={{ padding: '8px 12px', color: 'var(--ink-2)' }}>{slot.room || '—'}</td>
                        <td style={{ padding: '8px 12px', color: 'var(--ink-2)' }}>{slot.teacher || slot.instructor || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div style={{ padding: '14px 16px', fontSize: 12.5, color: 'var(--muted)', fontFamily: 'var(--font-sans)', fontStyle: 'italic' }}>
                No class slots defined for this routine.
              </div>
            )}
          </div>
        ))}
      </div>
    </>
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
            background: n <= value ? 'rgba(184,137,58,0.12)' : 'rgba(255,255,255,0.7)',
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

    fetch('http://localhost:8000/v1/departments/' + encodeURIComponent(selectedDept) + '/summary')
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
      const r = await fetch('http://localhost:8000/v1/departments/ratings', {
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
      fetch('http://localhost:8000/v1/departments/' + encodeURIComponent(selectedDept) + '/summary')
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
            background: d === selectedDept ? 'var(--navy)' : 'rgba(255,255,255,0.7)',
            color: d === selectedDept ? '#F7F3EE' : 'var(--ink-2)',
            border: '1px solid ' + (d === selectedDept ? 'var(--navy)' : 'var(--mist)'),
            cursor: 'pointer', fontFamily: 'var(--font-sans)',
          }}>{d}</button>
        ))}
      </div>

      <div style={{ padding: '14px 20px 32px', display: 'flex', flexDirection: 'column', gap: 14 }}>

        {/* Summary card */}
        <div style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid var(--mist)', borderRadius: 14, padding: 16 }}>
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
          <div style={{ padding: '18px 16px', background: 'rgba(255,255,255,0.7)', border: '1px solid var(--mist)', borderRadius: 14, textAlign: 'center' }}>
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
          <div style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid var(--mist)', borderRadius: 14, padding: 16 }}>
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
});
