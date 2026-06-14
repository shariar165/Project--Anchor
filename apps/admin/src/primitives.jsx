// Shared UI primitives for Anchor Admin
var { useState, useEffect, useMemo, useRef, useCallback } = React;

// Dark mode hook — persists to localStorage and toggles class on <html>
function useDark() {
  const [dark, setDark] = useState(() => {
    try {
      const stored = localStorage.getItem('anchor:dark');
      if (stored !== null) return stored === '1';
      return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    } catch (e) { return false; }
  });
  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
    try { localStorage.setItem('anchor:dark', dark ? '1' : '0'); } catch (e) {}
  }, [dark]);
  return [dark, setDark];
}

// Lucide icon wrapper. We use a single component that emits an <i data-lucide=...> and re-renders on mount.
function Icon({ name, size = 16, className = '', strokeWidth = 1.75, style }) {
  const ref = useRef(null);
  useEffect(() => {
    if (ref.current && window.lucide) {
      ref.current.innerHTML = '';
      const i = document.createElement('i');
      i.setAttribute('data-lucide', name);
      ref.current.appendChild(i);
      window.lucide.createIcons({ attrs: { width: size, height: size, 'stroke-width': strokeWidth } });
    }
  }, [name, size, strokeWidth]);
  return <span ref={ref} className={`inline-flex items-center justify-center ${className}`} style={{ width: size, height: size, ...style }} aria-hidden="true" />;
}

// Status pill
const STATUS_STYLES = {
  'Submitted':    { bg: '#EEEBE2', fg: '#3A4754', dot: '#6B7785' },
  'Under Review': { bg: '#F2E8D2', fg: '#7E5A19', dot: '#B8893A' },
  'Escalated':    { bg: '#F6E5E2', fg: '#A2362B', dot: '#E8312A' },
  'Resolved':     { bg: '#DDE8E1', fg: '#345249', dot: '#4A6B5C' },
  'Rejected':     { bg: '#E6E3DA', fg: '#52555C', dot: '#6B7785' },
  'Active':       { bg: '#F6E5E2', fg: '#A2362B', dot: '#E8312A' },
  'False Alarm':  { bg: '#EEEBE2', fg: '#3A4754', dot: '#6B7785' },
  'Pilot':        { bg: '#F2E8D2', fg: '#7E5A19', dot: '#B8893A' },
  'Suspended':    { bg: '#E6E3DA', fg: '#52555C', dot: '#6B7785' },
  'healthy':      { bg: '#DDE8E1', fg: '#345249', dot: '#4A6B5C' },
  'degraded':     { bg: '#F2E8D2', fg: '#7E5A19', dot: '#B8893A' },
  'down':         { bg: '#F6E5E2', fg: '#A2362B', dot: '#E8312A' },
  'Pending review':{ bg: '#F2E8D2', fg: '#7E5A19', dot: '#B8893A' },
  'Awaiting 2nd approval':{ bg: '#F6E5E2', fg: '#A2362B', dot: '#E8312A' },
  'User Safe':     { bg: '#DDE8E1', fg: '#345249', dot: '#4A6B5C' },
  'Closed':        { bg: '#E6E3DA', fg: '#52555C', dot: '#6B7785' },
};
function StatusPill({ status, dot=true, className='' }) {
  const s = STATUS_STYLES[status] || STATUS_STYLES['Submitted'];
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium tracking-wide ${className}`}
      style={{ background: s.bg, color: s.fg }}>
      {dot && <span className="w-1.5 h-1.5 rounded-full" style={{ background: s.dot }} />}
      <span className="whitespace-nowrap">{status}</span>
    </span>
  );
}

function StatusEdgeClass(status) {
  return {
    'Submitted':'edge-graphite','Under Review':'edge-gold','Escalated':'edge-red',
    'Resolved':'edge-sage','Rejected':'edge-mist','Active':'edge-red','False Alarm':'edge-mist',
  }[status] || 'edge-mist';
}

function SeverityDots({ severity=1, className='' }) {
  // returns dots: 1=info, 2=moderate, 3=serious
  const color = severity === 3 ? '#E8312A' : severity === 2 ? '#B8893A' : '#6B7785';
  return (
    <span className={`inline-flex items-center gap-0.5 ${className}`} title={`Rank ${severity}`}>
      {[1,2,3].map(i => (
        <span key={i} className="w-1.5 h-1.5 rounded-full" style={{ background: i<=severity ? color : '#E5E0D6' }} />
      ))}
    </span>
  );
}

function AnonymityBadge({ className='' }) {
  return (
    <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded-sm smallcaps ${className}`}
      style={{ background:'#13294B', color:'#F7F3EE', fontSize:'9.5px', letterSpacing:'0.16em' }}>
      <Icon name="eye-off" size={10} />
      <span>Anonymous</span>
    </span>
  );
}

function KpiCard({ label, value, delta, deltaTone='neutral', subtle, mono=true, accent='sage' }) {
  const accentColor = accent === 'ember' ? 'var(--ember)' : accent === 'gold' ? 'var(--gold)' : accent === 'navy' ? 'var(--navy)' : 'var(--sage)';
  const deltaColors = { up:'#345249', down:'#A2362B', neutral:'#6B7785' };
  return (
    <div className="bg-[var(--paper)] hair border rounded-sm p-4 flex flex-col gap-2 relative">
      <div className="flex items-center justify-between">
        <span className="smallcaps text-[var(--muted)]">{label}</span>
        <span className="w-1 h-3" style={{ background: accentColor }} />
      </div>
      <div className={`${mono?'font-mono':''} text-[28px] leading-none text-[var(--ink)] tabular-nums`}>{value}</div>
      <div className="flex items-center gap-2 text-[12px]">
        {delta && (
          <span className="inline-flex items-center gap-1" style={{ color: deltaColors[deltaTone] }}>
            <Icon name={deltaTone==='up'?'arrow-up-right':deltaTone==='down'?'arrow-down-right':'minus'} size={12} />
            <span className="font-medium">{delta}</span>
          </span>
        )}
        {subtle && <span className="text-[var(--muted)]">{subtle}</span>}
      </div>
    </div>
  );
}

function SectionLabel({ children, right, className='' }) {
  return (
    <div className={`flex items-end justify-between gap-2 mb-3 ${className}`}>
      <span className="smallcaps text-[var(--muted)]">{children}</span>
      {right && <div className="flex items-center gap-2">{right}</div>}
    </div>
  );
}

function Card({ children, className='', noPad=false }) {
  return <div className={`bg-[var(--paper)] hair border rounded-sm ${noPad?'':'p-5'} ${className}`}>{children}</div>;
}

function PageHeader({ title, bn, description, actions, accent='sage' }) {
  return (
    <div className="flex items-start justify-between gap-6 mb-6">
      <div className="min-w-0">
        <div className="flex items-baseline gap-3 flex-wrap">
          <h1 className="font-serif text-[34px] leading-[1.1] tracking-tight text-[var(--navy)]" style={{ fontWeight: 500 }}>
            {title}
          </h1>
          {bn && <span className="font-bn text-[18px] text-[var(--muted)]" style={{fontWeight:500, lineHeight:1.4}}>{bn}</span>}
        </div>
        {description && <p className="mt-2 text-[14px] text-[var(--graphite)] max-w-[68ch]">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2 shrink-0 pt-1">{actions}</div>}
    </div>
  );
}

function PrimaryButton({ children, onClick, mode='sage', icon, className='', size='md', as='button', ...rest }) {
  const bg = mode === 'ember' ? 'var(--ember)' : mode === 'navy' ? 'var(--navy)' : mode === 'red' ? 'var(--red)' : 'var(--sage)';
  const pad = size==='sm' ? 'px-3 py-1.5 text-[12px]' : 'px-4 py-2 text-[13px]';
  const Cmp = as;
  return (
    <Cmp onClick={onClick} className={`inline-flex items-center gap-2 ${pad} rounded-sm text-white font-medium hover:opacity-90 active:opacity-80 transition ${className}`} style={{ background: bg }} {...rest}>
      {icon && <Icon name={icon} size={14} />}
      <span>{children}</span>
    </Cmp>
  );
}

function GhostButton({ children, onClick, icon, className='', size='md', danger=false, ...rest }) {
  const pad = size==='sm' ? 'px-3 py-1.5 text-[12px]' : 'px-4 py-2 text-[13px]';
  const color = danger ? 'text-[var(--red)] border-[#F1D9D8] hover:bg-[#F6E5E2]' : 'text-[var(--navy)] hover:bg-[var(--mist)]/50';
  return (
    <button onClick={onClick} className={`inline-flex items-center gap-2 ${pad} rounded-sm border hair font-medium transition ${color} ${className}`} {...rest}>
      {icon && <Icon name={icon} size={14} />}
      <span>{children}</span>
    </button>
  );
}

// Audit log banner (contextual)
function AuditNote({ children, tone='gold', icon='shield-check' }) {
  const styles = {
    gold: { bg:'#FBF5E6', fg:'#7E5A19', bd:'#E8D5A1' },
    red:  { bg:'#FCEEEC', fg:'#A2362B', bd:'#F1C7C2' },
    navy: { bg:'#EDF1F7', fg:'#0B1D35', bd:'#C9D3E2' },
    sage: { bg:'#E8EFEA', fg:'#345249', bd:'#C7D6CD' },
  }[tone];
  return (
    <div className="flex items-start gap-2 px-3 py-2 rounded-sm border" style={{ background: styles.bg, color: styles.fg, borderColor: styles.bd }}>
      <Icon name={icon} size={14} className="mt-[1px]" />
      <p className="text-[12px] leading-snug">{children}</p>
    </div>
  );
}

// Generic data table
function DataTable({ columns, rows, onRowClick, dense=false, hoverable=true }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="text-left">
            {columns.map(c => (
              <th key={c.key} className={`smallcaps text-[var(--muted)] py-2 px-3 hair-b font-semibold whitespace-nowrap ${c.align==='right'?'text-right':''}`} style={{ width: c.width }}>
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} onClick={() => onRowClick && onRowClick(row)}
              className={`${hoverable?'hover:bg-[var(--mist)]/30':''} ${onRowClick?'cursor-pointer':''} hair-b transition`}>
              {columns.map(c => (
                <td key={c.key} className={`${dense?'py-2':'py-3'} px-3 align-middle ${c.align==='right'?'text-right':''}`}>
                  {c.render ? c.render(row) : row[c.key]}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Confirm modal that requires typing the action word
function ConfirmModal({ open, onClose, onConfirm, title, body, confirmWord='CONFIRM', tone='red', confirmLabel='Confirm' }) {
  const [val, setVal] = useState('');
  useEffect(() => { if (open) setVal(''); }, [open]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center fade-in" style={{ background:'rgba(11,29,53,0.35)' }} onClick={onClose}>
      <div className="bg-[var(--paper)] rounded-sm w-[440px] max-w-[92vw] border hair" onClick={e=>e.stopPropagation()}>
        <div className="p-5 hair-b">
          <h3 className="font-serif text-[20px] text-[var(--navy)]">{title}</h3>
        </div>
        <div className="p-5 space-y-3">
          <p className="text-[13px] text-[var(--graphite)] leading-relaxed">{body}</p>
          <AuditNote tone="red" icon="alert-triangle">This action is permanent and will be audit-logged.</AuditNote>
          <div>
            <label className="smallcaps text-[var(--muted)]">Type <span className="font-mono normal-case tracking-normal text-[var(--ink)]">{confirmWord}</span> to confirm</label>
            <input value={val} onChange={e=>setVal(e.target.value)} className="mt-2 w-full px-3 py-2 hair border rounded-sm font-mono text-[13px] bg-white" placeholder={confirmWord} />
          </div>
        </div>
        <div className="p-4 hair-t flex items-center justify-end gap-2">
          <GhostButton onClick={onClose}>Cancel</GhostButton>
          <PrimaryButton mode={tone==='red'?'red':'sage'} onClick={()=>{ if (val===confirmWord) { onConfirm(); onClose(); }}} icon="check">
            {confirmLabel}
          </PrimaryButton>
        </div>
      </div>
    </div>
  );
}

// SlideOver panel (right-aligned)
function SlideOver({ open, onClose, children, width=520 }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 flex justify-end fade-in" style={{ background:'rgba(11,29,53,0.18)' }} onClick={onClose}>
      <div className="bg-[var(--paper)] h-full hair-l border-l slide-in overflow-y-auto scrollbar-thin" style={{ width }} onClick={e=>e.stopPropagation()}>
        {children}
      </div>
    </div>
  );
}

// Vertical timeline stepper
function Timeline({ items }) {
  return (
    <ol className="relative pl-5">
      <span className="absolute left-[7px] top-1 bottom-1 w-px bg-[var(--mist)]" />
      {items.map((it, i) => (
        <li key={i} className="relative pb-3 last:pb-0">
          <span className="absolute -left-[18px] top-[5px] w-2.5 h-2.5 rounded-full" style={{ background: i===items.length-1?'var(--sage)':'var(--mist)', boxShadow:'0 0 0 3px var(--paper)' }} />
          <div className="text-[12px] text-[var(--muted)] font-mono">{it.t}</div>
          <div className="text-[13px] text-[var(--ink)]"><span className="font-medium">{it.who}</span> · {it.what}</div>
        </li>
      ))}
    </ol>
  );
}

// Empty state
function EmptyState({ title, body, icon='inbox', action }) {
  return (
    <div className="text-center py-12 px-6 flex flex-col items-center gap-3">
      <div className="w-12 h-12 rounded-full flex items-center justify-center bg-[var(--mist)]/50">
        <Icon name={icon} size={20} style={{ color: 'var(--graphite)' }} />
      </div>
      <h3 className="font-serif text-[20px] text-[var(--navy)]">{title}</h3>
      {body && <p className="text-[13px] text-[var(--graphite)] max-w-[44ch]">{body}</p>}
      {action}
    </div>
  );
}

// Small mono chip
function MonoChip({ children, className='', tone='mist' }) {
  const c = tone==='navy' ? 'bg-[var(--navy)] text-white' : tone==='sage' ? 'bg-[var(--sage-tint)] text-[var(--sage)]' : 'bg-[var(--mist)]/60 text-[var(--graphite)]';
  return <span className={`font-mono text-[11px] px-1.5 py-0.5 rounded-sm ${c} ${className}`}>{children}</span>;
}

// Tag
function Tag({ children, tone='mist', icon }) {
  const tones = {
    mist: { bg:'#EEEBE2', fg:'#3A4754' },
    sage: { bg:'#DDE8E1', fg:'#345249' },
    gold: { bg:'#F2E8D2', fg:'#7E5A19' },
    red:  { bg:'#F6E5E2', fg:'#A2362B' },
    navy: { bg:'#EDF1F7', fg:'#0B1D35' },
  }[tone] || { bg:'#EEEBE2', fg:'#3A4754' };
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-sm text-[11px] font-medium" style={{ background:tones.bg, color:tones.fg }}>
      {icon && <Icon name={icon} size={11} />}
      <span>{children}</span>
    </span>
  );
}

Object.assign(window, {
  Icon, StatusPill, StatusEdgeClass, SeverityDots, AnonymityBadge, KpiCard,
  SectionLabel, Card, PageHeader, PrimaryButton, GhostButton, AuditNote,
  DataTable, ConfirmModal, SlideOver, Timeline, EmptyState, MonoChip, Tag,
  useDark,
});
