// Notices, Alerts, Classroom reports, Hostel, Grievances, plus stubs
var { useState, useEffect, useCallback, useRef, useMemo } = React;

const STATE_LABEL_MISC = {
  draft:'Draft', moderation_queue:'Under Review', routed:'Submitted',
  subject_notified:'Under Review', subject_responded:'Under Review',
  under_review:'Under Review', resolved:'Resolved', dismissed:'Rejected',
  withdrawn:'Withdrawn', spam_rejected:'Rejected',
};

function UniNotices({ onGo }) {
  const [prompt, setPrompt] = useState('Library will extend hours to 1 AM during the finals week (June 8–15).');
  const [generated, setGenerated] = useState('Dear students,\n\nDuring the final examinations of Spring 2026 (June 8–15), the central library reading hall will remain open until 1:00 AM. Photo ID is required for entry after 10 PM. Group study rooms must be reserved in advance through the library portal.\n\nWe wish you a productive finals week.\n\nRegistrar\'s Office\nDaffodil International University');
  const [language, setLanguage] = useState('en');
  const [audience, setAudience] = useState(new Set(['University-wide']));
  const [subject, setSubject] = useState('Library extended hours · Finals week Spring 2026');
  const [channels, setChannels] = useState({ push:true, sms:true, email:false });
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [actionError, setActionError] = useState('');
  const [actionSuccess, setActionSuccess] = useState('');
  const [notices, setNotices] = useState([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState('');

  useEffect(() => {
    AnchorAPI.apiGet('/v1/notices?page=1')
      .then(data => { setNotices(Array.isArray(data) ? data : []); setListLoading(false); })
      .catch(err => { setListError(err.message || 'Could not load notices.'); setListLoading(false); });
  }, [actionSuccess]);

  function parseAudience() {
    for (const a of audience) {
      if (a === 'University-wide') return { scope: 'campus' };
      if (a.startsWith('Department: ')) return { scope: 'dept', dept: a.slice(12) };
      if (a.startsWith('Batch ')) return { scope: 'campus', batch: a.slice(6) };
    }
    return { scope: 'campus' };
  }

  async function handleSaveDraft() {
    if (!subject.trim() || !generated.trim()) { setActionError('Subject and body are required.'); return; }
    setSaving(true); setActionError(''); setActionSuccess('');
    try {
      const { scope, dept, batch } = parseAudience();
      await AnchorAPI.apiPostAuth('/v1/notices', { scope, dept: dept || null, batch: batch || null, title: subject.trim(), body: generated.trim() });
      setActionSuccess('Draft saved.');
    } catch (err) {
      setActionError(err.message || 'Could not save draft.');
    } finally { setSaving(false); }
  }

  async function handlePublish() {
    if (!subject.trim() || !generated.trim()) { setActionError('Subject and body are required.'); return; }
    setPublishing(true); setActionError(''); setActionSuccess('');
    try {
      const { scope, dept, batch } = parseAudience();
      const notice = await AnchorAPI.apiPostAuth('/v1/notices', { scope, dept: dept || null, batch: batch || null, title: subject.trim(), body: generated.trim() });
      await AnchorAPI.apiPostAuth(`/v1/notices/${notice.id}/publish`, {});
      setActionSuccess('Notice published successfully.');
    } catch (err) {
      setActionError(err.message || 'Could not publish notice.');
    } finally { setPublishing(false); }
  }

  return (
    <>
      <PageHeader
        title="Notice generator"
        bn="বিজ্ঞপ্তি প্রস্তুতকারক"
        description="Draft and publish notices in Bangla and English. The AI assists with tone and translation; distribution goes via push and SMS."
        actions={
          <>
            <GhostButton icon="archive" size="sm">Archive</GhostButton>
            <GhostButton icon="clock" size="sm">Drafts</GhostButton>
          </>
        }
      />

      <div className="grid gap-6" style={{ gridTemplateColumns:'1fr 380px' }}>
        {/* Compose */}
        <div className="space-y-4">
          {actionError && <div className="mb-3 px-3 py-2 rounded-sm text-[12.5px]" style={{ background:'rgba(232,49,42,0.08)', color:'var(--red)', border:'1px solid rgba(232,49,42,0.2)' }}>{actionError}</div>}
          {actionSuccess && <div className="mb-3 px-3 py-2 rounded-sm text-[12.5px]" style={{ background:'rgba(74,107,92,0.08)', color:'var(--sage)', border:'1px solid rgba(74,107,92,0.2)' }}>{actionSuccess}</div>}
          <Card>
            <Field label="Subject">
              <input value={subject} onChange={e=>setSubject(e.target.value)}
                className="w-full px-3 py-2.5 hair border rounded-sm bg-white text-[14px]" />
            </Field>

            <div className="mt-4">
              <Field label="Prompt to AI" hint="Describe what the notice should communicate. The AI will draft it in the configured tone.">
                <textarea value={prompt} onChange={e=>setPrompt(e.target.value)}
                  className="w-full p-3 hair border rounded-sm bg-white text-[13px] min-h-[80px]" />
              </Field>
              <div className="mt-2 flex items-center gap-2">
                <PrimaryButton mode="sage" size="sm" icon="sparkles" onClick={() => { setGenerating(true); setTimeout(()=>setGenerating(false), 900); }}>
                  {generating?'Generating…':'Generate notice'}
                </PrimaryButton>
                <span className="text-[11px] text-[var(--muted)]">Powered by Qwen3-8B · grounded in your university handbook</span>
              </div>
            </div>
          </Card>

          <Card>
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-1 hair border rounded-sm overflow-hidden">
                <button onClick={()=>setLanguage('en')} className={`px-3 py-1 text-[12px] ${language==='en'?'bg-[var(--sage)] text-white':'text-[var(--graphite)]'}`}>English</button>
                <button onClick={()=>setLanguage('bn')} className={`px-3 py-1 text-[12px] font-bn ${language==='bn'?'bg-[var(--sage)] text-white':'text-[var(--graphite)]'}`}>বাংলা</button>
              </div>
              <div className="flex items-center gap-1 text-[var(--muted)]">
                {['bold','italic','list','link','image'].map(i => (
                  <button key={i} className="w-7 h-7 rounded-sm hover:bg-[var(--mist)]/40 flex items-center justify-center"><Icon name={i==='bold'?'bold':i==='italic'?'italic':i==='list'?'list':i==='link'?'link':'image'} size={13} /></button>
                ))}
              </div>
            </div>
            <textarea value={language==='en'?generated:'প্রিয় শিক্ষার্থীবৃন্দ,\n\nস্প্রিং ২০২৬ এর চূড়ান্ত পরীক্ষাকালীন সময়ে (৮–১৫ জুন), কেন্দ্রীয় গ্রন্থাগারের পাঠকক্ষ রাত ১:০০ পর্যন্ত খোলা থাকবে। রাত ১০ টার পরে প্রবেশের জন্য আইডি কার্ড আবশ্যক।\n\nশুভকামনা।\n\nরেজিস্ট্রার কার্যালয়\nড্যাফোডিল ইন্টারন্যাশনাল ইউনিভার্সিটি'}
              onChange={e=>setGenerated(e.target.value)}
              className={`w-full p-4 hair border rounded-sm bg-[#FDFBF7] text-[13.5px] leading-relaxed min-h-[280px] ${language==='bn'?'font-bn':''}`} />
          </Card>

          <Card>
            <SectionLabel>Audience scope</SectionLabel>
            <div className="flex flex-wrap gap-2 mb-4">
              {['University-wide','Department: SWE','Department: CSE','Batch 54','Batch 55','Section 54-A','Female Hall 2'].map(a => {
                const on = audience.has(a);
                return (
                  <button key={a} onClick={()=>setAudience(s=>{ const n=new Set(s); n.has(a)?n.delete(a):n.add(a); return n;})}
                    className={`px-2.5 py-1 rounded-sm text-[12px] hair border ${on?'bg-[var(--sage)] text-white border-transparent':'text-[var(--graphite)]'}`}>
                    {a}
                  </button>
                );
              })}
            </div>

            <SectionLabel>Distribution channels</SectionLabel>
            <div className="grid grid-cols-3 gap-2">
              {[
                { key:'push', icon:'bell', label:'Push' },
                { key:'sms', icon:'message-square', label:'SMS' },
                { key:'email', icon:'mail', label:'Email' },
              ].map(c => (
                <label key={c.key} className={`flex items-center gap-2 px-3 py-2 hair border rounded-sm cursor-pointer ${channels[c.key]?'bg-[var(--sage-tint)]/70 border-[var(--sage)]':''}`}>
                  <Icon name={c.icon} size={14} />
                  <span className="text-[13px]">{c.label}</span>
                  <input type="checkbox" checked={channels[c.key]} onChange={e=>setChannels(s=>({...s,[c.key]:e.target.checked}))} className="ml-auto accent-[var(--sage)]" />
                </label>
              ))}
            </div>

            <div className="mt-4 grid grid-cols-2 gap-3">
              <Field label="Schedule"><select className="w-full px-2 py-1.5 hair border rounded-sm bg-white text-[13px]"><option>Send now</option><option>Schedule for later</option></select></Field>
              <Field label="Tone"><select className="w-full px-2 py-1.5 hair border rounded-sm bg-white text-[13px]"><option>Formal · institutional</option><option>Warm · student-friendly</option></select></Field>
            </div>
          </Card>

          <div className="flex items-center justify-end gap-2">
            <GhostButton icon="save" onClick={handleSaveDraft} disabled={saving}>{saving ? 'Saving…' : 'Save draft'}</GhostButton>
            <PrimaryButton icon="send" mode="sage" onClick={handlePublish} disabled={publishing}>{publishing ? 'Publishing…' : 'Publish'}</PrimaryButton>
          </div>
        </div>

        {/* Preview */}
        <div className="sticky top-20 self-start">
          <SectionLabel right={<MonoChip>preview</MonoChip>}>Student app preview</SectionLabel>
          <div className="mx-auto rounded-[28px] hair border p-2.5 shadow-lg" style={{ width: 280, background:'#0B1D35' }}>
            <div className="rounded-[20px] bg-[var(--cream)] overflow-hidden" style={{ height: 560 }}>
              <div className="px-5 pt-4 pb-3 hair-b flex items-center justify-between">
                <span className="font-serif text-[17px] text-[var(--navy)]" style={{fontWeight:500}}>Anchor</span>
                <Icon name="bell" size={14} />
              </div>
              <div className="px-4 py-3 hair-b flex items-center gap-2">
                <Icon name="megaphone" size={13} className="text-[var(--sage)]" />
                <span className="smallcaps text-[var(--sage)]">New notice</span>
                <span className="ml-auto text-[10px] text-[var(--muted)] font-mono">just now</span>
              </div>
              <div className="p-4">
                <h4 className="font-serif text-[16px] text-[var(--navy)] leading-tight" style={{fontWeight:500}}>
                  {subject || 'Notice subject'}
                </h4>
                <div className="mt-1 text-[11px] text-[var(--muted)]">Registrar's Office · DIU</div>
                <p className={`mt-3 text-[12px] text-[var(--ink)] leading-relaxed ${language==='bn'?'font-bn':''}`} style={{ textWrap:'pretty' }}>
                  {language==='en' ? generated.split('\n').slice(0,4).join('\n') : 'স্প্রিং ২০২৬ এর চূড়ান্ত পরীক্ষাকালীন সময়ে কেন্দ্রীয় গ্রন্থাগার রাত ১টা পর্যন্ত খোলা থাকবে।'}
                </p>
              </div>
            </div>
          </div>
          <div className="mt-4 hair border rounded-sm p-3 text-[12px] text-[var(--graphite)]">
            <div className="flex items-center justify-between">
              <span className="text-[var(--muted)]">Estimated reach</span>
              <span className="font-mono text-[var(--ink)]">1,240 students · 48 teachers</span>
            </div>
            <div className="flex items-center justify-between mt-1">
              <span className="text-[var(--muted)]">SMS cost (est.)</span>
              <span className="font-mono text-[var(--ink)]">৳ 1,890</span>
            </div>
          </div>

          <div className="mt-4">
            <SectionLabel right={<MonoChip>live</MonoChip>}>Published notices</SectionLabel>
            {listLoading && <div className="text-[12px] text-[var(--muted)] py-2">Loading…</div>}
            {listError && <div className="text-[12px] py-2" style={{color:'var(--red)'}}>{listError}</div>}
            {!listLoading && !listError && notices.length === 0 && (
              <div className="text-[12px] text-[var(--muted)] py-2">No notices yet.</div>
            )}
            <div className="space-y-2">
              {notices.slice(0, 5).map(n => (
                <div key={n.id} className="hair border rounded-sm p-2.5">
                  <div className="flex items-center gap-1.5 mb-1">
                    <Tag tone={n.status === 'published' ? 'sage' : 'mist'}>{n.status}</Tag>
                    <Tag tone="mist">{n.scope}</Tag>
                  </div>
                  <div className="text-[12.5px] font-medium text-[var(--ink)] leading-tight">{n.title}</div>
                  <div className="text-[11px] text-[var(--muted)] mt-0.5 font-mono">
                    {n.published_at ? new Date(n.published_at).toLocaleDateString() : new Date(n.created_at).toLocaleDateString()}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

// ---- Campus Geofence (university side — alert console moved to Super Admin) ----
function UniGeofence({ onGo }) {
  const [vertices, setVertices] = useState([]);
  const [zones, setZones] = useState([]);
  const [selectedZone, setSelectedZone] = useState(null);
  const [zoneName, setZoneName] = useState('');
  const [zoneDesc, setZoneDesc] = useState('');
  const [drawMode, setDrawMode] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [recentAlerts, setRecentAlerts] = useState([]);
  const [mapError, setMapError] = useState(null);

  const mapDivRef = useRef(null);
  const leafletMapRef = useRef(null);
  const polygonRef = useRef(null);
  const markersRef = useRef([]);
  const drawModeRef = useRef(false);

  const loadZones = () => {
    AnchorAPI.apiGet('/v1/admin/campus-zones')
      .then(r => setZones(Array.isArray(r) ? r : []))
      .catch(() => {});
  };

  useEffect(() => {
    loadZones();
    AnchorAPI.apiGet('/v1/admin/alerts?state=active&limit=5')
      .then(r => setRecentAlerts(r.items ?? []))
      .catch(() => {});
  }, []);

  useEffect(() => { drawModeRef.current = drawMode; }, [drawMode]);

  // Init Leaflet map once
  useEffect(() => {
    if (!mapDivRef.current || leafletMapRef.current) return;
    if (!window.L) { setMapError('Map library failed to load. Please refresh the page.'); return; }
    try {
      const map = window.L.map(mapDivRef.current, { zoomControl: true }).setView([23.7450, 90.3718], 15);
      window.L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap contributors',
        maxZoom: 19,
      }).addTo(map);
      leafletMapRef.current = map;
      setTimeout(() => map.invalidateSize(), 100);
      map.on('click', (e) => {
        if (!drawModeRef.current) return;
        const { lat, lng } = e.latlng;
        setVertices(v => [...v, [parseFloat(lat.toFixed(6)), parseFloat(lng.toFixed(6))]]);
      });
    } catch (err) {
      setMapError('Map failed to initialise: ' + (err.message || 'unknown error'));
    }
    return () => {
      if (leafletMapRef.current) { leafletMapRef.current.remove(); leafletMapRef.current = null; }
      polygonRef.current = null;
      markersRef.current = [];
    };
  }, []);

  // Redraw polygon + vertex markers when vertices change
  useEffect(() => {
    const map = leafletMapRef.current;
    if (!map || !window.L) return;
    if (polygonRef.current) { polygonRef.current.remove(); polygonRef.current = null; }
    markersRef.current.forEach(m => m.remove());
    markersRef.current = [];
    if (vertices.length >= 2) {
      polygonRef.current = window.L.polygon(vertices, {
        color: '#4A6B5C', fillColor: '#4A6B5C', fillOpacity: 0.15, weight: 2, dashArray: '5 5',
      }).addTo(map);
    }
    vertices.forEach(([lat, lng], i) => {
      const m = window.L.circleMarker([lat, lng], {
        radius: 5, color: 'white', fillColor: '#4A6B5C', fillOpacity: 1, weight: 2,
      }).bindTooltip(`#${i + 1}`, { permanent: false }).addTo(map);
      markersRef.current.push(m);
    });
  }, [vertices]);

  const selectZone = (zone) => {
    setSelectedZone(zone);
    setZoneName(zone.name || '');
    setZoneDesc(zone.description_public || '');
    if (zone.polygon_coords && zone.polygon_coords.length >= 3) {
      setVertices(zone.polygon_coords);
      if (leafletMapRef.current && window.L) {
        try { leafletMapRef.current.fitBounds(zone.polygon_coords); } catch (_) {}
      }
    }
    setDrawMode(false);
  };

  const startNew = () => {
    setSelectedZone(null);
    setZoneName('');
    setZoneDesc('');
    setVertices([]);
    setDrawMode(false);
  };

  const centroid = (coords) => {
    const n = coords.length;
    return [coords.reduce((s, c) => s + c[0], 0) / n, coords.reduce((s, c) => s + c[1], 0) / n];
  };

  const handleSave = async () => {
    if (vertices.length < 3 || !zoneName.trim()) return;
    setSaving(true);
    try {
      if (selectedZone) {
        await AnchorAPI.apiPatch(`/v1/admin/campus-zones/${selectedZone.id}`, {
          name: zoneName.trim(),
          description: zoneDesc.trim() || null,
          polygon_coords: vertices,
        });
      } else {
        const [c_lat, c_lng] = centroid(vertices);
        await AnchorAPI.apiPostAuth('/v1/admin/campus-zones', {
          name: zoneName.trim(),
          zone_type: 'campus',
          shape_type: 'polygon',
          polygon_coords: vertices,
          center_lat: c_lat,
          center_lng: c_lng,
          description: zoneDesc.trim() || null,
        });
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
      loadZones();
    } catch (e) {
      console.error('[Geofence] Save failed:', e);
      alert('Save failed: ' + (e.message || 'Unknown error'));
    } finally {
      setSaving(false);
    }
  };

  const handleArchive = async (zone, e) => {
    e.stopPropagation();
    if (!confirm(`Archive zone "${zone.name}"? It will be removed from the student map.`)) return;
    try {
      await AnchorAPI.apiDelete(`/v1/admin/campus-zones/${zone.id}`);
      if (selectedZone?.id === zone.id) startNew();
      loadZones();
    } catch (err) {
      console.error('[Geofence] Archive failed:', err);
    }
  };

  return (
    <>
      <PageHeader
        title="Campus geofence"
        bn="ক্যাম্পাস সীমানা"
        description="Draw your university's safety boundary. Saved zones appear on the student map immediately."
        actions={
          <>
            <GhostButton icon="plus" size="sm" onClick={startNew}>New zone</GhostButton>
            <GhostButton icon={drawMode ? 'pencil-off' : 'pencil'} size="sm" onClick={() => setDrawMode(m => !m)}>
              {drawMode ? 'Done drawing' : 'Draw boundary'}
            </GhostButton>
            {vertices.length > 0 && (
              <GhostButton icon="undo-2" size="sm" onClick={() => setVertices(v => v.slice(0, -1))}>Undo</GhostButton>
            )}
            <GhostButton icon="trash-2" size="sm" onClick={() => setVertices([])}>Clear</GhostButton>
            <PrimaryButton
              icon="save"
              mode="sage"
              size="sm"
              onClick={handleSave}
              disabled={saving || vertices.length < 3 || !zoneName.trim()}
            >
              {saving ? 'Saving…' : saved ? 'Saved ✓' : selectedZone ? 'Update zone' : 'Save zone'}
            </PrimaryButton>
          </>
        }
      />

      <AuditNote tone="navy" icon="shield-check">
        Campus zones appear on the student safety map as green highlighted areas. Active alerts inside a zone are routed to platform operators in real time.
      </AuditNote>

      <div className="flex gap-4 mt-5" style={{ height: 'calc(100vh - 220px)', minHeight: 420 }}>
        {/* Leaflet map */}
        <div className="flex-1 rounded-sm border hair relative" style={{ minWidth: 0 }}>
          {drawMode && (
            <div
              className="absolute top-3 z-[1000] px-3 py-1.5 rounded text-[12px] font-medium flex items-center gap-2"
              style={{ left: '50%', transform: 'translateX(-50%)', background: 'var(--sage)', color: 'white', boxShadow: 'var(--shadow)', pointerEvents: 'all' }}
            >
              <Icon name="map-pin" size={13} />
              Click map to place boundary vertices
              <button onClick={() => setDrawMode(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, opacity: 0.8, display: 'flex' }}>
                <Icon name="x" size={12} />
              </button>
            </div>
          )}
          {mapError ? (
            <div className="w-full h-full flex flex-col items-center justify-center p-6 text-center" style={{ background: 'var(--mist)' }}>
              <Icon name="map-off" size={32} className="mb-3 text-[var(--muted)]" />
              <p className="text-[13px] text-[var(--graphite)]">{mapError}</p>
            </div>
          ) : (
            <div ref={mapDivRef} className="w-full h-full" style={{ cursor: drawMode ? 'crosshair' : undefined }} />
          )}
        </div>

        {/* Right panel */}
        <div className="flex flex-col gap-4 overflow-y-auto" style={{ width: 280, flexShrink: 0 }}>
          <Card>
            <SectionLabel>{selectedZone ? 'Edit zone' : 'New zone'}</SectionLabel>
            <div className="space-y-3">
              <div>
                <label className="block text-[11px] font-medium mb-1" style={{ color: 'var(--muted)' }}>Zone name *</label>
                <input
                  type="text"
                  value={zoneName}
                  onChange={e => setZoneName(e.target.value)}
                  placeholder="e.g. Main Campus"
                  maxLength={200}
                  style={{ width: '100%', padding: '6px 10px', borderRadius: 4, border: '1px solid var(--mist)', background: 'var(--cream)', fontSize: 12.5, outline: 'none', boxSizing: 'border-box' }}
                />
              </div>
              <div>
                <label className="block text-[11px] font-medium mb-1" style={{ color: 'var(--muted)' }}>Description</label>
                <textarea
                  value={zoneDesc}
                  onChange={e => setZoneDesc(e.target.value)}
                  placeholder="Visible to students on the map…"
                  rows={3}
                  maxLength={2000}
                  style={{ width: '100%', padding: '6px 10px', borderRadius: 4, border: '1px solid var(--mist)', background: 'var(--cream)', fontSize: 12.5, outline: 'none', resize: 'none', boxSizing: 'border-box' }}
                />
              </div>
              <div className="flex items-center justify-between" style={{ fontSize: 12 }}>
                <span style={{ color: 'var(--muted)' }}>Vertices placed</span>
                <span className="font-mono">{vertices.length}</span>
              </div>
              {!zoneName.trim() && vertices.length >= 3 && (
                <p style={{ fontSize: 11, color: 'var(--ember)' }}>Zone name is required to save.</p>
              )}
            </div>
          </Card>

          <Card>
            <SectionLabel right={<MonoChip>{zones.length}</MonoChip>}>Campus zones</SectionLabel>
            {zones.length === 0 ? (
              <div style={{ fontSize: 12, color: 'var(--muted)', textAlign: 'center', padding: '8px 0' }}>No zones saved yet</div>
            ) : zones.map(z => (
              <div
                key={z.id}
                onClick={() => selectZone(z)}
                style={{
                  display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
                  margin: '0 -12px', padding: '8px 12px', borderBottom: '1px solid var(--mist)',
                  cursor: 'pointer', borderRadius: 4,
                  background: selectedZone?.id === z.id ? 'rgba(74,107,92,0.08)' : 'transparent',
                }}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#4A6B5C', flexShrink: 0 }} />
                    <span style={{ fontSize: 12.5, fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{z.name}</span>
                  </div>
                  {z.description_public && (
                    <p style={{ fontSize: 11, color: 'var(--muted)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', margin: '2px 0 0 14px' }}>{z.description_public}</p>
                  )}
                  <p style={{ fontSize: 11, color: 'var(--muted)', margin: '1px 0 0 14px' }}>
                    {(z.polygon_coords?.length ?? 0)} vertices
                  </p>
                </div>
                <button
                  onClick={(ev) => handleArchive(z, ev)}
                  title="Archive zone"
                  style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 2, opacity: 0.4, display: 'flex', flexShrink: 0, marginLeft: 8 }}
                  onMouseEnter={e => e.currentTarget.style.opacity = 1}
                  onMouseLeave={e => e.currentTarget.style.opacity = 0.4}
                >
                  <Icon name="archive" size={13} />
                </button>
              </div>
            ))}
          </Card>

          <Card>
            <SectionLabel>Recent alerts inside zone</SectionLabel>
            {recentAlerts.length === 0 ? (
              <div style={{ fontSize: 12, color: 'var(--muted)', textAlign: 'center', padding: '8px 0' }}>No active alerts</div>
            ) : recentAlerts.map(ev => (
              <div key={ev.event_id} className="flex justify-between items-center text-[12.5px] py-1.5 hair-b last:border-0">
                <span className="font-mono text-[var(--muted)]">{ev.event_id.slice(0, 8)}…</span>
                <span style={{ color: ev.state === 'active' ? 'var(--ember)' : 'var(--sage)' }}>{ev.state}</span>
              </div>
            ))}
          </Card>
        </div>
      </div>
    </>
  );
}

// ---- Classroom reports ----
function UniClassrooms({ onGo }) {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    AnchorAPI.apiGet('/v1/classroom-reports')
      .then(data => {
        const map = {};
        (Array.isArray(data) ? data : []).forEach(r => {
          if (!map[r.classroom_ref]) map[r.classroom_ref] = { room: r.classroom_ref, issues: [], count: 0 };
          map[r.classroom_ref].issues.push(r.issue_type);
          map[r.classroom_ref].count += r.count;
        });
        setRows(Object.values(map).sort((a, b) => b.count - a.count));
        setLoading(false);
      })
      .catch(err => { setError(err.message || 'Could not load classroom reports.'); setLoading(false); });
  }, []);

  return (
    <>
      <PageHeader
        title="Classroom reports"
        description="Sorted by most-reported classroom. Bulk-resolve and schedule maintenance from this view."
        actions={
          <>
            <GhostButton icon="wrench" size="sm">Schedule maintenance</GhostButton>
            <GhostButton icon="check-square" size="sm">Bulk resolve</GhostButton>
          </>
        }
      />

      {error && (
        <div className="mb-4 px-3 py-2 rounded-sm text-[12.5px]" style={{ background:'rgba(232,49,42,0.08)', color:'var(--red)', border:'1px solid rgba(232,49,42,0.2)' }}>
          {error}
        </div>
      )}

      {loading && (
        <Card>
          <div className="space-y-3 animate-pulse">
            {[1,2,3].map(i => <div key={i} className="h-4 bg-[var(--mist)] rounded-sm" />)}
          </div>
        </Card>
      )}

      {!loading && rows.length === 0 && !error && (
        <Card><EmptyState icon="clipboard" title="No classroom reports" body="No students have submitted classroom condition reports yet." /></Card>
      )}

      {!loading && rows.length > 0 && (
        <Card noPad>
          <DataTable
            columns={[
              { key:'room', label:'Room', render:r=><MonoChip tone="navy">{r.room}</MonoChip> },
              { key:'count', label:'Reports', align:'right', render:r=><span className="font-mono text-[var(--ink)]">{r.count}</span> },
              { key:'issues', label:'Issues reported', render:r=><div className="flex flex-wrap gap-1">{r.issues.map(i=><Tag key={i} tone="mist">{i}</Tag>)}</div> },
            ]}
            rows={rows}
            onRowClick={()=>{}}
          />
        </Card>
      )}
    </>
  );
}

// ---- Teacher Grievances ----
function UniTeacherGrievances() {
  const [tab, setTab] = useState('r1');
  const [r1Filings, setR1Filings] = useState([]);
  const [r2Filings, setR2Filings] = useState([]);
  const [r3Filings, setR3Filings] = useState([]);
  const [r1Loading, setR1Loading] = useState(false);
  const [r2Loading, setR2Loading] = useState(false);
  const [r3Loading, setR3Loading] = useState(false);
  const [r1Err, setR1Err] = useState('');
  const [r2Err, setR2Err] = useState('');
  const [r3Err, setR3Err] = useState('');

  useEffect(() => {
    if (tab === 'r1' && r1Filings.length === 0 && !r1Loading) {
      setR1Loading(true);
      AnchorAPI.apiGet('/v1/admin/filings?template_key=academic_rank1&page=1&page_size=50')
        .then(d => { setR1Filings(Array.isArray(d) ? d : []); setR1Loading(false); })
        .catch(e => { setR1Err(e.message || 'Load failed'); setR1Loading(false); });
    }
    if (tab === 'r2' && r2Filings.length === 0 && !r2Loading) {
      setR2Loading(true);
      AnchorAPI.apiGet('/v1/admin/filings?template_key=academic_rank2&page=1&page_size=50')
        .then(d => { setR2Filings(Array.isArray(d) ? d : []); setR2Loading(false); })
        .catch(e => { setR2Err(e.message || 'Load failed'); setR2Loading(false); });
    }
    if (tab === 'r3' && r3Filings.length === 0 && !r3Loading) {
      setR3Loading(true);
      AnchorAPI.apiGet('/v1/admin/filings?template_key=academic_rank3&page=1&page_size=50')
        .then(d => { setR3Filings(Array.isArray(d) ? d : []); setR3Loading(false); })
        .catch(e => { setR3Err(e.message || 'Load failed'); setR3Loading(false); });
    }
  }, [tab]);

  return (
    <>
      <PageHeader
        title="Teacher grievances"
        bn="শিক্ষক সংক্রান্ত অভিযোগ"
        description="Three rank levels of academic grievances. Rank-3 is restricted to Dean and Proctor — each view is audit-logged."
      />
      <div className="flex items-center gap-1 mb-4">
        {[
          { v:'r1', label:'Rank 1 · Feedback' },
          { v:'r2', label:'Rank 2 · Professional Conduct' },
          { v:'r3', label:'Rank 3 · Serious Misconduct' },
        ].map(t => (
          <button key={t.v} onClick={()=>setTab(t.v)} className={`px-3 py-1.5 text-[13px] rounded-sm ${tab===t.v?'bg-[var(--navy)] text-white':'hair border text-[var(--graphite)]'}`}>
            <span className="inline-flex items-center gap-1.5">
              {t.v==='r3' && <Icon name="lock" size={11} />}
              {t.label}
            </span>
          </button>
        ))}
      </div>

      {tab==='r1' && (
        <>
          {r1Err && <div className="mb-3 px-3 py-2 rounded-sm text-[12.5px]" style={{color:'var(--red)'}}>{r1Err}</div>}
          {r1Loading && <Card><div className="animate-pulse space-y-2">{[1,2,3].map(i=><div key={i} className="h-4 bg-[var(--mist)] rounded-sm" />)}</div></Card>}
          {!r1Loading && r1Filings.length === 0 && !r1Err && (
            <Card><EmptyState icon="inbox" title="No rank-1 feedback filings" body="No normal feedback complaints filed yet." /></Card>
          )}
          {!r1Loading && r1Filings.length > 0 && (
            <Card noPad>
              <DataTable
                columns={[
                  { key:'filing_number', label:'Filing #', render:r=><MonoChip>{r.filing_number || r.id.slice(0,10)}</MonoChip> },
                  { key:'subject', label:'Subject / Teacher', render:r=><span className="text-[13px]">{r.subject_descriptor || '— not specified —'}</span> },
                  { key:'state', label:'Status', render:r=><StatusPill status={STATE_LABEL_MISC[r.state] || r.state} /> },
                  { key:'created_at', label:'Filed', render:r=><span className="font-mono text-[12px] text-[var(--muted)]">{new Date(r.created_at).toLocaleDateString()}</span> },
                ]}
                rows={r1Filings}
                onRowClick={()=>{}}
              />
            </Card>
          )}
        </>
      )}

      {tab==='r2' && (
        <>
          {r2Err && <div className="mb-3 px-3 py-2 rounded-sm text-[12.5px]" style={{color:'var(--red)'}}>{r2Err}</div>}
          {r2Loading && <div className="grid grid-cols-2 gap-4">{[1,2].map(i=><Card key={i}><div className="animate-pulse h-20 bg-[var(--mist)] rounded-sm" /></Card>)}</div>}
          {!r2Loading && r2Filings.length === 0 && !r2Err && (
            <Card><EmptyState icon="inbox" title="No rank-2 conduct filings" body="No professional conduct complaints filed yet." /></Card>
          )}
          {!r2Loading && r2Filings.length > 0 && (
            <div className="grid grid-cols-2 gap-4">
              {r2Filings.map(f => (
                <Card key={f.id} className={StatusEdgeClass(STATE_LABEL_MISC[f.state] || f.state)}>
                  <div className="flex items-center gap-2 mb-1">
                    <MonoChip>{f.filing_number || f.id.slice(0,10)}</MonoChip>
                    {f.template?.anonymity_mode === 'anonymous' && <AnonymityBadge />}
                  </div>
                  <h3 className="font-serif text-[18px] text-[var(--navy)]" style={{fontWeight:500}}>
                    {f.body ? f.body.split('\n')[0].slice(0,60) : (f.template?.name || 'Conduct complaint')}
                  </h3>
                  <p className="mt-2 text-[12.5px] text-[var(--graphite)] line-clamp-2">{f.subject_descriptor || 'No subject identified'}</p>
                  <div className="mt-3 flex items-center justify-between">
                    <StatusPill status={STATE_LABEL_MISC[f.state] || f.state} />
                    <span className="text-[11px] text-[var(--muted)] font-mono">{new Date(f.created_at).toLocaleDateString()}</span>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </>
      )}

      {tab==='r3' && (
        <>
          <AuditNote tone="red" icon="lock" className="mb-4">
            Rank-3 reports are visible only to Dean and Proctor. Reports here have strongest anonymity protection and route directly, bypassing the Department Head. Each view is audit-logged.
          </AuditNote>
          {r3Err && <div className="mb-3 px-3 py-2 rounded-sm text-[12.5px]" style={{color:'var(--red)'}}>{r3Err}</div>}
          {r3Loading && <Card><div className="animate-pulse h-20 bg-[var(--mist)] rounded-sm" /></Card>}
          {!r3Loading && !r3Err && (
            <Card>
              {r3Filings.length === 0
                ? <EmptyState icon="lock" title="Sealed queue — empty" body="No Rank-3 reports filed yet. Each report is sealed with strongest anonymity protection." />
                : <EmptyState icon="lock" title={`Sealed queue — ${r3Filings.length} report${r3Filings.length > 1 ? 's' : ''}`} body="Open each individually to review; identity remains encrypted until formal de-anonymization through Super Admin." />
              }
            </Card>
          )}
        </>
      )}
    </>
  );
}

// ---- Department Grievances ----
function UniDeptGrievances() {
  const [tab, setTab] = useState('incidents');
  const [deptSel, setDeptSel] = useState('SWE');
  const [summary, setSummary] = useState(null);
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [summaryError, setSummaryError] = useState('');

  const [incidents, setIncidents] = useState([]);
  const [incLoading, setIncLoading] = useState(false);
  const [incErr, setIncErr] = useState('');

  const [culture, setCulture] = useState([]);
  const [cultureLoading, setCultureLoading] = useState(false);
  const [cultureErr, setCultureErr] = useState('');

  useEffect(() => {
    if (tab === 'incidents' && incidents.length === 0 && !incLoading) {
      setIncLoading(true);
      AnchorAPI.apiGet('/v1/admin/filings?template_key=dept_c1&page=1&page_size=50')
        .then(d => { setIncidents(Array.isArray(d) ? d : []); setIncLoading(false); })
        .catch(e => { setIncErr(e.message || 'Load failed'); setIncLoading(false); });
    }
    if (tab === 'periodic') {
      setSummaryLoading(true); setSummaryError('');
      AnchorAPI.apiGet(`/v1/departments/${encodeURIComponent(deptSel)}/summary`)
        .then(data => { setSummary(data); setSummaryLoading(false); })
        .catch(err => { setSummaryError(err.message || 'Could not load summary.'); setSummaryLoading(false); });
    }
    if (tab === 'culture' && culture.length === 0 && !cultureLoading) {
      setCultureLoading(true);
      AnchorAPI.apiGet('/v1/admin/filings?template_key=dept_c3&page=1&page_size=50')
        .then(d => { setCulture(Array.isArray(d) ? d : []); setCultureLoading(false); })
        .catch(e => { setCultureErr(e.message || 'Load failed'); setCultureLoading(false); });
    }
  }, [tab, deptSel]);

  return (
    <>
      <PageHeader
        title="Department grievances"
        description="Incident-based complaints, periodic performance ratings, and anonymous culture reports."
      />
      <div className="flex items-center gap-1 mb-4">
        {[
          { v:'incidents', label:'Incident-based' },
          { v:'periodic', label:'Periodic performance' },
          { v:'culture', label:'Anonymous culture reports', icon:'eye-off' },
        ].map(t => (
          <button key={t.v} onClick={()=>setTab(t.v)} className={`px-3 py-1.5 text-[13px] rounded-sm inline-flex items-center gap-1.5 ${tab===t.v?'bg-[var(--navy)] text-white':'hair border text-[var(--graphite)]'}`}>
            {t.icon && <Icon name={t.icon} size={12} />} {t.label}
          </button>
        ))}
      </div>

      {tab==='incidents' && (
        <>
          {incErr && <div className="mb-3 px-3 py-2 rounded-sm text-[12.5px]" style={{color:'var(--red)'}}>{incErr}</div>}
          {incLoading && <div className="grid grid-cols-2 gap-4">{[1,2].map(i=><Card key={i}><div className="animate-pulse h-20 bg-[var(--mist)] rounded-sm" /></Card>)}</div>}
          {!incLoading && incidents.length === 0 && !incErr && (
            <Card><EmptyState icon="inbox" title="No incident-based grievances" body="No department incident complaints filed yet." /></Card>
          )}
          {!incLoading && incidents.length > 0 && (
            <div className="grid grid-cols-2 gap-4">
              {incidents.map(f => (
                <Card key={f.id} className={StatusEdgeClass(STATE_LABEL_MISC[f.state] || f.state)}>
                  <div className="flex items-center gap-2 mb-1">
                    <MonoChip>{f.filing_number || f.id.slice(0,10)}</MonoChip>
                  </div>
                  <h3 className="font-serif text-[18px] text-[var(--navy)]" style={{fontWeight:500}}>
                    {f.body ? f.body.split('\n')[0].slice(0,60) : (f.template?.name || 'Dept grievance')}
                  </h3>
                  <p className="mt-2 text-[12.5px] text-[var(--graphite)]">{f.subject_descriptor || 'No department specified'}</p>
                  <div className="mt-3"><StatusPill status={STATE_LABEL_MISC[f.state] || f.state} /></div>
                </Card>
              ))}
            </div>
          )}
        </>
      )}

      {tab==='periodic' && (
        <Card>
          <div className="flex items-center justify-between mb-4">
            <SectionLabel className="mb-0">Department ratings</SectionLabel>
            <div className="flex items-center gap-2">
              <span className="text-[12px] text-[var(--muted)]">Department</span>
              <select value={deptSel} onChange={e=>setDeptSel(e.target.value)}
                className="hair border rounded-sm bg-white px-2 py-1 text-[13px]">
                {['SWE','CSE','EEE','BBA','English','Law'].map(d => <option key={d}>{d}</option>)}
              </select>
            </div>
          </div>

          {summaryLoading && <div className="text-[13px] text-[var(--muted)] py-4 text-center">Loading ratings…</div>}
          {summaryError && <div className="text-[13px] py-3" style={{color:'var(--red)'}}>{summaryError}</div>}

          {!summaryLoading && !summaryError && summary && (
            <>
              <div className="flex items-center gap-4 mb-4 hair border rounded-sm p-3">
                <div className="text-center">
                  <div className="font-mono text-[32px] text-[var(--navy)] leading-none">{summary.avg_overall ? summary.avg_overall.toFixed(1) : '—'}</div>
                  <div className="text-[11px] text-[var(--muted)] mt-1">Overall / 5</div>
                </div>
                <div className="h-10 w-px bg-[var(--mist)]" />
                <div className="text-[12.5px] text-[var(--graphite)]">
                  <span className="font-mono text-[var(--ink)]">{summary.total_count}</span> ratings · <span className="text-[var(--muted)]">{deptSel}</span>
                </div>
              </div>
              <div className="space-y-3">
                {[
                  { dim: 'Overall', val: summary.avg_overall },
                  { dim: 'Teaching quality', val: summary.avg_teaching },
                  { dim: 'Resources', val: summary.avg_resources },
                  { dim: 'Environment', val: summary.avg_environment },
                ].map(r => (
                  <div key={r.dim}>
                    <div className="flex items-center justify-between text-[13px] mb-1">
                      <span>{r.dim}</span>
                      <span className="font-mono">{r.val != null ? r.val.toFixed(1) : '—'} / 5</span>
                    </div>
                    <div className="h-2 bg-[var(--mist)]/70 rounded-sm overflow-hidden">
                      <div className="h-full bg-[var(--sage)]" style={{ width: r.val ? `${(r.val/5)*100}%` : '0%' }} />
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {!summaryLoading && !summaryError && !summary && (
            <EmptyState icon="bar-chart-2" title="No ratings yet" body={`No ratings submitted for ${deptSel} yet.`} />
          )}
        </Card>
      )}

      {tab==='culture' && (
        <>
          <AuditNote tone="navy" icon="eye-off" className="mb-4">
            These reports are visible only to the Dean. Department heads cannot see this view.
          </AuditNote>
          {cultureErr && <div className="mb-3 px-3 py-2 rounded-sm text-[12.5px]" style={{color:'var(--red)'}}>{cultureErr}</div>}
          {cultureLoading && <div className="animate-pulse space-y-3">{[1,2].map(i=><Card key={i}><div className="h-16 bg-[var(--mist)] rounded-sm" /></Card>)}</div>}
          {!cultureLoading && culture.length === 0 && !cultureErr && (
            <Card><EmptyState icon="eye-off" title="No culture reports" body="No anonymous department culture reports filed yet." /></Card>
          )}
          {!cultureLoading && culture.length > 0 && (
            <div className="grid gap-3">
              {culture.map(f => (
                <Card key={f.id}>
                  <div className="flex items-center gap-2 mb-1">
                    <MonoChip>{f.filing_number || f.id.slice(0,10)}</MonoChip>
                    <AnonymityBadge />
                    {f.subject_descriptor && <Tag tone="sage">{f.subject_descriptor}</Tag>}
                    <span className="ml-auto text-[11px] text-[var(--muted)] font-mono">filed {new Date(f.created_at).toLocaleDateString()}</span>
                  </div>
                  <p className="text-[13px] text-[var(--ink)]" style={{textWrap:'pretty'}}>
                    {f.body ? f.body.slice(0, 200) : <span className="text-[var(--muted)] italic">No body text provided.</span>}
                  </p>
                </Card>
              ))}
            </div>
          )}
        </>
      )}
    </>
  );
}

// ---- Hostel ----
function UniHostel() {
  return (
    <>
      <PageHeader
        title="Hostel complaints"
        bn="হোস্টেল সংক্রান্ত"
        description="Filter by hall and complaint type. Hall tutor reports and warden misconduct route here."
      />
      <div className="grid grid-cols-2 gap-4">
        {['Female Hall 1','Female Hall 2','Male Hall A','Male Hall B'].map(h => (
          <Card key={h}>
            <div className="flex items-center justify-between mb-3">
              <div>
                <div className="font-serif text-[20px] text-[var(--navy)]" style={{fontWeight:500}}>{h}</div>
                <div className="text-[12px] text-[var(--muted)]">Hall tutor: Mr. Saiful Islam · 312 residents</div>
              </div>
              <StatusPill status={h.includes('Hall 2')?'Escalated':'Under Review'} />
            </div>
            <div className="grid grid-cols-4 gap-3 mb-4 text-center">
              {[['Seat',4],['Curfew',2],['Roommate',3],['Warden',0]].map(([k,v]) => (
                <div key={k}>
                  <div className="font-mono text-[20px] text-[var(--ink)]">{v}</div>
                  <div className="smallcaps text-[var(--muted)]">{k}</div>
                </div>
              ))}
            </div>
            <GhostButton size="sm" icon="arrow-right">Open queue</GhostButton>
          </Card>
        ))}
      </div>
    </>
  );
}

// ---- Verification feed (university admin) ----
function UniFeedCard({ v, onDefer, onConfirm, onMarkFake, onDetail, busy, isDone, msg }) {
  const sc = v.signal_counts || {};
  const corrob = sc.corroborate ?? 0;
  const chall = sc.challenge ?? 0;
  const flags = sc.flags ?? 0;
  const isStepUpErr = msg && (msg.toLowerCase().includes('step') || msg.includes('401') || msg.includes('403'));

  return (
    <div className={`hair border rounded-sm p-4 space-y-3 ${isDone ? 'opacity-60' : ''}`}
      style={isDone ? { background:'var(--mist)' } : { background:'var(--paper)' }}>
      <div className="flex items-center gap-2 flex-wrap">
        <MonoChip tone="navy">#{v.post_number}</MonoChip>
        <Tag tone="navy">{v.scope}</Tag>
        <Tag tone="mist">{v.category}</Tag>
        {v.admin_confirmed && <Tag tone="sage">Confirmed</Tag>}
        <span className="ml-auto text-[11px] text-[var(--muted)] font-mono">{new Date(v.created_at).toLocaleDateString()}</span>
      </div>

      <h3 className="text-[15px] font-medium leading-snug" style={{textWrap:'pretty'}}>{v.title}</h3>

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

      {isStepUpErr && (
        <div className="px-3 py-2 rounded-sm text-[12px]" style={{ background:'rgba(184,137,58,0.10)', color:'#8A6520', border:'1px solid rgba(184,137,58,0.25)' }}>
          <Icon name="shield-alert" size={12} className="inline mr-1" />
          Step-up authentication required. Re-authenticate with your password in the Anchor app to confirm or mark-fake this post.
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

      <div className="flex items-center gap-2 pt-1">
        <GhostButton size="sm" icon="eye" onClick={onDetail}>View</GhostButton>
        <span className="flex-1" />
        <GhostButton size="sm" icon="rotate-ccw" disabled={busy || isDone} onClick={onDefer}>
          {busy ? '…' : 'Send back'}
        </GhostButton>
        <GhostButton size="sm" icon="x-circle" danger disabled={busy || isDone} onClick={onMarkFake}>
          Mark fake
        </GhostButton>
        <PrimaryButton size="sm" mode="sage" icon="check" disabled={busy || isDone} onClick={onConfirm}>
          {busy ? '…' : 'Approve'}
        </PrimaryButton>
      </div>
    </div>
  );
}

function UniVerificationFeed() {
  const TAB_API = { 'Pending': 'flagged', 'Confirmation': 'confirmation', 'Pre-publish': 'pre_publish' };
  const TABS = ['Pending', 'Confirmation', 'Pre-publish'];
  const [tab, setTab] = useState('Pending');
  const [posts, setPosts] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionMsg, setActionMsg] = useState({});
  const [actionLoading, setActionLoading] = useState({});
  const [detail, setDetail] = useState(null);

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
      await AnchorAPI.apiPostAuth(`/v1/feed/admin/${postId}/defer`, { internal_note: 'Deferred by admin.' });
      setActionMsg(m => ({...m, [postId]: 'deferred'}));
      setTimeout(() => loadPosts(tab), 400);
    } catch (err) {
      setActionMsg(m => ({...m, [postId]: err.message || 'Failed'}));
    } finally { setActionLoading(a => ({...a, [postId]: false})); }
  }

  async function handleConfirm(postId) {
    setActionLoading(a => ({...a, [postId]: true})); setActionMsg(m => ({...m, [postId]: ''}));
    try {
      await AnchorAPI.apiPostAuth(`/v1/feed/admin/${postId}/confirm`, { internal_note: 'Confirmed by admin.' });
      setActionMsg(m => ({...m, [postId]: 'confirmed'}));
      setTimeout(() => loadPosts(tab), 400);
    } catch (err) {
      setActionMsg(m => ({...m, [postId]: err.message || 'Confirm failed'}));
    } finally { setActionLoading(a => ({...a, [postId]: false})); }
  }

  async function handleMarkFake(postId) {
    setActionLoading(a => ({...a, [postId]: true})); setActionMsg(m => ({...m, [postId]: ''}));
    try {
      await AnchorAPI.apiPostAuth(`/v1/feed/admin/${postId}/mark-fake`, {
        public_note: 'Post marked as inaccurate by university admin after review.',
        internal_note: 'Marked fake by admin.',
      });
      setActionMsg(m => ({...m, [postId]: 'marked fake'}));
      setTimeout(() => loadPosts(tab), 400);
    } catch (err) {
      setActionMsg(m => ({...m, [postId]: err.message || 'Failed'}));
    } finally { setActionLoading(a => ({...a, [postId]: false})); }
  }

  async function openDetail(postId) {
    setDetail({ _loading: true });
    try {
      const d = await AnchorAPI.apiGet(`/v1/feed/admin/${postId}`);
      setDetail(d);
    } catch (err) {
      setDetail({ _error: err.message || 'Could not load post.' });
    }
  }

  const DONE = new Set(['deferred', 'confirmed', 'marked fake']);

  return (
    <>
      <PageHeader
        title="Verification feed"
        bn="যাচাইকরণ ফিড"
        description="Moderate posts from your tenant before they go platform-public. Confirm accurate reports, send back for more context, or mark as inaccurate."
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

      <AuditNote tone="navy" icon="shield-check" className="mb-4">
        Approving and marking-fake require step-up authentication (re-auth via Anchor app). Send-back does not.
      </AuditNote>

      <Card noPad>
        <div className="p-4 hair-b flex items-center gap-1">
          {TABS.map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-3 py-1.5 text-[13px] rounded-sm ${tab===t?'bg-[var(--sage)] text-white':'hair border text-[var(--graphite)]'}`}>
              {t}
            </button>
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
              <UniFeedCard
                key={v.id}
                v={v}
                onDefer={() => handleDefer(v.id)}
                onConfirm={() => handleConfirm(v.id)}
                onMarkFake={() => handleMarkFake(v.id)}
                onDetail={() => openDetail(v.id)}
                busy={actionLoading[v.id] || false}
                isDone={DONE.has(actionMsg[v.id])}
                msg={actionMsg[v.id] || ''}
              />
            ))}
          </div>
        )}
      </Card>

      <SlideOver open={!!detail} onClose={() => setDetail(null)} width={580}>
        {detail && detail._loading && (
          <div className="p-5 text-[13px] text-[var(--muted)]">Loading…</div>
        )}
        {detail && detail._error && (
          <div className="p-5 text-[13px]" style={{color:'var(--red)'}}>{detail._error}</div>
        )}
        {detail && !detail._loading && !detail._error && (
          <div className="p-5 space-y-4">
            <div className="flex items-center justify-between">
              <SectionLabel className="mb-0">Post detail</SectionLabel>
              <button onClick={() => setDetail(null)} className="w-7 h-7 rounded-sm hover:bg-[var(--mist)]/40 flex items-center justify-center">
                <Icon name="x" size={14} />
              </button>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <MonoChip tone="navy">#{detail.post_number}</MonoChip>
              <Tag tone="navy">{detail.scope}</Tag>
              <Tag tone="mist">{detail.category}</Tag>
              {detail.admin_confirmed && <Tag tone="sage">Confirmed</Tag>}
              <span className="ml-auto font-mono text-[11px] text-[var(--muted)]">{new Date(detail.created_at).toLocaleString()}</span>
            </div>
            <h3 className="font-serif text-[20px] text-[var(--navy)]" style={{fontWeight:500, textWrap:'pretty'}}>{detail.title}</h3>
            <div className="hair border rounded-sm p-3 bg-[#FDFBF7] text-[13px] leading-relaxed whitespace-pre-wrap">
              {detail.body || <span className="text-[var(--muted)] italic">No body text.</span>}
            </div>

            {detail.signal_counts && (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-[11.5px] font-medium" style={{ background:'rgba(74,107,92,0.10)', color:'var(--sage)' }}>
                  <Icon name="check-circle" size={11} />{detail.signal_counts.corroborate} corroborate
                </span>
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-[11.5px] font-medium" style={{ background:'rgba(196,69,54,0.10)', color:'var(--ember)' }}>
                  <Icon name="x-circle" size={11} />{detail.signal_counts.challenge} challenge
                </span>
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-[11.5px] font-medium" style={{ background:'rgba(184,137,58,0.12)', color:'var(--gold)' }}>
                  <Icon name="flag" size={11} />{detail.signal_counts.flags} flags
                </span>
              </div>
            )}

            {detail.flags && detail.flags.length > 0 && (
              <>
                <SectionLabel>Flags</SectionLabel>
                <div className="space-y-1.5">
                  {detail.flags.map((f, i) => (
                    <div key={i} className="hair border rounded-sm p-2.5 text-[12px] flex items-center gap-2">
                      <Icon name="flag" size={12} className="text-[var(--gold)]" />
                      <span className="font-mono text-[var(--muted)]">{f.flag_reason}</span>
                      {f.note && <span className="text-[var(--ink)]">— {f.note}</span>}
                      <span className="ml-auto font-mono text-[10px] text-[var(--muted)]">{new Date(f.created_at).toLocaleDateString()}</span>
                    </div>
                  ))}
                </div>
              </>
            )}

            {detail.moderation_history && detail.moderation_history.length > 0 && (
              <>
                <SectionLabel>Moderation history</SectionLabel>
                <div className="space-y-2">
                  {detail.moderation_history.map((m, i) => (
                    <div key={i} className="hair border rounded-sm p-2.5 text-[12px]">
                      <div className="flex items-center gap-2">
                        <MonoChip>{m.action}</MonoChip>
                        <span className="text-[var(--muted)] font-mono text-[10px]">{new Date(m.created_at).toLocaleString()}</span>
                      </div>
                      {m.public_note && <p className="mt-1 text-[var(--ink)]">{m.public_note}</p>}
                      {m.internal_note && <p className="mt-0.5 text-[var(--muted)] italic text-[11px]">{m.internal_note}</p>}
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}
      </SlideOver>
    </>
  );
}

// ---- generic stub for remaining university screens ----
function StubScreen({ title, description, items=[], icon='construction', bn }) {
  return (
    <>
      <PageHeader title={title} bn={bn} description={description} />
      <Card>
        <EmptyState icon={icon} title="Designed in the next phase" body="This surface is part of the v1.0 rollout. The information architecture is finalised; the implementation arrives in the next iteration." />
        {items.length>0 && (
          <div className="mt-4 grid grid-cols-2 gap-2 max-w-[680px] mx-auto">
            {items.map(it => (
              <div key={it} className="hair border rounded-sm p-3 text-[12.5px] flex items-center gap-2">
                <Icon name="circle-dot" size={12} className="text-[var(--muted)]" />
                <span>{it}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}

Object.assign(window, { UniNotices, UniGeofence, UniClassrooms, UniTeacherGrievances, UniDeptGrievances, UniHostel, StubScreen, UniFeedCard, UniVerificationFeed });
