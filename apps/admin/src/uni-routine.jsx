// Routine Builder — three-step workflow ending in the weekly grid timetable
var { useState, useEffect, useCallback, useRef, useMemo } = React;
function UniRoutine({ onGo }) {
  const [step, setStep] = useState(2); // 0,1,2 -> Input / Generate / Review
  const [tab, setTab] = useState('courses');
  const [solving, setSolving] = useState(false);
  const [solved, setSolved] = useState(true);
  const [publishConfirm, setPublishConfirm] = useState(false);
  const [dept, setDept] = useState('SWE');
  const [semester, setSemester] = useState('Spring 2026');
  const D = window.AnchorData;

  return (
    <>
      <PageHeader
        title="Routine Builder"
        bn="ক্লাসের রুটিন প্রস্তুতকারক"
        description="Generate and publish the academic routine for your department. The solver respects hard constraints and minimises soft violations."
        actions={
          <>
            <div className="flex items-center gap-2 text-[12.5px] text-[var(--graphite)] mr-2">
              <span className="smallcaps text-[var(--muted)]">Department</span>
              <select value={dept} onChange={e=>setDept(e.target.value)} className="hair border rounded-sm bg-white px-2 py-1">
                <option value="SWE">Department of SWE</option>
                <option value="CSE">Department of CSE</option>
                <option value="EEE">Department of EEE</option>
              </select>
              <span className="smallcaps text-[var(--muted)] ml-3">Semester</span>
              <select value={semester} onChange={e=>setSemester(e.target.value)} className="hair border rounded-sm bg-white px-2 py-1">
                <option>Spring 2026</option>
                <option>Summer 2026</option>
              </select>
            </div>
            <StatusPill status={step===2 && solved ? 'Submitted' : 'Submitted'} />
            <MonoChip tone="navy">Draft</MonoChip>
          </>
        }
      />

      {/* Stepper */}
      <Card noPad className="mb-6">
        <div className="grid grid-cols-3">
          {[
            { i:0, name:'Input data', sub:'Courses, teachers, rooms, constraints', icon:'database' },
            { i:1, name:'Generate schedule', sub:'OR-Tools CP-SAT solver', icon:'cpu' },
            { i:2, name:'Review & publish', sub:'Weekly grid, conflicts, notify', icon:'calendar-check' },
          ].map((s, idx) => {
            const done = idx < step;
            const active = idx === step;
            return (
              <button key={s.i} onClick={()=>setStep(idx)} className={`p-5 text-left flex items-center gap-3 hair-r last:border-r-0 transition ${active?'bg-[var(--sage-tint)]/60':'hover:bg-[var(--mist)]/30'}`}>
                <div className="w-9 h-9 rounded-full flex items-center justify-center font-mono text-[12px]"
                  style={{ background: done?'var(--sage)':active?'var(--navy)':'var(--mist)', color: (done||active)?'white':'var(--graphite)' }}>
                  {done ? <Icon name="check" size={14} /> : idx+1}
                </div>
                <div className="min-w-0">
                  <div className={`text-[13.5px] font-medium ${active?'text-[var(--sage)]':'text-[var(--ink)]'}`}>{s.name}</div>
                  <div className="text-[11.5px] text-[var(--muted)] truncate">{s.sub}</div>
                </div>
              </button>
            );
          })}
        </div>
      </Card>

      {step===0 && <RoutineInput tab={tab} setTab={setTab} D={D} />}
      {step===1 && <RoutineGenerate solving={solving} solved={solved} onSolve={() => { setSolving(true); setTimeout(()=>{ setSolving(false); setSolved(true); setStep(2); }, 1800); }} />}
      {step===2 && <RoutineReview D={D} dept={dept} semester={semester} onPublish={()=>setPublishConfirm(true)} />}

      <ConfirmModal
        open={publishConfirm} onClose={()=>setPublishConfirm(false)} onConfirm={()=>{}}
        title={`Publish ${semester} routine?`}
        body="This will notify 12 teachers and 320 students via push notification + SMS. Once published, edits will require a new version and re-notification."
        confirmWord="PUBLISH" confirmLabel="Publish" tone="sage"
      />
    </>
  );
}

function RoutineInput({ tab, setTab, D }) {
  return (
    <div className="grid gap-5" style={{ gridTemplateColumns: '1fr 320px' }}>
      <Card noPad>
        <div className="flex items-center gap-1 px-4 pt-3 hair-b">
          {[
            { v:'courses', label:'Courses', count:D.courses.length },
            { v:'teachers', label:'Teachers', count:9 },
            { v:'rooms', label:'Rooms', count:14 },
            { v:'sections', label:'Sections', count:5 },
            { v:'slots', label:'Time Slots', count:8 },
          ].map(t => (
            <button key={t.v} onClick={()=>setTab(t.v)} className={`px-3 py-2.5 text-[13px] -mb-px hair-b border-b-2 ${tab===t.v?'border-[var(--sage)] text-[var(--sage)] font-medium':'border-transparent text-[var(--graphite)] hover:text-[var(--ink)]'}`}>
              {t.label} <span className="font-mono text-[10px] text-[var(--muted)] ml-1">{t.count}</span>
            </button>
          ))}
          <div className="flex-1" />
          <button className="text-[12px] text-[var(--sage)] hover:underline inline-flex items-center gap-1 mb-1">
            <Icon name="plus" size={12} /> Add
          </button>
        </div>

        {tab==='courses' && (
          <DataTable
            columns={[
              { key:'code', label:'Code', render:r=><MonoChip>{r.code}</MonoChip> },
              { key:'name', label:'Course name' },
              { key:'credits', label:'Cr.', align:'right' },
              { key:'type', label:'Type', render:r=><Tag tone={r.type==='Lab'?'gold':'sage'}>{r.type}</Tag> },
              { key:'sections', label:'Sections', align:'right' },
              { key:'teacher', label:'Assigned teacher' },
              { key:'', label:'', render:()=><Icon name="more-horizontal" size={14} className="text-[var(--muted)]" /> },
            ]}
            rows={D.courses}
          />
        )}
        {tab==='teachers' && (
          <DataTable
            columns={[
              { key:'name', label:'Teacher' },
              { key:'avail', label:'Availability' },
              { key:'max', label:'Max teaching hrs/wk', align:'right' },
              { key:'pref', label:'Preferences' },
            ]}
            rows={[
              { name:'Dr. Mahbub Alam', avail:'Sun–Wed · 09:30–17:00', max:'12', pref:'No 18:30 slots; prefers KT-504' },
              { name:'Dr. Tahmina Karim', avail:'Sun, Tue, Thu · all day', max:'10', pref:'Lab block before noon' },
              { name:'Dr. Farzana Rahman', avail:'Mon–Thu · 08:00–15:30', max:'14', pref:'2-day teaching window' },
              { name:'Dr. Imran Chowdhury', avail:'Sun, Mon, Wed · 11:00–18:30', max:'10', pref:'No back-to-back 3-hour blocks' },
            ]}
          />
        )}
        {tab==='rooms' && (
          <DataTable
            columns={[
              { key:'room', label:'Room', render:r=><MonoChip>{r.room}</MonoChip> },
              { key:'type', label:'Type', render:r=><Tag tone={r.type==='Lab'?'gold':'sage'}>{r.type}</Tag> },
              { key:'cap', label:'Capacity', align:'right' },
              { key:'building', label:'Building' },
            ]}
            rows={[
              { room:'KT-504', type:'Theory', cap:42, building:'Knowledge Tower' },
              { room:'KT-308', type:'Lab',    cap:30, building:'Knowledge Tower' },
              { room:'KT-712', type:'Theory', cap:38, building:'Knowledge Tower' },
              { room:'KT-401', type:'Theory', cap:35, building:'Knowledge Tower' },
              { room:'AB1-201', type:'Theory',cap:45, building:'Academic Building 1' },
              { room:'AB2-105', type:'Lab',   cap:28, building:'Academic Building 2' },
            ]}
          />
        )}
        {tab==='sections' && (
          <DataTable
            columns={[
              { key:'sec', label:'Section', render:r=><MonoChip>{r.sec}</MonoChip> },
              { key:'batch', label:'Batch' },
              { key:'cap', label:'Enrollment', align:'right' },
            ]}
            rows={[
              { sec:'53-A', batch:'53', cap:38 },
              { sec:'53-B', batch:'53', cap:36 },
              { sec:'54-A', batch:'54', cap:42 },
              { sec:'54-B', batch:'54', cap:40 },
              { sec:'55-A', batch:'55', cap:34 },
            ]}
          />
        )}
        {tab==='slots' && (
          <div className="p-5 grid grid-cols-4 gap-2">
            {D.slots.map((s,i) => (
              <div key={s} className="hair border rounded-sm p-3 text-center">
                <div className="font-mono text-[14px] text-[var(--ink)]">{s}</div>
                <div className="text-[10px] text-[var(--muted)] mt-0.5">Slot {i+1} · 90 min</div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Constraints panel */}
      <div>
        <Card noPad>
          <div className="p-4 hair-b flex items-center gap-2">
            <Icon name="sliders-horizontal" size={14} />
            <span className="font-medium text-[13.5px]">Constraints</span>
          </div>
          <div className="p-4 space-y-4">
            <div>
              <div className="smallcaps text-[var(--muted)] mb-2">Hard · cannot violate</div>
              {[
                'No teacher in two rooms at once',
                'No section in two classes at once',
                'No room double-booked',
                'Lab courses → Lab-type rooms only',
                'Respect teacher availability windows',
              ].map(c => (
                <div key={c} className="flex items-center gap-2 py-1 text-[12.5px]">
                  <Icon name="check-circle" size={12} style={{ color:'var(--sage)' }} />
                  <span className="text-[var(--graphite)]">{c}</span>
                </div>
              ))}
            </div>
            <div className="hair-t border-t pt-3">
              <div className="smallcaps text-[var(--muted)] mb-2">Soft · weighted</div>
              {[
                { name:'Minimise teacher gaps', val:80 },
                { name:'Cluster lab sessions', val:60 },
                { name:'Prefer morning blocks', val:40 },
                { name:'Spread sections across week', val:55 },
              ].map(s => (
                <div key={s.name} className="py-2">
                  <div className="flex items-center justify-between text-[12.5px] mb-1">
                    <span className="text-[var(--ink)]">{s.name}</span>
                    <span className="font-mono text-[var(--muted)]">{s.val}</span>
                  </div>
                  <input type="range" defaultValue={s.val} min={0} max={100} className="w-full accent-[var(--sage)]" />
                </div>
              ))}
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}

function RoutineGenerate({ solving, solved, onSolve }) {
  return (
    <Card className="p-10 text-center flex flex-col items-center gap-4">
      <div className="w-16 h-16 rounded-full flex items-center justify-center" style={{ background: solving?'#F2E8D2':'#E8EFEA' }}>
        <Icon name={solving?'loader':'cpu'} size={28} style={{ color: solving?'var(--gold)':'var(--sage)' }} className={solving?'animate-spin':''} />
      </div>
      <div>
        <h3 className="font-serif text-[26px] text-[var(--navy)]" style={{fontWeight:500}}>
          {solving?'Solving…':'Generate schedule'}
        </h3>
        <p className="mt-2 text-[13px] text-[var(--graphite)] max-w-[60ch]">
          {solving
            ? 'CP-SAT solver is exploring the feasible region · 4 courses · 5 sections · 6 rooms · 8 time slots'
            : 'Click Generate to run the Google OR-Tools CP-SAT solver against your inputs. The result will surface in step 3 with conflicts and feasibility score.'}
        </p>
      </div>
      <PrimaryButton mode="sage" icon="play" onClick={onSolve} disabled={solving}>
        {solving?'Solving…':'Generate schedule'}
      </PrimaryButton>
      <div className="text-[11px] text-[var(--muted)] flex items-center gap-2 mt-2">
        <Icon name="cpu" size={11} /> <span>Google OR-Tools · CP-SAT solver · ~1.4s typical</span>
      </div>
      {solving && (
        <div className="w-full max-w-[480px] mt-4 text-left">
          <div className="text-[11px] text-[var(--muted)] mb-1 flex justify-between"><span>Constraint propagation</span><span className="font-mono">14,221 / 18,000</span></div>
          <div className="h-1.5 bg-[var(--mist)] rounded-sm overflow-hidden">
            <div className="h-full bg-[var(--sage)]" style={{ width:'78%', transition:'width 1.2s ease' }} />
          </div>
        </div>
      )}
    </Card>
  );
}

function RoutineReview({ D, dept, semester, onPublish }) {
  const [hovered, setHovered] = useState(null);
  const [editing, setEditing] = useState(null);
  const [publishing, setPublishing] = useState(false);
  const [publishDone, setPublishDone] = useState(false);
  const [publishError, setPublishError] = useState('');
  const [existingRoutines, setExistingRoutines] = useState([]);

  useEffect(() => {
    AnchorAPI.apiGet('/v1/routines?page=1')
      .then(data => setExistingRoutines(data))
      .catch(() => {});
  }, [publishDone]);

  async function handlePublishToAPI() {
    setPublishing(true); setPublishError('');
    try {
      const slots = D.timetable.map(t => ({ day: D.days[t.d], time: D.slots[t.s], course: t.code, room: t.room, teacher: t.teacher, section: t.sec }));
      const routine = await AnchorAPI.apiPostAuth('/v1/routines', {
        title: `${dept} ${semester} Routine`,
        department: dept,
        semester,
        academic_year: '2025-2026',
        slots,
      });
      await AnchorAPI.apiPostAuth(`/v1/routines/${routine.id}/publish`, {});
      setPublishDone(true);
    } catch (err) {
      setPublishError(err.message || 'Publish failed. Try again.');
    } finally { setPublishing(false); }
  }
  return (
    <div className="grid gap-5" style={{ gridTemplateColumns:'1fr 280px' }}>
      <Card noPad>
        <div className="p-4 hair-b flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Icon name="calendar" size={14} />
            <span className="font-medium text-[13.5px]">Spring 2026 · Department of SWE</span>
            <span className="text-[12px] text-[var(--muted)]">Drag any cell to swap. Conflicts are outlined in red.</span>
          </div>
          <div className="flex items-center gap-2">
            <GhostButton size="sm" icon="rotate-ccw">Re-generate</GhostButton>
            <GhostButton size="sm" icon="download">Export</GhostButton>
          </div>
        </div>

        <div className="p-4">
          <div className="grid" style={{ gridTemplateColumns: '70px repeat(5, 1fr)', gap: '4px' }}>
            <div />
            {D.days.map(d => (
              <div key={d} className="smallcaps text-center text-[var(--muted)] pb-2">{d}</div>
            ))}
            {D.slots.map((slot, si) => (
              <React.Fragment key={slot}>
                <div className="text-[11px] text-[var(--muted)] font-mono flex items-start pt-2">{slot}</div>
                {D.days.map((d, di) => {
                  const entry = D.timetable.find(t => t.d===di && t.s===si);
                  if (!entry) {
                    return <div key={di} className="hair border border-dashed rounded-sm min-h-[58px]" style={{ borderColor:'#EDEAE0', background:'#FBF9F3' }} />;
                  }
                  const color = D.sectionColors[entry.sec] || '#4A6B5C';
                  return (
                    <button key={di} onClick={()=>setEditing(entry)} className={`tt-cell text-left rounded-sm p-2 min-h-[58px] relative hair border`}
                      style={{ borderColor: entry.conflict?'#E8312A':color+'33', background: color+'12', boxShadow: entry.conflict?'inset 0 0 0 2px #E8312A':'none' }}>
                      <div className="flex items-center gap-1.5">
                        <span className="w-1 h-3 rounded-full" style={{ background: color }} />
                        <span className="font-mono text-[11px] text-[var(--ink)] font-medium">{entry.code}</span>
                      </div>
                      <div className="mt-1 text-[11px] text-[var(--graphite)] leading-tight">
                        {entry.sec} · {entry.room}
                      </div>
                      <div className="text-[10px] text-[var(--muted)] truncate">{entry.teacher}</div>
                      {entry.conflict && (
                        <span className="absolute top-1 right-1 inline-flex items-center gap-0.5 text-[9px] font-mono uppercase tracking-wide" style={{ color:'var(--red)' }}>
                          <Icon name="alert-triangle" size={10} /> conflict
                        </span>
                      )}
                    </button>
                  );
                })}
              </React.Fragment>
            ))}
          </div>
        </div>

        {/* Legend */}
        <div className="px-4 pb-4 flex flex-wrap items-center gap-3 hair-t border-t pt-3">
          <span className="smallcaps text-[var(--muted)]">Sections</span>
          {Object.entries(D.sectionColors).map(([sec, color]) => (
            <span key={sec} className="inline-flex items-center gap-1.5 text-[12px]">
              <span className="w-2.5 h-2.5 rounded-sm" style={{ background: color }} />
              <span>{sec}</span>
            </span>
          ))}
        </div>
      </Card>

      {/* Right rail */}
      <div className="flex flex-col gap-4">
        <Card>
          <SectionLabel>Solver result</SectionLabel>
          <div className="space-y-2 text-[13px]">
            <Row k="Hard conflicts" v="0" tone="sage" />
            <Row k="Soft violations" v="3 teacher gaps" tone="gold" />
            <Row k="Feasibility score" v="92 / 100" tone="sage" />
            <Row k="Solve time" v="1.42s" />
          </div>
        </Card>
        <Card>
          <SectionLabel>Affected entities</SectionLabel>
          <div className="grid grid-cols-2 gap-3">
            {[
              { k:'Teachers', v:12 }, { k:'Rooms', v:8 }, { k:'Sections', v:6 }, { k:'Students', v:320 },
            ].map(x => (
              <div key={x.k} className="hair border rounded-sm p-3">
                <div className="font-mono text-[22px] text-[var(--ink)]">{x.v}</div>
                <div className="smallcaps text-[var(--muted)]">{x.k}</div>
              </div>
            ))}
          </div>
        </Card>
        <Card>
          <SectionLabel>Conflicts to resolve</SectionLabel>
          <div className="space-y-2 text-[12.5px]">
            <div className="hair border rounded-sm p-2 edge-red">
              <div className="font-medium">Room double-booked</div>
              <div className="text-[var(--muted)]">KT-308 · Tue 12:30 · SWE-405 (54-A) and SWE-410 (53-B)</div>
            </div>
            <div className="text-[11px] text-[var(--muted)]">Click the conflict cell in the grid to resolve.</div>
          </div>
        </Card>
        {publishError && <div className="text-[12px] px-3 py-2 rounded-sm mb-2" style={{ background:'rgba(232,49,42,0.08)', color:'var(--red)', border:'1px solid rgba(232,49,42,0.2)' }}>{publishError}</div>}
        {publishDone ? (
          <div className="text-[12.5px] px-3 py-2 rounded-sm" style={{ background:'rgba(74,107,92,0.08)', color:'var(--sage)', border:'1px solid rgba(74,107,92,0.2)' }}>
            Routine published and students notified.
          </div>
        ) : (
          <PrimaryButton mode="sage" icon="send" className="justify-center" disabled={publishing} onClick={handlePublishToAPI}>
            {publishing ? 'Publishing…' : 'Publish routine'}
          </PrimaryButton>
        )}

        {existingRoutines.length > 0 && (
          <div className="mt-4">
            <SectionLabel>Published routines</SectionLabel>
            <div className="space-y-1.5">
              {existingRoutines.slice(0, 4).map(r => (
                <div key={r.id} className="hair border rounded-sm p-2 text-[12px] flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="font-medium text-[var(--ink)] truncate">{r.title}</div>
                    <div className="text-[var(--muted)] font-mono">{r.department} · {r.semester || '—'}</div>
                  </div>
                  <Tag tone={r.status === 'published' ? 'sage' : 'mist'}>{r.status}</Tag>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Cell edit popover (simple) */}
      {editing && (
        <div className="fixed inset-0 z-30 flex items-center justify-center" style={{ background:'rgba(11,29,53,0.25)' }} onClick={()=>setEditing(null)}>
          <div className="bg-[var(--paper)] rounded-sm w-[420px] hair border" onClick={e=>e.stopPropagation()}>
            <div className="p-4 hair-b">
              <div className="smallcaps text-[var(--muted)] mb-1">Edit slot</div>
              <h3 className="font-serif text-[20px] text-[var(--navy)]">{editing.code} · {editing.sec}</h3>
            </div>
            <div className="p-4 space-y-3 text-[13px]">
              <Field label="Room"><select className="w-full px-2 py-1.5 hair border rounded-sm bg-white"><option>{editing.room}</option><option>KT-712</option><option>AB1-201</option></select></Field>
              <Field label="Teacher"><select className="w-full px-2 py-1.5 hair border rounded-sm bg-white"><option>{editing.teacher}</option><option>Dr. Mahbub Alam</option><option>Dr. Farzana Rahman</option></select></Field>
            </div>
            <div className="p-3 hair-t flex items-center justify-end gap-2">
              <GhostButton onClick={()=>setEditing(null)}>Cancel</GhostButton>
              <PrimaryButton icon="check" mode="sage" onClick={()=>setEditing(null)}>Apply</PrimaryButton>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ k, v, tone }) {
  const c = tone==='sage' ? 'var(--sage)' : tone==='gold' ? 'var(--gold)' : 'var(--ink)';
  return (
    <div className="flex items-center justify-between hair-b last:border-b-0 py-1.5">
      <span className="text-[var(--muted)]">{k}</span>
      <span className="font-mono" style={{ color: c }}>{v}</span>
    </div>
  );
}

Object.assign(window, { UniRoutine });
