// University Complaints — moderation queue + slide-in detail (live API)
var { useState, useEffect, useCallback, useRef, useMemo } = React;
const STATE_LABEL = {
  draft:'Draft', moderation_queue:'Under Review', routed:'Submitted',
  subject_notified:'Under Review', subject_responded:'Under Review',
  under_review:'Under Review', resolved:'Resolved', dismissed:'Rejected',
  withdrawn:'Withdrawn', spam_rejected:'Rejected',
};

function _filingToCard(f) {
  const tpl = f.template || {};
  return {
    _raw: f,
    id: f.filing_number || f.id.slice(0, 12),
    fullId: f.id,
    title: f.body
      ? f.body.split('\n')[0].slice(0, 80) || tpl.name || 'Untitled'
      : tpl.name || 'Untitled',
    body: f.body || '',
    category: tpl.name || f.category,
    templateKey: tpl.key || '',
    anonymous: tpl.anonymity_mode === 'anonymous',
    status: STATE_LABEL[f.state] || f.state,
    state: f.state,
    severity: Math.min(3, Math.max(1, (f.escalation_level || 0) + 1)),
    level: f.escalation_level || 0,
    routing: f.escalation_level >= 2 ? ['Dean', 'VC Office'] : f.escalation_level >= 1 ? ['Dept Head', 'Dean'] : ['Dept Head'],
    submitted: new Date(f.created_at).toLocaleString(),
    lastAction: new Date(f.updated_at).toLocaleDateString(),
    submittedBy: f.anonymous ? null : (f.subject_descriptor || null),
    dept: f.field_values?.department || '',
    batch: f.field_values?.batch || '',
    notes: f.field_values?.admin_note || '',
    evidence: [],
    timeline: [],
    patternHint: null,
    reviews: f.reviews || [],
    attachments: f.attachments || [],
  };
}

function UniComplaints({ onGo }) {
  const [filings, setFilings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadErr, setLoadErr] = useState('');
  const [selected, setSelected] = useState(null);
  const [detailFiling, setDetailFiling] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [filters, setFilters] = useState({
    status: 'All',
    categories: new Set(),
    severity: new Set(),
    anonymous: 'All',
    level: new Set(),
  });
  const [confirm, setConfirm] = useState(null);
  const [actionErr, setActionErr] = useState('');
  const [actionBusy, setActionBusy] = useState(false);

  const STATUS_OPTIONS = ['All','Draft','Submitted','Under Review','Resolved','Rejected'];

  function loadFilings() {
    setLoading(true); setLoadErr('');
    AnchorAPI.apiGet('/v1/admin/filings?page=1&page_size=50')
      .then(data => { setFilings(Array.isArray(data) ? data.map(_filingToCard) : []); setLoading(false); })
      .catch(err => { setLoadErr(err.message || 'Could not load complaints.'); setLoading(false); });
  }

  useEffect(() => { loadFilings(); }, []);

  function openDetail(card) {
    setSelected(card);
    setDetailFiling(null);
    setDetailLoading(true);
    setActionErr('');
    AnchorAPI.apiGet(`/v1/admin/filings/${card.fullId}`)
      .then(f => { setDetailFiling(f); setDetailLoading(false); })
      .catch(() => { setDetailLoading(false); });
  }

  async function doAction(action) {
    if (!selected) return;
    setActionBusy(true); setActionErr('');
    try {
      await AnchorAPI.apiPostAuth(`/v1/admin/filings/${selected.fullId}/review`, { action });
      setSelected(null);
      loadFilings();
    } catch (err) {
      setActionErr(err.message || 'Action failed.');
    } finally { setActionBusy(false); }
  }

  const rows = useMemo(() => filings.filter(c => {
    if (filters.status !== 'All' && c.status !== filters.status) return false;
    if (filters.categories.size && !filters.categories.has(c.category)) return false;
    if (filters.severity.size && !filters.severity.has(c.severity)) return false;
    if (filters.anonymous === 'Yes' && !c.anonymous) return false;
    if (filters.anonymous === 'No' && c.anonymous) return false;
    if (filters.level.size && !filters.level.has(c.level)) return false;
    return true;
  }), [filings, filters]);

  const allCategories = useMemo(() => [...new Set(filings.map(f => f.category))], [filings]);

  const toggleSet = (key, val) => setFilters(f => {
    const s = new Set(f[key]);
    s.has(val) ? s.delete(val) : s.add(val);
    return { ...f, [key]: s };
  });

  return (
    <>
      <PageHeader
        title="Complaints"
        bn="অভিযোগসমূহ"
        description="Moderate the complaint queue. Select a case to open its detail, action it, or escalate. Every status change is audit-logged."
        actions={
          <>
            <GhostButton icon="refresh-cw" size="sm" onClick={loadFilings}>Refresh</GhostButton>
            <GhostButton icon="download" size="sm">Export</GhostButton>
          </>
        }
      />

      {loadErr && (
        <div className="mb-4 px-3 py-2 rounded-sm text-[12.5px]" style={{ background:'rgba(232,49,42,0.08)', color:'var(--red)', border:'1px solid rgba(232,49,42,0.2)' }}>
          {loadErr} — <button className="underline" onClick={loadFilings}>Retry</button>
        </div>
      )}

      <div className="grid gap-5" style={{ gridTemplateColumns: '240px 1fr' }}>
        {/* Filter rail */}
        <aside className="space-y-5">
          <FilterGroup label="Status">
            {STATUS_OPTIONS.map(s => (
              <label key={s} className="flex items-center gap-2 text-[13px] py-1 cursor-pointer">
                <input type="radio" checked={filters.status===s} onChange={()=>setFilters(f=>({...f, status:s}))} className="accent-[var(--sage)]" />
                <span className={filters.status===s?'text-[var(--ink)] font-medium':'text-[var(--graphite)]'}>{s}</span>
                <span className="ml-auto font-mono text-[10px] text-[var(--muted)]">
                  {s==='All' ? filings.length : filings.filter(c=>c.status===s).length}
                </span>
              </label>
            ))}
          </FilterGroup>

          {allCategories.length > 0 && (
            <FilterGroup label="Category">
              {allCategories.map(c => (
                <label key={c} className="flex items-center gap-2 text-[13px] py-1 cursor-pointer">
                  <input type="checkbox" checked={filters.categories.has(c)} onChange={()=>toggleSet('categories', c)} className="accent-[var(--sage)]" />
                  <span className="text-[var(--graphite)]">{c}</span>
                </label>
              ))}
            </FilterGroup>
          )}

          <FilterGroup label="Severity">
            {[1,2,3].map(s => (
              <label key={s} className="flex items-center gap-2 text-[13px] py-1 cursor-pointer">
                <input type="checkbox" checked={filters.severity.has(s)} onChange={()=>toggleSet('severity', s)} className="accent-[var(--sage)]" />
                <SeverityDots severity={s} />
                <span className="text-[var(--graphite)]">Rank {s}</span>
              </label>
            ))}
          </FilterGroup>

          <FilterGroup label="Anonymous">
            <div className="flex hair border rounded-sm overflow-hidden text-[12px]">
              {['All','Yes','No'].map(v => (
                <button key={v} onClick={()=>setFilters(f=>({...f, anonymous:v}))}
                  className={`flex-1 py-1.5 ${filters.anonymous===v?'bg-[var(--sage)] text-white':'text-[var(--graphite)] hover:bg-[var(--mist)]/40'}`}>
                  {v}
                </button>
              ))}
            </div>
          </FilterGroup>

          <button onClick={()=>setFilters({ status:'All', categories:new Set(), severity:new Set(), anonymous:'All', level:new Set() })}
            className="text-[12px] text-[var(--muted)] hover:text-[var(--ink)]">Clear all filters</button>
        </aside>

        {/* Result list */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <div className="text-[13px] text-[var(--graphite)]">
              {loading
                ? <span className="text-[var(--muted)]">Loading…</span>
                : <><span className="font-mono text-[var(--ink)]">{rows.length}</span> cases · sorted by most recent action</>
              }
            </div>
          </div>

          {loading && (
            <div className="space-y-2.5">
              {[1,2,3].map(i => (
                <div key={i} className="bg-[var(--paper)] hair border rounded-sm p-4 animate-pulse">
                  <div className="h-4 bg-[var(--mist)] rounded-sm w-1/3 mb-2" />
                  <div className="h-3 bg-[var(--mist)] rounded-sm w-2/3" />
                </div>
              ))}
            </div>
          )}

          {!loading && (
            <div className="space-y-2.5">
              {rows.map(c => (
                <ComplaintCard key={c.fullId} c={c} onClick={()=>openDetail(c)} active={selected?.fullId===c.fullId} />
              ))}
              {rows.length===0 && (
                <Card><EmptyState icon="inbox" title="No matching complaints" body={loadErr ? 'Backend error — check server.' : 'No filings found. Try clearing the filters.'} /></Card>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Slide-over */}
      <SlideOver open={!!selected} onClose={()=>setSelected(null)} width={620}>
        {selected && (
          <ComplaintDetail
            c={selected}
            detail={detailFiling}
            detailLoading={detailLoading}
            actionErr={actionErr}
            actionBusy={actionBusy}
            onClose={()=>setSelected(null)}
            onEscalate={()=>setConfirm('escalate')}
            onResolve={()=>setConfirm('resolve')}
            onMarkUnderReview={()=>doAction('mark_under_review')}
            onDismiss={()=>doAction('dismiss')}
          />
        )}
      </SlideOver>

      <ConfirmModal
        open={confirm==='escalate'} onClose={()=>setConfirm(null)} onConfirm={()=>{ setConfirm(null); doAction('escalate'); }}
        title="Escalate this complaint?"
        body="Escalation will route the case to the next authority level and notify the submitter."
        confirmWord="ESCALATE" confirmLabel="Escalate" tone="red"
      />
      <ConfirmModal
        open={confirm==='resolve'} onClose={()=>setConfirm(null)} onConfirm={()=>{ setConfirm(null); doAction('resolve'); }}
        title="Mark this complaint as resolved?"
        body="The submitter will be notified that the case is resolved. They can re-open it within 14 days."
        confirmWord="RESOLVE" confirmLabel="Resolve" tone="sage"
      />
    </>
  );
}

function FilterGroup({ label, children }) {
  return (
    <div>
      <div className="smallcaps text-[var(--muted)] mb-1.5">{label}</div>
      <div className="flex flex-col">{children}</div>
    </div>
  );
}

function ComplaintCard({ c, onClick, active }) {
  return (
    <button onClick={onClick}
      className={`w-full text-left bg-[var(--paper)] hair border rounded-sm p-4 hover:bg-[var(--mist)]/15 transition relative ${active?'shadow-md':''} ${StatusEdgeClass(c.status)}`}
      style={ active ? { boxShadow:'inset 3px 0 0 var(--sage), 0 0 0 1px var(--sage)' } : undefined }>
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 rounded-sm flex items-center justify-center shrink-0" style={{ background:'var(--mist)' }}>
          <Icon name="file-text" size={16} style={{ color:'var(--graphite)' }} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2 mb-1">
            <MonoChip>{c.id}</MonoChip>
            <span className="smallcaps text-[var(--muted)]">{c.category}</span>
            <SeverityDots severity={c.severity} />
            {c.anonymous && <AnonymityBadge />}
            <span className="ml-auto text-[11px] text-[var(--muted)] font-mono">{c.lastAction}</span>
          </div>
          <div className="text-[14px] text-[var(--ink)] font-medium leading-snug" style={{ textWrap:'pretty' }}>{c.title}</div>
          <div className="mt-2 flex items-center gap-3 text-[11.5px] text-[var(--muted)]">
            <span className="inline-flex items-center gap-1"><Icon name="user" size={12} /> {c.anonymous ? '— anonymous —' : (c.submittedBy || 'student')}</span>
            <span>·</span>
            <span className="inline-flex items-center gap-1"><Icon name="route" size={12} /> {c.routing.join(' → ')}</span>
            <span>·</span>
            <span className="inline-flex items-center gap-1"><Icon name="clock" size={12} /> {c.submitted.split(',')[0]}</span>
          </div>
        </div>
        <StatusPill status={c.status} />
      </div>
    </button>
  );
}

function ComplaintDetail({ c, detail, detailLoading, actionErr, actionBusy, onClose, onEscalate, onResolve, onMarkUnderReview, onDismiss }) {
  const [tab, setTab] = useState('overview');

  const reviews = detail?.reviews || [];
  const attachments = detail?.attachments || [];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="hair-b p-5 sticky top-0 bg-[var(--paper)] z-10">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2 mb-2">
              <MonoChip tone="navy">{c.id}</MonoChip>
              <StatusPill status={c.status} />
              <SeverityDots severity={c.severity} />
              {c.anonymous && <AnonymityBadge />}
            </div>
            <h2 className="font-serif text-[22px] leading-tight text-[var(--navy)]" style={{fontWeight:500, textWrap:'pretty'}}>{c.title}</h2>
            <div className="mt-1.5 text-[12px] text-[var(--muted)]">
              {c.anonymous ? '— anonymous submitter —' : (c.submittedBy || 'student')}
              {c.dept ? ` · ${c.dept}` : ''}
              {c.batch ? ` · ${c.batch}` : ''}
              {' · submitted '}<span className="font-mono">{c.submitted}</span>
            </div>
          </div>
          <button onClick={onClose} className="w-8 h-8 rounded-sm hover:bg-[var(--mist)]/40 flex items-center justify-center">
            <Icon name="x" size={16} />
          </button>
        </div>
        {/* Tabs */}
        <div className="mt-4 flex items-center gap-1 -mx-1">
          {['overview','timeline','evidence','routing','notes'].map(t => (
            <button key={t} onClick={()=>setTab(t)} className={`px-3 py-1.5 text-[12.5px] rounded-sm ${tab===t?'bg-[var(--sage-tint)] text-[var(--sage)] font-medium':'text-[var(--muted)] hover:bg-[var(--mist)]/40'}`}>
              {{overview:'Overview', timeline:'Timeline', evidence:'Evidence', routing:'Routing', notes:'Reviews'}[t]}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div className="p-5 flex-1 space-y-5 overflow-y-auto">
        {detailLoading && (
          <div className="space-y-3 animate-pulse">
            <div className="h-4 bg-[var(--mist)] rounded-sm w-full" />
            <div className="h-4 bg-[var(--mist)] rounded-sm w-4/5" />
            <div className="h-4 bg-[var(--mist)] rounded-sm w-3/5" />
          </div>
        )}

        {!detailLoading && tab==='overview' && (
          <>
            {c.anonymous && (
              <AuditNote tone="red" icon="shield-alert">
                This case has Rank-{c.severity} anonymity protection. Identity is not visible without formal de-anonymization through Super Admin.
              </AuditNote>
            )}
            <section>
              <SectionLabel>Complaint body</SectionLabel>
              <p className="text-[13.5px] text-[var(--ink)] leading-relaxed" style={{ textWrap:'pretty' }}>
                {(detail?.body || c.body) || <span className="text-[var(--muted)] italic">No body text — submitter left blank or draft.</span>}
              </p>
            </section>
            {attachments.length > 0 && (
              <section>
                <SectionLabel>Evidence</SectionLabel>
                <div className="flex gap-2 flex-wrap">
                  {attachments.map(e => (
                    <div key={e.id} className="hair border rounded-sm p-2 flex items-center gap-2 text-[12px]">
                      <div className="w-8 h-8 rounded-sm flex items-center justify-center" style={{ background:'#EEEBE2' }}>
                        <Icon name={e.content_type?.includes('pdf')?'file-text':'image'} size={14} />
                      </div>
                      <span className="font-mono text-[11px] text-[var(--graphite)]">{e.original_filename}</span>
                    </div>
                  ))}
                </div>
              </section>
            )}
          </>
        )}

        {!detailLoading && tab==='timeline' && (
          <div>
            <SectionLabel>Case timeline</SectionLabel>
            {reviews.length === 0 && <EmptyState icon="clock" title="No actions yet" body="No admin review actions have been taken on this filing." />}
            <ol className="relative pl-6 space-y-4">
              <span className="absolute left-[9px] top-2 bottom-2 w-px bg-[var(--mist)]" />
              {reviews.map((r, i) => (
                <li key={r.id || i} className="relative">
                  <span className="absolute -left-[24px] top-0 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-mono"
                    style={{ background:'var(--sage)', color:'white' }}>{i+1}</span>
                  <div className="text-[13px] text-[var(--ink)] font-medium">{r.action}</div>
                  <div className="text-[11px] text-[var(--muted)] font-mono">{r.reviewer_role} · {new Date(r.reviewed_at).toLocaleString()}</div>
                  {r.public_note && <div className="text-[12.5px] text-[var(--graphite)] mt-1">{r.public_note}</div>}
                </li>
              ))}
            </ol>
          </div>
        )}

        {!detailLoading && tab==='evidence' && (
          <div>
            <SectionLabel>All evidence ({attachments.length})</SectionLabel>
            {attachments.length>0 ? (
              <div className="grid grid-cols-2 gap-3">
                {attachments.map(e => (
                  <div key={e.id} className="hair border rounded-sm p-3">
                    <div className="aspect-video rounded-sm mb-2 dot-grid" style={{ background:'#EEEBE2' }} />
                    <div className="font-mono text-[11px] text-[var(--graphite)]">{e.original_filename}</div>
                    <div className="text-[10px] text-[var(--muted)]">{e.content_type}</div>
                  </div>
                ))}
              </div>
            ) : <EmptyState icon="image-off" title="No evidence attached" body="Submitter did not attach photos, documents, or audio." />}
          </div>
        )}

        {!detailLoading && tab==='routing' && (
          <div>
            <SectionLabel>Routing chain</SectionLabel>
            <ol className="relative pl-6">
              <span className="absolute left-[9px] top-2 bottom-2 w-px bg-[var(--mist)]" />
              {['Submitted by student', 'Dept Head', ...(c.level>=1?['Dean']:[]), ...(c.level>=2?['VC Office']:[])].map((step, i) => {
                const reached = i <= c.routing.length;
                return (
                  <li key={i} className="relative pb-5 last:pb-0">
                    <span className="absolute -left-[24px] top-0 w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-mono"
                      style={{ background: reached ? 'var(--sage)' : 'var(--mist)', color: reached ? 'white' : 'var(--muted)' }}>{i+1}</span>
                    <div className="text-[13px] text-[var(--ink)] font-medium">{step}</div>
                  </li>
                );
              })}
            </ol>
            <AuditNote tone="navy" icon="route" className="mt-3">
              Escalation level: <span className="font-mono">{c.level}</span>
            </AuditNote>
          </div>
        )}

        {!detailLoading && tab==='notes' && (
          <div>
            <SectionLabel>Admin review history</SectionLabel>
            {reviews.length === 0
              ? <EmptyState icon="clipboard" title="No reviews yet" body="No admin review actions recorded." />
              : (
                <div className="hair border rounded-sm divide-y" style={{ borderColor:'var(--mist)' }}>
                  {reviews.map((r, i) => (
                    <div key={r.id || i} className="p-3">
                      <div className="flex items-center gap-2 mb-1">
                        <MonoChip>{r.action}</MonoChip>
                        <span className="text-[11px] text-[var(--muted)]">{r.reviewer_role}</span>
                        <span className="ml-auto text-[10px] text-[var(--muted)] font-mono">{new Date(r.reviewed_at).toLocaleString()}</span>
                      </div>
                      {r.public_note && <p className="text-[12.5px] text-[var(--ink)]">{r.public_note}</p>}
                      {r.internal_note && <p className="text-[11.5px] text-[var(--muted)] mt-0.5 italic">{r.internal_note}</p>}
                    </div>
                  ))}
                </div>
              )
            }
          </div>
        )}
      </div>

      {/* Action bar */}
      {actionErr && (
        <div className="px-4 py-2 text-[12px]" style={{ background:'rgba(232,49,42,0.08)', color:'var(--red)' }}>{actionErr}</div>
      )}
      <div className="hair-t border-t p-4 sticky bottom-0 bg-[var(--paper)] flex flex-wrap items-center gap-2">
        <GhostButton size="sm" icon="eye" disabled={actionBusy} onClick={onMarkUnderReview}>Mark Under Review</GhostButton>
        <PrimaryButton size="sm" icon="check" mode="sage" disabled={actionBusy} onClick={onResolve}>Resolve</PrimaryButton>
        <PrimaryButton size="sm" icon="arrow-up-right" mode="red" disabled={actionBusy} onClick={onEscalate}>Escalate</PrimaryButton>
        <GhostButton size="sm" icon="x" danger disabled={actionBusy} onClick={onDismiss}>Reject</GhostButton>
      </div>
    </div>
  );
}

Object.assign(window, { UniComplaints });
