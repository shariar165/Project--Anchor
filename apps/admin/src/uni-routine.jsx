// Routine Editor — tweak the routines the Timetable Generator produces
// (AcademicRoutine.slots). Tweak by hand, by Excel round-trip, or by
// AI (local Ollama), see live conflicts, then publish to students. Fresh CP-SAT
// generation lives in the untouched Timetable Generator (handoff button below).
var { useState, useEffect, useCallback, useRef, useMemo } = React;

const RB_API = "/v1/routines";
const RB_DAY_ORDER = ["Saturday", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];
const RB_DAY_ABBR = { sat: "Saturday", sun: "Sunday", mon: "Monday", tue: "Tuesday", wed: "Wednesday", thu: "Thursday", fri: "Friday" };
const RB_SECTION_COLORS = ["#4A6B5C", "#B8893A", "#C44536", "#3B6EA5", "#7B5EA7", "#2E8B8B"];

function rbDayIndex(day) {
  const d = (day || "").trim().toLowerCase();
  const full = RB_DAY_ABBR[d.slice(0, 3)] || day;
  const i = RB_DAY_ORDER.findIndex(x => x.toLowerCase() === String(full).toLowerCase());
  return i === -1 ? 99 : i;
}

function rbSlotTime(s) {
  const t = (s.time || "").trim();
  if (t) return t;
  const a = (s.start_time || "").trim(), b = (s.end_time || "").trim();
  if (a && b) return a + "-" + b;
  return a || b || "";
}

// Sort key in minutes; campus afternoon slots (1:00–5:30) read as PM.
function rbStartMins(timeStr) {
  const first = String(timeStr || "").split("-")[0].trim();
  const m = first.match(/(\d{1,2})(?::(\d{2}))?/);
  if (!m) return 9999;
  let h = parseInt(m[1], 10);
  const min = m[2] ? parseInt(m[2], 10) : 0;
  if (h < 8) h += 12; // 1:00 → 13:00
  return h * 60 + min;
}

function rbStatusPill(status) {
  if (status === "published") return <Tag tone="sage" icon="check-circle">Published</Tag>;
  if (status === "archived") return <Tag tone="mist">Archived</Tag>;
  return <Tag tone="gold" icon="pencil">Draft</Tag>;
}

// ── Root ──────────────────────────────────────────────────────────────────────
function UniRoutine({ onGo }) {
  const [routines, setRoutines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);
  const [showNew, setShowNew] = useState(false);

  const loadList = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const data = await AnchorAPI.apiGet(`${RB_API}?page=1`);
      setRoutines(Array.isArray(data) ? data : []);
    } catch (e) {
      setError(e.message || "Could not load routines");
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { loadList(); }, [loadList]);

  if (selected) {
    return (
      <RoutineEditor
        routineId={selected}
        onBack={() => { setSelected(null); loadList(); }}
        onGo={onGo}
      />
    );
  }

  return (
    <>
      <PageHeader
        title="Routine Editor"
        bn="ক্লাসের রুটিন সম্পাদক"
        description="Open a routine produced by the Timetable Generator, then tweak it by hand, by Excel, or by AI — with live conflict checks — and publish it to students."
        actions={<PrimaryButton mode="sage" icon="plus" onClick={() => setShowNew(true)}>New routine</PrimaryButton>}
      />

      {/* Generator handoff */}
      <Card className="mb-5 flex items-center gap-4" >
        <div className="w-10 h-10 rounded-full flex items-center justify-center shrink-0" style={{ background: "rgba(74,107,92,0.10)" }}>
          <Icon name="cpu" size={18} style={{ color: "var(--sage)" }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-[13.5px] font-medium text-[var(--ink)]">Need a fresh schedule from scratch?</div>
          <div className="text-[12px] text-[var(--muted)]">The Timetable Generator runs the Google OR-Tools CP-SAT solver, then publishes routines here for you to fine-tune.</div>
        </div>
        <GhostButton icon="arrow-up-right" onClick={() => onGo && onGo("/university/timetable")}>Open Timetable Generator</GhostButton>
      </Card>

      {error && (
        <div className="mb-4 text-[12.5px] px-3 py-2 rounded-sm" style={{ background: "rgba(232,49,42,0.08)", color: "var(--red)", border: "1px solid rgba(232,49,42,0.2)" }}>{error}</div>
      )}

      <Card noPad>
        <div className="p-4 hair-b flex items-center gap-2">
          <Icon name="calendar" size={14} style={{ color: "var(--sage)" }} />
          <span className="font-medium text-[13.5px]">Your routines</span>
          <span className="text-[12px] text-[var(--muted)]">· drafts and published</span>
        </div>
        {loading ? (
          <div className="p-10 text-center text-[var(--muted)] text-[13px]">Loading…</div>
        ) : routines.length === 0 ? (
          <EmptyState
            icon="calendar-plus"
            title="No routines yet"
            body="Generate one in the Timetable Generator, import an Excel sheet, or start a blank routine to build by hand."
            action={<div className="flex items-center gap-2 mt-1">
              <PrimaryButton mode="sage" icon="plus" onClick={() => setShowNew(true)}>New routine</PrimaryButton>
              <GhostButton icon="cpu" onClick={() => onGo && onGo("/university/timetable")}>Timetable Generator</GhostButton>
            </div>}
          />
        ) : (
          <DataTable
            onRowClick={r => setSelected(r.id)}
            columns={[
              { key: "title", label: "Routine", render: r => <span className="font-medium text-[var(--ink)]">{r.title}</span> },
              { key: "department", label: "Dept", render: r => r.department ? <MonoChip>{r.department}</MonoChip> : <span className="text-[var(--muted)]">—</span> },
              { key: "batch", label: "Batch / section", render: r => r.batch || <span className="text-[var(--muted)]">—</span> },
              { key: "semester", label: "Semester", render: r => r.semester || <span className="text-[var(--muted)]">—</span> },
              { key: "slots", label: "Classes", align: "right", render: r => <span className="font-mono text-[12px]">{(r.slots || []).length}</span> },
              { key: "status", label: "Status", render: r => rbStatusPill(r.status) },
              { key: "", label: "", render: () => <Icon name="chevron-right" size={15} className="text-[var(--muted)]" /> },
            ]}
            rows={routines}
          />
        )}
      </Card>

      {showNew && (
        <NewRoutineForm
          onClose={() => setShowNew(false)}
          onCreated={id => { setShowNew(false); setSelected(id); }}
        />
      )}
    </>
  );
}

// ── New routine (blank draft) ─────────────────────────────────────────────────
function NewRoutineForm({ onClose, onCreated }) {
  const [form, setForm] = useState({ title: "", department: "", batch: "", semester: "", academic_year: "" });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  async function submit() {
    if (form.title.trim().length < 2) { setErr("Give the routine a title."); return; }
    setBusy(true); setErr("");
    try {
      const created = await AnchorAPI.apiPostAuth(RB_API, {
        title: form.title.trim(),
        department: form.department.trim() || null,
        batch: form.batch.trim() || null,
        semester: form.semester.trim() || null,
        academic_year: form.academic_year.trim() || null,
        slots: [],
      });
      onCreated(created.id);
    } catch (e) { setErr(e.message || "Could not create routine"); }
    finally { setBusy(false); }
  }

  const field = (k, label, placeholder) => (
    <div>
      <label className="smallcaps text-[var(--muted)] mb-1 block">{label}</label>
      <input value={form[k]} onChange={e => set(k, e.target.value)} placeholder={placeholder}
        className="w-full px-2 py-1.5 hair border rounded-sm bg-white text-[13px]" />
    </div>
  );

  return (
    <SlideOver open={true} onClose={onClose}>
      <div className="p-5 hair-b">
        <div className="smallcaps text-[var(--muted)] mb-1">Routine Editor</div>
        <h3 className="font-serif text-[22px] text-[var(--navy)]">New routine</h3>
      </div>
      <div className="p-5 space-y-4">
        {field("title", "Title", "SWE Spring 2026 — Section A")}
        <div className="grid grid-cols-2 gap-3">
          {field("department", "Department", "SWE")}
          {field("batch", "Batch / section", "Batch 41 (A)")}
        </div>
        <div className="grid grid-cols-2 gap-3">
          {field("semester", "Semester", "Spring 2026")}
          {field("academic_year", "Academic year", "2025-2026")}
        </div>
        {err && <div className="text-[var(--red)] text-[12px]">{err}</div>}
        <PrimaryButton mode="sage" icon={busy ? "loader" : "plus"} className="w-full justify-center" onClick={submit} disabled={busy}>
          {busy ? "Creating…" : "Create & edit"}
        </PrimaryButton>
        <div className="text-[11.5px] text-[var(--muted)]">Starts empty — add classes by hand, or import an Excel/CSV grid on the next screen.</div>
      </div>
    </SlideOver>
  );
}

// ── Editor ────────────────────────────────────────────────────────────────────
function RoutineEditor({ routineId, onBack, onGo }) {
  const [routine, setRoutine] = useState(null);
  const [slots, setSlots] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [conflicts, setConflicts] = useState([]);
  const [editCell, setEditCell] = useState(null); // { slot, index|null }
  const [publishConfirm, setPublishConfirm] = useState(false);
  const [published, setPublished] = useState(false);
  const [aiText, setAiText] = useState("");
  const [aiBusy, setAiBusy] = useState(false);
  const [aiPreview, setAiPreview] = useState(null); // { summary, new_slots }
  const [aiError, setAiError] = useState("");
  const fileRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await AnchorAPI.apiGet(`${RB_API}/${routineId}`);
      setRoutine(data);
      setSlots(Array.isArray(data.slots) ? data.slots : []);
      setPublished(data.status === "published");
    } catch (e) { setMsg(e.message || "Could not load routine"); }
    finally { setLoading(false); }
  }, [routineId]);

  useEffect(() => { load(); }, [load]);

  const validate = useCallback(async () => {
    try {
      const v = await AnchorAPI.apiGet(`${RB_API}/${routineId}/validate`);
      setConflicts(v.conflicts || []);
    } catch { setConflicts([]); }
  }, [routineId]);

  useEffect(() => { if (!loading) validate(); }, [loading, validate]);

  const conflictIdx = useMemo(() => {
    const set = new Set();
    conflicts.forEach(c => (c.slot_indexes || []).forEach(i => set.add(i)));
    return set;
  }, [conflicts]);

  // Persist the full slots array, then re-validate.
  async function persist(nextSlots, note) {
    setSaving(true); setMsg("");
    try {
      const updated = await AnchorAPI.apiPatch(`${RB_API}/${routineId}`, { slots: nextSlots });
      setRoutine(updated);
      setSlots(Array.isArray(updated.slots) ? updated.slots : nextSlots);
      setPublished(updated.status === "published");
      if (note) setMsg(note);
      await validate();
    } catch (e) { setMsg(e.message || "Save failed"); }
    finally { setSaving(false); }
  }

  const days = useMemo(() => {
    const seen = [];
    slots.forEach(s => { const d = (s.day || "").trim(); if (d && !seen.includes(d)) seen.push(d); });
    const arr = seen.length ? seen : RB_DAY_ORDER.slice(0, 6);
    return arr.slice().sort((a, b) => rbDayIndex(a) - rbDayIndex(b));
  }, [slots]);

  const times = useMemo(() => {
    const seen = [];
    slots.forEach(s => { const t = rbSlotTime(s); if (t && !seen.includes(t)) seen.push(t); });
    const arr = seen.length ? seen : ["8:30-10:00", "10:00-11:30", "11:30-1:00", "1:00-2:30", "2:30-4:00"];
    return arr.slice().sort((a, b) => rbStartMins(a) - rbStartMins(b));
  }, [slots]);

  // (day|time) -> array of {slot, index}
  const cellMap = useMemo(() => {
    const m = {};
    slots.forEach((s, index) => {
      const key = (s.day || "").trim() + "||" + rbSlotTime(s);
      (m[key] = m[key] || []).push({ slot: s, index });
    });
    return m;
  }, [slots]);

  function openCell(day, time, existing) {
    if (existing) { setEditCell({ slot: existing.slot, index: existing.index }); return; }
    const [start, end] = String(time).includes("-") ? time.split("-").map(x => x.trim()) : [time, ""];
    setEditCell({ slot: { day, start_time: start, end_time: end, course_code: "", course_name: "", teacher: "", room: "" }, index: null });
  }

  function saveCell(slot, index) {
    const next = slots.slice();
    if (index === null || index === undefined) next.push(slot);
    else next[index] = slot;
    setEditCell(null);
    persist(next, "Saved.");
  }

  function removeCell(index) {
    const next = slots.filter((_, i) => i !== index);
    setEditCell(null);
    persist(next, "Class removed.");
  }

  // Excel import (authenticated multipart — mirrors the Timetable Generator).
  async function handleImport(e) {
    const file = e.target.files[0];
    if (!file) return;
    setMsg("Importing…");
    const fd = new FormData();
    fd.append("file", file);
    try {
      const res = await fetch(
        `${window.ANCHOR_API_URL || "http://localhost:8000"}${RB_API}/${routineId}/import`,
        { method: "POST", headers: { Authorization: `Bearer ${localStorage.getItem("anchor_admin_access_token")}` }, body: fd }
      );
      const data = await res.json();
      if (!res.ok) { setMsg(data.detail || "Import failed"); return; }
      setRoutine(data.routine);
      setSlots(Array.isArray(data.routine.slots) ? data.routine.slots : []);
      setPublished(false);
      setMsg(`Imported ${data.imported} class${data.imported === 1 ? "" : "es"}${data.errors && data.errors.length ? ` · ${data.errors.length} skipped` : ""}.`);
      validate();
    } catch (err) { setMsg("Import failed — check the file and try again."); }
    finally { if (fileRef.current) fileRef.current.value = ""; }
  }

  function exportExcel() {
    const stem = `routine-${routine.semester || routine.department || String(routine.id).slice(0, 8)}`;
    AnchorAPI.apiDownload(`${RB_API}/${routineId}/export?format=xlsx`, `${stem}.xlsx`).catch(e => setMsg(e.message || "Export failed"));
  }

  async function askAI() {
    if (aiText.trim().length < 2) return;
    setAiBusy(true); setAiError(""); setAiPreview(null);
    try {
      const res = await AnchorAPI.apiPostAuth(`${RB_API}/${routineId}/ai-edit`, { text: aiText.trim() });
      if (res.ok) setAiPreview({ summary: res.summary, new_slots: res.new_slots });
      else setAiError(res.reason || "Couldn't apply that.");
    } catch (e) { setAiError(e.message || "AI request failed"); }
    finally { setAiBusy(false); }
  }

  function applyAI() {
    const next = aiPreview.new_slots;
    setAiPreview(null); setAiText("");
    persist(next, "AI change applied.");
  }

  async function doPublish() {
    setSaving(true); setMsg("");
    try {
      const r = await AnchorAPI.apiPostAuth(`${RB_API}/${routineId}/publish`, {});
      setRoutine(r); setPublished(true);
      setMsg("Published — students can see it now.");
    } catch (e) { setMsg(e.message || "Publish failed"); }
    finally { setSaving(false); }
  }

  if (loading) return <div className="p-10 text-center text-[var(--muted)] text-[13px]">Loading routine…</div>;
  if (!routine) return (
    <div className="p-10 text-center">
      <div className="text-[13px] text-[var(--red)] mb-3">{msg || "Routine not found."}</div>
      <GhostButton icon="arrow-left" onClick={onBack}>Back to routines</GhostButton>
    </div>
  );

  const hasConflicts = conflicts.length > 0;

  return (
    <>
      <div className="flex items-center gap-2 mb-4">
        <GhostButton size="sm" icon="arrow-left" onClick={onBack}>Routines</GhostButton>
      </div>

      <PageHeader
        title={routine.title}
        description={[routine.department, routine.batch, routine.semester].filter(Boolean).join(" · ") || "Edit classes, then publish to students."}
        actions={
          <>
            {rbStatusPill(routine.status)}
            {saving && <span className="text-[11px] text-[var(--muted)] flex items-center gap-1"><Icon name="loader" size={12} className="animate-spin" /> saving</span>}
          </>
        }
      />

      {/* Toolbar */}
      <Card noPad className="mb-4">
        <div className="p-3 flex items-center gap-2 flex-wrap">
          <input ref={fileRef} type="file" accept=".csv,.xlsx,.xls" className="hidden" onChange={handleImport} />
          <GhostButton size="sm" icon="download" onClick={exportExcel}>Export to Excel</GhostButton>
          <GhostButton size="sm" icon="upload" onClick={() => fileRef.current && fileRef.current.click()}>Import Excel / CSV</GhostButton>
          <GhostButton size="sm" icon="plus" onClick={() => openCell(days[0], times[0], null)}>Add class</GhostButton>
          <div className="flex-1" />
          {msg && <span className="text-[12px] text-[var(--sage)]">{msg}</span>}
          {published ? (
            <Tag tone="sage" icon="check-circle">Live for students</Tag>
          ) : (
            <PrimaryButton size="sm" mode="sage" icon="send" onClick={() => setPublishConfirm(true)} disabled={saving}>Publish</PrimaryButton>
          )}
        </div>
      </Card>

      <div className="grid gap-4" style={{ gridTemplateColumns: "1fr 300px" }}>
        {/* Grid */}
        <Card noPad>
          <div className="p-4">
            <div className="grid" style={{ gridTemplateColumns: `90px repeat(${days.length}, 1fr)`, gap: 4 }}>
              <div />
              {days.map(d => <div key={d} className="smallcaps text-center text-[var(--muted)] pb-2">{d}</div>)}
              {times.map(time => (
                <React.Fragment key={time}>
                  <div className="text-[10.5px] text-[var(--muted)] font-mono flex items-start pt-2">{time}</div>
                  {days.map(day => {
                    const cell = (cellMap[day + "||" + time] || [])[0];
                    if (!cell) {
                      return (
                        <button key={day} onClick={() => openCell(day, time, null)}
                          className="hair border border-dashed rounded-sm min-h-[60px] flex items-center justify-center text-[var(--muted)] hover:bg-[var(--mist)]/30 transition"
                          style={{ borderColor: "#EDEAE0", background: "#FBF9F3" }}>
                          <Icon name="plus" size={12} className="opacity-0 hover:opacity-100" />
                        </button>
                      );
                    }
                    const { slot, index } = cell;
                    const color = RB_SECTION_COLORS[index % RB_SECTION_COLORS.length];
                    const bad = conflictIdx.has(index);
                    const dupes = (cellMap[day + "||" + time] || []).length;
                    return (
                      <button key={day} onClick={() => openCell(day, time, cell)}
                        className="text-left rounded-sm p-2 min-h-[60px] relative hair border transition"
                        style={{ borderColor: bad ? "#E8312A" : color + "33", background: color + "12", boxShadow: bad ? "inset 0 0 0 2px #E8312A" : "none" }}>
                        <div className="flex items-center gap-1.5">
                          <span className="w-1 h-3 rounded-full" style={{ background: color }} />
                          <span className="font-mono text-[11px] text-[var(--ink)] font-medium">{slot.course_code || "—"}</span>
                        </div>
                        <div className="mt-1 text-[11px] text-[var(--graphite)] leading-tight truncate">{slot.course_name || ""}</div>
                        <div className="text-[10px] text-[var(--muted)] truncate">{[slot.room, slot.teacher].filter(Boolean).join(" · ")}</div>
                        {(bad || dupes > 1) && (
                          <span className="absolute top-1 right-1 inline-flex items-center gap-0.5 text-[9px] font-mono uppercase" style={{ color: "var(--red)" }}>
                            <Icon name="alert-triangle" size={10} /> {dupes > 1 ? `+${dupes - 1}` : "clash"}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </React.Fragment>
              ))}
            </div>
            <div className="mt-3 text-[11px] text-[var(--muted)] flex items-center gap-1.5">
              <Icon name="info" size={11} /> Click any cell to edit a class or add one. Conflicts are outlined in red.
            </div>
          </div>
        </Card>

        {/* Right rail */}
        <div className="flex flex-col gap-4">
          {/* AI tweak */}
          <Card>
            <SectionLabel right={<Tag tone="navy" icon="sparkles">AI</Tag>}>Edit by AI</SectionLabel>
            <textarea rows={3} value={aiText} onChange={e => setAiText(e.target.value)}
              placeholder="e.g. Move CSE-301 to Tuesday 10:00, or put Dr. Rahman's class in room KT-601"
              className="w-full px-2 py-1.5 hair border rounded-sm bg-white text-[12.5px] resize-none" />
            <PrimaryButton mode="sage" size="sm" icon={aiBusy ? "loader" : "wand-2"} className="w-full justify-center mt-2" onClick={askAI} disabled={aiBusy || aiText.trim().length < 2}>
              {aiBusy ? "Thinking…" : "Suggest change"}
            </PrimaryButton>
            {aiError && <div className="mt-2 text-[11.5px] px-2 py-1.5 rounded-sm" style={{ background: "rgba(184,137,58,0.10)", color: "var(--gold)" }}>{aiError}</div>}
            {aiPreview && (
              <div className="mt-3 hair border rounded-sm p-3" style={{ background: "rgba(74,107,92,0.05)" }}>
                <div className="text-[12px] text-[var(--ink)] mb-2">{aiPreview.summary}</div>
                <div className="flex items-center gap-2">
                  <PrimaryButton mode="sage" size="sm" icon="check" onClick={applyAI}>Apply</PrimaryButton>
                  <GhostButton size="sm" onClick={() => setAiPreview(null)}>Discard</GhostButton>
                </div>
              </div>
            )}
          </Card>

          {/* Conflicts */}
          <Card>
            <SectionLabel right={hasConflicts ? <Tag tone="red">{conflicts.length}</Tag> : <Tag tone="sage" icon="check">clear</Tag>}>Conflicts</SectionLabel>
            {hasConflicts ? (
              <div className="space-y-2 text-[12px]">
                {conflicts.map((c, i) => (
                  <div key={i} className="hair border rounded-sm p-2" style={{ borderColor: "rgba(232,49,42,0.3)", background: "rgba(232,49,42,0.04)" }}>
                    <div className="font-medium text-[var(--ink)]">{c.type.replace(/_/g, " ")}</div>
                    <div className="text-[var(--muted)]">{c.description}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-[12px] text-[var(--muted)]">No teacher, room, or time clashes detected.</div>
            )}
          </Card>

          {/* Summary */}
          <Card>
            <SectionLabel>At a glance</SectionLabel>
            <div className="grid grid-cols-2 gap-3">
              {[
                { k: "Classes", v: slots.length },
                { k: "Days", v: days.length },
                { k: "Time slots", v: times.length },
                { k: "Conflicts", v: conflicts.length },
              ].map(x => (
                <div key={x.k} className="hair border rounded-sm p-3">
                  <div className="font-mono text-[20px] text-[var(--ink)]">{x.v}</div>
                  <div className="smallcaps text-[var(--muted)]">{x.k}</div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>

      {editCell && (
        <CellEditor
          entry={editCell}
          onClose={() => setEditCell(null)}
          onSave={saveCell}
          onRemove={removeCell}
        />
      )}

      <ConfirmModal
        open={publishConfirm} onClose={() => setPublishConfirm(false)} onConfirm={doPublish}
        title="Publish this routine?"
        body={hasConflicts
          ? `This routine still has ${conflicts.length} conflict(s). You can publish, but students will see the clashes. Continue?`
          : "Students with the app will see this class schedule immediately. You can edit and re-publish later."}
        confirmWord="PUBLISH" confirmLabel="Publish" tone="sage"
      />
    </>
  );
}

// ── Cell editor modal ─────────────────────────────────────────────────────────
function CellEditor({ entry, onClose, onSave, onRemove }) {
  const [s, setS] = useState({ ...entry.slot });
  const set = (k, v) => setS(prev => ({ ...prev, [k]: v }));
  const isNew = entry.index === null || entry.index === undefined;

  const field = (k, label, placeholder) => (
    <div>
      <label className="smallcaps text-[var(--muted)] mb-1 block">{label}</label>
      <input value={s[k] || ""} onChange={e => set(k, e.target.value)} placeholder={placeholder}
        className="w-full px-2 py-1.5 hair border rounded-sm bg-white text-[13px]" />
    </div>
  );

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center fade-in" style={{ background: "rgba(11,29,53,0.30)" }} onClick={onClose}>
      <div className="bg-[var(--paper)] rounded-sm w-[460px] max-w-[92vw] hair border" onClick={e => e.stopPropagation()}>
        <div className="p-4 hair-b">
          <div className="smallcaps text-[var(--muted)] mb-1">{isNew ? "Add class" : "Edit class"}</div>
          <h3 className="font-serif text-[20px] text-[var(--navy)]">{s.course_code || "New class"}</h3>
        </div>
        <div className="p-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            {field("day", "Day", "Saturday")}
            <div className="grid grid-cols-2 gap-2">
              {field("start_time", "Start", "8:30")}
              {field("end_time", "End", "10:00")}
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            {field("course_code", "Course code", "CSE-301")}
            {field("course_name", "Course name", "Algorithms")}
          </div>
          <div className="grid grid-cols-2 gap-3">
            {field("teacher", "Teacher", "Dr. Rahman")}
            {field("room", "Room", "KT-601")}
          </div>
        </div>
        <div className="p-3 hair-t flex items-center justify-between gap-2">
          {!isNew
            ? <GhostButton size="sm" danger icon="trash-2" onClick={() => onRemove(entry.index)}>Remove</GhostButton>
            : <span />}
          <div className="flex items-center gap-2">
            <GhostButton size="sm" onClick={onClose}>Cancel</GhostButton>
            <PrimaryButton size="sm" mode="sage" icon="check" onClick={() => onSave(s, entry.index)}>Save</PrimaryButton>
          </div>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { UniRoutine });
