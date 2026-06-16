// University Applications — Apply-Formally approval queue (live API)
var { useState, useEffect, useMemo } = React;

const APP_STAGE_LABEL = {
  mentor: 'Mentor', department_head: 'Dept Head', dean: 'Dean', accounts: 'Accounts',
};
const APP_STATE_LABEL = {
  draft: 'Draft', submitted: 'Submitted', in_review: 'In Review',
  changes_requested: 'Changes Requested', approved: 'Approved',
  rejected: 'Rejected', withdrawn: 'Withdrawn', escalated: 'Escalated',
};
const APP_TABS = [
  { key: 'mine', label: 'Needs my action' },
  { key: 'mentor', label: 'Mentor' },
  { key: 'department_head', label: 'Dept Head' },
  { key: 'dean', label: 'Dean' },
  { key: 'accounts', label: 'Accounts' },
  { key: 'decided', label: 'Decided' },
];

function _chainStages(detail) {
  if (!detail) return ['mentor', 'dean'];
  const first = detail.first_approver_type === 'mentor' ? 'mentor' : 'department_head';
  const stages = [first, 'dean'];
  if (detail.template && detail.template.requires_accounts_approval) stages.push('accounts');
  return stages;
}

function UniApplications({ onGo }) {
  const [tab, setTab] = useState('mine');
  const [rows, setRows] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadErr, setLoadErr] = useState('');
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [timeline, setTimeline] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [actionErr, setActionErr] = useState('');
  const [actionBusy, setActionBusy] = useState(false);
  const [confirm, setConfirm] = useState(null);
  const [note, setNote] = useState('');

  function load() {
    setLoading(true); setLoadErr('');
    let path;
    if (tab === 'mine') path = '/v1/admin/applications?scope=mine&page=1&page_size=50';
    else if (tab === 'decided') path = '/v1/admin/applications?scope=all&page=1&page_size=50';
    else path = `/v1/admin/applications?scope=all&stage=${tab}&page=1&page_size=50`;

    AnchorAPI.apiGet(path)
      .then(data => {
        let list = Array.isArray(data) ? data : [];
        if (tab === 'decided') {
          list = list.filter(r => ['approved', 'rejected', 'withdrawn'].includes(r.state));
        }
        setRows(list); setLoading(false);
      })
      .catch(err => { setLoadErr(err.message || 'Could not load applications.'); setLoading(false); });
  }

  function loadStats() {
    AnchorAPI.apiGet('/v1/admin/applications/stats')
      .then(setStats).catch(() => {});
  }

  useEffect(() => { load(); }, [tab]);
  useEffect(() => { loadStats(); }, []);

  function openDetail(row) {
    setSelected(row); setDetail(null); setTimeline(null);
    setDetailLoading(true); setActionErr(''); setNote('');
    AnchorAPI.apiGet(`/v1/admin/applications/${row.id}`)
      .then(d => { setDetail(d); setDetailLoading(false); })
      .catch(() => setDetailLoading(false));
    AnchorAPI.apiGet(`/v1/admin/applications/${row.id}/timeline`)
      .then(setTimeline).catch(() => {});
  }

  async function doAction(decision) {
    if (!selected) return;
    setActionBusy(true); setActionErr('');
    try {
      await AnchorAPI.apiPostAuth(`/v1/applications/${selected.id}/review`, {
        decision,
        notes: note.trim() || null,
      });
      setSelected(null); setNote('');
      load(); loadStats();
    } catch (err) {
      setActionErr(err.message || 'Action failed.');
    } finally { setActionBusy(false); }
  }

  const statCount = (k) => (stats ? stats[k] : null);

  return (
    <>
      <PageHeader
        title="Applications"
        bn="আবেদনসমূহ"
        description="Formal student applications routed to your stage. Approve to advance to the next authority, request changes, or reject. Every decision is recorded on the application's timeline."
        actions={<GhostButton icon="refresh-cw" size="sm" onClick={() => { load(); loadStats(); }}>Refresh</GhostButton>}
      />

      {loadErr && (
        <div className="mb-4 px-3 py-2 rounded-sm text-[12.5px]" style={{ background: 'rgba(232,49,42,0.08)', color: 'var(--red)', border: '1px solid rgba(232,49,42,0.2)' }}>
          {loadErr} — <button className="underline" onClick={load}>Retry</button>
        </div>
      )}

      {/* Stage tabs */}
      <div className="flex flex-wrap items-center gap-1 mb-4">
        {APP_TABS.map(t => {
          const c = t.key === 'mine' ? null : (t.key === 'decided' ? statCount('decided') : statCount(t.key));
          return (
            <button key={t.key} onClick={() => setTab(t.key)}
              className={`px-3 py-1.5 text-[12.5px] rounded-sm inline-flex items-center gap-1.5 ${tab === t.key ? 'bg-[var(--sage-tint)] text-[var(--sage)] font-medium' : 'text-[var(--muted)] hover:bg-[var(--mist)]/40'}`}>
              {t.label}
              {c != null && c > 0 && <span className="font-mono text-[10px] px-1.5 py-0.5 rounded-full" style={{ background: 'var(--mist)', color: 'var(--graphite)' }}>{c}</span>}
            </button>
          );
        })}
      </div>

      <div className="text-[13px] text-[var(--graphite)] mb-3">
        {loading ? <span className="text-[var(--muted)]">Loading…</span>
          : <><span className="font-mono text-[var(--ink)]">{rows.length}</span> application{rows.length === 1 ? '' : 's'}</>}
      </div>

      {loading && (
        <div className="space-y-2.5">
          {[1, 2, 3].map(i => (
            <div key={i} className="bg-[var(--paper)] hair border rounded-sm p-4 animate-pulse">
              <div className="h-4 bg-[var(--mist)] rounded-sm w-1/3 mb-2" />
              <div className="h-3 bg-[var(--mist)] rounded-sm w-2/3" />
            </div>
          ))}
        </div>
      )}

      {!loading && (
        <div className="space-y-2.5">
          {rows.map(r => (
            <ApplicationCard key={r.id} r={r} active={selected && selected.id === r.id} onClick={() => openDetail(r)} />
          ))}
          {rows.length === 0 && (
            <Card><EmptyState icon="inbox" title="Nothing here" body={tab === 'mine' ? 'No applications are waiting on your action right now.' : 'No applications at this stage.'} /></Card>
          )}
        </div>
      )}

      <SlideOver open={!!selected} onClose={() => setSelected(null)} width={620}>
        {selected && (
          <ApplicationDetail
            row={selected}
            detail={detail}
            timeline={timeline}
            detailLoading={detailLoading}
            note={note}
            setNote={setNote}
            actionErr={actionErr}
            actionBusy={actionBusy}
            onClose={() => setSelected(null)}
            onApprove={() => doAction('approved')}
            onChanges={() => doAction('changes_requested')}
            onReject={() => setConfirm('reject')}
          />
        )}
      </SlideOver>

      <ConfirmModal
        open={confirm === 'reject'} onClose={() => setConfirm(null)}
        onConfirm={() => { setConfirm(null); doAction('rejected'); }}
        title="Reject this application?"
        body="The student will see the application as rejected. This ends the approval chain."
        confirmWord="REJECT" confirmLabel="Reject" tone="red"
      />
    </>
  );
}

function ApplicationCard({ r, active, onClick }) {
  const money = r.requires_accounts_approval;
  return (
    <button onClick={onClick}
      className={`w-full text-left bg-[var(--paper)] hair border rounded-sm p-4 hover:bg-[var(--mist)]/15 transition ${active ? 'shadow-md' : ''}`}
      style={active ? { boxShadow: 'inset 3px 0 0 var(--sage), 0 0 0 1px var(--sage)' } : undefined}>
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-sm flex items-center justify-center shrink-0" style={{ background: 'var(--mist)' }}>
          <Icon name="file-check" size={16} style={{ color: 'var(--graphite)' }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <MonoChip>{String(r.id).slice(0, 8).toUpperCase()}</MonoChip>
            <span className="smallcaps text-[var(--muted)]">{r.template_name || 'Application'}</span>
            {money && <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium" style={{ background: 'rgba(184,137,58,0.12)', color: 'var(--gold)' }}>Money-related</span>}
            <span className="ml-auto text-[11px] text-[var(--muted)] font-mono">{new Date(r.updated_at).toLocaleDateString()}</span>
          </div>
          <div className="text-[14px] text-[var(--ink)] font-medium leading-snug">{r.student_name || 'Student'}</div>
          <div className="mt-2 flex items-center gap-3 text-[11.5px] text-[var(--muted)]">
            <span className="inline-flex items-center gap-1"><Icon name="map-pin" size={12} /> {r.current_approver_level ? (APP_STAGE_LABEL[r.current_approver_level] || r.current_approver_level) : '—'}</span>
            {r.round_count > 1 && <><span>·</span><span>round {r.round_count}</span></>}
          </div>
        </div>
        <StatusPill status={APP_STATE_LABEL[r.state] || r.state} />
      </div>
    </button>
  );
}

function ApplicationStepper({ detail }) {
  const stages = _chainStages(detail);
  const current = detail.current_approver_level;
  const done = detail.state === 'approved';
  const rejected = detail.state === 'rejected';
  // Index of current stage; if approved, everything is complete
  const curIdx = done ? stages.length : stages.indexOf(current);
  const labels = [...stages.map(s => APP_STAGE_LABEL[s] || s), 'Approved'];
  return (
    <div className="flex items-center gap-1">
      {labels.map((lbl, i) => {
        const reached = done ? true : i < curIdx;
        const isCurrent = !done && !rejected && i === curIdx;
        const isFinal = i === labels.length - 1;
        const color = (isFinal && done) ? 'var(--sage)' : reached ? 'var(--sage)' : isCurrent ? 'var(--gold)' : 'var(--mist)';
        return (
          <React.Fragment key={i}>
            <div className="flex flex-col items-center gap-1" style={{ minWidth: 54 }}>
              <div className="w-6 h-6 rounded-full flex items-center justify-center text-[10px]"
                style={{ background: (reached || (isFinal && done)) ? color : 'transparent', border: `1.5px solid ${color}`, color: (reached || (isFinal && done)) ? '#fff' : isCurrent ? 'var(--gold)' : 'var(--muted)' }}>
                {(reached || (isFinal && done)) ? '✓' : (isCurrent ? '•' : '○')}
              </div>
              <div className="text-[9.5px] text-center" style={{ color: isCurrent ? 'var(--navy)' : 'var(--muted)', fontWeight: isCurrent ? 600 : 400 }}>{lbl}</div>
            </div>
            {i < labels.length - 1 && <div style={{ height: 1, flex: 1, background: i < curIdx || done ? 'var(--sage)' : 'var(--mist)', marginBottom: 14 }} />}
          </React.Fragment>
        );
      })}
    </div>
  );
}

function ApplicationDetail({ row, detail, timeline, detailLoading, note, setNote, actionErr, actionBusy, onClose, onApprove, onChanges, onReject }) {
  const reviews = (detail && detail.reviews) || [];
  const attachments = (detail && detail.attachments) || [];
  const fv = (detail && detail.field_values) || {};
  const canAct = detail && detail.state === 'in_review';

  return (
    <div className="flex flex-col h-full">
      <div className="hair-b p-5 sticky top-0 bg-[var(--paper)] z-10">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <MonoChip tone="navy">{String(row.id).slice(0, 8).toUpperCase()}</MonoChip>
              <StatusPill status={APP_STATE_LABEL[row.state] || row.state} />
              {row.requires_accounts_approval && <span className="text-[10px] px-1.5 py-0.5 rounded-full font-medium" style={{ background: 'rgba(184,137,58,0.12)', color: 'var(--gold)' }}>Money-related</span>}
            </div>
            <h2 className="font-serif text-[22px] leading-tight text-[var(--navy)]" style={{ fontWeight: 500 }}>{row.template_name || 'Application'}</h2>
            <div className="mt-1.5 text-[12px] text-[var(--muted)]">
              {row.student_name || 'Student'} · submitted <span className="font-mono">{new Date(row.created_at).toLocaleString()}</span>
            </div>
          </div>
          <button onClick={onClose} className="w-8 h-8 rounded-sm hover:bg-[var(--mist)]/40 flex items-center justify-center"><Icon name="x" size={16} /></button>
        </div>
        {detail && <div className="mt-4"><ApplicationStepper detail={detail} /></div>}
      </div>

      <div className="p-5 flex-1 space-y-5 overflow-y-auto">
        {detailLoading && (
          <div className="space-y-3 animate-pulse">
            <div className="h-4 bg-[var(--mist)] rounded-sm w-full" />
            <div className="h-4 bg-[var(--mist)] rounded-sm w-4/5" />
            <div className="h-4 bg-[var(--mist)] rounded-sm w-3/5" />
          </div>
        )}

        {!detailLoading && detail && (
          <>
            <section>
              <SectionLabel>Letter</SectionLabel>
              {detail.letter_body
                ? <p className="text-[13.5px] text-[var(--ink)] leading-relaxed whitespace-pre-wrap" style={{ fontFamily: 'var(--font-serif)' }}>{detail.letter_body}</p>
                : <span className="text-[var(--muted)] italic text-[13px]">No letter drafted.</span>}
            </section>

            {Object.keys(fv).length > 0 && (
              <section>
                <SectionLabel>Details</SectionLabel>
                <div className="hair border rounded-sm divide-y" style={{ borderColor: 'var(--mist)' }}>
                  {Object.entries(fv).map(([k, v]) => (
                    <div key={k} className="px-3 py-2 flex gap-3 text-[12.5px]">
                      <span className="text-[var(--muted)] w-36 shrink-0">{k.replace(/_/g, ' ')}</span>
                      <span className="text-[var(--ink)]">{String(v)}</span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            {attachments.length > 0 && (
              <section>
                <SectionLabel>Attachments ({attachments.length})</SectionLabel>
                <div className="flex gap-2 flex-wrap">
                  {attachments.map(a => (
                    <div key={a.id} className="hair border rounded-sm p-2 flex items-center gap-2 text-[12px]">
                      <div className="w-8 h-8 rounded-sm flex items-center justify-center" style={{ background: '#EEEBE2' }}>
                        <Icon name={a.content_type && a.content_type.includes('pdf') ? 'file-text' : 'image'} size={14} />
                      </div>
                      <span className="font-mono text-[11px] text-[var(--graphite)]">{a.original_filename}</span>
                    </div>
                  ))}
                </div>
              </section>
            )}

            <section>
              <SectionLabel>Timeline</SectionLabel>
              {(!timeline || timeline.entries.length === 0)
                ? <EmptyState icon="clock" title="No history yet" body="No decisions recorded." />
                : (
                  <ol className="relative pl-6 space-y-4">
                    <span className="absolute left-[9px] top-2 bottom-2 w-px bg-[var(--mist)]" />
                    {timeline.entries.map((e, i) => (
                      <li key={i} className="relative">
                        <span className="absolute -left-[24px] top-0 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-mono" style={{ background: 'var(--sage)', color: 'white' }}>{i + 1}</span>
                        <div className="text-[13px] text-[var(--ink)] font-medium">{e.note || e.event}{e.actor_role ? <span className="font-normal text-[var(--muted)]"> · {APP_STAGE_LABEL[e.actor_role] || e.actor_role}</span> : ''}</div>
                        <div className="text-[11px] text-[var(--muted)] font-mono">{new Date(e.timestamp).toLocaleString()}</div>
                      </li>
                    ))}
                  </ol>
                )}
            </section>
          </>
        )}
      </div>

      {actionErr && <div className="px-4 py-2 text-[12px]" style={{ background: 'rgba(232,49,42,0.08)', color: 'var(--red)' }}>{actionErr}</div>}

      {canAct ? (
        <div className="hair-t border-t p-4 sticky bottom-0 bg-[var(--paper)] space-y-2.5">
          <textarea value={note} onChange={e => setNote(e.target.value)} rows={2}
            placeholder="Optional note to the student (required context for changes/reject)…"
            className="w-full hair border rounded-sm px-3 py-2 text-[12.5px] resize-none bg-[var(--paper)]" />
          <div className="flex flex-wrap items-center gap-2">
            <PrimaryButton size="sm" icon="check" mode="sage" disabled={actionBusy} onClick={onApprove}>Approve</PrimaryButton>
            <GhostButton size="sm" icon="rotate-ccw" disabled={actionBusy} onClick={onChanges}>Request changes</GhostButton>
            <GhostButton size="sm" icon="x" danger disabled={actionBusy} onClick={onReject}>Reject</GhostButton>
          </div>
        </div>
      ) : (
        <div className="hair-t border-t p-4 sticky bottom-0 bg-[var(--paper)] text-[12px] text-[var(--muted)]">
          This application is not awaiting a decision at your stage.
        </div>
      )}
    </div>
  );
}

Object.assign(window, { UniApplications });
