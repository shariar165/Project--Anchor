// Notices, Alerts, Classroom reports, Hostel, Grievances, plus stubs

const STATE_LABEL_MISC = {
  draft:'Draft', moderation_queue:'Under Review', routed:'Submitted',
  subject_notified:'Under Review', subject_responded:'Under Review',
  under_review:'Under Review', resolved:'Resolved', dismissed:'Rejected',
  withdrawn:'Withdrawn', spam_rejected:'Rejected',
};

function UniNotices({ onGo }) {
  const [prompt, setPrompt] = useState('Library will extend hours to 1 AM during the finals week (June 8–15).');
  const [generated, setGenerated] = useState('Dear students,\n\nDuring the final examinations of Spring 2026 (June 8–15), the central library reading hall will remain open until 1:00 AM. Photo ID is required for entry after 10 PM. Group study rooms must be reserved in advance through the library portal.\n\nWe wish you a productive finals week.\n\nRegistrar’s Office\nDaffodil International University');
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
                <div className="mt-1 text-[11px] text-[var(--muted)]">Registrar’s Office · DIU</div>
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

// ---- Campus Zone Management (Leaflet polygon CRUD via /v1/admin/campus-zones) ----
function UniCampusZones({ onGo }) {
  const [zones, setZones] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [mapError, setMapError] = useState(null);

  // ‘list’ | ‘draw’ | ‘form’
  const [panelMode, setPanelMode] = useState(‘list’);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState({ name: ‘’, description: ‘’ });
  const [formError, setFormError] = useState(null);
  const [saving, setSaving] = useState(false);

  const [confirmArchive, setConfirmArchive] = useState(null);
  const [archiving, setArchiving] = useState(false);

  // Drawing state
  const [drawingVertices, setDrawingVertices] = useState([]);
  const drawingVerticesRef = useRef([]);
  const isDrawingRef = useRef(false);

  const mapDivRef = useRef(null);
  const leafletMapRef = useRef(null);
  const zoneLayersRef = useRef({});
  const draftLayerRef = useRef(null);

  const CAMPUS_COLOR = ‘#22c55e’;

  function load() {
    setLoading(true);
    setLoadError(null);
    AnchorAPI.apiGet(‘/v1/admin/campus-zones?include_archived=false’)
      .then(data => { setZones(Array.isArray(data) ? data : []); setLoading(false); })
      .catch(err => {
        const msg = err.message || ‘Failed to load campus zones’;
        setLoadError(msg.includes(‘Session expired’) ? ‘Session expired — please sign in again.’ : msg);
        setLoading(false);
      });
  }

  useEffect(() => { load(); }, []);

  function _clearDraftLayer() {
    if (draftLayerRef.current && leafletMapRef.current) {
      try { draftLayerRef.current.remove(); } catch (_) {}
      draftLayerRef.current = null;
    }
  }

  // Init Leaflet once
  useEffect(() => {
    if (!mapDivRef.current || leafletMapRef.current) return;
    if (!window.L) { setMapError(‘Map library failed to load. Please refresh.’); return; }
    try {
      const map = window.L.map(mapDivRef.current, { zoomControl: true }).setView([23.7450, 90.3718], 14);
      window.L.tileLayer(‘https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png’, {
        attribution: ‘© OpenStreetMap contributors’, maxZoom: 19,
      }).addTo(map);
      leafletMapRef.current = map;

      map.on(‘click’, (e) => {
        if (!isDrawingRef.current) return;
        const newVerts = [...drawingVerticesRef.current, [e.latlng.lat, e.latlng.lng]];
        drawingVerticesRef.current = newVerts;
        setDrawingVertices([...newVerts]);

        _clearDraftLayer();
        if (newVerts.length >= 2) {
          const layer = window.L.polygon(newVerts, {
            color: CAMPUS_COLOR, fillColor: CAMPUS_COLOR, fillOpacity: 0.15,
            weight: 2, dashArray: ‘6 4’,
          }).addTo(map);
          draftLayerRef.current = layer;
        }
      });
    } catch (err) {
      setMapError(‘Map failed to initialise: ‘ + (err.message || ‘unknown error’));
    }
    return () => {
      if (leafletMapRef.current) { leafletMapRef.current.remove(); leafletMapRef.current = null; }
      zoneLayersRef.current = {};
    };
  }, []);

  // Redraw all campus zones when list changes
  useEffect(() => {
    const map = leafletMapRef.current;
    if (!map || !window.L) return;
    Object.values(zoneLayersRef.current).forEach(l => { try { l.remove(); } catch (_) {} });
    zoneLayersRef.current = {};

    zones.forEach(zone => {
      if (!Array.isArray(zone.polygon_coords) || zone.polygon_coords.length < 3) return;
      const layer = window.L.polygon(zone.polygon_coords, {
        color: CAMPUS_COLOR, fillColor: CAMPUS_COLOR, fillOpacity: 0.18, weight: 2,
      });
      layer.bindPopup(`<strong>${zone.name || ‘Campus Zone’}</strong><br/>${zone.polygon_coords.length} vertices`);
      layer.on(‘click’, (ev) => { window.L.DomEvent.stopPropagation(ev); openEdit(zone); });
      layer.addTo(map);
      zoneLayersRef.current[zone.id] = layer;
    });
  }, [zones]);

  function startDraw() {
    setDrawingVertices([]);
    drawingVerticesRef.current = [];
    _clearDraftLayer();
    isDrawingRef.current = true;
    setPanelMode(‘draw’);
    setFormError(null);
  }

  function undoVertex() {
    const newVerts = drawingVerticesRef.current.slice(0, -1);
    drawingVerticesRef.current = newVerts;
    setDrawingVertices([...newVerts]);
    _clearDraftLayer();
    const map = leafletMapRef.current;
    if (newVerts.length >= 2 && map && window.L) {
      const layer = window.L.polygon(newVerts, {
        color: CAMPUS_COLOR, fillColor: CAMPUS_COLOR, fillOpacity: 0.15,
        weight: 2, dashArray: ‘6 4’,
      }).addTo(map);
      draftLayerRef.current = layer;
    }
  }

  function finishDraw() {
    const verts = drawingVerticesRef.current;
    if (verts.length < 3) { setFormError(‘Draw at least 3 points on the map to create a polygon.’); return; }
    isDrawingRef.current = false;
    setEditing(null);
    setForm({ name: ‘’, description: ‘’ });
    setFormError(null);
    setPanelMode(‘form’);
  }

  function cancelDraw() {
    isDrawingRef.current = false;
    _clearDraftLayer();
    setDrawingVertices([]);
    drawingVerticesRef.current = [];
    setPanelMode(‘list’);
    setFormError(null);
  }

  function openEdit(zone) {
    setEditing(zone);
    setForm({ name: zone.name || ‘’, description: zone.description || ‘’ });
    setFormError(null);
    setPanelMode(‘form’);
  }

  function closeForm() {
    setPanelMode(‘list’);
    setEditing(null);
    setFormError(null);
    if (!editing) {
      // coming from draw mode — clean up draft
      _clearDraftLayer();
      isDrawingRef.current = false;
      setDrawingVertices([]);
      drawingVerticesRef.current = [];
    }
  }

  async function handleSave(e) {
    e.preventDefault();
    setFormError(null);

    if (editing) {
      const patch = { name: form.name || null, description: form.description || null };
      setSaving(true);
      try {
        await AnchorAPI.apiPatch(`/v1/admin/campus-zones/${editing.id}`, patch);
        closeForm(); load();
      } catch (err) { setFormError(err.message || ‘Save failed’); }
      finally { setSaving(false); }
      return;
    }

    // Create — use vertices from drawingVerticesRef
    const verts = drawingVerticesRef.current;
    if (!verts || verts.length < 3) { setFormError(‘Draw at least 3 points on the map first.’); return; }

    setSaving(true);
    const center_lat = verts.reduce((s, v) => s + v[0], 0) / verts.length;
    const center_lng = verts.reduce((s, v) => s + v[1], 0) / verts.length;
    try {
      await AnchorAPI.apiPostAuth(‘/v1/admin/campus-zones’, {
        name: form.name?.trim() || ‘Campus Zone’,
        description: form.description || null,
        polygon_coords: verts,
        zone_type: ‘campus’,
        shape_type: ‘polygon’,
        center_lat,
        center_lng,
      });
      _clearDraftLayer();
      drawingVerticesRef.current = [];
      setDrawingVertices([]);
      closeForm();
      load();
    } catch (err) { setFormError(err.message || ‘Save failed — please try again’); }
    finally { setSaving(false); }
  }

  async function handleArchive() {
    if (!confirmArchive) return;
    setArchiving(true);
    try {
      await AnchorAPI.apiDelete(`/v1/admin/campus-zones/${confirmArchive.id}`);
    } catch (_) {}
    finally {
      setArchiving(false);
      setConfirmArchive(null);
      load();
    }
  }

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <>
      <PageHeader
        title="Campus zones"
        bn="ক্যাম্পাস এলাকা"
        description="Draw polygon zones on your campus map. Students see these as green safe-area overlays."
        actions={
          panelMode === ‘list’ ? (
            <PrimaryButton icon="plus" mode="sage" size="sm" onClick={startDraw}>
              New zone
            </PrimaryButton>
          ) : panelMode === ‘draw’ ? (
            <>
              <GhostButton icon="undo-2" size="sm" onClick={undoVertex} disabled={drawingVertices.length === 0}>Undo</GhostButton>
              <GhostButton size="sm" icon="x" onClick={cancelDraw}>Cancel</GhostButton>
              <PrimaryButton
                icon="check" mode="sage" size="sm"
                onClick={finishDraw}
                disabled={drawingVertices.length < 3}
              >
                Finish ({drawingVertices.length} pts)
              </PrimaryButton>
            </>
          ) : (
            <GhostButton size="sm" icon="x" onClick={closeForm}>Cancel</GhostButton>
          )
        }
      />

      {loadError && (
        <div className="mb-4 px-3 py-2 rounded-sm text-[12.5px] flex items-center gap-2" style={{ background: ‘rgba(232,49,42,0.08)’, color: ‘var(--red)’, border: ‘1px solid rgba(232,49,42,0.2)’ }}>
          <Icon name="circle-alert" size={13} className="shrink-0" />
          {loadError}
          <button onClick={load} className="ml-auto underline text-[12px]">Retry</button>
        </div>
      )}

      {formError && (
        <div className="mb-4 px-3 py-2 rounded-sm text-[12.5px] flex items-center gap-2" style={{ background: ‘rgba(232,49,42,0.08)’, color: ‘var(--red)’, border: ‘1px solid rgba(232,49,42,0.2)’ }}>
          <Icon name="circle-alert" size={13} className="shrink-0" />
          {formError}
        </div>
      )}

      <div className="flex gap-5 mt-4" style={{ height: ‘calc(100vh - 180px)’, minHeight: 480 }}>

        {/* ── Leaflet map ── */}
        <div className="flex-1 rounded-sm overflow-hidden border hair relative" style={{ minWidth: 0, height: ‘100%’ }}>
          {mapError ? (
            <div style={{ position: ‘absolute’, inset: 0, display: ‘flex’, flexDirection: ‘column’, alignItems: ‘center’, justifyContent: ‘center’, padding: 24, textAlign: ‘center’, background: ‘var(--mist)’ }}>
              <Icon name="map-off" size={32} className="mb-3 text-[var(--muted)]" />
              <p className="text-[13px] text-[var(--graphite)]">{mapError}</p>
            </div>
          ) : (
            <>
              {panelMode === ‘draw’ && (
                <div
                  className="absolute top-3 z-[1000] px-3 py-1.5 rounded text-[12px] font-medium flex items-center gap-2"
                  style={{ left: ‘50%’, transform: ‘translateX(-50%)’, background: ‘#16a34a’, color: ‘white’, boxShadow: ‘var(--shadow)’, pointerEvents: ‘all’ }}
                >
                  <Icon name="map-pin" size={13} />
                  {drawingVertices.length < 3
                    ? `Click to add vertices (${drawingVertices.length}/3 minimum)`
                    : `${drawingVertices.length} vertices — click "Finish" when done`
                  }
                </div>
              )}
              <div
                ref={mapDivRef}
                style={{ position: ‘absolute’, top: 0, left: 0, right: 0, bottom: 0, cursor: panelMode === ‘draw’ ? ‘crosshair’ : undefined }}
              />
            </>
          )}
        </div>

        {/* ── Side panel ── */}
        <div
          className="flex flex-col rounded-sm border hair bg-[var(--paper)] overflow-hidden"
          style={{ width: 320, flexShrink: 0 }}
        >
          {/* List mode */}
          {panelMode === ‘list’ && (
            <>
              <div className="px-4 py-3 hair-b shrink-0">
                <div className="text-[13px] font-semibold text-[var(--graphite)]">Campus zones</div>
                <div className="text-[10px] text-[var(--muted)] mt-0.5">{zones.length} active zone{zones.length !== 1 ? ‘s’ : ‘’}</div>
              </div>
              <div className="flex-1 overflow-y-auto scrollbar-none">
                {loading && (
                  <div className="flex items-center justify-center py-10 gap-2 text-[var(--muted)] text-[13px]">
                    <Icon name="loader-circle" size={15} />
                    Loading…
                  </div>
                )}
                {!loading && zones.length === 0 && !loadError && (
                  <div className="flex flex-col items-center justify-center py-12 px-4 text-center">
                    <Icon name="map-pin-off" size={28} className="mb-2 text-[var(--muted)]" />
                    <p className="text-[12px] text-[var(--muted)]">No campus zones yet.</p>
                    <button
                      onClick={startDraw}
                      className="mt-3 text-[12px] underline"
                      style={{ color: ‘var(--sage)’ }}
                    >
                      Click Create to draw the first one.
                    </button>
                  </div>
                )}
                {!loading && zones.map(zone => (
                  <div
                    key={zone.id}
                    className="px-4 py-3 hair-b last:border-0 hover:bg-[var(--mist)]/20 group cursor-pointer"
                    onClick={() => openEdit(zone)}
                  >
                    <div className="flex items-start gap-2.5">
                      <span className="mt-1 w-2.5 h-2.5 rounded-sm shrink-0" style={{ background: CAMPUS_COLOR }} />
                      <div className="flex-1 min-w-0">
                        <div className="text-[12px] font-semibold text-[var(--graphite)] truncate">
                          {zone.name || ‘Unnamed zone’}
                        </div>
                        <div className="flex gap-1.5 mt-0.5 text-[11px] text-[var(--muted)]">
                          <span>Polygon</span>
                          <span>·</span>
                          <span>{(zone.polygon_coords || []).length} vertices</span>
                          {zone.created_at && (
                            <>
                              <span>·</span>
                              <span>{zone.created_at.slice(0, 10)}</span>
                            </>
                          )}
                        </div>
                      </div>
                      <Icon name="chevron-right" size={14} className="text-[var(--mist)] group-hover:text-[var(--muted)] shrink-0 mt-0.5" />
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}

          {/* Draw mode hint */}
          {panelMode === ‘draw’ && (
            <div className="flex flex-col items-center justify-center flex-1 p-6 text-center">
              <Icon name="map-pin" size={30} className="mb-3" style={{ color: CAMPUS_COLOR }} />
              <p className="text-[13px] font-semibold text-[var(--graphite)] mb-1">Drawing polygon</p>
              <p className="text-[12px] text-[var(--muted)]">Click on the map to place vertices. Need at least 3 to finish.</p>
              <div className="mt-3 font-mono text-[24px] font-bold" style={{ color: CAMPUS_COLOR }}>
                {drawingVertices.length}
              </div>
              <div className="text-[11px] text-[var(--muted)]">vertices placed</div>
            </div>
          )}

          {/* Form mode */}
          {panelMode === ‘form’ && (
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
                  {editing ? ‘Edit Zone’ : ‘New Zone’}
                </span>
              </div>

              <div className="flex-1 overflow-y-auto scrollbar-none px-4 py-4">
                {!editing && (
                  <AuditNote tone="sage" icon="check-circle" className="mb-4">
                    {drawingVerticesRef.current.length} vertices captured. Name this zone and save.
                  </AuditNote>
                )}

                <form id="campus-zone-form" onSubmit={handleSave} className="space-y-4">
                  <div>
                    <label className="block text-[11px] font-semibold text-[var(--graphite)] uppercase tracking-wide mb-1">
                      Zone name <span className="text-[var(--muted)] normal-case font-normal">(optional)</span>
                    </label>
                    <input
                      value={form.name}
                      onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                      placeholder="e.g. Main Campus, Library Block, Sports Ground"
                      className="w-full px-2.5 py-2 hair border rounded-sm bg-white text-[12px]"
                    />
                  </div>
                  <div>
                    <label className="block text-[11px] font-semibold text-[var(--graphite)] uppercase tracking-wide mb-1">
                      Description <span className="text-[var(--muted)] normal-case font-normal">(optional)</span>
                    </label>
                    <textarea
                      rows={3}
                      value={form.description}
                      onChange={e => setForm(f => ({ ...f, description: e.target.value }))}
                      placeholder="Shown in the zone popup on the student map."
                      className="w-full px-2.5 py-2 hair border rounded-sm bg-white text-[12px] resize-none"
                    />
                  </div>
                  {editing && (
                    <div>
                      <label className="block text-[11px] font-semibold text-[var(--graphite)] uppercase tracking-wide mb-1">Polygon</label>
                      <div className="px-2.5 py-2 rounded-sm text-[12px] font-mono" style={{ background: ‘var(--mist)’, color: ‘var(--graphite)’ }}>
                        {(editing.polygon_coords || []).length} vertices (shape fixed)
                      </div>
                    </div>
                  )}
                </form>

                {editing && (
                  <div className="pt-4 mt-4 border-t hair">
                    <button
                      type="button"
                      onClick={() => setConfirmArchive(editing)}
                      className="w-full flex items-center gap-2 px-3 py-2 rounded-sm border text-[12px] transition-colors"
                      style={{ borderColor: ‘var(--ember)’, color: ‘var(--ember)’, background: ‘var(--ember-tint)’ }}
                    >
                      <Icon name="trash-2" size={13} />
                      Delete this zone
                    </button>
                  </div>
                )}
              </div>

              <div className="px-4 py-3 hair-t flex gap-2 shrink-0">
                <PrimaryButton
                  as="button"
                  type="submit"
                  form="campus-zone-form"
                  mode="sage"
                  icon={editing ? ‘save’ : ‘map-pin’}
                  disabled={saving}
                  className="flex-1 justify-center"
                >
                  {saving ? ‘Saving…’ : editing ? ‘Save changes’ : ‘Create zone’}
                </PrimaryButton>
                <GhostButton type="button" onClick={closeForm}>Cancel</GhostButton>
              </div>
            </div>
          )}
        </div>
      </div>

      <ConfirmModal
        open={!!confirmArchive}
        onClose={() => setConfirmArchive(null)}
        onConfirm={handleArchive}
        title="Delete this zone?"
        body={confirmArchive ? `"${confirmArchive.name || ‘This zone’}" will be removed from the student map immediately.` : ‘’}
        confirmWord="DELETE"
        confirmLabel={archiving ? ‘Deleting…’ : ‘Delete zone’}
        tone="red"
      />
    </>
  );
}

// Keep old name as alias so existing routes still work
const UniGeofence = UniCampusZones;

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

// ---- Step-up modal for uni admin ----
function UniStepUpModal({ onDone, onCancel }) {
  const [pw, setPw] = React.useState('');
  const [err, setErr] = React.useState('');
  const [loading, setLoading] = React.useState(false);

  async function submit() {
    setLoading(true); setErr('');
    try {
      const data = await AnchorAPI.apiPostAuth('/auth/stepup', { password: pw });
      onDone(data.stepup_token);
    } catch (e) { setErr(e.message || 'Authentication failed'); }
    setLoading(false);
  }

  return (
    <div style={{ position:'fixed', inset:0, background:'rgba(11,29,53,0.55)', zIndex:200, display:'flex', alignItems:'center', justifyContent:'center' }}>
      <div style={{ background:'var(--paper)', borderRadius:12, padding:'28px 24px', width:340, boxShadow:'0 8px 32px rgba(0,0,0,0.18)' }}>
        <div style={{ fontWeight:700, fontSize:15, color:'var(--navy)', marginBottom:6 }}>Confirm your identity</div>
        <div style={{ fontSize:13, color:'var(--graphite)', marginBottom:16 }}>This action requires your password.</div>
        <input
          type="password" value={pw} onChange={e => setPw(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && submit()}
          placeholder="Password"
          style={{ width:'100%', padding:'10px 12px', borderRadius:8, fontSize:13, border:'1.5px solid var(--mist)', marginBottom:10, boxSizing:'border-box' }}
          autoFocus
        />
        {err && <div style={{ color:'var(--ember)', fontSize:12, marginBottom:8 }}>{err}</div>}
        <div style={{ display:'flex', gap:8 }}>
          <GhostButton size="sm" onClick={onCancel} style={{ flex:1 }}>Cancel</GhostButton>
          <PrimaryButton size="sm" mode="sage" onClick={submit} disabled={loading || !pw} style={{ flex:1 }}>
            {loading ? 'Verifying…' : 'Confirm'}
          </PrimaryButton>
        </div>
      </div>
    </div>
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
  const [stepUp, setStepUp] = useState(null); // { postId, action: 'confirm'|'fake' }

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

  function handleConfirm(postId) { setStepUp({ postId, action: 'confirm' }); }
  function handleMarkFake(postId) { setStepUp({ postId, action: 'fake' }); }

  async function doActionWithToken(postId, action, stepupToken) {
    setActionLoading(a => ({...a, [postId]: true})); setActionMsg(m => ({...m, [postId]: ''}));
    try {
      const path = action === 'confirm' ? 'confirm' : 'mark-fake';
      const body = action === 'confirm'
        ? { internal_note: 'Confirmed by admin.' }
        : { public_note: 'Post marked as inaccurate by university admin after review.', internal_note: 'Marked fake by admin.' };
      const r = await fetch(`http://localhost:8000/v1/feed/admin/${postId}/${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + stepupToken },
        body: JSON.stringify(body),
      });
      if (!r.ok) { const d = await r.json(); throw new Error(d.detail || 'Action failed'); }
      setActionMsg(m => ({...m, [postId]: action === 'confirm' ? 'confirmed' : 'marked fake'}));
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
      {stepUp && (
        <UniStepUpModal
          onDone={token => { setStepUp(null); doActionWithToken(stepUp.postId, stepUp.action, token); }}
          onCancel={() => setStepUp(null)}
        />
      )}
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
        Approving and marking-fake require step-up authentication — you'll be prompted for your password. Send-back does not.
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

Object.assign(window, { UniNotices, UniCampusZones, UniGeofence, UniClassrooms, UniTeacherGrievances, UniDeptGrievances, UniHostel, StubScreen, UniFeedCard, UniVerificationFeed });
