// Anchor — Screens part 1: Home, Chat, Alert (the three signature screens)
// Depends globally on icons.jsx + app.jsx (useApp, Header, C2CToggle)

const { useState: _useS, useEffect: _useE, useRef: _useR } = React;

// ═══════════════════════════════════════════════════════════════
//  HOME SCREEN
// ═══════════════════════════════════════════════════════════════
function HomeScreen() {
  const { mode, go, lang, auth } = useApp();
  const accent = mode === 'campus' ? 'var(--sage)' : 'var(--ember)';
  const isStudent = auth?.user?.role === 'student';

  const campusTiles = [
    { k: 'complaint', label: 'File a complaint', sub: 'Anonymous available', Icon: IconFile, route: 'compose' },
    { k: 'application', label: 'Generate application', sub: 'AI-drafted · for any need', Icon: IconSparkles, route: 'compose', params: { kind: 'application' } },
    { k: 'routine',   label: 'Academic routine', sub: 'Today · 4 classes',  Icon: IconClock },
    { k: 'notices',   label: 'University notices', sub: '3 new this week',   Icon: IconNews, route: 'notices' },
    { k: 'hostel',    label: 'Hostel issue',   sub: 'Maintenance · Mess',   Icon: IconBed, route: 'compose', params: { kind: 'hostel' } },
    { k: 'classroom', label: 'Report classroom', sub: 'AC · Projector · Net', Icon: IconBuilding, route: 'compose', params: { kind: 'classroom' } },
    { k: 'feed',      label: 'Campus verified',sub: 'Notices & rumours',     Icon: IconNews, route: 'feed' },
    { k: 'rate',      label: 'Rate department', sub: 'SWE · CSE · BBA',     Icon: IconStar },
  ];

  const countryTiles = [
    { k: 'fir',     label: 'Draft FIR / GD',   sub: 'AI-assisted document', Icon: IconGavel,  route: 'compose', params: { kind: 'gd' } },
    { k: 'lawyer',  label: 'Find a lawyer',    sub: 'End-to-end encrypted', Icon: IconScale,  route: 'lawyers' },
    { k: 'zones',   label: 'Red zone map',     sub: 'Dhaka · live overlay',  Icon: IconMap,    route: 'map' },
    { k: 'rights',  label: 'Know your rights', sub: 'BD Penal Code · DV Act', Icon: IconBook, route: 'rights' },
    { k: 'feed',    label: 'Verified news', sub: 'Human-moderated',     Icon: IconNews,   route: 'feed' },
    { k: 'officer', label: 'Officer scorecard',sub: 'Public accountability', Icon: IconBadge },
  ];
  const tiles = mode === 'campus' ? campusTiles : countryTiles;

  return (
    <>
      <Header/>

      {/* C2C toggle hero — students only */}
      <div style={{ padding: '8px 20px 4px' }}>
        {isStudent ? (
          <>
            <div className="eyebrow" style={{ marginBottom: 8, color: 'var(--muted)' }}>
              Choose your context
            </div>
            <C2CToggle/>
            <div style={{
              marginTop: 10, fontFamily: 'var(--font-serif)', fontStyle: 'italic',
              fontSize: 13, color: 'var(--muted)', textAlign: 'center', letterSpacing: '0.005em',
            }}>
              {mode === 'campus'
                ? 'Governance, complaints, and routine — within Daffodil.'
                : 'Legal aid, safety, and verification — across Bangladesh.'}
            </div>
          </>
        ) : (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '10px 16px', borderRadius: 14,
            background: 'rgba(196,69,54,0.06)', border: '1px solid rgba(196,69,54,0.14)',
          }}>
            <IconGlobe size={18} stroke="var(--ember)" />
            <div>
              <div style={{ fontWeight: 600, fontSize: 14, color: 'var(--navy)', fontFamily: 'var(--font-sans)' }}>
                National · Bangladesh
              </div>
              <div style={{ fontSize: 12, color: 'var(--muted)', fontFamily: 'var(--font-sans)' }}>
                Legal aid, safety &amp; verification
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Emergency hold banner */}
      <div style={{ padding: '14px 20px 8px' }}>
        <div className="em-banner">
          <div style={{ flexShrink: 0, width: 30, height: 30, borderRadius: 999,
            background: 'rgba(232,49,42,0.18)', display: 'flex',
            alignItems: 'center', justifyContent: 'center', color: 'var(--red)' }}>
            <IconAlert size={16}/>
          </div>
          <div style={{ flex: 1, lineHeight: 1.3 }}>
            <div className="eyebrow eyebrow-dark" style={{ color: 'rgba(247,243,238,0.55)' }}>Phase 2 alert</div>
            <div style={{ fontSize: 13, marginTop: 2 }}>Hold 4 seconds to broadcast emergency</div>
          </div>
          <button onClick={() => go('alert')} style={{
            background: 'var(--red)', color: '#fff', border: 'none', cursor: 'pointer',
            padding: '8px 12px', borderRadius: 999, fontFamily: 'var(--font-sans)',
            fontSize: 11, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase',
          }}>Hold</button>
        </div>
      </div>

      {/* AI chat input */}
      <div style={{ padding: '14px 20px 6px' }}>
        <AIInputCard onActivate={() => go('chat')}/>
      </div>

      {/* Quick action tiles */}
      <div style={{ padding: '20px 20px 8px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10 }}>
          <div className="eyebrow">Quick actions · {mode === 'campus' ? 'Campus' : 'National'}</div>
          <div className="serif" style={{ fontStyle: 'italic', fontSize: 12, color: 'var(--muted)' }}>{tiles.length} routes</div>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
          {tiles.map((t, i) => {
            const Ico = t.Icon;
            return (
              <button key={t.k} className="tile tile-anim"
                onClick={() => t.route && go(t.route, t.params || {})}
                style={{ animationDelay: `${i * 40}ms` }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 18 }}>
                  <div style={{
                    width: 34, height: 34, borderRadius: 10,
                    background: `linear-gradient(180deg, ${accent}11, ${accent}22)`,
                    border: `1px solid ${accent}33`,
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: accent,
                  }}>
                    <Ico size={17}/>
                  </div>
                  <IconChevronRight size={14} stroke="var(--mist-2)"/>
                </div>
                <div className="serif" style={{ fontWeight: 500, fontSize: 14.5, lineHeight: 1.2, color: 'var(--navy)', letterSpacing: '-0.005em' }}>
                  {t.label}
                </div>
                <div style={{ marginTop: 4, fontSize: 11.5, color: 'var(--muted)' }}>{t.sub}</div>
              </button>
            );
          })}
        </div>
      </div>

      {/* My Cases preview */}
      <div style={{ padding: '20px 0 8px 20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', paddingRight: 20, marginBottom: 10 }}>
          <div className="eyebrow">Active cases · {mode === 'campus' ? 'Campus' : 'National'}</div>
          <button onClick={() => go('cases')} style={{
            background: 'transparent', border: 'none', cursor: 'pointer',
            color: 'var(--navy)', fontSize: 12, fontFamily: 'var(--font-serif)', fontStyle: 'italic',
          }}>View all →</button>
        </div>
        <div className="h-scroll no-scrollbar" style={{ paddingRight: 20 }}>
          {ACTIVE_CASES.filter(c => c.scope === mode).slice(0, 3).map(c => (
            <button key={c.id} onClick={() => go('case', { id: c.id })} style={{
              width: 250, textAlign: 'left', background: 'rgba(255,255,255,0.7)',
              border: '1px solid var(--mist)', borderRadius: 14, padding: 14, cursor: 'pointer',
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                <span className="mono" style={{ fontSize: 10.5, color: 'var(--muted)' }}>{c.id}</span>
                <StatusPill status={c.status}/>
              </div>
              <div className="serif" style={{ fontSize: 14.5, fontWeight: 500, color: 'var(--navy)', lineHeight: 1.25, marginBottom: 6 }}>
                {c.title}
              </div>
              <Stepper status={c.status}/>
              <div style={{ marginTop: 8, fontSize: 11, color: 'var(--muted)' }}>{c.routed}</div>
            </button>
          ))}
        </div>
      </div>

      {/* Verification feed preview */}
      <div style={{ padding: '16px 20px 28px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10 }}>
          <div className="eyebrow">{mode === 'campus' ? 'Campus verified' : 'Verified news'}</div>
          <button onClick={() => go('feed')} style={{
            background: 'transparent', border: 'none', cursor: 'pointer',
            color: 'var(--navy)', fontSize: 12, fontFamily: 'var(--font-serif)', fontStyle: 'italic',
          }}>Open →</button>
        </div>
        {FEED.filter(f => f.scope === mode).slice(0, 2).map(f => <FeedRowMini key={f.id} item={f}/>)}
      </div>
    </>
  );
}

function AIInputCard({ onActivate }) {
  const { lang, setLang } = useApp();
  const suggestions = lang === 'BN'
    ? ['হোস্টেলে harassment হলে কী করব?', 'GD draft করো', 'আমার অধিকার কী?']
    : ['What if I face harassment in hostel?', 'Help me draft a GD', 'Know my rights'];
  return (
    <div onClick={onActivate} style={{
      border: '1px solid var(--mist-2)', borderRadius: 18, padding: '14px 14px 12px',
      background: 'rgba(255,255,255,0.7)', cursor: 'pointer',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{
          width: 30, height: 30, borderRadius: 999,
          background: 'var(--navy)', color: '#F7F3EE',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'var(--font-serif)', fontStyle: 'italic', fontWeight: 500, fontSize: 14,
        }}>A</div>
        <div style={{ flex: 1, fontFamily: 'var(--font-serif)', fontStyle: 'italic', color: 'var(--muted)', fontSize: 14.5 }}>
          Ask Anchor AI…
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <span style={{ width: 30, height: 30, borderRadius: 999, border: '1px solid var(--mist)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', color: 'var(--ink-2)' }}><IconMic size={14}/></span>
          <span style={{ width: 30, height: 30, borderRadius: 999, border: '1px solid var(--mist)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', color: 'var(--ink-2)' }}><IconImage size={14}/></span>
        </div>
      </div>
      <div style={{ display: 'flex', gap: 6, marginTop: 10, flexWrap: 'nowrap', overflow: 'hidden' }}>
        {suggestions.map((s, i) => (
          <span key={i} className={lang === 'BN' ? 'bn' : ''} style={{
            padding: '5px 10px', borderRadius: 999, background: 'var(--cream-2)',
            border: '1px solid var(--mist)', fontSize: 11, color: 'var(--ink-2)', whiteSpace: 'nowrap',
            textOverflow: 'ellipsis', overflow: 'hidden',
          }}>{s}</span>
        ))}
        <button onClick={(e) => { e.stopPropagation(); setLang(lang === 'EN' ? 'BN' : 'EN'); }} style={{
          marginLeft: 'auto', padding: '5px 8px', borderRadius: 999, background: 'transparent',
          border: '1px solid var(--mist-2)', fontSize: 10, fontWeight: 600, letterSpacing: '0.1em',
          color: 'var(--ink-2)', cursor: 'pointer', flexShrink: 0,
        }}>{lang}</button>
      </div>
    </div>
  );
}

function StatusPill({ status }) {
  const map = {
    submitted:  { cls: 'pill-submitted', label: 'Submitted' },
    review:     { cls: 'pill-review',    label: 'Under Review' },
    escalated:  { cls: 'pill-escalated', label: 'Escalated' },
    resolved:   { cls: 'pill-resolved',  label: 'Resolved' },
  };
  const m = map[status];
  return (
    <span className={`pill ${m.cls}`}>
      <span className="dot" style={status === 'review' ? { animation: 'statusPulse 1.8s ease-in-out infinite' } : {}}/>
      {m.label}
    </span>
  );
}

function Stepper({ status }) {
  const order = ['submitted', 'review', 'escalated', 'resolved'];
  const idx = order.indexOf(status);
  return (
    <div className="stepper">
      {order.map((s, i) => (
        <React.Fragment key={s}>
          <span className={`node ${i < idx ? 'done' : i === idx ? 'active' : ''}`}/>
          {i < order.length - 1 && <span className={`seg ${i < idx ? 'done' : ''}`}/>}
        </React.Fragment>
      ))}
    </div>
  );
}

function FeedRow({ item }) {
  return (
    <div style={{
      padding: '14px 0', borderTop: '1px solid var(--mist)',
    }}>
      <div style={{ display: 'flex', gap: 6, marginBottom: 6 }}>
        {item.trusted && <span className="pill" style={{ color: 'var(--gold)', borderColor: 'rgba(184,137,58,0.35)', background: 'rgba(184,137,58,0.08)' }}>
          <IconBadge size={9}/> Trusted source
        </span>}
        <span className="pill pill-resolved"><IconCheck size={9} sw={3}/> Reviewed</span>
      </div>
      <div className="serif" style={{ fontSize: 16, fontWeight: 500, lineHeight: 1.2, color: 'var(--navy)' }}>
        {item.headline}
      </div>
      <div style={{ marginTop: 4, fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.4 }}>{item.summary}</div>
      <div style={{ marginTop: 8, display: 'flex', gap: 12, alignItems: 'center' }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11.5, color: 'var(--sage-2)' }}>
          <IconCheck size={12} sw={2.4}/> {item.corr} corroborated
        </span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11.5, color: 'var(--ember)' }}>
          <IconX size={12} sw={2.4}/> {item.chal} challenged
        </span>
        <span style={{ flex: 1 }}/>
        <span style={{ fontSize: 10.5, color: 'var(--muted)' }}>{item.when}</span>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
//  CHAT SCREEN — Live AI Legal Companion (real API)
// ═══════════════════════════════════════════════════════════════

// Change this if your backend runs on a different port
const AI_BASE = (typeof window !== 'undefined' && window.ANCHOR_AI_URL) || 'http://localhost:8000';

// ── Simple inline-markdown renderer (no library needed) ─────────
function _renderLine(line, i, accentColor) {
  const inlineMarkup = (str) => {
    // Bold: **text**
    const parts = [];
    const re = /\*\*(.*?)\*\*/g;
    let last = 0, m, k = 0;
    while ((m = re.exec(str)) !== null) {
      if (m.index > last) parts.push(React.createElement('span', { key: k++ }, str.slice(last, m.index)));
      parts.push(React.createElement('strong', { key: k++ }, m[1]));
      last = re.lastIndex;
    }
    if (last < str.length) parts.push(React.createElement('span', { key: k++ }, str.slice(last)));
    return parts.length ? parts : str;
  };

  // Horizontal rule
  if (line.trim() === '---') return React.createElement('hr', { key: i, style: { border: 'none', borderTop: '1px dashed var(--mist)', margin: '10px 0' } });

  // Numbered steps: "1. LABEL: body" or "1. body"
  const numM = line.match(/^(\d+)\.\s*(?:(SITUATION|APPLICABLE LAW|APPLICATION|PRACTICAL STEP|SCOPE LIMITS)[:\s]+)?(.*)/);
  if (numM && numM[1] && line.match(/^\d+\./)) {
    const badge = React.createElement('span', {
      key: 'b', style: {
        flexShrink: 0, width: 20, height: 20, borderRadius: 999,
        background: accentColor || 'var(--navy)', color: '#F7F3EE',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontFamily: 'var(--font-serif)', fontSize: 11, fontWeight: 500,
      }
    }, numM[1]);
    const label = numM[2] ? React.createElement('strong', { key: 'l', style: { color: 'var(--navy)' } }, numM[2] + ': ') : null;
    return React.createElement('div', { key: i, style: { display: 'flex', gap: 10, margin: '6px 0', alignItems: 'flex-start' } },
      badge,
      React.createElement('span', { style: { fontSize: 13, lineHeight: 1.5, color: 'var(--ink)', paddingTop: 2 } },
        label, inlineMarkup(numM[3] || ''))
    );
  }

  // Bullet: "- " or "  • "
  if (/^\s*[-•]\s/.test(line)) {
    const body = line.replace(/^\s*[-•]\s*/, '');
    return React.createElement('div', { key: i, style: { display: 'flex', gap: 8, margin: '2px 0 2px 6px', alignItems: 'flex-start' } },
      React.createElement('span', { style: { color: 'var(--muted)', marginTop: 1, flexShrink: 0 } }, '·'),
      React.createElement('span', { style: { fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.45 } }, inlineMarkup(body))
    );
  }

  // Bold-only heading line like "**Sources:**"
  if (/^\*\*[^*]+\*\*:?$/.test(line.trim())) {
    return React.createElement('div', { key: i, style: { fontWeight: 700, fontSize: 10.5, letterSpacing: '0.09em', textTransform: 'uppercase', color: 'var(--muted)', margin: '12px 0 4px' } },
      line.replace(/\*\*/g, '')
    );
  }

  // Italic disclaimer line: "*text*"
  if (line.startsWith('*') && line.endsWith('*') && !line.startsWith('**')) {
    return React.createElement('div', { key: i, style: { fontSize: 11, color: 'var(--muted)', fontStyle: 'italic', fontFamily: 'var(--font-serif)', marginTop: 6 } }, line.slice(1, -1));
  }

  // Empty line → small spacer
  if (!line.trim()) return React.createElement('div', { key: i, style: { height: 6 } });

  // Default text line
  return React.createElement('div', { key: i, style: { fontSize: 13.5, color: 'var(--ink)', lineHeight: 1.6, margin: '1px 0' } }, inlineMarkup(line));
}

function renderMarkdown(text, accentColor) {
  if (!text) return null;
  return text.split('\n').map((line, i) => _renderLine(line, i, accentColor));
}

// ── Message bubble components ────────────────────────────────────

function UserBubble({ text, lang }) {
  return React.createElement('div', { style: { display: 'flex', justifyContent: 'flex-end' } },
    React.createElement('div', { className: `bubble-user ${lang === 'BN' ? 'bn' : ''}`, style: { fontSize: 14 } }, text)
  );
}

function AIBubble({ msg, accent, accentBg, accentBd, lang, go }) {
  const confPct = Math.round((msg.confidence || 0) * 100);
  const confColor = confPct >= 65 ? 'var(--sage-2)' : 'var(--ember)';
  const confBg   = confPct >= 65 ? 'rgba(74,107,92,0.1)' : 'rgba(196,69,54,0.08)';
  const corpusCites = (msg.citations || []).filter(c => c.source !== 'web');

  return (
    <div className="bubble-ai">
      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <div style={{
          width: 22, height: 22, borderRadius: 999, background: 'var(--navy)', color: '#F7F3EE',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'var(--font-serif)', fontStyle: 'italic', fontWeight: 500, fontSize: 11,
        }}>A</div>
        <span className="eyebrow">Anchor AI</span>
        <span style={{ flex: 1 }}/>
        {confPct > 0 && !msg.error && (
          <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 999, background: confBg, color: confColor, fontWeight: 600, letterSpacing: '0.04em' }}>
            {confPct}% confidence
          </span>
        )}
        {!msg.error && <span className="ai-tag"><IconSparkles size={9} stroke="var(--gold)"/> AI</span>}
      </div>

      {/* Answer body */}
      <div className={lang === 'BN' ? 'bn' : ''}>
        {renderMarkdown(msg.text, accent)}
      </div>

      {/* Citations */}
      {corpusCites.length > 0 && (
        <div style={{ marginTop: 12, paddingTop: 10, borderTop: '1px dashed var(--mist)' }}>
          <div className="eyebrow" style={{ marginBottom: 6 }}>Sources</div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {corpusCites.map((c, i) => (
              <span key={i} className="cite">{c.title || c.id}</span>
            ))}
          </div>
        </div>
      )}

      {/* Lawyer referral CTA */}
      {msg.lawyer_referral && go && (
        <div style={{
          marginTop: 12, padding: '10px 12px', borderRadius: 10,
          background: accentBg, border: `1px solid ${accentBd}`,
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <IconScale size={16} stroke={accent}/>
          <div style={{ flex: 1, fontSize: 12, color: 'var(--ink-2)', lineHeight: 1.4 }}>
            For your specific situation, a verified lawyer can give you better guidance.
          </div>
          <button onClick={() => go('lawyers')} style={{
            padding: '6px 10px', borderRadius: 8, border: 'none', cursor: 'pointer',
            background: accent, color: '#F7F3EE',
            fontFamily: 'var(--font-sans)', fontSize: 11, fontWeight: 600,
          }}>Find lawyer</button>
        </div>
      )}
    </div>
  );
}

function AIBubbleTyping() {
  return (
    <div className="bubble-ai">
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <div style={{
          width: 22, height: 22, borderRadius: 999, background: 'var(--navy)', color: '#F7F3EE',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'var(--font-serif)', fontStyle: 'italic', fontWeight: 500, fontSize: 11,
        }}>A</div>
        <span className="eyebrow">Anchor AI</span>
      </div>
      <div style={{ fontSize: 13, color: 'var(--muted)' }}>
        <span style={{ fontFamily: 'var(--font-serif)', fontStyle: 'italic' }}>thinking</span>
        <span style={{ display: 'inline-block', marginLeft: 5, fontSize: 20, lineHeight: 0.5, letterSpacing: 3, verticalAlign: 'middle' }}>···</span>
      </div>
    </div>
  );
}

// ── ChatScreen ───────────────────────────────────────────────────
function ChatScreen() {
  const { lang, setLang, mode, go } = useApp();
  const [messages, setMessages] = _useS([]);
  const [input, setInput] = _useS('');
  const [loading, setLoading] = _useS(false);
  const [convId, setConvId] = _useS(null);
  const bottomRef = _useR(null);
  const inputRef  = _useR(null);

  const accent   = mode === 'campus' ? 'var(--sage-2)'              : 'var(--ember-2)';
  const accentBg = mode === 'campus' ? 'rgba(74,107,92,0.06)'       : 'rgba(196,69,54,0.06)';
  const accentBd = mode === 'campus' ? 'rgba(74,107,92,0.25)'       : 'rgba(196,69,54,0.25)';

  const suggestions = mode === 'campus'
    ? (lang === 'BN'
        ? ['হোস্টেলে AC ১১ দিন ধরে নষ্ট — কীভাবে complaint করব?', 'Leave application draft করো', 'Anonymous complaint করতে পারব?']
        : ['AC broken in hostel 11 days — how to complain?', 'Draft a leave application', 'Can I file an anonymous complaint?'])
    : (lang === 'BN'
        ? ['Mirpur-10 এ ফোন ছিনতাই — GD কীভাবে করব?', 'আমার অধিকার কী গ্রেপ্তার হলে?', 'DV Act এ protection order কীভাবে পাব?']
        : ['Phone snatched at Mirpur-10 — how to file a GD?', 'What are my rights if arrested?', 'How do I get a domestic violence protection order?']);

  // Auto-scroll to latest message
  _useE(() => {
    if (bottomRef.current) bottomRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  const send = async (text) => {
    const q = (text !== undefined ? text : input).trim();
    if (!q || loading) return;

    setMessages(prev => [...prev, { role: 'user', text: q }]);
    setInput('');
    setLoading(true);

    try {
      const resp = await fetch(`${AI_BASE}/ai/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: q,
          mode: mode,
          lang: lang,
          conversation_id: convId || undefined,
        }),
      });

      if (!resp.ok) {
        const errText = await resp.text().catch(() => '');
        throw new Error(`Server error ${resp.status}${errText ? ': ' + errText.slice(0, 80) : ''}`);
      }

      const data = await resp.json();
      if (!convId && data.conversation_id) setConvId(data.conversation_id);

      setMessages(prev => [...prev, {
        role: 'ai',
        text: data.answer,
        citations: data.citations || [],
        confidence: data.confidence || 0,
        exit_ramp: data.exit_ramp,
        lawyer_referral: data.lawyer_referral,
      }]);
    } catch (err) {
      const isNetworkErr = err.message.includes('fetch') || err.message.includes('Failed');
      setMessages(prev => [...prev, {
        role: 'ai',
        text: isNetworkErr
          ? `**Anchor AI server is not reachable.**\n\nStart the backend:\n- \`cd backend\`\n- \`uvicorn app.main:app --port 8000\`\n\n*${err.message}*`
          : `**Something went wrong.**\n\n*${err.message}*`,
        citations: [],
        confidence: 0,
        exit_ramp: false,
        lawyer_referral: false,
        error: true,
      }]);
    } finally {
      setLoading(false);
      setTimeout(() => inputRef.current?.focus(), 80);
    }
  };

  const onKey = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  };

  const canSend = input.trim().length > 0 && !loading;

  return (
    <>
      <Header back/>

      {/* Title bar */}
      <div style={{ padding: '4px 20px 0', display: 'flex', alignItems: 'center', gap: 8 }}>
        <div>
          <div className="eyebrow">Anchor AI · {mode === 'campus' ? 'Campus assistant' : 'Legal companion'}</div>
          <div className="serif" style={{ fontSize: 22, fontWeight: 500, color: 'var(--navy)', letterSpacing: '-0.01em', marginTop: 2 }}>
            {lang === 'BN' ? 'কীভাবে সাহায্য করতে পারি?' : 'How can I help today?'}
          </div>
        </div>
        <div style={{ flex: 1 }}/>
        <button onClick={() => setLang(lang === 'EN' ? 'BN' : 'EN')} style={{
          padding: '7px 11px', borderRadius: 999, background: 'rgba(255,255,255,0.7)',
          border: '1px solid var(--mist-2)', fontSize: 11, fontWeight: 600, letterSpacing: '0.1em',
          color: 'var(--ink-2)', cursor: 'pointer',
        }}>{lang === 'EN' ? 'EN · BN' : 'BN · EN'}</button>
      </div>

      {/* Messages area */}
      <div style={{ padding: '14px 20px 150px', display: 'flex', flexDirection: 'column', gap: 14 }}>

        {/* Empty state — suggestion chips */}
        {messages.length === 0 && (
          <>
            <div className="eyebrow" style={{ marginTop: 4, marginBottom: 6 }}>
              {lang === 'BN' ? 'কিছু প্রশ্নের উদাহরণ' : 'Try one of these'}
            </div>
            {suggestions.map((s, i) => (
              <button key={i} onClick={() => send(s)} className={lang === 'BN' ? 'bn' : ''} style={{
                textAlign: 'left', padding: '12px 16px', borderRadius: 14,
                background: 'rgba(255,255,255,0.75)', border: '1px solid var(--mist)',
                fontSize: 13.5, color: 'var(--navy)', cursor: 'pointer', lineHeight: 1.35,
                fontFamily: lang === 'BN' ? 'var(--font-bn)' : 'var(--font-serif)',
                fontStyle: lang === 'BN' ? 'normal' : 'italic',
              }}>{s}</button>
            ))}
            <div style={{ textAlign: 'center', padding: '12px 0 4px' }}>
              <div style={{ fontSize: 11, color: 'var(--muted)', fontFamily: 'var(--font-serif)', fontStyle: 'italic' }}>
                {lang === 'BN'
                  ? 'বাংলা বা ইংরেজিতে প্রশ্ন করুন · এটি AI পরামর্শ, আইনজীবীর বিকল্প নয়'
                  : 'Ask in Bangla or English · AI guidance, not a substitute for a lawyer'}
              </div>
            </div>
          </>
        )}

        {/* Conversation */}
        {messages.map((msg, i) => (
          msg.role === 'user'
            ? <UserBubble key={i} text={msg.text} lang={lang}/>
            : <AIBubble key={i} msg={msg} accent={accent} accentBg={accentBg} accentBd={accentBd} lang={lang} go={go}/>
        ))}

        {/* Typing indicator */}
        {loading && <AIBubbleTyping/>}

        <div ref={bottomRef}/>
      </div>

      {/* Sticky input bar */}
      <div style={{
        position: 'sticky', bottom: 80, padding: '8px 12px',
        background: 'linear-gradient(180deg, transparent, rgba(247,243,238,0.98) 30%)',
      }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 8, padding: '6px 6px 6px 14px',
          background: '#fff', border: '1px solid var(--mist-2)', borderRadius: 999,
          boxShadow: '0 4px 18px rgba(11,29,53,0.06)',
        }}>
          <input
            ref={inputRef}
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={onKey}
            placeholder={lang === 'BN' ? 'Anchor AI কে জিজ্ঞেস করুন…' : 'Ask Anchor AI…'}
            style={{
              flex: 1, border: 'none', outline: 'none', background: 'transparent',
              fontFamily: lang === 'BN' ? 'var(--font-bn)' : 'var(--font-sans)',
              fontSize: 14, color: 'var(--ink)', padding: '8px 0',
            }}
          />
          <button style={{ width: 32, height: 32, borderRadius: 999, background: 'transparent', border: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--ink-2)', cursor: 'pointer' }}>
            <IconMic size={16}/>
          </button>
          <button
            onClick={() => send()}
            disabled={!canSend}
            style={{
              width: 36, height: 36, borderRadius: 999,
              background: canSend ? 'var(--navy)' : 'var(--mist-2)',
              border: 'none', cursor: canSend ? 'pointer' : 'not-allowed',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#F7F3EE', transition: 'background 0.15s',
            }}
          >
            <IconArrowUp size={16} sw={2.2}/>
          </button>
        </div>
        {convId && (
          <div style={{ textAlign: 'center', marginTop: 3, fontSize: 9, color: 'var(--muted)', fontFamily: 'var(--font-mono)' }}>
            session {convId.slice(0, 8)}
          </div>
        )}
      </div>
    </>
  );
}

// ═══════════════════════════════════════════════════════════════
//  ALERT SCREEN — 3-phase emergency
// ═══════════════════════════════════════════════════════════════
function AlertScreen() {
  const { back } = useApp();
  const [phase, setPhase] = _useS('during');
  const [holding, setHolding] = _useS(false);
  const [progress, setProgress] = _useS(0);
  const [activated, setActivated] = _useS(false);
  const startRef = _useR(null);
  const rafRef = _useR(null);

  const startHold = () => {
    if (activated) return;
    setHolding(true);
    startRef.current = performance.now();
    const tick = () => {
      const elapsed = (performance.now() - startRef.current) / 1000;
      const p = Math.min(elapsed / 4, 1);
      setProgress(p);
      if (p >= 1) { setActivated(true); setHolding(false); return; }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
  };
  const cancelHold = () => {
    if (activated) return;
    setHolding(false); setProgress(0);
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
  };

  return (
    <div style={{
      minHeight: '100%', position: 'relative',
      background: phase === 'during'
        ? 'linear-gradient(180deg, #0A0A0C 0%, #161013 100%)'
        : 'var(--cream)',
      color: phase === 'during' ? '#F7F3EE' : 'var(--ink)',
      paddingBottom: 20,
    }}>
      {/* Header (custom dark) */}
      <div style={{
        padding: '60px 20px 14px', display: 'flex', alignItems: 'center', gap: 10,
      }}>
        <button onClick={back} style={{
          background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.15)',
          borderRadius: 999, padding: '6px 10px 6px 8px', display: 'flex',
          alignItems: 'center', gap: 4, cursor: 'pointer',
          color: phase === 'during' ? '#F7F3EE' : 'var(--navy)',
          fontFamily: 'var(--font-sans)', fontSize: 12, fontWeight: 500,
        }}>
          <IconArrowLeft size={14}/> Back
        </button>
        <div style={{ flex: 1 }}/>
        <div className="eyebrow" style={{ color: phase === 'during' ? 'rgba(247,243,238,0.5)' : 'var(--muted)' }}>
          Emergency · Phase 2
        </div>
      </div>

      {/* Title */}
      <div style={{ padding: '4px 20px 8px' }}>
        <div className="serif" style={{
          fontSize: 30, fontWeight: 500, letterSpacing: '-0.015em', lineHeight: 1.05,
          color: phase === 'during' ? '#F7F3EE' : 'var(--navy)',
        }}>
          {activated ? 'Alert broadcast.' : 'In an emergency,\nyou are not alone.'}
        </div>
        <div style={{
          marginTop: 8, fontSize: 13, color: phase === 'during' ? 'rgba(247,243,238,0.6)' : 'var(--muted)',
          fontFamily: 'var(--font-serif)', fontStyle: 'italic', lineHeight: 1.45,
        }}>
          {activated
            ? 'Trusted contacts and the nearest verified responder have been notified. Stay where you are if safe.'
            : 'Hold the button for four seconds. We will reach your contacts, share your location, and start recording.'}
        </div>
      </div>

      {/* Phase tabs */}
      <div style={{ padding: '14px 20px 4px' }}>
        <div className="tabbar" style={{
          background: phase === 'during' ? 'rgba(255,255,255,0.06)' : 'var(--cream-2)',
          borderColor: phase === 'during' ? 'rgba(255,255,255,0.1)' : 'var(--mist)',
        }}>
          {['before', 'during', 'after'].map(p => (
            <button key={p} onClick={() => setPhase(p)}
              className={phase === p ? 'on' : ''}
              style={phase === p ? { background: phase === 'during' ? '#E8312A' : 'var(--navy)' }
                                 : { color: phase === 'during' ? 'rgba(247,243,238,0.7)' : 'var(--ink-2)' }}>
              <span style={{ textTransform: 'capitalize' }}>{p}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Body */}
      <div style={{ padding: '18px 20px 32px' }}>
        {phase === 'before' && <AlertBefore/>}
        {phase === 'during' && <AlertDuring holding={holding} progress={progress} activated={activated} onDown={startHold} onUp={cancelHold}/>}
        {phase === 'after'  && <AlertAfter/>}
      </div>
    </div>
  );
}

function AlertDuring({ holding, progress, activated, onDown, onUp }) {
  const circ = 2 * Math.PI * 102;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18 }}>
      <button
        onPointerDown={onDown}
        onPointerUp={onUp}
        onPointerLeave={onUp}
        className="hold-btn"
        aria-label="Hold to activate emergency alert"
        style={{ background: activated ? 'radial-gradient(circle at 30% 30%, #5A0907, #2A0403)' : undefined }}>
        {/* Progress ring */}
        <svg width="244" height="244" style={{ position: 'absolute', inset: -12 }}>
          <circle cx="122" cy="122" r="102" fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="6"/>
          <circle cx="122" cy="122" r="102" fill="none" stroke="#fff" strokeWidth="6" strokeLinecap="round"
            strokeDasharray={circ}
            strokeDashoffset={circ * (1 - progress)}
            transform="rotate(-90 122 122)"
            style={{ transition: holding ? 'none' : 'stroke-dashoffset 240ms ease' }}/>
        </svg>
        <div style={{ position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6 }}>
          <IconShield size={36} sw={1.6}/>
          <div className="serif" style={{ fontSize: 16, fontWeight: 500, letterSpacing: '-0.01em' }}>
            {activated ? 'Activated' : holding ? `${Math.ceil((1 - progress) * 4)}…` : 'Hold to alert'}
          </div>
          <div style={{ fontSize: 10.5, letterSpacing: '0.18em', textTransform: 'uppercase', opacity: 0.6 }}>
            {activated ? 'Help on the way' : '4 seconds'}
          </div>
        </div>
      </button>

      <div style={{
        padding: '8px 14px', borderRadius: 999, border: '1px solid rgba(255,255,255,0.1)',
        background: 'rgba(255,255,255,0.04)', fontSize: 11.5, color: 'rgba(247,243,238,0.75)',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <IconClock size={13}/> 1 alert remaining today
      </div>

      {/* Recording note */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        padding: '11px 14px', borderRadius: 12, marginTop: 2,
        background: 'rgba(232,49,42,0.08)', border: '1px solid rgba(232,49,42,0.3)',
        width: '100%', boxSizing: 'border-box',
      }}>
        <div style={{
          flexShrink: 0, width: 26, height: 26, borderRadius: 999,
          background: 'rgba(232,49,42,0.18)', display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: '#FF8A85', position: 'relative',
        }}>
          <IconCamera size={14}/>
          <span style={{
            position: 'absolute', top: -1, right: -1, width: 8, height: 8, borderRadius: 999,
            background: '#E8312A', border: '2px solid #0A0A0C',
            animation: 'statusPulse 1.5s ease-in-out infinite',
          }}/>
        </div>
        <div style={{ flex: 1, fontSize: 11.5, color: 'rgba(247,243,238,0.92)', lineHeight: 1.4 }}>
          <div style={{ fontWeight: 600, color: '#FFD9D7', letterSpacing: '0.04em' }}>10-second video will record automatically</div>
          <div style={{ fontSize: 10.5, color: 'rgba(247,243,238,0.55)', marginTop: 1 }}>
            Encrypted, timestamped, sent to your trusted contacts
          </div>
        </div>
      </div>

      <div style={{ width: '100%', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 4 }}>
        <div style={{ padding: 12, borderRadius: 12, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
          <div className="eyebrow" style={{ color: 'rgba(247,243,238,0.5)' }}>Will notify</div>
          <div style={{ marginTop: 6, fontSize: 12.5, lineHeight: 1.4, color: 'rgba(247,243,238,0.85)' }}>
            3 trusted contacts<br/>Nearest responder (2.1 km)<br/>Anchor Verify Team
          </div>
        </div>
        <div style={{ padding: 12, borderRadius: 12, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
          <div className="eyebrow" style={{ color: 'rgba(247,243,238,0.5)' }}>Will share</div>
          <div style={{ marginTop: 6, fontSize: 12.5, lineHeight: 1.4, color: 'rgba(247,243,238,0.85)' }}>
            Live GPS (5 min)<br/>Audio recording<br/>Encrypted timestamp
          </div>
        </div>
      </div>
    </div>
  );
}

function AlertBefore() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div className="card" style={{ background: 'rgba(255,255,255,0.7)' }}>
        <div className="eyebrow" style={{ marginBottom: 8 }}>Around you</div>
        <div style={{
          position: 'relative', height: 130, borderRadius: 12, overflow: 'hidden',
          background: 'linear-gradient(135deg, #E8E2D6, #D8D0BE)',
          border: '1px solid var(--mist)',
        }}>
          <svg width="100%" height="100%" viewBox="0 0 300 130" preserveAspectRatio="none">
            <path d="M0 80 Q50 60 100 75 T200 70 T300 85 L300 130 L0 130 Z" fill="rgba(11,29,53,0.06)"/>
            <path d="M0 100 Q60 90 120 100 T240 95 T300 105 L300 130 L0 130 Z" fill="rgba(11,29,53,0.1)"/>
          </svg>
          <div className="zone-circle zone-red" style={{ left: '30%', top: '60%', width: 60, height: 60 }}/>
          <div className="zone-circle zone-black" style={{ left: '65%', top: '50%', width: 50, height: 50 }}/>
          <div style={{
            position: 'absolute', left: '50%', top: '70%', transform: 'translate(-50%,-50%)',
            width: 14, height: 14, borderRadius: 999, background: 'var(--navy)',
            border: '3px solid #fff', boxShadow: '0 2px 8px rgba(11,29,53,0.3)',
          }}/>
        </div>
        <div style={{ marginTop: 10, fontSize: 12, color: 'var(--ink-2)' }}>
          <strong>2 risk zones</strong> within 800m. Avoid Dhanmondi-3 after 9pm.
        </div>
      </div>

      <button className="btn btn-ghost" style={{ width: '100%' }}>
        <IconCamera size={16}/> Document a threat (encrypted)
      </button>

      <div>
        <div className="eyebrow" style={{ marginBottom: 8 }}>Trusted contacts · 3</div>
        {[
          { n: 'Bappa (Brother)', p: '+880 1712 ●●●●●●', tag: 'Primary' },
          { n: 'Mrs. Akter (Mother)', p: '+880 1819 ●●●●●●', tag: 'Family' },
          { n: 'Rifat (Roommate)', p: '+880 1521 ●●●●●●', tag: 'Friend' },
        ].map((c, i) => (
          <div key={i} style={{
            display: 'flex', alignItems: 'center', gap: 10, padding: '11px 12px',
            background: 'rgba(255,255,255,0.6)', border: '1px solid var(--mist)',
            borderRadius: 12, marginBottom: 6,
          }}>
            <div style={{
              width: 32, height: 32, borderRadius: 999,
              background: 'var(--cream-2)', display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--navy)',
            }}><IconUser size={15}/></div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13.5, color: 'var(--navy)', fontWeight: 500 }}>{c.n}</div>
              <div className="mono" style={{ fontSize: 10.5, color: 'var(--muted)' }}>{c.p}</div>
            </div>
            <span className="pill">{c.tag}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function AlertAfter() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div className="card" style={{ background: 'rgba(255,255,255,0.7)', borderColor: 'rgba(74,107,92,0.3)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <IconLock size={16} stroke="var(--sage-2)"/>
          <div className="eyebrow" style={{ color: 'var(--sage-2)' }}>Evidence vault · encrypted</div>
        </div>
        <div className="serif" style={{ marginTop: 4, fontSize: 17, fontWeight: 500, color: 'var(--navy)' }}>
          Upload evidence — timestamped & sealed
        </div>
        <div style={{ marginTop: 12, padding: '24px 14px', border: '1px dashed var(--mist-2)', borderRadius: 12, background: 'var(--cream)', textAlign: 'center' }}>
          <IconUpload size={26} stroke="var(--muted)"/>
          <div style={{ marginTop: 8, fontSize: 12.5, color: 'var(--ink-2)' }}>Drop photos, audio, or video</div>
          <div style={{ marginTop: 2, fontSize: 11, color: 'var(--muted)' }}>SHA-256 hashed · GPS embedded · 7-year retention</div>
        </div>
      </div>

      <div>
        <div className="eyebrow" style={{ marginBottom: 8 }}>Previous alerts · 2</div>
        {[
          { d: 'May 18, 2026 · 22:47', loc: 'Dhanmondi-27', resp: 'Resolved · responder reached in 7 min' },
          { d: 'Mar 02, 2026 · 19:12', loc: 'Mirpur-10',     resp: 'Closed · false trigger' },
        ].map((a, i) => (
          <div key={i} style={{
            padding: '12px 14px', background: 'rgba(255,255,255,0.6)',
            border: '1px solid var(--mist)', borderRadius: 12, marginBottom: 8,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="serif" style={{ fontSize: 14, fontWeight: 500, color: 'var(--navy)' }}>{a.loc}</span>
              <span className="pill pill-resolved">Closed</span>
            </div>
            <div className="mono" style={{ fontSize: 10.5, color: 'var(--muted)', marginTop: 4 }}>{a.d}</div>
            <div style={{ fontSize: 12, color: 'var(--ink-2)', marginTop: 4 }}>{a.resp}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Shared mock data exported to window so screens-2 can reuse
const ACTIVE_CASES = [
  { id: 'CMP-2026-A4F2', title: 'Hostel curfew dispute — Block B, Floor 3', status: 'review',
    routed: 'Routed to: Hostel Warden → DSA', scope: 'campus',
    updated: '2 hours ago', anon: false,
    desc: 'Block B curfew has been arbitrarily moved to 8:30pm without notice. Affects 64 residents.',
    timeline: [
      { t: 'Submitted',  d: 'May 22, 09:14', done: true },
      { t: 'Acknowledged by Warden', d: 'May 22, 11:02', done: true },
      { t: 'Under review at DSA office', d: 'May 23, 16:30', active: true },
      { t: 'Resolution', d: 'Pending' },
    ],
    routing: ['Warden', 'DSA', 'Proctor', 'VC Office'],
  },
  { id: 'CMP-2026-B17C', title: 'Classroom AC broken — Room 705, SWE', status: 'submitted',
    routed: 'Routed to: Maintenance Cell', updated: '1 day ago', scope: 'campus', anon: false,
    desc: 'AC unit in 705 has been broken for 11 days. Classroom temperature exceeds 32°C.',
    timeline: [
      { t: 'Submitted', d: 'May 23, 10:00', active: true },
      { t: 'Acknowledgement', d: 'Pending' },
      { t: 'Repair scheduled', d: 'Pending' },
      { t: 'Resolved', d: 'Pending' },
    ],
    routing: ['Maintenance', 'Dept. Head', 'Admin'],
  },
  { id: 'NTL-2026-X9A1', title: 'GD draft — phone snatched at Mirpur-10', status: 'escalated',
    routed: 'Filed at: Mirpur Model Thana · GD #4827',
    updated: '3 days ago', scope: 'country', anon: false, deadMan: true,
    desc: 'Phone snatched on the way home, near Mirpur-10 circle. Two suspects on motorbike.',
    timeline: [
      { t: 'Drafted by Anchor AI', d: 'May 18, 22:50', done: true },
      { t: 'Reviewed by Adv. Kabir', d: 'May 19, 09:30', done: true },
      { t: 'Filed at Mirpur Thana', d: 'May 19, 14:12', done: true },
      { t: 'Escalated to FIR (cognizable)', d: 'May 20, 11:00', active: true },
    ],
    routing: ['Anchor AI', 'Verified Lawyer', 'Thana', 'Court'],
  },
  { id: 'NTL-2026-K3M2', title: 'Cyber harassment — anonymous complaint', status: 'review',
    routed: 'Routed to: Cyber Tribunal Dhaka',
    updated: '12 hours ago', scope: 'country', anon: true, deadMan: true,
    desc: 'Targeted online harassment from multiple accounts. Screenshots and metadata preserved.',
    timeline: [
      { t: 'Submitted (anonymous)', d: 'May 23, 08:00', done: true },
      { t: 'Routed to Cyber Tribunal', d: 'May 23, 14:20', active: true },
      { t: 'Lawyer assigned', d: 'Pending' },
      { t: 'Hearing scheduled', d: 'Pending' },
    ],
    routing: ['Anchor AI', 'Verified Lawyer', 'Cyber Tribunal', 'Court'],
  },
  { id: 'CMP-2026-E2D3', title: 'Anonymous report — bias in grading, BBA', status: 'review',
    routed: 'Routed to: Dept. Head of BBA', updated: '4 days ago', scope: 'campus', anon: true,
    desc: 'Pattern of grade discrepancy in a single section across 3 graded assignments.',
    timeline: [
      { t: 'Submitted (anonymous)', d: 'May 19, 13:00', done: true },
      { t: 'Under review at Dept.', d: 'May 21', active: true },
      { t: 'Resolution', d: 'Pending' },
    ],
    routing: ['Dept. Head', 'Dean', 'Academic Council'],
  },
  { id: 'CMP-2026-R7K0', title: 'Mess food quality — Block C', status: 'resolved',
    routed: 'Resolved by: Hostel Office', updated: '1 week ago', scope: 'campus', anon: false,
    desc: 'Mess quality complaints from Block C, addressed with new vendor onboarding.',
    timeline: [
      { t: 'Submitted', d: 'May 11', done: true },
      { t: 'Reviewed', d: 'May 12', done: true },
      { t: 'Resolved · new vendor', d: 'May 17', done: true },
    ],
    routing: ['Hostel Warden', 'DSA'],
  },
  { id: 'NTL-2025-P9L4', title: 'Eviction notice dispute — resolved', status: 'resolved',
    routed: 'Resolved by: Settlement at Tribunal',
    updated: '3 months ago', scope: 'country', anon: false,
    desc: 'Disputed eviction notice resolved through mediation with verified counsel.',
    timeline: [
      { t: 'Drafted application', d: 'Feb 8', done: true },
      { t: 'Tribunal hearing', d: 'Mar 14', done: true },
      { t: 'Settlement reached', d: 'Mar 21', done: true },
    ],
    routing: ['Anchor AI', 'Verified Lawyer', 'Tribunal'],
  },
];

const FEED = [
  // CAMPUS-SCOPED items
  { id: 'c1', scope: 'campus', art: 'protest',
    kicker: 'Campus · Top story',
    headline: 'Hostel notice circulating online — confirmed authentic by DSA',
    byline: { author: 'Tasnia Rahman', source: 'Anchor Verifiers', when: '4h ago' },
    lead: 'A notice attributed to the Dean of Students Affairs about updated curfew rules began circulating in batch group-chats yesterday afternoon. After cross-checking with three sources inside DSA, Anchor verifiers confirm the document is genuine and was issued May 23.',
    corr: 217, chal: 2, trusted: true },
  { id: 'c2', scope: 'campus', art: 'building',
    kicker: 'Department · SWE',
    headline: 'SWE industrial visit registration cap raised to 80 students',
    byline: { author: 'Rifat Chowdhury', source: 'SWE Office', when: '1d ago' },
    lead: 'Following high demand, the department has increased the cap on the upcoming industrial visit from 60 to 80 students. Anchor verifiers have a signed copy of the revision from the head of department.',
    corr: 64, chal: 0, trusted: true },
  { id: 'c3', scope: 'campus', art: 'mess',
    kicker: 'Rumour · Disputed',
    headline: 'Mess food cost hike — not confirmed, Hostel Office responds',
    byline: { author: 'Tanvir Hossain', source: 'Hostel Office (DIU)', when: '2d ago' },
    lead: 'Rumours of a Tk 1,200 hike in monthly mess fees are circulating in Block C. The Hostel Office tells Anchor that no rate change has been approved for this semester and the rumour likely stems from a vendor quotation page.',
    corr: 32, chal: 41, trusted: false },
  { id: 'c4', scope: 'campus', art: 'library',
    kicker: 'Campus · Notice',
    headline: 'Library sections A & B closed for renovation May 25 – June 12',
    byline: { author: 'Anchor Editorial', source: 'University Notices', when: '4d ago' },
    lead: 'The university library will close two of its three reading sections for scheduled renovation. Digital library access and reading room C remain open as usual.',
    corr: 88, chal: 1, trusted: true },

  // COUNTRY-SCOPED items
  { id: 'n1', scope: 'country', art: 'protest',
    kicker: 'National · Top story',
    headline: 'Dhanmondi cordon: official statement contradicts video evidence',
    byline: { author: 'Sumaiya Ahmed', source: 'Anchor Verifiers', when: '6h ago' },
    lead: 'Three independent verifiers cross-checked publicly available footage from May 22 against the briefing held by the Home Ministry that evening. Discrepancies were found in the stated timing of the police cordon and the exact location of two reported injuries.',
    corr: 142, chal: 11, trusted: true },
  { id: 'n2', scope: 'country', art: 'traffic',
    kicker: 'Misinformation · Debunked',
    headline: 'Mirpur traffic disruption was a power-feeder fault, not protest',
    byline: { author: 'Imran Sarker', source: 'Anchor Verifiers · DPDC', when: '11h ago' },
    lead: 'Traffic disruption near Mirpur-10 today was due to a power-feeder fault confirmed by Dhaka Power Distribution Company. Earlier social-media posts wrongly attributed it to student protest.',
    corr: 89, chal: 4, trusted: false },
  { id: 'n3', scope: 'country', art: 'court',
    kicker: 'Legal · Update',
    headline: 'New cyber-harassment fast-track bench begins hearings this week',
    byline: { author: 'Adv. F. Kabir', source: 'Cyber Tribunal Dhaka', when: '1d ago' },
    lead: 'A new fast-track bench at the Cyber Tribunal of Dhaka begins hearings on Wednesday. Citizens with pending complaints have been notified by SMS. Anchor will track resolution timelines.',
    corr: 173, chal: 3, trusted: true },
  { id: 'n4', scope: 'country', art: 'road',
    kicker: 'Public Safety',
    headline: 'Hazaribagh murder case suspect convicted — case closed',
    byline: { author: 'Anchor Editorial', source: 'Court records', when: '2d ago' },
    lead: 'After a fourteen-month trial, the Hazaribagh murder case from February 2026 concluded with a guilty verdict. The red-zone marker on the Anchor map has been moved to "Resolved".',
    corr: 209, chal: 0, trusted: true },
];

Object.assign(window, {
  HomeScreen, ChatScreen, AlertScreen,
  StatusPill, Stepper,
  ACTIVE_CASES, FEED,
});

// ═══════════════════════════════════════════════════════════════
//  NEWS ART — flat editorial SVG illustrations for feed images
// ═══════════════════════════════════════════════════════════════
function NewsArt({ variant }) {
  const skies = {
    protest:  ['#1F3759', '#0B1D35'],
    traffic:  ['#3a2418', '#1c100a'],
    court:    ['#2c2a3d', '#0F0E1A'],
    road:     ['#1f2d24', '#0c1310'],
    building: ['#34302a', '#1a1814'],
    library:  ['#1e2a36', '#0d1620'],
    mess:     ['#3a2820', '#1a120e'],
  };
  const [a, b] = skies[variant] || ['#1f2937', '#111827'];

  const Common = ({ children }) => (
    <svg viewBox="0 0 320 180" preserveAspectRatio="xMidYMid slice"
      style={{ position: 'absolute', inset: 0, width: '100%', height: '100%' }}>
      <defs>
        <linearGradient id={`g-${variant}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={a}/><stop offset="1" stopColor={b}/>
        </linearGradient>
      </defs>
      <rect width="320" height="180" fill={`url(#g-${variant})`}/>
      {children}
    </svg>
  );

  if (variant === 'protest') return (
    <Common>
      {/* Distant skyline */}
      <g fill="rgba(247,243,238,0.08)">
        <rect x="0" y="100" width="40" height="40"/>
        <rect x="42" y="90" width="28" height="50"/>
        <rect x="72" y="105" width="36" height="35"/>
        <rect x="220" y="95" width="44" height="45"/>
        <rect x="266" y="85" width="30" height="55"/>
        <rect x="298" y="100" width="22" height="40"/>
      </g>
      {/* Crowd silhouette */}
      <g fill="rgba(247,243,238,0.32)">
        {Array.from({length: 22}).map((_, i) => (
          <circle key={i} cx={10 + i * 14 + (i % 3) * 3} cy={140 + (i % 4) * 2} r="6"/>
        ))}
        <rect x="0" y="148" width="320" height="32" opacity="0.6"/>
      </g>
      {/* Sign */}
      <g transform="translate(132 60)">
        <rect width="56" height="36" rx="2" fill="#F7F3EE"/>
        <line x1="28" y1="36" x2="28" y2="86" stroke="#F7F3EE" strokeWidth="2"/>
        <line x1="8" y1="14" x2="48" y2="14" stroke="#0B1D35" strokeWidth="2"/>
        <line x1="8" y1="22" x2="40" y2="22" stroke="#0B1D35" strokeWidth="2"/>
      </g>
    </Common>
  );

  if (variant === 'traffic') return (
    <Common>
      {/* Sky highlight */}
      <circle cx="260" cy="30" r="36" fill="rgba(232,49,42,0.18)"/>
      {/* Road */}
      <rect x="0" y="130" width="320" height="50" fill="rgba(20,20,20,0.5)"/>
      <g stroke="#F7F3EE" strokeWidth="2" strokeDasharray="14 10" opacity="0.4">
        <line x1="0" y1="155" x2="320" y2="155"/>
      </g>
      {/* Traffic light */}
      <g transform="translate(150 50)">
        <rect x="6" y="0" width="28" height="68" rx="3" fill="#1a1a1a" stroke="rgba(247,243,238,0.2)"/>
        <circle cx="20" cy="14" r="6" fill="#E8312A"/>
        <circle cx="20" cy="34" r="6" fill="rgba(247,243,238,0.15)"/>
        <circle cx="20" cy="54" r="6" fill="rgba(247,243,238,0.15)"/>
        <line x1="20" y1="68" x2="20" y2="130" stroke="#1a1a1a" strokeWidth="3"/>
      </g>
      {/* Cars */}
      <g fill="rgba(247,243,238,0.7)">
        <rect x="40" y="138" width="46" height="18" rx="4"/>
        <rect x="46" y="132" width="34" height="10" rx="2"/>
      </g>
      <g fill="rgba(247,243,238,0.4)">
        <rect x="230" y="138" width="46" height="18" rx="4"/>
        <rect x="236" y="132" width="34" height="10" rx="2"/>
      </g>
    </Common>
  );

  if (variant === 'court') return (
    <Common>
      {/* Columns */}
      <g fill="rgba(247,243,238,0.12)">
        {[40, 100, 160, 220, 280].map((x, i) => (
          <React.Fragment key={i}>
            <rect x={x - 8} y="40" width="16" height="100"/>
            <rect x={x - 12} y="36" width="24" height="6"/>
            <rect x={x - 12} y="140" width="24" height="6"/>
          </React.Fragment>
        ))}
        <rect x="20" y="30" width="280" height="8"/>
        <polygon points="20,30 160,8 300,30"/>
      </g>
      <rect x="0" y="148" width="320" height="32" fill="rgba(247,243,238,0.08)"/>
      {/* Scales */}
      <g transform="translate(140 88)" stroke="rgba(184,137,58,0.85)" fill="none" strokeWidth="1.8">
        <line x1="20" y1="0" x2="20" y2="44"/>
        <line x1="2" y1="14" x2="38" y2="14"/>
        <circle cx="6" cy="22" r="5" fill="rgba(184,137,58,0.3)"/>
        <circle cx="34" cy="22" r="5" fill="rgba(184,137,58,0.3)"/>
      </g>
    </Common>
  );

  if (variant === 'road') return (
    <Common>
      <rect x="0" y="120" width="320" height="60" fill="rgba(20,20,20,0.5)"/>
      <g stroke="#F7F3EE" strokeWidth="2.5" strokeDasharray="22 16" opacity="0.45">
        <line x1="0" y1="150" x2="320" y2="150"/>
      </g>
      {/* Skyline */}
      <g fill="rgba(247,243,238,0.1)">
        <rect x="20" y="60" width="40" height="60"/>
        <rect x="64" y="50" width="32" height="70"/>
        <rect x="100" y="70" width="46" height="50"/>
        <rect x="200" y="55" width="36" height="65"/>
        <rect x="240" y="65" width="60" height="55"/>
      </g>
      <circle cx="60" cy="34" r="20" fill="rgba(247,243,238,0.08)"/>
    </Common>
  );

  if (variant === 'building') return (
    <Common>
      <g fill="rgba(247,243,238,0.15)">
        <rect x="60" y="40" width="200" height="120"/>
      </g>
      <g fill="rgba(11,29,53,0.45)">
        {[0,1,2,3].map(r => [0,1,2,3,4,5,6].map(c => (
          <rect key={`${r}-${c}`} x={70 + c * 28} y={50 + r * 28} width="20" height="20"/>
        )))}
      </g>
      <rect x="148" y="120" width="24" height="40" fill="rgba(11,29,53,0.7)"/>
      <rect x="0" y="160" width="320" height="20" fill="rgba(247,243,238,0.08)"/>
    </Common>
  );

  if (variant === 'library') return (
    <Common>
      {/* Books on shelves */}
      <g>
        {Array.from({length: 4}).map((_, r) => (
          <g key={r} transform={`translate(20 ${20 + r * 40})`}>
            {Array.from({length: 14}).map((_, c) => {
              const colors = ['rgba(184,137,58,0.7)', 'rgba(74,107,92,0.7)', 'rgba(196,69,54,0.65)', 'rgba(247,243,238,0.5)'];
              return <rect key={c} x={c * 20} y={(c % 3) * 2} width="16" height={26 - (c % 3) * 2} fill={colors[(c + r) % 4]}/>;
            })}
            <line x1="0" y1="32" x2="280" y2="32" stroke="rgba(247,243,238,0.18)"/>
          </g>
        ))}
      </g>
    </Common>
  );

  if (variant === 'mess') return (
    <Common>
      {/* Plate */}
      <circle cx="160" cy="100" r="60" fill="rgba(247,243,238,0.85)"/>
      <circle cx="160" cy="100" r="48" fill="rgba(247,243,238,0.65)" stroke="rgba(11,29,53,0.1)"/>
      <circle cx="160" cy="100" r="20" fill="rgba(184,137,58,0.6)"/>
      <circle cx="138" cy="92" r="10" fill="rgba(74,107,92,0.7)"/>
      <circle cx="184" cy="92" r="10" fill="rgba(196,69,54,0.6)"/>
      <circle cx="160" cy="120" r="10" fill="rgba(247,243,238,0.9)"/>
      <rect x="0" y="160" width="320" height="20" fill="rgba(247,243,238,0.08)"/>
    </Common>
  );

  return <Common>{null}</Common>;
}

// ═══════════════════════════════════════════════════════════════
//  FeedRowMini — compact preview for Home
// ═══════════════════════════════════════════════════════════════
function FeedRowMini({ item }) {
  return (
    <div style={{ padding: '14px 0', borderTop: '1px solid var(--mist)', display: 'flex', gap: 12 }}>
      <div style={{ width: 80, height: 60, borderRadius: 6, overflow: 'hidden', flexShrink: 0, position: 'relative' }}>
        <NewsArt variant={item.art}/>
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="news-kicker" style={{ marginBottom: 3, fontSize: 9 }}>{item.kicker}</div>
        <div className="serif" style={{ fontSize: 14, fontWeight: 500, lineHeight: 1.15, color: 'var(--navy)' }}>{item.headline}</div>
        <div style={{ marginTop: 6, display: 'flex', gap: 10, alignItems: 'center', fontSize: 10.5, color: 'var(--muted)' }}>
          <span style={{ color: 'var(--sage-2)', display: 'inline-flex', alignItems: 'center', gap: 3 }}>
            <IconCheck size={10} sw={2.4}/> {item.corr}
          </span>
          <span style={{ color: 'var(--ember)', display: 'inline-flex', alignItems: 'center', gap: 3 }}>
            <IconX size={10} sw={2.4}/> {item.chal}
          </span>
          <span style={{ marginLeft: 'auto' }}>{item.byline.when}</span>
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
//  COMPOSE SCREEN — AI-drafted application / complaint / GD
// ═══════════════════════════════════════════════════════════════
function ComposeScreen({ params = {} }) {
  const { mode, go, lang } = useApp();
  const kind = params.kind || (mode === 'campus' ? 'application' : 'gd');
  const isCampus = mode === 'campus';
  const accent = isCampus ? 'var(--sage-2)' : 'var(--ember-2)';

  // Pre-set problem text per kind
  const presets = {
    application: {
      problem: 'I need a few days of academic leave next week for a family medical emergency. I would like to request approval from my department head.',
      to: 'Head of Department, Software Engineering\nDaffodil International University',
      subject: 'Application for Academic Leave (May 27 – May 30, 2026)',
      body: [
        'I, Sadia Akter, a fourth-year student of the Software Engineering department (ID: 213-35-4128), am writing to respectfully request a brief academic leave from May 27 to May 30, 2026.',
        'A close family member has been admitted to hospital and my presence is required to assist with their care. I will ensure that I make up for any missed coursework promptly and stay in touch with my course instructors via email throughout the period.',
        'I would be grateful if you could kindly approve this leave. I have attached a copy of the medical admission slip for your reference.',
      ],
      sign: 'Sadia Akter\nID: 213-35-4128 · Software Engineering · 4th Year',
      routedTo: 'Head of Department · SWE',
    },
    hostel: {
      problem: 'The AC in hostel Room 308, Block B has been broken for 11 days. The room temperature stays above 32°C, making it difficult to study.',
      to: 'The Hostel Provost\nDaffodil International University',
      subject: 'Application for repair of air-conditioning unit, Room 308 (Block B)',
      body: [
        'I, Sadia Akter, a resident of Block B, Room 308 (ID: 213-35-4128), am writing to respectfully bring to your attention an issue that has persisted for the past eleven days.',
        'The air-conditioning unit in our room has been non-functional since May 13. Despite a verbal report to the floor warden on May 14, no maintenance action has been taken. Room temperature in the afternoon has consistently exceeded 32°C, which has affected my ability to study and rest.',
        'I would be grateful if you could kindly direct the maintenance cell to inspect and repair the unit at the earliest. I am available at +880 1521 ●●●●●● should anyone need access to the room.',
      ],
      sign: 'Sadia Akter\nBlock B, Room 308 · ID: 213-35-4128',
      routedTo: 'Hostel Provost · Maintenance Cell',
    },
    classroom: {
      problem: 'The projector in Room 705 (SWE) keeps cutting out during lectures. It has been raised verbally twice already.',
      to: 'Head of Department, Software Engineering\nDaffodil International University',
      subject: 'Request for projector replacement, Room 705',
      body: [
        'On behalf of the students attending lectures in Room 705, I would like to formally raise an ongoing issue with the classroom projector.',
        'The projector intermittently loses signal mid-lecture. Despite two verbal reports made by our class representative on May 15 and May 19, no replacement or repair has been scheduled. This is meaningfully affecting our learning, particularly during slide-heavy lectures.',
        'I respectfully request that the department arrange for inspection and replacement of the unit if necessary, before the upcoming mid-term week.',
      ],
      sign: 'Sadia Akter (Class Rep)\nID: 213-35-4128 · SWE · 4th Year',
      routedTo: 'Head of Department · SWE',
    },
    complaint: {
      problem: 'I want to file a formal complaint about a delayed grade revision request that has not been processed for three weeks.',
      to: 'The Controller of Examinations\nDaffodil International University',
      subject: 'Complaint regarding pending grade revision request (ID 213-35-4128)',
      body: [
        'I, Sadia Akter, submitted a formal grade-revision request through the examination portal on May 3, 2026, regarding the course CSE-411. As of today, three weeks have passed without any acknowledgement of the request.',
        'University policy stipulates that grade-revision queries are to be acknowledged within seven working days. The absence of communication has caused understandable concern, particularly as the final transcript window approaches.',
        'I would be grateful for an update on the status of this request, and respectfully request that the matter be expedited.',
      ],
      sign: 'Sadia Akter\nID: 213-35-4128 · Software Engineering',
      routedTo: 'Controller of Examinations',
    },
    gd: {
      problem: 'My mobile phone (Samsung A54) was snatched at Mirpur-10 circle on the evening of May 18 around 9:30 PM by two suspects on a motorbike.',
      to: 'The Officer-in-Charge\nMirpur Model Thana, Dhaka',
      subject: 'General Diary — mobile phone theft incident, Mirpur-10 (May 18, 2026)',
      body: [
        'I, Sadia Akter, daughter of Mr. Aminul Akter, residing at House 14/B, Road 3, Sobhanbag, Dhaka-1207, wish to report the following matter for record.',
        'On May 18, 2026, at approximately 9:30 PM, while crossing Mirpur-10 circle on foot, my mobile phone (Samsung Galaxy A54, IMEI 359****2189) was forcibly snatched by two unknown individuals on a black motorbike. The incident occurred near the central island. I was not physically harmed.',
        'I respectfully request that this matter be entered as a General Diary, and that the IMEI be circulated for tracing. I have attached a copy of the device purchase invoice and my national ID.',
      ],
      sign: 'Sadia Akter\nNID: 1990-●●●●●●●●● · +880 1521 ●●●●●●',
      routedTo: 'Mirpur Model Thana · GD entry',
    },
  };
  const data = presets[kind] || presets.application;
  const [step, setStep] = _useS(2); // 1: write problem · 2: review draft · 3: submit
  const [submitted, setSubmitted] = _useS(false);

  return (
    <>
      <Header back/>

      <div style={{ padding: '4px 20px 0' }}>
        <div className="ai-tag" style={{ marginBottom: 6 }}>
          <IconSparkles size={10} stroke="var(--gold)"/> Anchor AI · drafted in 2.1s
        </div>
        <h1 className="h-display" style={{ margin: '4px 0 4px', fontSize: 26, lineHeight: 1.05 }}>
          {kind === 'gd' ? 'Your General Diary, drafted.' : 'Your application, drafted.'}
        </h1>
        <div style={{ fontSize: 13, color: 'var(--muted)', fontFamily: 'var(--font-serif)', fontStyle: 'italic' }}>
          Review carefully before submitting. You can edit any line.
        </div>
      </div>

      {/* Steps strip */}
      <div style={{ padding: '14px 20px 4px', display: 'flex', alignItems: 'center', gap: 8 }}>
        {[
          { i: 1, t: 'Describe' },
          { i: 2, t: 'Review draft' },
          { i: 3, t: 'Submit' },
        ].map((s, idx, arr) => (
          <React.Fragment key={s.i}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span className={`step-badge ${step > s.i ? 'done' : ''}`} style={{
                background: step >= s.i ? accent : 'var(--mist-2)',
                color: step >= s.i ? '#F7F3EE' : 'var(--muted)',
              }}>
                {step > s.i ? <IconCheck size={11} sw={3}/> : s.i}
              </span>
              <span style={{
                fontSize: 11, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase',
                color: step === s.i ? 'var(--navy)' : 'var(--muted)',
              }}>{s.t}</span>
            </div>
            {idx < arr.length - 1 && <span style={{ flex: 1, height: 1, background: 'var(--mist-2)' }}/>}
          </React.Fragment>
        ))}
      </div>

      {/* Problem prompt (collapsed) */}
      <div style={{ padding: '10px 20px 0' }}>
        <div style={{
          padding: '12px 14px', borderRadius: 12,
          background: 'rgba(255,255,255,0.6)', border: '1px solid var(--mist)',
        }}>
          <div className="eyebrow" style={{ marginBottom: 4 }}>You told Anchor AI</div>
          <div className="serif" style={{ fontStyle: 'italic', fontSize: 13.5, color: 'var(--ink)', lineHeight: 1.5 }}>
            “{data.problem}”
          </div>
          <button onClick={() => setStep(1)} style={{
            marginTop: 8, background: 'transparent', border: 'none', cursor: 'pointer',
            fontFamily: 'var(--font-serif)', fontStyle: 'italic', fontSize: 12, color: accent,
            padding: 0,
          }}>Edit your description →</button>
        </div>
      </div>

      {/* Doc paper */}
      <div style={{ padding: '14px 20px 4px' }}>
        <div className="doc-paper">
          <div className="doc-header">
            <span>Generated · {new Date().toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}</span>
            <span style={{ color: 'var(--gold)' }}>AI draft · review required</span>
          </div>
          <div className="doc-line lbl">To</div>
          <div className="doc-line" style={{ whiteSpace: 'pre-line' }}>{data.to}</div>
          <div className="doc-line subject">Subject: {data.subject}</div>
          <div className="doc-body">
            {data.body.map((p, i) => <p key={i}>{p}</p>)}
          </div>
          <div className="doc-sig">
            <em>Sincerely,</em><br/>
            <span style={{ whiteSpace: 'pre-line' }}>{data.sign}</span>
          </div>
        </div>
      </div>

      {/* Routing info */}
      <div style={{ padding: '12px 20px 0' }}>
        <div style={{
          padding: '10px 14px', borderRadius: 12,
          background: 'rgba(255,255,255,0.6)', border: '1px solid var(--mist)',
          display: 'flex', alignItems: 'center', gap: 10,
        }}>
          <div style={{
            width: 30, height: 30, borderRadius: 8, background: 'var(--cream-2)',
            border: '1px solid var(--mist)', display: 'flex',
            alignItems: 'center', justifyContent: 'center', color: accent,
          }}><IconRoute size={15}/></div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div className="eyebrow" style={{ marginBottom: 2 }}>Will be routed to</div>
            <div style={{ fontSize: 12.5, color: 'var(--navy)', fontWeight: 500 }}>{data.routedTo}</div>
          </div>
        </div>
      </div>

      {/* Actions */}
      <div style={{ padding: '16px 20px 28px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <button className="btn btn-ghost"><IconUpload size={15}/> Attach evidence</button>
        <button
          onClick={() => { setSubmitted(true); setStep(3); }}
          style={{
            padding: '12px 18px', borderRadius: 12, border: 'none', cursor: 'pointer',
            background: accent, color: '#F7F3EE',
            fontFamily: 'var(--font-sans)', fontSize: 15, fontWeight: 500,
            display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8,
          }}>
          <IconArrowUp size={15}/> {kind === 'gd' ? 'File GD' : 'Submit'}
        </button>
      </div>

      {submitted && (
        <div style={{
          position: 'sticky', bottom: 80, margin: '0 20px 20px',
          padding: 14, borderRadius: 12, background: '#0F2A1F', color: '#F7F3EE',
          border: '1px solid rgba(74,107,92,0.6)',
        }}>
          <div className="eyebrow" style={{ color: 'rgba(247,243,238,0.6)', marginBottom: 4 }}>Submitted</div>
          <div style={{ fontSize: 13.5, lineHeight: 1.45 }}>
            Your draft has been routed to <strong>{data.routedTo}</strong>. Track progress in <button onClick={() => go('cases')} style={{ background:'transparent', border:'none', color:'#F7F3EE', textDecoration:'underline', cursor:'pointer', padding:0, font:'inherit' }}>My Cases</button>.
          </div>
        </div>
      )}
    </>
  );
}

// ═══════════════════════════════════════════════════════════════
//  RIGHTS SCREEN — Know your rights (national mode)
// ═══════════════════════════════════════════════════════════════
function RightsScreen() {
  const rights = [
    { tag: 'Personal safety',
      title: 'Right against harassment in public spaces',
      cite: 'Penal Code 1860 · § 509',
      desc: 'Any word, gesture, or act intended to insult the modesty of a woman is punishable with imprisonment up to one year, or fine, or both.',
    },
    { tag: 'Cyber',
      title: 'Right to lodge cyber-harassment complaint',
      cite: 'Cyber Security Act 2023 · § 25',
      desc: 'Targeted online harassment is a cognizable offence. You may file at the Cyber Police Centre or any thana, which will forward it to the Cyber Tribunal.',
    },
    { tag: 'Custody',
      title: 'Right to inform a relative on arrest',
      cite: 'CrPC § 60A · Constitution Art. 33',
      desc: 'On arrest, you must be informed of the grounds, allowed to consult a lawyer of your choice, and produced before a magistrate within twenty-four hours.',
    },
    { tag: 'Workplace',
      title: 'Right to a safe workplace',
      cite: 'High Court Directive 2009',
      desc: 'Every workplace, including educational institutions, must have a complaint committee for sexual harassment, chaired by a woman.',
    },
    { tag: 'Domestic',
      title: 'Right to seek protection order',
      cite: 'DV (Prevention & Protection) Act 2010',
      desc: 'Victims of domestic violence may apply for a residence order, protection order, or compensation through a court of magistrate.',
    },
    { tag: 'Privacy',
      title: 'Right to data privacy and consent',
      cite: 'Constitution Art. 43',
      desc: 'Every citizen has the right to privacy of correspondence and communication. Surveillance without due process is unconstitutional.',
    },
  ];

  return (
    <>
      <Header back/>
      <div style={{ padding: '4px 20px 4px' }}>
        <div className="eyebrow">Bangladesh · Civic rights</div>
        <h1 className="h-display" style={{ margin: '4px 0', fontSize: 26, lineHeight: 1.05 }}>
          Know your rights.
        </h1>
        <div style={{ fontSize: 13, color: 'var(--muted)', fontFamily: 'var(--font-serif)', fontStyle: 'italic' }}>
          Six rights that matter most for daily life. Tap any item for the full text and where to invoke it.
        </div>
      </div>

      <div style={{ padding: '16px 20px 28px' }}>
        {rights.map((r, i) => (
          <div key={i} style={{
            padding: '16px 0',
            borderBottom: i < rights.length - 1 ? '1px solid var(--mist)' : 'none',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span className="eyebrow" style={{ color: 'var(--ember-2)' }}>{r.tag}</span>
              <span style={{ width: 3, height: 3, borderRadius: 999, background: 'var(--mist-2)' }}/>
              <span className="cite" style={{ borderBottom: 'none' }}>{r.cite}</span>
            </div>
            <div className="serif" style={{ fontSize: 18, fontWeight: 500, color: 'var(--navy)', lineHeight: 1.15, letterSpacing: '-0.005em' }}>
              {r.title}
            </div>
            <p style={{ margin: '8px 0 0', fontSize: 13, color: 'var(--ink-2)', lineHeight: 1.55 }}>
              {r.desc}
            </p>
          </div>
        ))}
      </div>
    </>
  );
}

Object.assign(window, {
  NewsArt, FeedRowMini, ComposeScreen, RightsScreen,
});
