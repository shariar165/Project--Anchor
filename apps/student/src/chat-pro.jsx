// chat-pro.jsx — Professional chat UI (ChatGPT/Claude style)
// Depends on: icons.jsx (Icon*), screens.jsx (renderMarkdown, AI_BASE), app.jsx (useApp)

const { useState, useEffect, useRef } = React;

const AI_BASE_PRO = window.ANCHOR_AI_URL || 'http://localhost:8000';

// ─── LocalStorage helpers ────────────────────────────────────────────────────

function loadConversations() {
  try {
    const raw = localStorage.getItem('anchor_conversations');
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

function saveConversations(convs) {
  const trimmed = convs.length > 50 ? convs.slice(convs.length - 50) : convs;
  try { localStorage.setItem('anchor_conversations', JSON.stringify(trimmed)); } catch {}
}

function createConversation(mode, lang) {
  const id = (typeof crypto !== 'undefined' && crypto.randomUUID)
    ? crypto.randomUUID()
    : `conv-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const now = Date.now();
  return { id, name: 'New conversation', messages: [], convId: null, mode, lang, created_at: now, updated_at: now };
}

function updateConversation(convs, id, patch) {
  return convs.map(c => c.id === id ? { ...c, ...patch, updated_at: Date.now() } : c);
}

function getConvName(messages) {
  const first = messages.find(m => m.role === 'user');
  if (!first || !first.text.trim()) return 'New conversation';
  const txt = first.text.trim().replace(/\s+/g, ' ');
  return txt.length > 40 ? txt.slice(0, 40) + '…' : txt;
}

function fmtTimestamp(ts) {
  const diff = Date.now() - ts;
  if (diff < 60000) return 'just now';
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  return new Date(ts).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
}

// ─── Conversation Drawer ─────────────────────────────────────────────────────

function DrawerConvItem({ conv, active, accent, accentBg, onSelect, onDelete }) {
  return (
    <div
      className={`cp-drawer-conv${active ? ' active' : ''}`}
      style={active ? { background: accentBg, borderLeft: `3px solid ${accent}` } : {}}
      onClick={onSelect}
    >
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 13.5, fontWeight: active ? 600 : 400, color: 'var(--ink)',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          fontFamily: 'var(--font-sans)',
        }}>
          {conv.name}
        </div>
        <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>
          {fmtTimestamp(conv.updated_at)}
        </div>
      </div>
      <button
        className="cp-drawer-delete"
        onClick={e => { e.stopPropagation(); onDelete(); }}
        title="Delete conversation"
      >
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
          <path d="M2 3.5h10M5.5 3.5V2.5h3v1M3 3.5l.75 7.5h6.5L11 3.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </button>
    </div>
  );
}

function ConversationDrawer({ conversations, activeId, visible, onClose, onSelect, onNew, onDelete, mode }) {
  const accent   = mode === 'campus' ? 'var(--sage)'              : 'var(--ember)';
  const accentBg = mode === 'campus' ? 'rgba(74,107,92,0.08)'    : 'rgba(196,69,54,0.07)';

  return (
    <>
      <div
        className="cp-drawer-overlay"
        style={{ opacity: visible ? 1 : 0, transition: 'opacity 280ms ease' }}
        onClick={onClose}
      />
      <div
        className="cp-drawer"
        style={{ transform: visible ? 'translateX(0)' : 'translateX(-100%)', transition: 'transform 280ms ease' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Drawer header */}
        <div style={{
          padding: '20px 16px 12px', borderBottom: '1px solid var(--mist)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        }}>
          <span style={{ fontFamily: 'var(--font-serif)', fontSize: 17, fontWeight: 500, color: 'var(--navy)' }}>
            Conversations
          </span>
          <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--muted)', padding: 4, lineHeight: 0 }}>
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <line x1="4" y1="4" x2="14" y2="14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
              <line x1="14" y1="4" x2="4" y2="14" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
            </svg>
          </button>
        </div>

        {/* New conversation */}
        <button
          className="cp-drawer-new"
          onClick={() => { onNew(); onClose(); }}
          style={{ color: accent }}
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ flexShrink: 0 }}>
            <line x1="7" y1="1.5" x2="7" y2="12.5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
            <line x1="1.5" y1="7" x2="12.5" y2="7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
          </svg>
          New conversation
        </button>

        {/* Conversation list */}
        <div style={{ flex: 1, overflowY: 'auto' }} className="no-scrollbar">
          {conversations.length === 0 ? (
            <div style={{ padding: '28px 16px', textAlign: 'center', color: 'var(--muted)', fontSize: 13 }}>
              No conversations yet
            </div>
          ) : (
            [...conversations].reverse().map(conv => (
              <DrawerConvItem
                key={conv.id}
                conv={conv}
                active={conv.id === activeId}
                accent={accent}
                accentBg={accentBg}
                onSelect={() => { onSelect(conv.id); onClose(); }}
                onDelete={() => onDelete(conv.id)}
              />
            ))
          )}
        </div>
      </div>
    </>
  );
}

// ─── Chat Header ─────────────────────────────────────────────────────────────

function ChatHeader({ convName, mode, onOpenDrawer, onNew }) {
  const accent = mode === 'campus' ? 'var(--sage)' : 'var(--ember)';
  return (
    <div className="cp-header">
      {/* Two-dot history icon */}
      <button className="cp-two-dot" onClick={onOpenDrawer} title="Conversation history" style={{ color: 'var(--navy)' }}>
        <svg width="22" height="14" viewBox="0 0 22 14" fill="none">
          <circle cx="5"  cy="7" r="4" fill="currentColor"/>
          <circle cx="17" cy="7" r="4" fill="currentColor"/>
        </svg>
      </button>

      {/* Conversation name */}
      <div style={{
        flex: 1, textAlign: 'center', fontFamily: 'var(--font-serif)',
        fontSize: 15, fontWeight: 500, color: 'var(--navy)',
        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        padding: '0 8px',
      }}>
        {convName}
      </div>

      {/* New chat button */}
      <button
        onClick={onNew}
        style={{
          background: 'none', border: 'none', cursor: 'pointer',
          color: accent, padding: 6, borderRadius: 8, lineHeight: 0,
        }}
        title="New conversation"
      >
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
          <rect x="2.5" y="2.5" width="15" height="15" rx="4" stroke="currentColor" strokeWidth="1.6"/>
          <line x1="10" y1="6" x2="10" y2="14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
          <line x1="6" y1="10" x2="14" y2="10" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
        </svg>
      </button>
    </div>
  );
}

// ─── Empty State ─────────────────────────────────────────────────────────────

const SUGGESTIONS = {
  campus: {
    EN: ['How do I file a hostel complaint?', 'Draft a leave application', 'What happens if I miss exams?', 'AC broken in my classroom — steps?'],
    BN: ['হোস্টেল অভিযোগ কীভাবে করবো?', 'ছুটির আবেদন তৈরি করো', 'পরীক্ষা মিস হলে কী হবে?', 'ক্লাসরুমে AC নষ্ট — কী করবো?'],
  },
  country: {
    EN: ['How do I file a GD at the police station?', 'What are my rights if arrested?', 'Find me a lawyer in Dhaka', 'What is the punishment for harassment?'],
    BN: ['থানায় জিডি কীভাবে করবো?', 'গ্রেপ্তারে আমার অধিকার কী?', 'ঢাকায় আইনজীবী খুঁজে দাও', 'হয়রানির শাস্তি কী?'],
  },
};

function EmptyState({ mode, lang, onSuggest }) {
  const accent = mode === 'campus' ? 'var(--sage)' : 'var(--ember)';
  const chips = SUGGESTIONS[mode]?.[lang] || SUGGESTIONS[mode]?.EN || [];
  const subtitle = mode === 'campus'
    ? (lang === 'BN' ? 'ক্যাম্পাস সমস্যায় সাহায্য করতে প্রস্তুত' : 'Complaints · Applications · Campus rights')
    : (lang === 'BN' ? 'আইনি সহায়তা · নিরাপত্তা · অধিকার' : 'Legal aid · Safety · Know your rights');

  return (
    <div className="cp-empty">
      <div style={{
        width: 56, height: 56, borderRadius: 18, background: 'var(--navy)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        marginBottom: 14, boxShadow: '0 6px 28px rgba(11,29,53,0.20)',
      }}>
        <span style={{ fontFamily: 'var(--font-serif)', fontStyle: 'italic', fontWeight: 500, fontSize: 28, color: 'var(--cream)', letterSpacing: '-0.02em' }}>A</span>
      </div>
      <div style={{ fontFamily: 'var(--font-serif)', fontSize: 22, fontWeight: 400, color: 'var(--navy)', marginBottom: 6 }}>
        Anchor AI
      </div>
      <div style={{ fontSize: 13, color: 'var(--muted)', marginBottom: 30, textAlign: 'center', maxWidth: 230, lineHeight: 1.55 }}>
        {subtitle}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, width: '100%' }}>
        {chips.map((s, i) => (
          <button
            key={i}
            className="cp-suggestion-chip"
            onClick={() => onSuggest(s)}
            style={{ borderColor: `${accent}30`, color: 'var(--ink-2)' }}
          >
            {s}
          </button>
        ))}
      </div>
    </div>
  );
}

// ─── Confidence Badge ─────────────────────────────────────────────────────────

function ConfBadge({ confidence }) {
  const pct = Math.round((confidence || 0) * 100);
  const cls = pct >= 70 ? 'cp-conf-green' : pct >= 50 ? 'cp-conf-amber' : 'cp-conf-red';
  return <span className={`cp-conf-badge ${cls}`}>{pct}%</span>;
}

// ─── Citations Panel ──────────────────────────────────────────────────────────

function CitationsPanel({ citations, open, onToggle }) {
  if (!citations || citations.length === 0) return null;
  return (
    <div className="cp-citations">
      <button className="cp-citations-toggle" onClick={onToggle}>
        <span>Sources ({citations.length})</span>
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style={{ transform: open ? 'rotate(180deg)' : 'none', transition: 'transform 200ms' }}>
          <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </button>
      {open && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
          {citations.map((c, i) => (
            <span key={i} className="cp-cite-chip" title={c.source === 'web' ? 'Web source' : 'Legal corpus'}>
              {c.title || c.id || `[${i + 1}]`}
              {c.source === 'web' && <span style={{ marginLeft: 3, opacity: 0.55, fontSize: 10 }}>↗</span>}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Lawyer Referral Card ─────────────────────────────────────────────────────

function LawyerReferralCard({ mode, onGo }) {
  const accent   = mode === 'campus' ? 'var(--sage)'           : 'var(--ember)';
  const accentBg = mode === 'campus' ? 'rgba(74,107,92,0.06)' : 'rgba(196,69,54,0.05)';
  const accentBd = mode === 'campus' ? 'rgba(74,107,92,0.22)' : 'rgba(196,69,54,0.22)';
  return (
    <div style={{
      marginTop: 12, padding: '11px 13px', borderRadius: 11,
      background: accentBg, border: `1px solid ${accentBd}`,
    }}>
      <div style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.5, marginBottom: 8 }}>
        For your specific situation, a verified lawyer can give you better guidance.
      </div>
      <button
        onClick={onGo}
        style={{
          padding: '6px 13px', borderRadius: 9, border: 'none', cursor: 'pointer',
          background: accent, color: '#fff',
          fontFamily: 'var(--font-sans)', fontWeight: 600, fontSize: 12, letterSpacing: '0.01em',
        }}
      >
        Find a lawyer →
      </button>
    </div>
  );
}

// ─── Error Bubble ─────────────────────────────────────────────────────────────

function ErrorBubble({ text, errorType, onRetry }) {
  const isServer = errorType === 'offline' || errorType === 'network';
  return (
    <div className="cp-error-bubble">
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8 }}>
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ flexShrink: 0, marginTop: 1 }}>
          <circle cx="8" cy="8" r="7" stroke="var(--ember)" strokeWidth="1.4"/>
          <line x1="8" y1="5" x2="8" y2="9" stroke="var(--ember)" strokeWidth="1.5" strokeLinecap="round"/>
          <circle cx="8" cy="11.5" r="0.8" fill="var(--ember)"/>
        </svg>
        <span style={{ fontSize: 13.5, color: 'var(--ink-2)', lineHeight: 1.55 }}>{text}</span>
      </div>
      {isServer && (
        <div style={{
          marginTop: 9, padding: '6px 10px', borderRadius: 8,
          background: 'rgba(0,0,0,0.04)', fontFamily: 'var(--font-mono)',
          fontSize: 11, color: 'var(--muted)',
        }}>
          uvicorn app.main:app --port 8000
        </div>
      )}
      {onRetry && (
        <button onClick={onRetry} style={{
          marginTop: 10, padding: '6px 14px', borderRadius: 10, border: 'none',
          background: 'var(--ember)', color: '#fff', cursor: 'pointer',
          fontFamily: 'var(--font-sans)', fontWeight: 600, fontSize: 12.5,
        }}>
          Try again
        </button>
      )}
    </div>
  );
}

// ─── Typing Indicator ─────────────────────────────────────────────────────────

function ProTypingIndicator() {
  return (
    <div className="cp-msg-ai">
      <div className="cp-typing">
        <div style={{ fontSize: 11, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--muted)', marginBottom: 7, fontFamily: 'var(--font-sans)' }}>
          Anchor AI
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
          <span className="cp-dot-1" style={{ fontSize: 8, color: 'var(--muted)' }}>●</span>
          <span className="cp-dot-2" style={{ fontSize: 8, color: 'var(--muted)' }}>●</span>
          <span className="cp-dot-3" style={{ fontSize: 8, color: 'var(--muted)' }}>●</span>
          <span style={{ fontSize: 12.5, color: 'var(--muted)', marginLeft: 3, fontFamily: 'var(--font-serif)', fontStyle: 'italic' }}>thinking</span>
        </div>
      </div>
    </div>
  );
}

// ─── Message Components ───────────────────────────────────────────────────────

function UserMessage({ msg }) {
  return (
    <div className="cp-msg-user">
      <div className="cp-bubble-user">{msg.text}</div>
      <div className="cp-timestamp" style={{ textAlign: 'right', marginTop: 4 }}>
        {fmtTimestamp(msg.timestamp)}
      </div>
    </div>
  );
}

function AIMessage({ msg, msgIndex, citationsOpen, onToggleCitations, mode, onGoLawyers, onRetry }) {
  const accent = mode === 'campus' ? 'var(--sage)' : 'var(--ember)';

  if (msg.error) {
    return (
      <div className="cp-msg-ai">
        <ErrorBubble text={msg.text} errorType={msg.errorType} onRetry={onRetry} />
        <div className="cp-timestamp" style={{ marginTop: 4 }}>{fmtTimestamp(msg.timestamp)}</div>
      </div>
    );
  }

  return (
    <div className="cp-msg-ai">
      <div className="cp-bubble-ai">
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <div style={{
            width: 22, height: 22, borderRadius: 999, background: 'var(--navy)', color: 'var(--cream)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: 'var(--font-serif)', fontStyle: 'italic', fontWeight: 500, fontSize: 11, flexShrink: 0,
          }}>A</div>
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: accent, fontFamily: 'var(--font-sans)' }}>
            Anchor AI
          </span>
          {msg.confidence != null && <ConfBadge confidence={msg.confidence} />}
        </div>

        {/* Answer */}
        <div style={{ fontSize: 14, lineHeight: 1.7, color: 'var(--ink-2)' }}>
          {renderMarkdown(msg.text, accent)}
        </div>

        {/* Citations */}
        <CitationsPanel
          citations={msg.citations}
          open={!!citationsOpen[msgIndex]}
          onToggle={() => onToggleCitations(msgIndex)}
        />

        {/* Lawyer referral */}
        {msg.lawyer_referral && (
          <LawyerReferralCard mode={mode} onGo={onGoLawyers} />
        )}

        {/* Exit ramp note */}
        {msg.exit_ramp && !msg.lawyer_referral && (
          <div style={{ marginTop: 10, fontSize: 12, color: 'var(--muted)', fontStyle: 'italic', fontFamily: 'var(--font-serif)' }}>
            This situation may require professional legal advice.
          </div>
        )}
      </div>
      <div className="cp-timestamp" style={{ marginTop: 4 }}>{fmtTimestamp(msg.timestamp)}</div>
    </div>
  );
}

// ─── Input Bar ────────────────────────────────────────────────────────────────

function ChatInputBar({ input, setInput, onSend, loading, lang, mode }) {
  const textareaRef = useRef(null);
  const accent = mode === 'campus' ? 'var(--sage)' : 'var(--ember)';
  const maxChars = 2000;
  const canSend = input.trim().length > 0 && !loading;

  const handleInput = (e) => {
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 88) + 'px';
    setInput(el.value);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (canSend) onSend();
    }
  };

  useEffect(() => {
    if (!input && textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  }, [input]);

  return (
    <div className="cp-input-bar">
      <div className="cp-input-wrap" style={{ borderColor: loading ? 'var(--mist)' : `${accent}55` }}>
        <textarea
          ref={textareaRef}
          className={`cp-textarea${lang === 'BN' ? ' bn' : ''}`}
          placeholder={lang === 'BN' ? 'আপনার প্রশ্ন লিখুন...' : 'Ask Anchor AI anything...'}
          value={input}
          onInput={handleInput}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          maxLength={maxChars}
          rows={1}
          disabled={loading}
        />
        <div style={{ display: 'flex', alignItems: 'flex-end', gap: 6, padding: '6px 8px 6px 0', flexShrink: 0 }}>
          {input.length > 1700 && (
            <span className="cp-char-count" style={{ color: input.length > 1900 ? 'var(--ember)' : 'var(--muted)' }}>
              {maxChars - input.length}
            </span>
          )}
          <button
            className="cp-send-btn"
            disabled={!canSend}
            onClick={onSend}
            style={{ background: canSend ? 'var(--navy)' : 'var(--mist-2)', cursor: canSend ? 'pointer' : 'not-allowed' }}
            title="Send"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M13.5 2.5L2.5 6.5l4.5 2 2 4.5 4.5-11z" stroke={canSend ? '#fff' : 'var(--muted)'} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round"/>
            </svg>
          </button>
        </div>
      </div>
      <div style={{ textAlign: 'center', fontSize: 10.5, color: 'var(--muted)', marginTop: 5, fontFamily: 'var(--font-sans)' }}>
        AI guidance only · Not a substitute for legal advice
      </div>
    </div>
  );
}

// ─── Main ChatProScreen ───────────────────────────────────────────────────────

function ChatProScreen() {
  const { mode, go, back, lang, setLang, auth } = useApp();

  const [conversations, setConversations] = useState(() => loadConversations());
  const [activeId, setActiveId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [convId, setConvId] = useState(null);

  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [citationsOpen, setCitationsOpen] = useState({});

  const bottomRef = useRef(null);

  // ── Mount: restore last conversation ──────────────────────────────
  useEffect(() => {
    let convs = loadConversations();
    if (convs.length === 0) {
      const fresh = createConversation(mode, lang);
      convs = [fresh];
      saveConversations(convs);
    }
    const last = convs.reduce((best, c) => c.updated_at > (best?.updated_at || 0) ? c : best, null);
    setConversations(convs);
    setActiveId(last.id);
    setMessages(last.messages || []);
    setConvId(last.convId || null);
  }, []);

  // ── Auto-scroll ───────────────────────────────────────────────────
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  // ── ESC key to close drawer ───────────────────────────────────────
  useEffect(() => {
    if (!drawerOpen) return;
    const handler = (e) => { if (e.key === 'Escape') closeDrawer(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [drawerOpen]);

  // ── Drawer open / close ───────────────────────────────────────────
  const openDrawer = () => {
    setDrawerOpen(true);
    requestAnimationFrame(() => setDrawerVisible(true));
  };
  const closeDrawer = () => {
    setDrawerVisible(false);
    setTimeout(() => setDrawerOpen(false), 285);
  };

  // ── Persist ───────────────────────────────────────────────────────
  const persist = (msgs, aid, cid) => {
    const name = getConvName(msgs);
    setConversations(prev => {
      const updated = updateConversation(prev, aid, { messages: msgs, convId: cid, name });
      saveConversations(updated);
      return updated;
    });
  };

  // ── New conversation ──────────────────────────────────────────────
  const handleNew = () => {
    const fresh = createConversation(mode, lang);
    setConversations(prev => {
      const updated = [...prev, fresh];
      saveConversations(updated);
      return updated;
    });
    setActiveId(fresh.id);
    setMessages([]);
    setConvId(null);
    setCitationsOpen({});
    setInput('');
  };

  // ── Select conversation ───────────────────────────────────────────
  const handleSelect = (id) => {
    const conv = conversations.find(c => c.id === id);
    if (!conv) return;
    setActiveId(id);
    setMessages(conv.messages || []);
    setConvId(conv.convId || null);
    setCitationsOpen({});
    setInput('');
  };

  // ── Delete conversation ───────────────────────────────────────────
  const handleDelete = (id) => {
    setConversations(prev => {
      let updated = prev.filter(c => c.id !== id);
      if (id === activeId) {
        if (updated.length > 0) {
          const last = updated[updated.length - 1];
          setActiveId(last.id);
          setMessages(last.messages || []);
          setConvId(last.convId || null);
        } else {
          const fresh = createConversation(mode, lang);
          updated = [fresh];
          setActiveId(fresh.id);
          setMessages([]);
          setConvId(null);
        }
        setCitationsOpen({});
      }
      saveConversations(updated);
      return updated;
    });
  };

  // ── Send ──────────────────────────────────────────────────────────
  const send = async (queryText, stripLastError = false) => {
    const q = (queryText !== undefined ? queryText : input).trim();
    if (!q || loading) return;

    setInput('');
    const now = Date.now();
    const userMsg = { role: 'user', text: q, timestamp: now };
    // When retrying, strip the trailing error bubble from the same render's messages
    const base = (stripLastError && messages.length > 0 && messages[messages.length - 1]?.error)
      ? messages.slice(0, -1)
      : messages;
    const nextMessages = [...base, userMsg];
    setMessages(nextMessages);
    setLoading(true);

    const aid = activeId; // capture for closure
    const currentConvId = convId;

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 30000);

    try {
      const resp = await fetch(`${AI_BASE_PRO}/ai/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query: q, mode, lang, conversation_id: currentConvId || undefined }),
        signal: controller.signal,
      });
      clearTimeout(timeoutId);

      // Classify HTTP errors
      if (resp.status === 429) {
        pushError(nextMessages, aid, currentConvId, 'Rate limit reached. Please wait a moment before trying again.', 'rate_limit', q);
        return;
      }
      if (resp.status === 502 || resp.status === 503) {
        pushError(nextMessages, aid, currentConvId, 'AI engine is offline. Please start the backend server.', 'offline', q);
        return;
      }
      if (!resp.ok) {
        let body = '';
        try { body = await resp.text(); } catch {}
        pushError(nextMessages, aid, currentConvId, `Error ${resp.status}: ${body.slice(0, 80)}`, 'http_error', q);
        return;
      }

      let data;
      try { data = await resp.json(); } catch {
        pushError(nextMessages, aid, currentConvId, 'Received an unexpected response from the server.', 'parse_error', q);
        return;
      }

      const newConvId = data.conversation_id || currentConvId;
      setConvId(newConvId);

      const aiMsg = {
        role: 'ai', text: data.answer || '',
        citations: data.citations || [],
        confidence: data.confidence ?? 0,
        exit_ramp: !!data.exit_ramp,
        lawyer_referral: !!data.lawyer_referral,
        timestamp: Date.now(), error: false,
      };
      const withAI = [...nextMessages, aiMsg];
      setMessages(withAI);
      persist(withAI, aid, newConvId);

    } catch (err) {
      clearTimeout(timeoutId);
      if (err.name === 'AbortError') {
        pushError(nextMessages, aid, currentConvId, 'Request timed out. Please try again.', 'timeout', q);
      } else {
        pushError(nextMessages, aid, currentConvId, 'Unable to reach Anchor AI. Check your connection or start the backend server.', 'network', q);
      }
    } finally {
      setLoading(false);
    }
  };

  const pushError = (base, aid, cid, text, errorType, query) => {
    const errMsg = { role: 'ai', error: true, errorType, text, retryPayload: { query }, timestamp: Date.now() };
    const withErr = [...base, errMsg];
    setMessages(withErr);
    persist(withErr, aid, cid);
  };

  // ── Retry ──────────────────────────────────────────────────────────
  const retry = (retryPayload) => {
    // Pass stripLastError=true so send() removes the error bubble before appending
    // the user message again — avoids stale-closure issue with setTimeout.
    send(retryPayload.query, true);
  };

  const toggleCitations = (idx) => setCitationsOpen(prev => ({ ...prev, [idx]: !prev[idx] }));

  const activeConv = conversations.find(c => c.id === activeId);
  const convName   = activeConv?.name || 'New conversation';

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%',
      background: 'var(--cream)', position: 'relative', overflow: 'hidden',
    }}>
      {/* Drawer */}
      {drawerOpen && (
        <ConversationDrawer
          conversations={conversations}
          activeId={activeId}
          visible={drawerVisible}
          onClose={closeDrawer}
          onSelect={handleSelect}
          onNew={handleNew}
          onDelete={handleDelete}
          mode={mode}
        />
      )}

      {/* Header */}
      <ChatHeader convName={convName} mode={mode} onOpenDrawer={openDrawer} onNew={handleNew} />

      {/* Messages */}
      <div className="cp-messages no-scrollbar" style={{ flex: 1, overflowY: 'auto' }}>
        {messages.length === 0 ? (
          <EmptyState mode={mode} lang={lang} onSuggest={s => send(s)} />
        ) : (
          messages.map((msg, i) =>
            msg.role === 'user' ? (
              <UserMessage key={i} msg={msg} />
            ) : (
              <AIMessage
                key={i}
                msg={msg}
                msgIndex={i}
                citationsOpen={citationsOpen}
                onToggleCitations={toggleCitations}
                mode={mode}
                onGoLawyers={() => go('lawyers')}
                onRetry={msg.error ? () => retry(msg.retryPayload) : null}
              />
            )
          )
        )}
        {loading && <ProTypingIndicator />}
        <div ref={bottomRef} style={{ height: 1 }} />
      </div>

      {/* Input */}
      <ChatInputBar
        input={input}
        setInput={setInput}
        onSend={() => send()}
        loading={loading}
        lang={lang}
        mode={mode}
      />
    </div>
  );
}

Object.assign(window, { ChatProScreen });
