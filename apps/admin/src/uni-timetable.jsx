// Timetable Generator — Admin UI (UX-upgraded, rooms×slots grid)
var { useState, useEffect, useRef } = React;

const TT_BASE = "/v1/admin/timetable";
const DAY_NAMES = ["Sat", "Sun", "Mon", "Tue", "Wed", "Thu"];
const DAY_IDX_MAP = {
  sat:0, sun:1, mon:2, tue:3, wed:4, thu:5,
  saturday:0, sunday:1, monday:2, tuesday:3, wednesday:4, thursday:5,
};
const SECTION_COLORS = [
  "#4A6B5C","#B8893A","#C44536","#3B6EA5","#7B5EA7",
  "#2E8B8B","#D4782A","#5A8A3C","#A53B5E","#3B7A8A",
];
const CONSTRAINT_LABELS = {
  no_overlap_teacher:    "No teacher overlap",
  no_overlap_section:    "No section overlap",
  no_overlap_room:       "No room double-booking",
  room_type_match:       "Room type must match course type",
  weekly_count:          "Weekly class count",
  max_classes_per_day:   "Max classes per day (per teacher)",
  consecutive_limit:     "Max consecutive slots",
  off_day:               "Teacher off-day",
  friday_excluded:       "Friday never scheduled",
  teacher_credit_band:   "Teacher credit band",
  pref_slot_reward:      "Preferred slot reward",
  gap_minimize:          "Minimize teacher gaps",
  online_penalty:        "Penalize online rooms",
  adjacent_lab:          "Adjacent lab groups preferred",
};
const EMPTY_HINTS = {
  courses:     { icon:"book-open",     msg:"Add or import the courses being offered this term." },
  rooms:       { icon:"building",      msg:"Add classrooms and labs the solver can assign." },
  faculty:     { icon:"user-circle",   msg:"Link teachers and set their credit caps before generating." },
  batches:     { icon:"users",         msg:"Create batches, then generate sections with one click." },
  offerings:   { icon:"link",          msg:"Pair each course with the batches taking it this term." },
  eligibility: { icon:"check-square",  msg:"Specify which teachers can teach which courses." },
};

// ── SectionLabel helper ───────────────────────────────────────────────────────
function SectionLabel({ children, right }) {
  return (
    <div className="flex items-center justify-between mb-3">
      <div className="smallcaps text-[var(--muted)]">{children}</div>
      {right}
    </div>
  );
}

// ── TermStatusBar — always visible across all tabs ────────────────────────────
function TermStatusBar({ terms, termId, onTermChange, version, onVersionChange, onAddTerm }) {
  const [adding, setAdding] = useState(false);
  const [newName, setNewName] = useState("");
  const [saving, setSaving] = useState(false);

  async function createTerm() {
    if (!newName.trim()) return;
    setSaving(true);
    try {
      await onAddTerm(newName.trim());
      setNewName(""); setAdding(false);
    } catch (e) { alert(e.message || "Failed to create term"); }
    finally { setSaving(false); }
  }

  return (
    <div className="flex items-center gap-2.5 mb-4 px-3 py-2.5 hair border rounded-sm flex-wrap"
      style={{ background: "rgba(74,107,92,0.04)" }}>
      <Icon name="calendar" size={14} style={{ color: "var(--sage)" }} />
      <span className="smallcaps text-[var(--muted)]">Term</span>
      <select className="hair border rounded-sm bg-white px-2 py-1 text-[13px]"
        value={termId} onChange={e => onTermChange(e.target.value)}>
        <option value="">— select term —</option>
        {terms.map(t => (
          <option key={t.id} value={t.id}>{t.name}{t.is_active ? " ✓" : ""}</option>
        ))}
      </select>
      {!adding ? (
        <GhostButton size="sm" icon="plus" onClick={() => setAdding(true)}>New term</GhostButton>
      ) : (
        <div className="flex items-center gap-1.5">
          <input autoFocus value={newName} onChange={e => setNewName(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter") createTerm(); if (e.key === "Escape") { setAdding(false); setNewName(""); } }}
            placeholder="e.g. Spring 2027"
            className="px-2 py-1 hair border rounded-sm text-[12.5px] w-36" />
          <GhostButton size="sm" onClick={createTerm} disabled={saving}>{saving ? "…" : "Create"}</GhostButton>
          <GhostButton size="sm" onClick={() => { setAdding(false); setNewName(""); }}>✕</GhostButton>
        </div>
      )}
      <div className="flex-1" />
      {termId && (
        <>
          <span className="smallcaps text-[var(--muted)]">Version</span>
          <input type="number" min="1" value={version} onChange={e => onVersionChange(+e.target.value)}
            className="w-14 px-2 py-1 hair border rounded-sm text-[12px] font-mono" />
        </>
      )}
    </div>
  );
}

// ── ProgressStepper — visual guide with completed-step check marks ────────────
function ProgressStepper({ currentTab, tabs, onClick }) {
  const icons = ["database", "clock", "sliders", "cpu", "layout-grid", "send"];
  return (
    <div className="flex items-center mb-6 overflow-x-auto pb-1" style={{ gap: 0 }}>
      {tabs.map((t, i) => (
        <React.Fragment key={t}>
          <button onClick={() => onClick(i)}
            className="flex items-center gap-1.5 px-3 py-2 text-[12px] whitespace-nowrap transition rounded-sm"
            style={
              currentTab === i ? { background: "var(--sage)", color: "white", fontWeight: 500 }
              : currentTab > i ? { color: "var(--sage)" }
              : { color: "var(--muted)" }
            }>
            {currentTab > i
              ? <Icon name="check" size={12} />
              : <Icon name={icons[i]} size={12} />}
            <span>{t}</span>
          </button>
          {i < tabs.length - 1 && (
            <div style={{
              width: 16, height: 1, flexShrink: 0,
              background: currentTab > i ? "var(--sage)" : "var(--mist)",
            }} />
          )}
        </React.Fragment>
      ))}
    </div>
  );
}

// ── UniTimetable root — shared term + version state ───────────────────────────
function UniTimetable({ onGo }) {
  const [tab, setTab] = useState(0);
  const [terms, setTerms] = useState([]);
  const [termId, setTermId] = useState("");
  const [version, setVersion] = useState(1);

  useEffect(() => {
    AnchorAPI.apiGet(`${TT_BASE}/terms`)
      .then(d => {
        const list = Array.isArray(d) ? d : [];
        setTerms(list);
        const active = list.find(t => t.is_active);
        if (active) setTermId(active.id);
      }).catch(() => {});
  }, []);

  async function addTerm(name) {
    const t = await AnchorAPI.apiPostAuth(`${TT_BASE}/terms`, { name });
    setTerms(ts => [...ts, t]);
    setTermId(t.id);
  }

  const tabs = ["Data", "Schedule", "Rules", "Generate", "Grid", "Publish"];

  return (
    <>
      <TermStatusBar
        terms={terms} termId={termId} onTermChange={setTermId}
        version={version} onVersionChange={setVersion}
        onAddTerm={addTerm}
      />
      <PageHeader
        title="Timetable Generator"
        bn="ক্লাস সময়সূচী তৈরি করুন"
        description="Data → Schedule → Rules → Generate → Grid → Publish."
      />
      <ProgressStepper currentTab={tab} tabs={tabs} onClick={setTab} />

      {tab === 0 && <TimetableData termId={termId} />}
      {tab === 1 && <ScheduleConfig termId={termId} onDone={() => setTab(2)} />}
      {tab === 2 && <TimetableRules termId={termId} onNext={() => setTab(3)} />}
      {tab === 3 && <TimetableGenerate termId={termId} onSolved={v => { setVersion(v); setTab(4); }} />}
      {tab === 4 && <TimetableGrid termId={termId} version={version} onVersionChange={setVersion} onPublish={() => setTab(5)} />}
      {tab === 5 && <TimetablePublish termId={termId} version={version} onGo={onGo} />}
    </>
  );
}

// ── Tab 0: Data ───────────────────────────────────────────────────────────────
function TimetableData({ termId }) {
  const [sub, setSub] = useState("courses");
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [importMsg, setImportMsg] = useState("");
  const fileRef = useRef();

  const subTabs = ["courses", "rooms", "faculty", "batches", "offerings", "eligibility"];
  const subLabels = { courses:"Courses", rooms:"Rooms", faculty:"Faculty", batches:"Batches", offerings:"Offerings", eligibility:"Eligibility" };

  async function load() {
    setLoading(true);
    try {
      const data = await AnchorAPI.apiGet(`${TT_BASE}/${sub}`);
      setItems(Array.isArray(data) ? data : []);
    } catch { setItems([]); }
    finally { setLoading(false); }
  }

  useEffect(() => { load(); setShowAdd(false); setImportMsg(""); }, [sub]);

  async function handleImport(e) {
    const file = e.target.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await fetch(
        `http://localhost:8000${TT_BASE}/import?entity=${sub}`,
        { method:"POST", headers:{ Authorization:`Bearer ${localStorage.getItem("anchor_admin_access_token")}` }, body:fd }
      ).then(r => r.json());
      setImportMsg(`Imported ${res.created} rows${res.errors?.length ? ` · ${res.errors.length} errors` : ""}`);
      load();
    } catch { setImportMsg("Import failed"); }
    fileRef.current.value = "";
  }

  return (
    <Card noPad>
      {/* Sub-tab strip */}
      <div className="flex items-center gap-0.5 px-3 pt-2 hair-b flex-wrap">
        {subTabs.map(t => (
          <button key={t} onClick={() => setSub(t)}
            className={`px-3 py-2 text-[12.5px] -mb-px border-b-2 transition ${sub === t ? "border-[var(--sage)] text-[var(--sage)] font-medium" : "border-transparent text-[var(--graphite)] hover:text-[var(--ink)]"}`}>
            {subLabels[t]}
          </button>
        ))}
        <div className="flex-1" />
        <div className="flex items-center gap-2 mb-1.5">
          {importMsg && <span className="text-[11px] text-[var(--sage)]">{importMsg}</span>}
          {(sub === "courses" || sub === "rooms") && (
            <>
              <input ref={fileRef} type="file" accept=".csv,.xlsx" className="hidden" onChange={handleImport} />
              <GhostButton size="sm" icon="upload" onClick={() => fileRef.current.click()}>Import</GhostButton>
            </>
          )}
          <PrimaryButton size="sm" icon="plus" mode="sage" onClick={() => setShowAdd(true)}>Add</PrimaryButton>
        </div>
      </div>

      {loading ? (
        <div className="p-8 text-center text-[var(--muted)] text-[13px]">Loading…</div>
      ) : items.length === 0 ? (
        <DataEmptyState sub={sub} />
      ) : (
        <DataEntityTable sub={sub} items={items} onRefresh={load} />
      )}

      {showAdd && sub === "offerings" ? (
        <AddOfferingSlideOver termId={termId} onClose={() => setShowAdd(false)} onDone={() => { setShowAdd(false); load(); }} />
      ) : showAdd && sub === "eligibility" ? (
        <AddEligibilitySlideOver onClose={() => setShowAdd(false)} onDone={() => { setShowAdd(false); load(); }} />
      ) : showAdd ? (
        <AddEntitySlideOver sub={sub} onClose={() => setShowAdd(false)} onDone={() => { setShowAdd(false); load(); }} />
      ) : null}
    </Card>
  );
}

function DataEmptyState({ sub }) {
  const hint = EMPTY_HINTS[sub] || { icon:"inbox", msg:"No entries yet." };
  return (
    <div className="flex flex-col items-center gap-3 py-14 text-center px-6">
      <div className="w-10 h-10 rounded-full flex items-center justify-center"
        style={{ background: "rgba(74,107,92,0.08)" }}>
        <Icon name={hint.icon} size={18} style={{ color: "var(--sage)" }} />
      </div>
      <div className="text-[13px] text-[var(--graphite)] max-w-xs">{hint.msg}</div>
    </div>
  );
}

function DataEntityTable({ sub, items, onRefresh }) {
  async function del(url) {
    if (!confirm("Delete this item?")) return;
    try { await AnchorAPI.apiDelete(url); onRefresh(); }
    catch (e) { alert(e.message || "Delete failed"); }
  }

  const delBtn = (url) => (
    <button onClick={() => del(url)} className="text-[var(--muted)] hover:text-[var(--red)]">
      <Icon name="trash-2" size={13} />
    </button>
  );

  if (sub === "courses") return (
    <DataTable columns={[
      { key:"code",   label:"Code",        render:r => <MonoChip>{r.code}</MonoChip> },
      { key:"name",   label:"Course name" },
      { key:"credits",label:"Cr.", align:"right" },
      { key:"is_lab", label:"Type",        render:r => <Tag tone={r.is_lab?"gold":"sage"}>{r.is_lab?"Lab":"Theory"}</Tag> },
      { key:"weekly_classes", label:"Classes/wk", align:"right" },
      { key:"",       label:"",            render:r => delBtn(`${TT_BASE}/courses/${r.id}`) },
    ]} rows={items} />
  );

  if (sub === "rooms") return (
    <DataTable columns={[
      { key:"name",      label:"Room",     render:r => <MonoChip>{r.name}</MonoChip> },
      { key:"room_type", label:"Type",     render:r => <Tag tone={r.room_type==="LAB"?"gold":r.room_type==="ONLINE"?"mist":"sage"}>{r.room_type}</Tag> },
      { key:"capacity",  label:"Capacity", align:"right" },
      { key:"",          label:"",         render:r => delBtn(`${TT_BASE}/rooms/${r.id}`) },
    ]} rows={items} />
  );

  if (sub === "faculty") return (
    <DataTable columns={[
      { key:"id",         label:"ID",        render:r => <MonoChip>{String(r.id).slice(0,8)}</MonoChip> },
      { key:"rank",       label:"Rank" },
      { key:"max_per_day",label:"Max/day",   align:"right" },
      { key:"active",     label:"Status",    render:r => <Tag tone={r.active?"sage":"mist"}>{r.active?"Active":"Off"}</Tag> },
      { key:"",           label:"",          render:r => delBtn(`${TT_BASE}/faculty/${r.id}`) },
    ]} rows={items} />
  );

  if (sub === "batches") return (
    <div className="p-4 space-y-3">
      {items.map(b => (
        <div key={b.id} className="hair border rounded-sm p-3">
          <div className="flex items-center justify-between mb-2">
            <div>
              <span className="font-medium text-[13px]">{b.name}</span>
              <span className="ml-2 text-[11px] text-[var(--muted)]">{b.program}</span>
            </div>
            <GenerateSectionsButton batchId={b.id} />
          </div>
          {(b.sections || []).length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {b.sections.map(s => (
                <span key={s.id} className="inline-flex items-center gap-1 text-[11px] px-2 py-0.5 hair border rounded-sm font-mono">
                  {s.name}
                  {(s.lab_groups || []).map(lg => (
                    <span key={lg.id} className="text-[var(--muted)]">/{lg.name}</span>
                  ))}
                </span>
              ))}
            </div>
          ) : (
            <div className="text-[11.5px] text-[var(--muted)]">No sections yet — click "Generate sections".</div>
          )}
        </div>
      ))}
    </div>
  );

  if (sub === "offerings") return (
    <DataTable columns={[
      { key:"course_id", label:"Course", render:r => <MonoChip>{String(r.course_id).slice(0,8)}</MonoChip> },
      { key:"batch_id",  label:"Batch",  render:r => <MonoChip>{String(r.batch_id).slice(0,8)}</MonoChip> },
      { key:"term_id",   label:"Term",   render:r => <MonoChip>{String(r.term_id).slice(0,8)}</MonoChip> },
      { key:"",          label:"",       render:r => delBtn(`${TT_BASE}/offerings/${r.id}`) },
    ]} rows={items} />
  );

  if (sub === "eligibility") return (
    <DataTable columns={[
      { key:"faculty_id", label:"Faculty", render:r => <MonoChip>{String(r.faculty_id).slice(0,8)}</MonoChip> },
      { key:"course_id",  label:"Course",  render:r => <MonoChip>{String(r.course_id).slice(0,8)}</MonoChip> },
      { key:"",           label:"",        render:r => delBtn(`${TT_BASE}/eligibility/${r.id}`) },
    ]} rows={items} />
  );

  return null;
}

function GenerateSectionsButton({ batchId }) {
  const [count, setCount] = useState(3);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  async function gen() {
    setBusy(true);
    try {
      await AnchorAPI.apiPostAuth(`${TT_BASE}/batches/${batchId}/generate-structure`, { count, lab_split: true });
      setOpen(false);
      window.location.reload();
    } catch (e) { alert(e.message || "Failed"); }
    finally { setBusy(false); }
  }
  if (!open) return <GhostButton size="sm" icon="plus-circle" onClick={() => setOpen(true)}>Generate sections</GhostButton>;
  return (
    <div className="flex items-center gap-2">
      <input type="number" min="1" max="26" value={count} onChange={e => setCount(+e.target.value)}
        className="w-14 px-2 py-1 hair border rounded-sm text-[12px] font-mono" />
      <span className="text-[11.5px] text-[var(--muted)]">sections + lab groups</span>
      <GhostButton size="sm" onClick={gen} disabled={busy}>{busy ? "…" : "Create"}</GhostButton>
      <GhostButton size="sm" onClick={() => setOpen(false)}>Cancel</GhostButton>
    </div>
  );
}

// User search for faculty add form
function UserSearchField({ value, onChange }) {
  const [q, setQ] = useState("");
  const [results, setResults] = useState([]);
  const [selected, setSelected] = useState(null);
  const timerRef = useRef(null);

  function search(text) {
    setQ(text);
    clearTimeout(timerRef.current);
    if (text.length < 2) { setResults([]); return; }
    timerRef.current = setTimeout(async () => {
      try {
        const data = await AnchorAPI.apiGet(`/v1/admin/users?search=${encodeURIComponent(text)}&page_size=8`);
        setResults(Array.isArray(data) ? data : (data.items || []));
      } catch { setResults([]); }
    }, 300);
  }

  if (selected) return (
    <div className="flex items-center gap-2 px-2 py-1.5 hair border rounded-sm bg-white">
      <span className="text-[13px] flex-1">{selected.full_name}<span className="text-[var(--muted)] ml-2">{selected.email}</span></span>
      <button onClick={() => { setSelected(null); onChange(""); setQ(""); }} className="text-[var(--muted)] hover:text-[var(--red)]">
        <Icon name="x" size={12} />
      </button>
    </div>
  );

  return (
    <div className="relative">
      <input value={q} onChange={e => search(e.target.value)}
        placeholder="Search by name or email…"
        className="w-full px-2 py-1.5 hair border rounded-sm bg-white text-[13px]" />
      {results.length > 0 && (
        <div className="absolute top-full left-0 right-0 z-20 mt-0.5 bg-[var(--paper)] hair border rounded-sm shadow-lg">
          {results.map(u => (
            <button key={u.id} onClick={() => { setSelected(u); onChange(u.id); setResults([]); }}
              className="w-full text-left px-3 py-2 text-[12.5px] hover:bg-[var(--mist)]/40 flex items-center gap-2">
              <span className="font-medium">{u.full_name}</span>
              <span className="text-[var(--muted)] text-[11.5px]">{u.email}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

// Generic add form for courses/rooms/faculty/batches
function AddEntitySlideOver({ sub, onClose, onDone }) {
  const [form, setForm] = useState({});
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));
  const [err, setErr] = useState("");

  async function submit() {
    setErr("");
    try {
      const endpoints = {
        courses: `${TT_BASE}/courses`,
        rooms:   `${TT_BASE}/rooms`,
        faculty: `${TT_BASE}/faculty`,
        batches: `${TT_BASE}/batches`,
      };
      await AnchorAPI.apiPostAuth(endpoints[sub], form);
      onDone();
    } catch (e) { setErr(e.message || "Failed"); }
  }

  const fields = {
    courses: [
      { k:"code",           label:"Code",         placeholder:"SE223" },
      { k:"name",           label:"Course name",  placeholder:"Algorithms" },
      { k:"credits",        label:"Credits",      type:"number", placeholder:"3" },
      { k:"weekly_classes", label:"Classes/week", type:"number", placeholder:"2" },
      { k:"is_lab",         label:"Is lab?",      type:"checkbox" },
    ],
    rooms: [
      { k:"name",      label:"Room name", placeholder:"KT-504" },
      { k:"room_type", label:"Type",      type:"select", opts:["THEORY","LAB","ONLINE"] },
      { k:"capacity",  label:"Capacity",  type:"number", placeholder:"30" },
    ],
    faculty: [
      { k:"user_id",     label:"User",          type:"user_search" },
      { k:"rank",        label:"Rank",          type:"select", opts:["LECTURER","SENIOR_LECTURER","ASSISTANT_PROF","ASSOCIATE_PROF","PROFESSOR","HOD","PHD_STUDENT","MASTERS_STUDENT"] },
      { k:"max_per_day", label:"Max classes/day", type:"number", placeholder:"4" },
    ],
    batches: [
      { k:"name",    label:"Batch name", placeholder:"Batch 41" },
      { k:"program", label:"Program",    placeholder:"SWE" },
    ],
  };

  return (
    <SlideOver title={`Add ${sub.slice(0,-1)}`} onClose={onClose}>
      <div className="space-y-4">
        {(fields[sub] || []).map(f => (
          <div key={f.k}>
            <label className="smallcaps text-[var(--muted)] mb-1 block">{f.label}</label>
            {f.type === "user_search" ? (
              <UserSearchField value={form[f.k] || ""} onChange={v => set(f.k, v)} />
            ) : f.type === "select" ? (
              <select className="w-full px-2 py-1.5 hair border rounded-sm bg-white text-[13px]"
                onChange={e => set(f.k, e.target.value)}>
                <option value="">Select…</option>
                {f.opts.map(o => <option key={o} value={o}>{o}</option>)}
              </select>
            ) : f.type === "checkbox" ? (
              <input type="checkbox" className="accent-[var(--sage)]"
                onChange={e => set(f.k, e.target.checked)} />
            ) : (
              <input type={f.type || "text"} placeholder={f.placeholder}
                className="w-full px-2 py-1.5 hair border rounded-sm bg-white text-[13px]"
                onChange={e => set(f.k, f.type === "number" ? +e.target.value : e.target.value)} />
            )}
          </div>
        ))}
        {err && <div className="text-[var(--red)] text-[12px]">{err}</div>}
        <PrimaryButton mode="sage" onClick={submit} className="w-full justify-center">Add</PrimaryButton>
      </div>
    </SlideOver>
  );
}

// Specialized offering form — course + batch dropdowns, no UUID typing
function AddOfferingSlideOver({ termId, onClose, onDone }) {
  const [courses, setCourses] = useState([]);
  const [batches, setBatches] = useState([]);
  const [courseId, setCourseId] = useState("");
  const [batchId, setBatchId] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    AnchorAPI.apiGet(`${TT_BASE}/courses`).then(setCourses).catch(() => {});
    AnchorAPI.apiGet(`${TT_BASE}/batches`).then(setBatches).catch(() => {});
  }, []);

  async function submit() {
    setErr("");
    if (!courseId || !batchId || !termId) { setErr("Select course and batch (and a term above)"); return; }
    try {
      await AnchorAPI.apiPostAuth(`${TT_BASE}/offerings`, { term_id:termId, course_id:courseId, batch_id:batchId });
      onDone();
    } catch (e) { setErr(e.message || "Failed"); }
  }

  return (
    <SlideOver title="Add offering" onClose={onClose}>
      <div className="space-y-4">
        {!termId && (
          <div className="px-3 py-2 rounded-sm text-[12px]"
            style={{ background:"rgba(232,49,42,0.06)", color:"var(--red)", border:"1px solid rgba(232,49,42,0.2)" }}>
            Select a term in the bar at the top first.
          </div>
        )}
        <div>
          <label className="smallcaps text-[var(--muted)] mb-1 block">Course</label>
          <select className="w-full px-2 py-1.5 hair border rounded-sm bg-white text-[13px]"
            value={courseId} onChange={e => setCourseId(e.target.value)}>
            <option value="">Select course…</option>
            {courses.map(c => <option key={c.id} value={c.id}>{c.code} — {c.name}</option>)}
          </select>
        </div>
        <div>
          <label className="smallcaps text-[var(--muted)] mb-1 block">Batch</label>
          <select className="w-full px-2 py-1.5 hair border rounded-sm bg-white text-[13px]"
            value={batchId} onChange={e => setBatchId(e.target.value)}>
            <option value="">Select batch…</option>
            {batches.map(b => <option key={b.id} value={b.id}>{b.name} ({b.program})</option>)}
          </select>
        </div>
        {err && <div className="text-[var(--red)] text-[12px]">{err}</div>}
        <PrimaryButton mode="sage" onClick={submit} className="w-full justify-center"
          disabled={!courseId || !batchId || !termId}>
          Add offering
        </PrimaryButton>
      </div>
    </SlideOver>
  );
}

// Specialized eligibility form — faculty + course dropdowns
function AddEligibilitySlideOver({ onClose, onDone }) {
  const [faculty, setFaculty] = useState([]);
  const [courses, setCourses] = useState([]);
  const [facultyId, setFacultyId] = useState("");
  const [courseId, setCourseId] = useState("");
  const [err, setErr] = useState("");

  useEffect(() => {
    AnchorAPI.apiGet(`${TT_BASE}/faculty`).then(setFaculty).catch(() => {});
    AnchorAPI.apiGet(`${TT_BASE}/courses`).then(setCourses).catch(() => {});
  }, []);

  async function submit() {
    setErr("");
    if (!facultyId || !courseId) { setErr("Select faculty and course"); return; }
    try {
      await AnchorAPI.apiPostAuth(`${TT_BASE}/eligibility`, { faculty_id:facultyId, course_id:courseId });
      onDone();
    } catch (e) { setErr(e.message || "Failed"); }
  }

  return (
    <SlideOver title="Add eligibility" onClose={onClose}>
      <div className="space-y-4">
        <div>
          <label className="smallcaps text-[var(--muted)] mb-1 block">Teacher</label>
          <select className="w-full px-2 py-1.5 hair border rounded-sm bg-white text-[13px]"
            value={facultyId} onChange={e => setFacultyId(e.target.value)}>
            <option value="">Select teacher…</option>
            {faculty.map(f => <option key={f.id} value={f.id}>{f.rank} · {String(f.user_id).slice(0,8)}</option>)}
          </select>
        </div>
        <div>
          <label className="smallcaps text-[var(--muted)] mb-1 block">Course</label>
          <select className="w-full px-2 py-1.5 hair border rounded-sm bg-white text-[13px]"
            value={courseId} onChange={e => setCourseId(e.target.value)}>
            <option value="">Select course…</option>
            {courses.map(c => <option key={c.id} value={c.id}>{c.code} — {c.name}</option>)}
          </select>
        </div>
        {err && <div className="text-[var(--red)] text-[12px]">{err}</div>}
        <PrimaryButton mode="sage" onClick={submit} className="w-full justify-center"
          disabled={!facultyId || !courseId}>
          Add eligibility
        </PrimaryButton>
      </div>
    </SlideOver>
  );
}

// ── Tab 1: Schedule Config ────────────────────────────────────────────────────
function ScheduleConfig({ termId, onDone }) {
  const ALL_DAYS = ["Sat","Sun","Mon","Tue","Wed","Thu","Fri"];
  const DEFAULT_DAYS = ["Sat","Sun","Mon","Tue","Wed","Thu"];
  const DEFAULT_SLOTS = ["8:30-10:00","10:00-11:30","11:30-1:00","1:00-2:30","2:30-4:00","4:00-5:30"];

  const [days, setDays] = useState(DEFAULT_DAYS);
  const [slots, setSlots] = useState(DEFAULT_SLOTS);
  const [fromServer, setFromServer] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!termId) return;
    AnchorAPI.apiGet(`${TT_BASE}/config?term_id=${termId}`)
      .then(c => { if (c) { setDays(c.days || DEFAULT_DAYS); setSlots(c.slots || DEFAULT_SLOTS); setFromServer(true); } })
      .catch(() => {});
  }, [termId]);

  function toggleDay(d) {
    setDays(ds => ds.includes(d) ? ds.filter(x => x !== d) : [...ds, d]);
  }

  function updateSlot(i, v) { setSlots(ss => ss.map((x, j) => j === i ? v : x)); }
  function removeSlot(i) { setSlots(ss => ss.filter((_, j) => j !== i)); }
  function addSlot() { setSlots(ss => [...ss, ""]); }

  async function save() {
    setErr(""); setSaving(true);
    try {
      await AnchorAPI.apiPostAuth(`${TT_BASE}/config`, {
        term_id: termId, days, slots: slots.filter(s => s.trim()), off_days: ["Fri"],
      });
      setSaved(true);
      setTimeout(() => { setSaved(false); onDone(); }, 800);
    } catch (e) { setErr(e.message || "Failed to save"); }
    finally { setSaving(false); }
  }

  return (
    <div className="max-w-[680px] space-y-5">
      {!termId && (
        <Card>
          <div className="text-[13px] text-[var(--muted)]">Select a term above to configure its schedule.</div>
        </Card>
      )}

      <Card>
        <SectionLabel>Working days</SectionLabel>
        <div className="flex flex-wrap gap-2 mb-2">
          {ALL_DAYS.map(d => (
            <button key={d} onClick={() => toggleDay(d)}
              className="px-3 py-1.5 rounded-sm text-[12.5px] hair border transition"
              style={days.includes(d)
                ? { background:"var(--sage)", color:"white", borderColor:"var(--sage)" }
                : { color:"var(--muted)" }}>
              {d}
            </button>
          ))}
        </div>
        <div className="text-[11px] text-[var(--muted)]">
          Friday is always excluded by the CP-SAT solver regardless of this setting.
        </div>
      </Card>

      <Card>
        <SectionLabel right={
          <GhostButton size="sm" icon="plus" onClick={addSlot}>Add slot</GhostButton>
        }>
          Time slots
        </SectionLabel>
        <div className="space-y-2">
          {slots.map((s, i) => (
            <div key={i} className="flex items-center gap-2">
              <input value={s} onChange={e => updateSlot(i, e.target.value)}
                placeholder="8:30-10:00"
                className="flex-1 px-2 py-1.5 hair border rounded-sm text-[12.5px] font-mono" />
              <button onClick={() => removeSlot(i)}
                className="text-[var(--muted)] hover:text-[var(--red)]">
                <Icon name="x" size={13} />
              </button>
            </div>
          ))}
        </div>
      </Card>

      {err && <div className="text-[var(--red)] text-[12.5px] px-1">{err}</div>}

      <div className="flex items-center gap-3">
        <PrimaryButton mode="sage" icon={saving ? "loader" : saved ? "check" : "save"}
          onClick={save} disabled={saving || !termId}>
          {saving ? "Saving…" : saved ? "Saved — moving to Rules →" : "Save & continue"}
        </PrimaryButton>
        {fromServer && (
          <span className="text-[11.5px] text-[var(--sage)] flex items-center gap-1">
            <Icon name="cloud" size={12} /> Loaded from server
          </span>
        )}
      </div>
    </div>
  );
}

// ── Tab 2: Rules ──────────────────────────────────────────────────────────────
function TimetableRules({ termId, onNext }) {
  const [constraints, setConstraints] = useState([]);
  const [showAdd, setShowAdd] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!termId) return;
    setLoading(true);
    AnchorAPI.apiGet(`${TT_BASE}/constraints?term_id=${termId}`)
      .then(d => setConstraints(Array.isArray(d) ? d : []))
      .catch(() => setConstraints([]))
      .finally(() => setLoading(false));
  }, [termId]);

  async function toggle(con) {
    try {
      await AnchorAPI.apiPatch(`${TT_BASE}/constraints/${con.id}`, { enabled: !con.enabled });
      setConstraints(cs => cs.map(c => c.id === con.id ? { ...c, enabled: !c.enabled } : c));
    } catch (e) { alert(e.message); }
  }

  async function updateWeight(con, w) {
    try {
      await AnchorAPI.apiPatch(`${TT_BASE}/constraints/${con.id}`, { weight: w });
      setConstraints(cs => cs.map(c => c.id === con.id ? { ...c, weight: w } : c));
    } catch {}
  }

  async function del(con) {
    if (!confirm("Delete this constraint?")) return;
    try {
      await AnchorAPI.apiDelete(`${TT_BASE}/constraints/${con.id}`);
      setConstraints(cs => cs.filter(c => c.id !== con.id));
    } catch (e) { alert(e.message); }
  }

  const hard = constraints.filter(c => c.enforcement === "hard");
  const soft = constraints.filter(c => c.enforcement === "soft");

  return (
    <div className="space-y-4">
      <Card>
        <div className="flex items-center gap-3">
          {!termId ? (
            <span className="text-[13px] text-[var(--muted)]">Select a term above to manage constraints.</span>
          ) : (
            <>
              <span className="text-[13px] text-[var(--graphite)]">
                {constraints.length} constraint{constraints.length !== 1 ? "s" : ""} for this term
              </span>
              <div className="flex-1" />
              <PrimaryButton size="sm" icon="plus" mode="sage" onClick={() => setShowAdd(true)}>Add rule</PrimaryButton>
              <PrimaryButton size="sm" icon="arrow-right" mode="sage" onClick={onNext}>Continue to Generate</PrimaryButton>
            </>
          )}
        </div>
      </Card>

      {loading && <div className="text-center text-[var(--muted)] text-[13px] py-8">Loading…</div>}

      {!loading && termId && constraints.length === 0 && (
        <Card className="text-center py-10">
          <div className="text-[var(--graphite)] text-[13px] mb-1">No constraints yet.</div>
          <div className="text-[11.5px] text-[var(--muted)]">The solver will use only its built-in hard rules. Add rules to customize the output.</div>
        </Card>
      )}

      {[{ label:"Hard constraints", items:hard }, { label:"Soft constraints", items:soft }].map(grp => (
        grp.items.length > 0 && (
          <div key={grp.label} className="space-y-2">
            <div className="smallcaps text-[var(--muted)] px-1">{grp.label}</div>
            {grp.items.map(con => (
              <Card key={con.id} noPad>
                <div className="p-3 flex items-start gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium text-[13px]">{CONSTRAINT_LABELS[con.constraint_type] || con.constraint_type}</span>
                      <Tag tone={con.enforcement === "hard" ? "red" : "gold"}>{con.enforcement}</Tag>
                      {!con.enabled && <Tag tone="mist">disabled</Tag>}
                    </div>
                    {Object.keys(con.params || {}).length > 0 && (
                      <div className="text-[11.5px] text-[var(--muted)] mt-0.5 font-mono">{JSON.stringify(con.params)}</div>
                    )}
                    {con.enforcement === "soft" && (
                      <div className="flex items-center gap-2 mt-2">
                        <span className="text-[11px] text-[var(--muted)]">Weight</span>
                        <input type="range" min="1" max="100" value={con.weight || 10}
                          className="accent-[var(--sage)]"
                          onChange={e => updateWeight(con, +e.target.value)} />
                        <span className="font-mono text-[11px] w-6 text-right">{con.weight || 10}</span>
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button onClick={() => toggle(con)}
                      className="w-8 h-4 rounded-full transition relative"
                      style={{ background: con.enabled ? "var(--sage)" : "var(--mist)" }}>
                      <span className="absolute top-0.5 w-3 h-3 rounded-full bg-white transition-all"
                        style={{ left: con.enabled ? "calc(100% - 14px)" : "2px" }} />
                    </button>
                    <button onClick={() => del(con)} className="text-[var(--muted)] hover:text-[var(--red)]">
                      <Icon name="trash-2" size={13} />
                    </button>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )
      ))}

      {showAdd && termId && (
        <AddConstraintSlideOver
          termId={termId}
          onClose={() => setShowAdd(false)}
          onDone={con => { setConstraints(cs => [...cs, con]); setShowAdd(false); }}
        />
      )}
    </div>
  );
}

function AddConstraintSlideOver({ termId, onClose, onDone }) {
  const [type, setType] = useState("max_classes_per_day");
  const [enforcement, setEnforcement] = useState("soft");
  const [weight, setWeight] = useState(10);
  const [paramStr, setParamStr] = useState('{"limit": 4}');
  const [err, setErr] = useState("");

  const DEFAULT_PARAMS = {
    max_classes_per_day: '{"limit": 4}',
    consecutive_limit:   '{"limit": 3}',
    pref_slot_reward:    '{}',
    online_penalty:      '{"penalty": 5}',
    gap_minimize:        '{}',
  };

  function onTypeChange(t) {
    setType(t);
    setParamStr(DEFAULT_PARAMS[t] || "{}");
  }

  async function submit() {
    setErr("");
    let params;
    try { params = JSON.parse(paramStr); } catch { setErr("Invalid JSON in params"); return; }
    try {
      const con = await AnchorAPI.apiPostAuth(`${TT_BASE}/constraints`, {
        constraint_type: type, scope: {}, params,
        enforcement, weight: enforcement === "soft" ? weight : null, term_id: termId,
      });
      onDone(con);
    } catch (e) { setErr(e.message || "Failed"); }
  }

  return (
    <SlideOver title="Add constraint rule" onClose={onClose}>
      <div className="space-y-4">
        <div>
          <label className="smallcaps text-[var(--muted)] mb-1 block">Constraint type</label>
          <select className="w-full px-2 py-1.5 hair border rounded-sm bg-white text-[13px]"
            value={type} onChange={e => onTypeChange(e.target.value)}>
            {Object.entries(CONSTRAINT_LABELS).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="smallcaps text-[var(--muted)] mb-1 block">Enforcement</label>
          <div className="flex gap-4">
            {["hard", "soft"].map(e => (
              <label key={e} className="flex items-center gap-2 text-[13px] cursor-pointer">
                <input type="radio" name="enf" value={e} checked={enforcement === e}
                  onChange={() => setEnforcement(e)} className="accent-[var(--sage)]" />
                <span>{e}</span>
                <span className="text-[11px] text-[var(--muted)]">
                  {e === "hard" ? "— solver cannot violate" : "— penalised, may relax"}
                </span>
              </label>
            ))}
          </div>
        </div>
        {enforcement === "soft" && (
          <div>
            <label className="smallcaps text-[var(--muted)] mb-1 block">Penalty weight — {weight}</label>
            <input type="range" min="1" max="100" value={weight}
              className="w-full accent-[var(--sage)]" onChange={e => setWeight(+e.target.value)} />
          </div>
        )}
        <div>
          <label className="smallcaps text-[var(--muted)] mb-1 block">Parameters (JSON)</label>
          <textarea rows={3} value={paramStr} onChange={e => setParamStr(e.target.value)}
            className="w-full px-2 py-1.5 hair border rounded-sm bg-white text-[12px] font-mono resize-none" />
        </div>
        {err && <div className="text-[var(--red)] text-[12px]">{err}</div>}
        <PrimaryButton mode="sage" onClick={submit} className="w-full justify-center">Add rule</PrimaryButton>
      </div>
    </SlideOver>
  );
}

// ── Tab 3: Generate ───────────────────────────────────────────────────────────
function TimetableGenerate({ termId, onSolved }) {
  const [timeLimit, setTimeLimit] = useState(60);
  const [jobId, setJobId] = useState(null);
  const [job, setJob] = useState(null);
  const [polling, setPolling] = useState(false);
  const [err, setErr] = useState("");
  const [constraintMap, setConstraintMap] = useState({});
  const pollRef = useRef(null);

  useEffect(() => {
    if (!termId) return;
    AnchorAPI.apiGet(`${TT_BASE}/constraints?term_id=${termId}`)
      .then(cs => {
        const m = {};
        (Array.isArray(cs) ? cs : []).forEach(c => {
          m[c.id] = { label: CONSTRAINT_LABELS[c.constraint_type] || c.constraint_type, enforcement: c.enforcement };
        });
        setConstraintMap(m);
      }).catch(() => {});
  }, [termId]);

  useEffect(() => {
    if (!jobId) return;
    setPolling(true);
    pollRef.current = setInterval(async () => {
      try {
        const j = await AnchorAPI.apiGet(`${TT_BASE}/solve/${jobId}`);
        setJob(j);
        if (["optimal","feasible","infeasible","failed"].includes(j.status)) {
          clearInterval(pollRef.current);
          setPolling(false);
          if ((j.status === "optimal" || j.status === "feasible") && j.result_version) {
            setTimeout(() => onSolved(j.result_version), 1200);
          }
        }
      } catch { clearInterval(pollRef.current); setPolling(false); }
    }, 1500);
    return () => clearInterval(pollRef.current);
  }, [jobId]);

  async function handleSolve() {
    if (!termId) { setErr("Select a term above first"); return; }
    setErr(""); setJob(null); setJobId(null);
    try {
      const j = await AnchorAPI.apiPostAuth(`${TT_BASE}/solve`, { term_id: termId, time_limit_s: timeLimit });
      setJobId(j.job_id);
      setJob(j);
    } catch (e) { setErr(e.message || "Solve failed"); }
  }

  async function makeSoft(conId) {
    try {
      await AnchorAPI.apiPatch(`${TT_BASE}/constraints/${conId}`, { enforcement:"soft", weight:50 });
      setConstraintMap(m => ({ ...m, [conId]: { ...m[conId], enforcement:"soft" } }));
    } catch (e) { alert(e.message); }
  }

  async function handleRelaxAll() {
    if (!job?.infeasible_core?.length) return;
    for (const id of job.infeasible_core) { await makeSoft(id).catch(() => {}); }
    handleSolve();
  }

  const isRunning = job && ["queued","running"].includes(job.status);
  const statusColor = { optimal:"var(--sage)", feasible:"var(--sage)", infeasible:"var(--red)", failed:"var(--red)", running:"var(--gold)", queued:"var(--muted)" };

  return (
    <div className="max-w-[680px] mx-auto space-y-4">
      {!termId && (
        <Card>
          <div className="text-[13px] text-[var(--muted)]">Select a term above, then configure schedule and rules first.</div>
        </Card>
      )}

      <Card className="space-y-5">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex-1">
            <label className="smallcaps text-[var(--muted)] mb-1 block">Time limit — {timeLimit}s</label>
            <input type="range" min="10" max="300" step="10" value={timeLimit}
              className="w-full accent-[var(--sage)]" onChange={e => setTimeLimit(+e.target.value)} />
            <div className="flex justify-between text-[10.5px] text-[var(--muted)] mt-0.5">
              <span>10s (fast, fewer options)</span><span>300s (thorough)</span>
            </div>
          </div>
        </div>

        {err && <div className="text-[var(--red)] text-[12px]">{err}</div>}

        <div className="flex flex-col items-center gap-4 py-4">
          <div className="w-16 h-16 rounded-full flex items-center justify-center"
            style={{ background: isRunning ? "rgba(184,137,58,0.12)" : "rgba(74,107,92,0.10)" }}>
            <Icon name={isRunning ? "loader" : "cpu"} size={28}
              style={{ color: isRunning ? "var(--gold)" : "var(--sage)" }}
              className={isRunning ? "animate-spin" : ""} />
          </div>
          <div className="text-center">
            <h3 className="font-serif text-[22px] text-[var(--navy)]" style={{ fontWeight:500 }}>
              {isRunning ? "Solving…" : "Generate schedule"}
            </h3>
            {job && (
              <div className="mt-1 flex items-center justify-center gap-2">
                <span className="font-mono text-[12px]" style={{ color: statusColor[job.status] || "var(--ink)" }}>
                  {job.status.toUpperCase()}
                </span>
                {job.result_version && <span className="text-[11px] text-[var(--muted)]">· version {job.result_version}</span>}
              </div>
            )}
          </div>
          <PrimaryButton mode="sage" icon={isRunning ? "loader" : "play"}
            onClick={handleSolve} disabled={isRunning || !termId}>
            {isRunning ? "Solving…" : job ? "Re-generate" : "Generate schedule"}
          </PrimaryButton>
        </div>

        {isRunning && (
          <div>
            <div className="text-[11px] text-[var(--muted)] mb-1 flex justify-between">
              <span>Solver progress</span>
              <span className="font-mono">{job?.progress || 0}%</span>
            </div>
            <div className="h-1.5 bg-[var(--mist)] rounded-sm overflow-hidden">
              <div className="h-full bg-[var(--sage)] transition-all duration-500"
                style={{ width: `${job?.progress || 8}%` }} />
            </div>
          </div>
        )}

        {job?.status === "optimal" && (
          <div className="flex items-center gap-2 text-[var(--sage)] text-[13px]">
            <Icon name="check-circle" size={14} /> Optimal solution found — opening Grid editor…
          </div>
        )}

        {job?.status === "infeasible" && (
          <div className="rounded-sm p-4 space-y-3"
            style={{ border:"1px solid rgba(232,49,42,0.3)", background:"rgba(232,49,42,0.04)" }}>
            <div className="text-[var(--red)] font-medium text-[13px] flex items-center gap-2">
              <Icon name="alert-triangle" size={14} /> Schedule is infeasible — conflicting rules
            </div>
            <div className="text-[12px] text-[var(--graphite)] mb-1">
              These constraints cannot all be satisfied at once. Make them soft so the solver can trade them off:
            </div>
            <div className="space-y-1.5">
              {(job.infeasible_core || []).map(id => {
                const info = constraintMap[id];
                return (
                  <div key={id} className="flex items-center justify-between gap-2 py-1">
                    <span className="text-[12.5px] text-[var(--ink)]">
                      {info?.label || <span className="font-mono text-[11px]">{id.slice(0,12)}…</span>}
                    </span>
                    {info?.enforcement !== "soft" && (
                      <GhostButton size="sm" onClick={() => makeSoft(id)}>Make soft</GhostButton>
                    )}
                    {info?.enforcement === "soft" && (
                      <Tag tone="gold">already soft</Tag>
                    )}
                  </div>
                );
              })}
            </div>
            <GhostButton icon="refresh-cw" onClick={handleRelaxAll}>
              Make all soft &amp; re-solve
            </GhostButton>
          </div>
        )}

        {job?.status === "failed" && (
          <div className="text-[var(--red)] text-[12.5px] flex items-center gap-2">
            <Icon name="x-circle" size={14} /> Solver failed. Check that schedule config and data are set up correctly.
          </div>
        )}
      </Card>
    </div>
  );
}

// ── Tab 4: Grid — rooms × slots per day tab ───────────────────────────────────
function TimetableGrid({ termId, version, onVersionChange, onPublish }) {
  const [entries, setEntries] = useState([]);
  const [config, setConfig] = useState(null);
  const [sections, setSections] = useState([]);
  const [activeDay, setActiveDay] = useState(0);
  const [filterSection, setFilterSection] = useState("");
  const [conflictIds, setConflictIds] = useState(new Set());
  const [prevEntries, setPrevEntries] = useState([]);
  const [editEntry, setEditEntry] = useState(null);
  const [resolving, setResolving] = useState(false);
  const [loading, setLoading] = useState(false);
  const pollRef = useRef(null);

  const days = config?.days || DAY_NAMES;
  const slots = config?.slots || [];

  useEffect(() => {
    if (!termId) return;
    AnchorAPI.apiGet(`${TT_BASE}/config?term_id=${termId}`)
      .then(c => setConfig(c)).catch(() => {});
  }, [termId]);

  useEffect(() => {
    if (!termId) return;
    loadEntries();
  }, [termId, version]);

  async function loadEntries() {
    setLoading(true);
    try {
      const data = await AnchorAPI.apiGet(`${TT_BASE}/entries?term_id=${termId}&version=${version}`);
      setEntries(Array.isArray(data) ? data : []);
      const secs = [...new Map(data.map(e => [
        e.section_id, { id: e.section_id, name: `${e.batch_name} ${e.section_name}` }
      ])).values()];
      setSections(secs);
      loadValidation();
    } catch { setEntries([]); }
    finally { setLoading(false); }
  }

  async function loadValidation() {
    try {
      const v = await AnchorAPI.apiGet(`${TT_BASE}/validate?term_id=${termId}&version=${version}`);
      setConflictIds(new Set((v.conflicts || []).flatMap(c => c.entry_ids || [])));
    } catch {}
  }

  async function toggleLock(entry) {
    try {
      await AnchorAPI.apiPatch(`${TT_BASE}/entries/${entry.id}`, { lock: !entry.locked });
      setEntries(es => es.map(e => e.id === entry.id ? { ...e, locked: !e.locked } : e));
    } catch (e) { alert(e.message); }
  }

  function pollResolveJob(jId) {
    setResolving(true);
    pollRef.current = setInterval(async () => {
      try {
        const j = await AnchorAPI.apiGet(`${TT_BASE}/solve/${jId}`);
        if (["optimal","feasible","failed","infeasible"].includes(j.status)) {
          clearInterval(pollRef.current);
          setResolving(false);
          if (j.result_version) {
            setPrevEntries(entries);
            onVersionChange(j.result_version);
          }
        }
      } catch { clearInterval(pollRef.current); setResolving(false); }
    }, 1500);
  }

  async function handleResolve() {
    try {
      const job = await AnchorAPI.apiPostAuth(`${TT_BASE}/resolve`, {
        term_id: termId, base_version: version, change: {}, keep_locked: true, time_limit_s: 60,
      });
      pollResolveJob(job.job_id);
    } catch (e) { alert(e.message || "Resolve failed"); }
  }

  async function applyEdit(entry, newDay, newSlot, newFacultyId, newRoomId) {
    try {
      await AnchorAPI.apiPatch(`${TT_BASE}/entries/${entry.id}`, {
        new_day: newDay, new_slot: newSlot, new_faculty_id: newFacultyId, new_room_id: newRoomId, lock: true,
      });
      setEditEntry(null);
      loadEntries();
    } catch (e) { alert(e.message); }
  }

  // Derive grid data for active day
  const dayEntries = entries.filter(e =>
    e.day === activeDay && (!filterSection || e.section_id === filterSection)
  );
  const roomsMap = new Map();
  dayEntries.forEach(e => { if (!roomsMap.has(e.room_id)) roomsMap.set(e.room_id, e.room_name); });
  const gridRooms = [...roomsMap.entries()];
  const cellMap = {};
  dayEntries.forEach(e => { cellMap[`${e.room_id}-${e.slot}`] = e; });

  const changedIds = new Set(
    entries.filter(e => {
      const prev = prevEntries.find(p => p.id === e.id);
      return prev && (prev.day !== e.day || prev.slot !== e.slot);
    }).map(e => e.id)
  );

  const noEntries = !loading && entries.length === 0;

  return (
    <div className="space-y-4">
      {/* Controls */}
      <Card>
        <div className="flex items-center gap-3 flex-wrap">
          <span className="smallcaps text-[var(--muted)]">Filter</span>
          <select className="hair border rounded-sm bg-white px-2 py-1 text-[12.5px]"
            value={filterSection} onChange={e => setFilterSection(e.target.value)}>
            <option value="">All sections</option>
            {sections.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
          <div className="flex-1" />
          {resolving && (
            <span className="text-[12px] flex items-center gap-1" style={{ color:"var(--gold)" }}>
              <Icon name="loader" size={12} className="animate-spin" /> Re-solving…
            </span>
          )}
          {changedIds.size > 0 && (
            <span className="text-[11.5px]" style={{ color:"var(--sage)" }}>
              {changedIds.size} cell(s) moved ▣
            </span>
          )}
          {conflictIds.size > 0 && (
            <span className="text-[11.5px] flex items-center gap-1" style={{ color:"var(--red)" }}>
              <Icon name="alert-circle" size={12} /> {conflictIds.size} conflict(s)
            </span>
          )}
          <GhostButton size="sm" icon="refresh-cw" onClick={handleResolve} disabled={resolving}>Re-solve</GhostButton>
          <GhostButton size="sm" icon="shield-check" onClick={loadValidation}>Validate</GhostButton>
          <PrimaryButton size="sm" icon="send" mode="sage" onClick={onPublish}>Publish →</PrimaryButton>
        </div>
      </Card>

      {!termId && (
        <Card className="text-center py-10">
          <div className="text-[var(--muted)] text-[13px]">Select a term above and generate a schedule first.</div>
        </Card>
      )}

      {noEntries && termId && (
        <Card className="text-center py-10">
          <div className="font-serif text-[18px] text-[var(--navy)] mb-2" style={{ fontWeight:500 }}>No entries yet</div>
          <div className="text-[12.5px] text-[var(--muted)]">Generate a schedule in the Generate tab, then come back here to tune it.</div>
        </Card>
      )}

      {!noEntries && termId && (
        <Card noPad>
          {/* Day tabs */}
          <div className="flex gap-0.5 px-2 pt-2">
            {days.map((d, i) => {
              const hasConflict = entries.some(e => e.day === i && conflictIds.has(e.id));
              return (
                <button key={d} onClick={() => setActiveDay(i)}
                  className={`px-3 py-2 text-[12.5px] rounded-t-sm transition relative ${
                    activeDay === i ? "font-medium" : "text-[var(--graphite)]"
                  }`}
                  style={activeDay === i
                    ? { background:"white", border:"1px solid var(--mist)", borderBottom:"1px solid white", marginBottom:-1, color:"var(--sage)" }
                    : { border:"1px solid transparent" }}>
                  {d}
                  {hasConflict && (
                    <span className="absolute top-1 right-1 w-1.5 h-1.5 rounded-full"
                      style={{ background:"var(--red)" }} />
                  )}
                </button>
              );
            })}
          </div>

          <div className="p-3 overflow-x-auto" style={{ borderTop:"1px solid var(--mist)" }}>
            {loading ? (
              <div className="text-center py-8 text-[var(--muted)] text-[13px]">Loading…</div>
            ) : gridRooms.length === 0 ? (
              <div className="text-center py-8 text-[var(--muted)] text-[13px]">
                No classes scheduled on {days[activeDay]}{filterSection ? " for this section" : ""}.
              </div>
            ) : (
              <div style={{
                display:"grid",
                gridTemplateColumns: `130px repeat(${slots.length}, minmax(100px, 1fr))`,
                gap: 3,
                minWidth: Math.max(700, 130 + slots.length * 110),
              }}>
                {/* Header row */}
                <div className="text-[10px] text-[var(--muted)] font-mono pb-1 flex items-end pl-1">Room</div>
                {slots.map((s, i) => (
                  <div key={i} className="text-[10px] text-[var(--muted)] font-mono text-center pb-1 truncate px-1">{s}</div>
                ))}
                {/* Room rows */}
                {gridRooms.map(([roomId, roomName]) => (
                  <React.Fragment key={roomId}>
                    <div className="font-mono text-[11px] text-[var(--graphite)] flex items-center pr-2 min-h-[72px] pl-1 truncate"
                      title={roomName}>{roomName}</div>
                    {slots.map((_, si) => {
                      const entry = cellMap[`${roomId}-${si}`];
                      if (!entry) return (
                        <div key={si} className="min-h-[72px] rounded-sm"
                          style={{ border:"1px dashed var(--mist)", background:"#FBF9F3" }} />
                      );
                      return (
                        <RoutineCell key={si}
                          entry={entry}
                          moved={changedIds.has(entry.id)}
                          conflict={conflictIds.has(entry.id)}
                          onLockToggle={() => toggleLock(entry)}
                          onClick={() => setEditEntry(entry)} />
                      );
                    })}
                  </React.Fragment>
                ))}
              </div>
            )}
          </div>

          {/* Legend */}
          <div className="px-4 pb-3 pt-2 hair-t flex flex-wrap items-center gap-4 text-[11px] text-[var(--muted)]">
            <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-sm border-2" style={{ borderColor:"var(--gold)" }} /> Locked</span>
            <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-sm" style={{ background:"rgba(74,107,92,0.12)", border:"1px solid var(--sage)" }} /> Changed ▣</span>
            <span className="flex items-center gap-1"><span className="inline-block w-3 h-3 rounded-sm border-2" style={{ borderColor:"var(--red)" }} /> Conflict ‼</span>
          </div>
        </Card>
      )}

      {/* CommandBar */}
      {termId && !noEntries && (
        <CommandBar
          termId={termId}
          version={version}
          entries={entries}
          onEntryLockChange={(id, locked) => setEntries(es => es.map(e => e.id === id ? { ...e, locked } : e))}
          onResolved={jId => pollResolveJob(jId)}
        />
      )}

      {editEntry && (
        <CellEditModal
          entry={editEntry}
          onClose={() => setEditEntry(null)}
          onLock={() => { toggleLock(editEntry); setEditEntry(null); }}
          onApply={applyEdit}
        />
      )}
    </div>
  );
}

// Individual grid cell
function RoutineCell({ entry, moved, conflict, onLockToggle, onClick }) {
  const borderStyle = conflict
    ? "2px solid var(--red)"
    : entry.locked ? "2px solid var(--gold)"
    : "1px solid var(--mist)";
  const bg = conflict ? "rgba(232,49,42,0.05)"
    : moved ? "rgba(74,107,92,0.10)"
    : entry.locked ? "rgba(184,137,58,0.05)"
    : "rgba(255,255,255,0.85)";

  return (
    <button onClick={onClick}
      className="text-left rounded-sm p-2 min-h-[72px] relative w-full"
      style={{ border: borderStyle, background: bg }}>
      {entry.locked && (
        <button onClick={e => { e.stopPropagation(); onLockToggle(); }}
          className="absolute top-1 right-1 hover:opacity-70"
          style={{ color:"var(--gold)" }}>
          <Icon name="lock" size={10} />
        </button>
      )}
      {conflict && (
        <span className="absolute top-1 left-1 font-bold text-[9px]" style={{ color:"var(--red)" }}>‼</span>
      )}
      {moved && (
        <span className="absolute bottom-1 right-1 text-[9px]" style={{ color:"var(--sage)" }}>▣</span>
      )}
      <div className="font-mono text-[11.5px] font-semibold leading-tight" style={{ color:"var(--ink)" }}>
        {entry.course_code}
      </div>
      <div className="text-[10.5px] leading-tight mt-0.5 truncate" style={{ color:"var(--graphite)" }}>
        {entry.section_name}{entry.lab_group_name ? `·${entry.lab_group_name}` : ""}
      </div>
      <div className="text-[10px] leading-tight mt-0.5 truncate" style={{ color:"var(--muted)" }}>
        {entry.faculty_name}
      </div>
    </button>
  );
}

// Cell detail & edit modal
function CellEditModal({ entry, onClose, onLock, onApply }) {
  const [rooms, setRooms] = useState([]);
  const [faculty, setFaculty] = useState([]);
  const [newDay, setNewDay] = useState(entry.day);
  const [newSlot, setNewSlot] = useState(entry.slot);
  const [newRoomId, setNewRoomId] = useState(entry.room_id);
  const [newFacultyId, setNewFacultyId] = useState(entry.faculty_id);

  useEffect(() => {
    AnchorAPI.apiGet(`${TT_BASE}/rooms`).then(setRooms).catch(() => {});
    AnchorAPI.apiGet(`${TT_BASE}/faculty`).then(setFaculty).catch(() => {});
  }, []);

  return (
    <div className="fixed inset-0 z-30 flex items-center justify-center"
      style={{ background:"rgba(11,29,53,0.25)" }} onClick={onClose}>
      <div className="bg-[var(--paper)] rounded-sm w-[440px] hair border shadow-lg" onClick={e => e.stopPropagation()}>
        <div className="p-4 hair-b flex items-center justify-between">
          <div>
            <div className="smallcaps text-[var(--muted)]">Edit slot</div>
            <h3 className="font-serif text-[20px] text-[var(--navy)]" style={{ fontWeight:500 }}>
              {entry.course_code} · {entry.section_name}
            </h3>
            <div className="text-[11.5px] text-[var(--muted)] mt-0.5">{entry.faculty_name} · {entry.room_name}</div>
          </div>
          <button onClick={onLock}
            className="flex items-center gap-1.5 text-[12px] px-2 py-1 hair border rounded-sm hover:bg-[var(--mist)]/40">
            <Icon name={entry.locked ? "unlock" : "lock"} size={12} />
            {entry.locked ? "Unlock" : "Lock"}
          </button>
        </div>
        <div className="p-4 space-y-3 text-[13px]">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="smallcaps text-[var(--muted)] mb-1 block">Day</label>
              <select className="w-full px-2 py-1.5 hair border rounded-sm bg-white"
                value={newDay} onChange={e => setNewDay(+e.target.value)}>
                {DAY_NAMES.map((d, i) => <option key={d} value={i}>{d}</option>)}
              </select>
            </div>
            <div>
              <label className="smallcaps text-[var(--muted)] mb-1 block">Slot (0-indexed)</label>
              <input type="number" min="0" value={newSlot}
                onChange={e => setNewSlot(+e.target.value)}
                className="w-full px-2 py-1.5 hair border rounded-sm bg-white" />
            </div>
          </div>
          <div>
            <label className="smallcaps text-[var(--muted)] mb-1 block">Room</label>
            <select className="w-full px-2 py-1.5 hair border rounded-sm bg-white"
              value={newRoomId} onChange={e => setNewRoomId(e.target.value)}>
              {rooms.map(r => <option key={r.id} value={r.id}>{r.name} ({r.room_type})</option>)}
            </select>
          </div>
          <div>
            <label className="smallcaps text-[var(--muted)] mb-1 block">Teacher</label>
            <select className="w-full px-2 py-1.5 hair border rounded-sm bg-white"
              value={newFacultyId} onChange={e => setNewFacultyId(e.target.value)}>
              {faculty.map(f => <option key={f.id} value={f.id}>{f.rank} · {String(f.user_id).slice(0,8)}</option>)}
            </select>
          </div>
        </div>
        <div className="p-3 hair-t flex items-center justify-end gap-2">
          <GhostButton onClick={onClose}>Cancel</GhostButton>
          <PrimaryButton icon="check" mode="sage"
            onClick={() => onApply(entry, newDay, newSlot, newFacultyId, newRoomId)}>
            Apply &amp; lock
          </PrimaryButton>
        </div>
      </div>
    </div>
  );
}

// Command bar — slash commands + NL free text
function CommandBar({ termId, version, entries, onEntryLockChange, onResolved }) {
  const [text, setText] = useState("");
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [history, setHistory] = useState([]);
  const [showHelp, setShowHelp] = useState(false);

  const SLASH_HELP = [
    { cmd:"/move SE223 A → Mon 1",  desc:"Move course+section to day (Mon/Tue/…) + slot index" },
    { cmd:"/lock SE223 A",          desc:"Pin cell — solver won't move it on re-solve" },
    { cmd:"/unlock SE223 A",        desc:"Unpin cell" },
  ];

  function resolveEntry(code, sec) {
    return entries.find(e =>
      e.course_code.toLowerCase() === code.toLowerCase() &&
      e.section_name.toLowerCase() === sec.toLowerCase()
    );
  }

  function buildPreview(t) {
    t = t.trim();
    let m;

    m = t.match(/^\/lock\s+(\S+)\s+(\S+)/i);
    if (m) {
      const [,code,sec] = m;
      const e = resolveEntry(code, sec);
      if (!e) return { label:`No entry found for ${code} section ${sec}`, action:null };
      return {
        label: `Lock ${code} section ${sec} — solver will not move this cell on re-solve.`,
        action: async () => {
          await AnchorAPI.apiPatch(`${TT_BASE}/entries/${e.id}`, { lock:true });
          onEntryLockChange(e.id, true);
          addHistory(`/lock ${code} ${sec}`);
        }
      };
    }

    m = t.match(/^\/unlock\s+(\S+)\s+(\S+)/i);
    if (m) {
      const [,code,sec] = m;
      const e = resolveEntry(code, sec);
      if (!e) return { label:`No entry found for ${code} section ${sec}`, action:null };
      return {
        label: `Unlock ${code} section ${sec} — solver can freely place this cell.`,
        action: async () => {
          await AnchorAPI.apiPatch(`${TT_BASE}/entries/${e.id}`, { lock:false });
          onEntryLockChange(e.id, false);
          addHistory(`/unlock ${code} ${sec}`);
        }
      };
    }

    m = t.match(/^\/move\s+(\S+)\s+(\S+)\s*[→->]\s*(\w+)\s+(\d+)/i);
    if (m) {
      const [,code,sec,dayStr,slotStr] = m;
      const dayKey = dayStr.toLowerCase();
      const dayIdx = DAY_IDX_MAP[dayKey];
      if (dayIdx === undefined) return { label:`Unknown day "${dayStr}". Use: Sat, Sun, Mon, Tue, Wed, Thu.`, action:null };
      const slot = +slotStr;
      const e = resolveEntry(code, sec);
      if (!e) return { label:`No entry found for ${code} section ${sec}`, action:null };
      return {
        label: `Move ${code} section ${sec} → ${DAY_NAMES[dayIdx]}, slot ${slot}. All locked cells stay put.`,
        action: async () => {
          const job = await AnchorAPI.apiPostAuth(`${TT_BASE}/resolve`, {
            term_id: termId, base_version: version,
            change: { entry_id: e.id, new_day: dayIdx, new_slot: slot, lock: true },
            keep_locked: true, time_limit_s: 60,
          });
          onResolved(job.job_id);
          addHistory(`/move ${code} ${sec} → ${DAY_NAMES[dayIdx]} ${slot}`);
        }
      };
    }

    if (t.startsWith("/")) {
      return { label:"Unknown slash command. Type / to see available commands.", action:null };
    }

    return null; // NL path
  }

  function addHistory(cmd) { setHistory(h => [`✓ ${cmd}`, ...h.slice(0,4)]); }

  function onChange(val) {
    setText(val);
    if (val === "/") { setShowHelp(true); setPreview(null); return; }
    setShowHelp(false);
    if (val.startsWith("/")) {
      const p = buildPreview(val);
      setPreview(p);
    } else {
      setPreview(null);
    }
  }

  async function apply() {
    if (preview?.action) {
      setBusy(true);
      try { await preview.action(); setText(""); setPreview(null); }
      catch (e) { alert(e.message || "Command failed"); }
      finally { setBusy(false); }
      return;
    }
    // NL free-text path
    const t = text.trim();
    if (!t || t.startsWith("/")) return;
    setBusy(true);
    try {
      const job = await AnchorAPI.apiPostAuth(`${TT_BASE}/nl-edit`, {
        term_id: termId, base_version: version, text: t,
      });
      addHistory(t.slice(0, 40));
      onResolved(job.job_id);
      setText(""); setPreview(null);
    } catch (e) {
      alert(e.message || "NL parse failed — try rephrasing or use the popover to edit a cell directly.");
    } finally { setBusy(false); }
  }

  const canSubmit = !busy && text.trim() && (!preview || !!preview.action);

  return (
    <Card>
      <SectionLabel right={
        <span className="text-[10.5px] text-[var(--muted)]">slash command or free text EN/BN</span>
      }>Command</SectionLabel>

      {/* Slash help dropdown */}
      {showHelp && (
        <div className="mb-3 p-3 rounded-sm space-y-2" style={{ background:"var(--mist)", opacity:0.9 }}>
          {SLASH_HELP.map(({ cmd, desc }) => (
            <div key={cmd} className="flex items-start gap-3">
              <span className="font-mono text-[11.5px] text-[var(--ink)] whitespace-nowrap">{cmd}</span>
              <span className="text-[11.5px] text-[var(--muted)]">{desc}</span>
            </div>
          ))}
          <div className="text-[11px] text-[var(--muted)] pt-1">Or type any sentence in English or Bangla for the AI to interpret.</div>
        </div>
      )}

      {/* Confirm chip */}
      {preview && (
        <div className="flex items-center gap-2 px-3 py-2 rounded-sm mb-3"
          style={{
            background: preview.action ? "rgba(74,107,92,0.06)" : "rgba(232,49,42,0.05)",
            border: `1px solid ${preview.action ? "rgba(74,107,92,0.2)" : "rgba(232,49,42,0.2)"}`,
          }}>
          <Icon name={preview.action ? "info" : "alert-circle"} size={13}
            style={{ color: preview.action ? "var(--sage)" : "var(--red)" }} />
          <span className="text-[12.5px] flex-1">{preview.label}</span>
          {preview.action && (
            <>
              <GhostButton size="sm" onClick={() => { setText(""); setPreview(null); }}>Cancel</GhostButton>
              <PrimaryButton size="sm" mode="sage" onClick={apply} disabled={busy}>
                {busy ? "…" : "Apply"}
              </PrimaryButton>
            </>
          )}
        </div>
      )}

      <div className="flex gap-2">
        <input type="text" value={text} onChange={e => onChange(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter" && canSubmit && !preview?.action) apply(); }}
          placeholder="SE223 A ke Monday 1st slot e niye jao… or /lock SE223 A"
          className="flex-1 px-3 py-2 hair border rounded-sm text-[13px] bg-white" />
        <PrimaryButton mode="sage" icon={busy ? "loader" : "send"}
          disabled={!canSubmit} onClick={apply}>
          {busy ? "…" : "Send"}
        </PrimaryButton>
      </div>
      <div className="text-[11px] text-[var(--muted)] mt-1.5 flex items-center gap-1">
        <Icon name="zap" size={10} /> Type <span className="font-mono">/</span> to see slash commands · or describe the change in plain text
      </div>

      {history.length > 0 && (
        <div className="mt-2.5 space-y-0.5 border-t hair-t pt-2">
          {history.map((h, i) => (
            <div key={i} className="font-mono text-[10.5px] text-[var(--muted)]">{h}</div>
          ))}
        </div>
      )}
    </Card>
  );
}

// ── Tab 5: Publish ────────────────────────────────────────────────────────────
function TimetablePublish({ termId, version, onGo }) {
  const [validation, setValidation] = useState(null);
  const [publishing, setPublishing] = useState(false);
  const [publishResult, setPublishResult] = useState(null);
  const [err, setErr] = useState("");
  const [confirmOpen, setConfirmOpen] = useState(false);

  async function runValidate() {
    if (!termId) { setErr("Select a term first"); return; }
    setErr(""); setValidation(null);
    try {
      const v = await AnchorAPI.apiGet(`${TT_BASE}/validate?term_id=${termId}&version=${version}`);
      setValidation(v);
    } catch (e) { setErr(e.message || "Validate failed"); }
  }

  async function handlePublish() {
    setPublishing(true); setErr("");
    try {
      const result = await AnchorAPI.apiPostAuth(`${TT_BASE}/publish`, { term_id:termId, version });
      setPublishResult(result);
      setConfirmOpen(false);
    } catch (e) { setErr(e.message || "Publish failed"); }
    finally { setPublishing(false); }
  }

  const canPublish = validation && validation.hard_count === 0;

  return (
    <div className="max-w-[680px] space-y-4">
      {!termId && (
        <Card><div className="text-[13px] text-[var(--muted)]">Select a term above to validate and publish.</div></Card>
      )}

      <Card>
        <div className="flex items-center gap-3 flex-wrap">
          <div>
            <div className="font-medium text-[13px]">Version {version}</div>
            <div className="text-[11.5px] text-[var(--muted)]">Change the version number in the bar above if needed.</div>
          </div>
          <div className="flex-1" />
          <GhostButton icon="shield-check" onClick={runValidate} disabled={!termId}>
            Run validator
          </GhostButton>
        </div>
      </Card>

      {err && <div className="text-[var(--red)] text-[12.5px] px-1">{err}</div>}

      {validation && (
        <Card>
          <SectionLabel>Validation — version {validation.version}</SectionLabel>
          {validation.hard_count === 0 ? (
            <div className="flex items-center gap-2 text-[13px]" style={{ color:"var(--sage)" }}>
              <Icon name="check-circle" size={14} /> All hard constraints satisfied — ready to publish.
            </div>
          ) : (
            <div className="space-y-2">
              <div className="flex items-center gap-1.5 text-[13px]" style={{ color:"var(--red)" }}>
                <Icon name="alert-triangle" size={14} /> {validation.hard_count} conflict(s) — resolve before publishing.
              </div>
              {(validation.conflicts || []).map((c, i) => (
                <div key={i} className="hair border rounded-sm p-2.5 text-[12.5px]"
                  style={{ borderColor:"rgba(232,49,42,0.3)", background:"rgba(232,49,42,0.03)" }}>
                  <div className="font-medium">{c.conflict_type.replace(/_/g," ")}</div>
                  <div className="text-[var(--muted)]">{c.description}</div>
                </div>
              ))}
              {validation.soft_count > 0 && (
                <div className="text-[11.5px] text-[var(--muted)]">
                  + {validation.soft_count} soft violation(s) — these are acceptable and won't block publish.
                </div>
              )}
            </div>
          )}
        </Card>
      )}

      {canPublish && !publishResult && (
        <div className="flex items-center gap-3">
          <PrimaryButton mode="sage" icon="send" onClick={() => setConfirmOpen(true)}>
            Publish routine to students
          </PrimaryButton>
          <span className="text-[11.5px] text-[var(--muted)]">Students see this immediately.</span>
        </div>
      )}

      {!canPublish && validation && validation.hard_count > 0 && (
        <div className="text-[12.5px] text-[var(--muted)]">
          Fix the {validation.hard_count} conflict(s) in the Grid tab first, or go back to Generate and re-solve.
        </div>
      )}

      {publishResult && (
        <Card>
          <div className="flex items-center gap-2 font-medium text-[13px] mb-2" style={{ color:"var(--sage)" }}>
            <Icon name="check-circle" size={14} /> Published {publishResult.published_routines} routine(s) to students.
          </div>
          <div className="text-[12px] text-[var(--muted)] mb-3">
            Students can now view their schedule in the Anchor app.
          </div>
          <GhostButton size="sm" onClick={() => onGo && onGo("/university/routine")}>
            View in Routine Builder
          </GhostButton>
        </Card>
      )}

      <ConfirmModal
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        onConfirm={handlePublish}
        title={`Publish version ${version}?`}
        body="This writes the timetable to the student-facing routine feed. Students with the app will see their class schedule immediately."
        confirmWord="PUBLISH"
        confirmLabel={publishing ? "Publishing…" : "Publish"}
        tone="sage"
      />
    </div>
  );
}

Object.assign(window, { UniTimetable });
