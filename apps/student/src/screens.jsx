// Anchor — Screens part 1: Home, Chat, Alert (the three signature screens)
// Depends globally on icons.jsx + app.jsx (useApp, Header, C2CToggle)

const { useState: _useS, useEffect: _useE, useRef: _useR } = React;

// ═══════════════════════════════════════════════════════════════
//  iOS INSTALL BANNER — additive, iOS-only (no effect on Android)
// ═══════════════════════════════════════════════════════════════
// On iOS, WebKit delivers web push ONLY to a PWA added to the Home Screen via
// Safari. A plain Safari tab, and iOS Chrome (CriOS) entirely, can never receive
// push — which is why alerts work on Android but not iPhone. This banner tells
// iPhone users the one thing that makes alerts possible: install via Safari.
// It renders nothing unless window.getPushCapability() reports an iOS device that
// is not yet installed, so Android / desktop are completely unaffected.
function IOSInstallBanner({ persistDismiss = true }) {
  const cap = (typeof window !== 'undefined' && window.getPushCapability)
    ? window.getPushCapability() : null;
  const [dismissed, setDismissed] = _useS(
    () => persistDismiss && localStorage.getItem('anchor_ios_install_dismissed') === 'true'
  );

  if (!cap || !cap.isIOS || cap.isStandalone) return null;            // not iOS, or already installed → nothing
  if (cap.reason !== 'ios-needs-install' && cap.reason !== 'ios-chrome') return null;
  if (dismissed) return null;

  const isChrome = cap.reason === 'ios-chrome';
  const title = isChrome ? 'Open in Safari to get alerts' : 'Add Anchor to your Home Screen';
  const body = isChrome
    ? 'On iPhone, alerts work only through Safari. Open Anchor in Safari, then Share → Add to Home Screen.'
    : 'To receive emergency push alerts on iPhone: tap Share, then “Add to Home Screen”, and open Anchor from the icon.';

  const onClose = () => {
    setDismissed(true);
    if (persistDismiss) { try { localStorage.setItem('anchor_ios_install_dismissed', 'true'); } catch (_) {} }
  };

  return (
    <div style={{ padding: '8px 20px 0' }}>
      <div style={{
        display: 'flex', alignItems: 'flex-start', gap: 12,
        padding: '12px 14px', borderRadius: 14,
        background: 'rgba(184,137,58,0.08)', border: '1px solid rgba(184,137,58,0.30)',
      }}>
        <div style={{ flexShrink: 0, width: 30, height: 30, borderRadius: 999,
          background: 'rgba(184,137,58,0.16)', display: 'flex',
          alignItems: 'center', justifyContent: 'center', color: 'var(--gold)' }}>
          {/* iOS share glyph */}
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 16V4"/><path d="m7 9 5-5 5 5"/>
            <path d="M5 13v6a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-6"/>
          </svg>
        </div>
        <div style={{ flex: 1, lineHeight: 1.4 }}>
          <div className="serif" style={{ fontSize: 13.5, fontWeight: 500, color: 'var(--navy)' }}>{title}</div>
          <div style={{ marginTop: 3, fontSize: 11.5, color: 'var(--ink-2)' }}>{body}</div>
        </div>
        <button onClick={onClose} aria-label="Dismiss" style={{
          flexShrink: 0, background: 'none', border: 'none', cursor: 'pointer',
          color: 'var(--muted)', fontSize: 16, lineHeight: 1, padding: 0,
        }}>×</button>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════
//  HOME SCREEN
// ═══════════════════════════════════════════════════════════════
function HomeScreen() {
  const { mode, go, lang, auth, tr } = useApp();
  const accent = mode === 'campus' ? 'var(--sage)' : 'var(--ember)';
  const isStudent = auth?.user?.role === 'student';

  // Live filings preview — replace demo data with real API cases
  const [previewFilings, setPreviewFilings] = _useS([]);
  _useE(() => {
    if (typeof filingApiFetch !== 'function') return;
    filingApiFetch('/v1/filings?page=1')
      .then(data => setPreviewFilings((data || []).slice(0, 3)))
      .catch(() => {});
  }, [mode]);

  // Live verification feed preview — refresh-aware via the shared fetch helper
  const [feedPosts, setFeedPosts] = _useS([]);
  _useE(() => {
    if (typeof apiFetch !== 'function') return;
    if (!localStorage.getItem('anchor_access_token')) return;
    const hasTenant = !!auth?.user?.tenant_id;
    const scope = (mode === 'campus' && hasTenant) ? 'campus' : 'national';
    apiFetch(`/v1/feed?scope=${scope}&sort=recent&page_size=3`)
      .then(data => { if (Array.isArray(data) && data.length) setFeedPosts(data); })
      .catch(() => {});
  }, [mode]);

  const campusTiles = [
    { k: 'complaint', label: tr('tile_file'), sub: tr('tile_file_sub'), Icon: IconFile, route: 'new-filing' },
    { k: 'application', label: tr('tile_apply'), sub: tr('tile_apply_sub'), Icon: IconDoc, route: 'applications' },
    { k: 'routine',   label: tr('tile_routine'), sub: tr('tile_routine_sub'),  Icon: IconClock,  route: 'routines' },
    { k: 'notices',   label: tr('tile_notices'), sub: tr('tile_notices_sub'),   Icon: IconNews, route: 'notices' },
    { k: 'my-filings', label: tr('tile_my_filings'), sub: tr('tile_my_filings_sub'), Icon: IconFile, route: 'filings' },
    { k: 'classroom', label: tr('tile_classroom'), sub: tr('tile_classroom_sub'), Icon: IconBuilding, route: 'classroom-report' },
    { k: 'feed',      label: tr('tile_feed'),   sub: tr('tile_feed_sub_campus'),     Icon: IconNews, route: 'feed-publish' },
    { k: 'rate',      label: tr('tile_rate'), sub: tr('tile_rate_sub'),     Icon: IconStar,   route: 'dept-rating' },
  ];

  const countryTiles = [
    { k: 'fir',     label: tr('tile_fir'),   sub: tr('tile_fir_sub'), Icon: IconGavel,  route: 'police-reports' },
    { k: 'lawyer',  label: tr('tile_lawyer'),    sub: tr('tile_lawyer_sub'), Icon: IconScale,  route: 'lawyers' },
    { k: 'zones',   label: tr('tile_zones'),     sub: tr('tile_zones_sub'),  Icon: IconMap,    route: 'map' },
    { k: 'rights',  label: tr('tile_rights'), sub: tr('tile_rights_sub'), Icon: IconBook, route: 'rights' },
    { k: 'feed',    label: tr('tile_feed'),  sub: tr('tile_feed_sub_national'),     Icon: IconNews,   route: 'feed-publish' },
    { k: 'officer', label: tr('tile_officer'),sub: tr('tile_officer_sub'), Icon: IconBadge, route: 'officer-scorecard' },
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
              {tr('home_choose_context')}
            </div>
            <C2CToggle/>
            <div style={{
              marginTop: 10, fontFamily: 'var(--font-serif)', fontStyle: 'italic',
              fontSize: 13, color: 'var(--muted)', textAlign: 'center', letterSpacing: '0.005em',
            }}>
              {mode === 'campus'
                ? tr('home_campus_tag')
                : tr('home_national_tag')}
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
                {tr('home_national_title')}
              </div>
              <div style={{ fontSize: 12, color: 'var(--muted)', fontFamily: 'var(--font-sans)' }}>
                {tr('home_national_sub')}
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
            <div className="eyebrow eyebrow-dark" style={{ color: 'rgba(247,243,238,0.55)' }}>{tr('home_alert_eyebrow')}</div>
            <div style={{ fontSize: 13, marginTop: 2 }}>{tr('home_alert_text')}</div>
          </div>
          <button onClick={() => go('alert')} style={{
            background: 'var(--red)', color: '#fff', border: 'none', cursor: 'pointer',
            padding: '8px 12px', borderRadius: 999, fontFamily: 'var(--font-sans)',
            fontSize: 11, fontWeight: 600, letterSpacing: '0.1em', textTransform: 'uppercase',
          }}>{tr('home_alert_hold')}</button>
        </div>
      </div>

      {/* iOS-only: how to actually receive alerts (no-op on Android) */}
      <IOSInstallBanner/>

      {/* AI chat input */}
      <div style={{ padding: '14px 20px 6px' }}>
        <AIInputCard onActivate={() => go('chat')}/>
      </div>

      {/* Quick action tiles */}
      <div style={{ padding: '20px 20px 8px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10 }}>
          <div className="eyebrow">{tr('home_quick_actions')} · {mode === 'campus' ? tr('c2c_campus') : tr('c2c_national')}</div>
          <div className="serif" style={{ fontStyle: 'italic', fontSize: 12, color: 'var(--muted)' }}>{tiles.length} {tr('home_routes')}</div>
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

      {/* My Cases preview — real filings from API */}
      <div style={{ padding: '20px 0 8px 20px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', paddingRight: 20, marginBottom: 10 }}>
          <div className="eyebrow">{tr('home_my_filings')}</div>
          <button onClick={() => go('cases')} style={{
            background: 'transparent', border: 'none', cursor: 'pointer',
            color: 'var(--navy)', fontSize: 12, fontFamily: 'var(--font-serif)', fontStyle: 'italic',
          }}>{tr('home_view_all')}</button>
        </div>
        {previewFilings.length === 0 ? (
          /* Empty state — no filed cases yet */
          <div style={{ paddingRight: 20 }}>
            <button onClick={() => go('new-filing')} style={{
              width: '100%', textAlign: 'left', background: 'rgba(255,255,255,0.6)',
              border: '1px dashed var(--mist-2)', borderRadius: 14, padding: '14px 16px', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: 12,
            }}>
              <div style={{
                width: 36, height: 36, borderRadius: 10, flexShrink: 0,
                background: `${accent}15`, display: 'flex', alignItems: 'center', justifyContent: 'center', color: accent,
              }}>
                <IconFile size={16}/>
              </div>
              <div>
                <div className="serif" style={{ fontSize: 13.5, fontWeight: 500, color: 'var(--navy)', marginBottom: 2 }}>{tr('home_no_filings_title')}</div>
                <div style={{ fontSize: 11.5, color: 'var(--muted)' }}>{tr('home_no_filings_sub')}</div>
              </div>
              <IconChevronRight size={14} stroke="var(--mist-2)" style={{ marginLeft: 'auto', flexShrink: 0 }}/>
            </button>
          </div>
        ) : (
          <div className="h-scroll no-scrollbar" style={{ paddingRight: 20 }}>
            {previewFilings.map(f => {
              const stateMap = {
                draft: 'submitted', moderation_queue: 'review', routed: 'review',
                subject_notified: 'review', subject_responded: 'review', under_review: 'review',
                resolved: 'resolved', dismissed: 'resolved', withdrawn: 'resolved',
              };
              const displayState = stateMap[f.state] || 'submitted';
              return (
                <button key={f.id} onClick={() => go('filing', { id: f.id })} style={{
                  width: 240, flexShrink: 0, textAlign: 'left', background: 'rgba(255,255,255,0.7)',
                  border: '1px solid var(--mist)', borderRadius: 14, padding: 14, cursor: 'pointer',
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                    <span className="mono" style={{ fontSize: 10, color: 'var(--muted)' }}>
                      {f.filing_number || 'Draft'}
                    </span>
                    <StatusPill status={displayState}/>
                  </div>
                  <div className="serif" style={{ fontSize: 14, fontWeight: 500, color: 'var(--navy)', lineHeight: 1.25, marginBottom: 6 }}>
                    {f.template?.name || f.category}
                  </div>
                  <Stepper status={displayState}/>
                  <div style={{ marginTop: 8, fontSize: 11, color: 'var(--muted)' }}>
                    {f.state.replace(/_/g, ' ')} · {new Date(f.updated_at || f.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Verification feed preview */}
      <div style={{ padding: '16px 20px 28px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 10 }}>
          <div className="eyebrow">{mode === 'campus' ? tr('home_campus_verified') : tr('home_verified_news')}</div>
          <button onClick={() => go('news-feed')} style={{
            background: 'transparent', border: 'none', cursor: 'pointer',
            color: 'var(--muted)', fontSize: 11.5, fontFamily: 'var(--font-serif)', fontStyle: 'italic',
          }}>{tr('home_newspaper')}</button>
        </div>
        {(feedPosts.length
          ? feedPosts
          : FEED.filter(f => f.scope === mode)
        ).slice(0, 2).map(f => (
          <FeedRowMini
            key={f.id}
            item={f}
            onOpen={f.post_number ? () => go('feed-post', { id: f.id }) : undefined}
          />
        ))}
      </div>
    </>
  );
}

function AIInputCard({ onActivate }) {
  const { lang: rawLang, setLang } = useApp();
  // Content surface: "Both" (BI) shows Bangla. Collapse BI→BN for display.
  const lang = (typeof contentLang === 'function') ? contentLang(rawLang)
                                                   : ((rawLang === 'BN' || rawLang === 'BI') ? 'BN' : 'EN');
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
const AI_BASE = window.ANCHOR_API_URL || 'http://localhost:8000';

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
  const { lang: rawLang, setLang, mode, go } = useApp();
  // Chat is content: "Both" (BI) renders Bangla, and the backend only knows
  // EN/BN — collapse BI→BN so 'BI' is never sent or branched on as English.
  const lang = (typeof contentLang === 'function') ? contentLang(rawLang)
                                                   : ((rawLang === 'BN' || rawLang === 'BI') ? 'BN' : 'EN');
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
//  ALERT SCREEN — 3-phase emergency (spec-compliant)
// ═══════════════════════════════════════════════════════════════

const API_BASE = window.ANCHOR_API_URL || 'http://localhost:8000';

async function alertApiPost(path, body, token) {
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(API_BASE + path, {
    method: 'POST', headers, body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function alertApiGet(path, token) {
  const headers = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  const res = await fetch(API_BASE + path, { headers });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

function AlertScreen() {
  const { back, go, auth } = useApp();
  const [phase, setPhase] = _useS('during');
  const [holding, setHolding] = _useS(false);
  const [progress, setProgress] = _useS(0);
  const [showConfirm, setShowConfirm] = _useS(false);
  const [activated, setActivated] = _useS(false);
  const [alertEventId, setAlertEventId] = _useS(null);
  const [responderCount, setResponderCount] = _useS(0);
  const [safeMarked, setSafeMarked] = _useS(false);
  const [sending, setSending] = _useS(false);
  const [gpsResult, setGpsResult] = _useS(null);
  const [gpsRetrying, setGpsRetrying] = _useS(false);
  const [noticeMsg, setNoticeMsg] = _useS(null);
  const startRef = _useR(null);
  const rafRef = _useR(null);
  const token = localStorage.getItem('anchor_access_token');

  // Pre-check GPS when confirmation modal opens so the warning appears before the user taps SEND
  _useE(() => {
    if (!showConfirm) { setGpsResult(null); return; }
    if (!navigator.geolocation) { setGpsResult({ gps_status: 'unavailable' }); return; }
    // iOS often returns POSITION_UNAVAILABLE quickly for low-accuracy requests, so
    // give iPhones high accuracy + a longer timeout. Android keeps its original
    // (fast, low-accuracy) options since it works well there.
    const isIOS = !!(window.getPushCapability && window.getPushCapability().isIOS);
    const gpsOpts = isIOS
      ? { timeout: 15000, maximumAge: 30000, enableHighAccuracy: true }
      : { timeout: 10000, maximumAge: 30000, enableHighAccuracy: false };
    navigator.geolocation.getCurrentPosition(
      (pos) => setGpsResult({
        lat: pos.coords.latitude,
        lng: pos.coords.longitude,
        gps_accuracy_m: pos.coords.accuracy ? Math.round(pos.coords.accuracy) : null,
        gps_status: 'ok',
      }),
      // Attach the error code so the UI can show specific guidance (1=permission
      // denied, 2=position unavailable, 3=timeout) instead of a flat failure.
      (err) => setGpsResult({ gps_status: 'unavailable', gps_error_code: err && err.code }),
      gpsOpts
    );
  }, [showConfirm]);

  // Retry with a longer timeout + high accuracy when the quick pre-check failed —
  // on phones the first fix is often denied/slow; a deliberate retry frequently
  // succeeds and lets the alert carry real coordinates instead of "no GPS".
  const retryGps = () => {
    if (!navigator.geolocation) { setGpsResult({ gps_status: 'unavailable' }); return; }
    setGpsRetrying(true);
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setGpsResult({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          gps_accuracy_m: pos.coords.accuracy ? Math.round(pos.coords.accuracy) : null,
          gps_status: 'ok',
        });
        setGpsRetrying(false);
      },
      (err) => { setGpsResult({ gps_status: 'unavailable', gps_error_code: err && err.code }); setGpsRetrying(false); },
      { timeout: 20000, maximumAge: 0, enableHighAccuracy: true }
    );
  };

  const startHold = () => {
    if (activated || showConfirm) return;
    setHolding(true);
    startRef.current = performance.now();
    const tick = () => {
      const elapsed = (performance.now() - startRef.current) / 1000;
      const p = Math.min(elapsed / 4, 1);
      setProgress(p);
      if (p >= 1) {
        setHolding(false);
        setShowConfirm(true);  // show confirmation modal instead of activating immediately
        return;
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
  };

  const cancelHold = () => {
    if (activated || showConfirm) return;
    setHolding(false); setProgress(0);
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
  };

  const handleConfirmSend = async () => {
    setSending(true);
    try {
      // Use cached GPS result from the pre-check that ran when the modal opened
      const gpsPayload = gpsResult || { gps_status: 'unavailable' };
      const data = await alertApiPost('/v1/alerts/trigger', gpsPayload, token);
      // The backend returns 200 with state='rate_limited' (and a throwaway
      // event_id that is never persisted) when the per-user daily alert limit
      // is hit. Do NOT enter the tracking screen with that fake id — it would
      // poll /responders forever and 404. Surface the message instead.
      if (data.state === 'rate_limited' || !data.event_id) {
        setNoticeMsg(data.message || 'You have already triggered an alert recently. If this is a continuing emergency, call 999.');
        return;
      }
      setNoticeMsg(null);
      setAlertEventId(data.event_id);
      setActivated(true);
    } catch (e) {
      console.error('[Alert] Trigger failed:', e);
      setActivated(true);  // still show activated state even if offline
    } finally {
      setSending(false);
      setShowConfirm(false);
    }
  };

  const handleCancelConfirm = () => {
    setShowConfirm(false);
    setProgress(0);
    setHolding(false);
  };

  const handleMarkSafe = async () => {
    if (alertEventId) {
      try {
        await alertApiPost(`/v1/alerts/${alertEventId}/safe`, {}, token);
      } catch (e) { console.error(e); }
    }
    setSafeMarked(true);
    back();
  };

  const handleNeedMoreHelp = async () => {
    if (alertEventId) {
      try {
        await alertApiPost(`/v1/alerts/${alertEventId}/need_more_help`, {}, token);
      } catch (e) { console.error(e); }
    }
  };

  const phaseLabel = { before: 'Before', during: 'During', after: 'After' };

  return (
    <div style={{
      minHeight: '100%', position: 'relative',
      background: phase === 'during'
        ? 'linear-gradient(180deg, #0A0A0C 0%, #161013 100%)'
        : 'var(--cream)',
      color: phase === 'during' ? '#F7F3EE' : 'var(--ink)',
      paddingBottom: 20,
    }}>
      {/* Confirmation modal overlay */}
      {showConfirm && (
        <ConfirmAlertModal
          onConfirm={handleConfirmSend}
          onCancel={handleCancelConfirm}
          sending={sending}
          gpsUnavailable={gpsResult?.gps_status === 'unavailable'}
          gpsErrorCode={gpsResult?.gps_error_code}
          onRetryGps={retryGps}
          retryingGps={gpsRetrying}
        />
      )}

      {/* Header */}
      <div style={{ padding: '60px 20px 14px', display: 'flex', alignItems: 'center', gap: 10 }}>
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
          Emergency · Phase {['before','during','after'].indexOf(phase) + 1}
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
          marginTop: 8, fontSize: 13,
          color: phase === 'during' ? 'rgba(247,243,238,0.6)' : 'var(--muted)',
          fontFamily: 'var(--font-serif)', fontStyle: 'italic', lineHeight: 1.45,
        }}>
          {activated
            ? 'Trusted contacts and nearby users have been notified. Mark yourself safe when ready.'
            : 'Hold the button for four seconds. Your proctor, nearby users, and contacts will be notified.'}
        </div>
      </div>

      {/* Rate-limit / notice banner */}
      {noticeMsg && !activated && (
        <div style={{
          margin: '8px 20px 0', padding: '12px 14px', borderRadius: 12,
          background: 'rgba(232,49,42,0.10)', border: '1px solid rgba(232,49,42,0.35)',
          color: phase === 'during' ? '#FCD9D7' : '#8A1B16',
          fontFamily: 'var(--font-sans)', fontSize: 12.5, lineHeight: 1.45,
          display: 'flex', alignItems: 'flex-start', gap: 8,
        }}>
          <span style={{ flex: 1 }}>{noticeMsg}</span>
          <button onClick={() => setNoticeMsg(null)} style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'inherit', fontWeight: 700, fontSize: 14, lineHeight: 1, padding: 0,
          }}>×</button>
        </div>
      )}

      {/* Phase tabs */}
      <div style={{ padding: '14px 20px 4px' }}>
        <div className="tabbar" style={{
          background: phase === 'during' ? 'rgba(255,255,255,0.06)' : 'var(--cream-2)',
          borderColor: phase === 'during' ? 'rgba(255,255,255,0.1)' : 'var(--mist)',
        }}>
          {['before', 'during', 'after'].map(p => (
            <button key={p} onClick={() => setPhase(p)}
              className={phase === p ? 'on' : ''}
              style={phase === p
                ? { background: phase === 'during' ? '#E8312A' : 'var(--navy)' }
                : { color: phase === 'during' ? 'rgba(247,243,238,0.7)' : 'var(--ink-2)' }}>
              <span style={{ textTransform: 'capitalize' }}>{p}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Body */}
      <div style={{ padding: '18px 20px 32px' }}>
        {phase === 'before' && <AlertBefore token={token}/>}
        {phase === 'during' && (
          <AlertDuring
            holding={holding} progress={progress} activated={activated}
            eventId={alertEventId} gpsResult={gpsResult} token={token}
            onDown={startHold} onUp={cancelHold}
            responderCount={responderCount}
            onCount={setResponderCount}
            onMarkSafe={handleMarkSafe}
            onNeedMoreHelp={handleNeedMoreHelp}
          />
        )}
        {phase === 'after' && <AlertAfter eventId={alertEventId} token={token} go={go}/>}
      </div>
    </div>
  );
}

// ─── Double-confirmation modal (anti-trap, spec §4.2) ────────────────────────
function ConfirmAlertModal({ onConfirm, onCancel, sending, gpsUnavailable, gpsErrorCode, onRetryGps, retryingGps }) {
  const [btnEnabled, setBtnEnabled] = _useS(false);
  const _isIOS = !!(window.getPushCapability && window.getPushCapability().isIOS);
  // iOS-only extra hint based on the geolocation error code (1=denied, 2=unavailable, 3=timeout).
  const iosGpsHint = (_isIOS && gpsUnavailable)
    ? (gpsErrorCode === 1
        ? 'On iPhone: Settings → Privacy & Security → Location Services → Safari → While Using, and turn on Precise Location.'
        : 'On iPhone, move near a window or outdoors and tap Retry — the first GPS fix can take a few seconds.')
    : null;

  _useE(() => {
    // 1-second minimum delay before SEND button is enabled (spec §4.2)
    const t = setTimeout(() => setBtnEnabled(true), 1000);
    return () => clearTimeout(t);
  }, []);

  return (
    <div style={{
      position: 'absolute', inset: 0, zIndex: 100,
      background: 'rgba(5,5,8,0.96)', display: 'flex',
      flexDirection: 'column', justifyContent: 'center',
      padding: '32px 24px', boxSizing: 'border-box',
    }}>
      {/* Icon */}
      <div style={{
        width: 56, height: 56, borderRadius: 999,
        background: 'rgba(232,49,42,0.15)', border: '1px solid rgba(232,49,42,0.4)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        marginBottom: 20,
      }}>
        <IconShield size={26} sw={1.5} stroke="#E8312A"/>
      </div>

      <div className="serif" style={{ fontSize: 22, fontWeight: 500, color: '#F7F3EE', marginBottom: 10 }}>
        Send emergency alert?
      </div>
      <div style={{ fontSize: 13, color: 'rgba(247,243,238,0.65)', lineHeight: 1.6, marginBottom: 24 }}>
        This action will immediately:
      </div>

      {/* What will happen */}
      {[
        'Create an anonymous alert event',
        'Notify your campus proctor via push + email',
        'Alert verified users within 1km of you',
        'Start 10-second video recording (stays on device)',
        'Share your GPS with emergency contacts',
      ].map((item, i) => (
        <div key={i} style={{
          display: 'flex', alignItems: 'flex-start', gap: 10,
          marginBottom: 10, fontSize: 13, color: 'rgba(247,243,238,0.85)',
        }}>
          <div style={{
            flexShrink: 0, width: 18, height: 18, borderRadius: 999,
            background: 'rgba(232,49,42,0.2)', border: '1px solid rgba(232,49,42,0.5)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            marginTop: 1,
          }}>
            <div style={{ width: 5, height: 5, borderRadius: 999, background: '#E8312A' }}/>
          </div>
          {item}
        </div>
      ))}

      {gpsUnavailable && (
        <div style={{
          marginTop: 8, padding: '10px 12px', borderRadius: 10,
          background: 'rgba(184,137,58,0.12)', border: '1px solid rgba(184,137,58,0.35)',
          fontSize: 12, color: 'rgba(184,137,58,0.95)', lineHeight: 1.5,
        }}>
          ⚠️ Location unavailable — nearby users won't receive an alert. Your proctor will still be notified.
          {iosGpsHint && (
            <div style={{ marginTop: 6, fontSize: 11.5, color: 'rgba(184,137,58,0.85)' }}>{iosGpsHint}</div>
          )}
          {onRetryGps && (
            <button onClick={onRetryGps} disabled={retryingGps}
              style={{
                display: 'block', marginTop: 8, padding: '6px 12px', borderRadius: 8,
                border: '1px solid rgba(184,137,58,0.5)', background: 'transparent',
                color: 'rgba(184,137,58,0.95)', fontSize: 12, fontWeight: 600,
                cursor: retryingGps ? 'default' : 'pointer', fontFamily: 'var(--font-sans)',
              }}>
              {retryingGps ? 'Locating…' : 'Retry location'}
            </button>
          )}
        </div>
      )}

      <div style={{
        marginTop: 8, padding: '10px 12px', borderRadius: 10,
        background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
        fontSize: 11.5, color: 'rgba(247,243,238,0.5)', lineHeight: 1.5,
      }}>
        This action is logged and cannot be undone. Daily limit: 1 alert per day.
      </div>

      <div style={{ display: 'flex', gap: 10, marginTop: 24 }}>
        <button onClick={onCancel} style={{
          flex: 1, padding: '14px 0', borderRadius: 12,
          background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.12)',
          color: 'rgba(247,243,238,0.8)', fontFamily: 'var(--font-sans)',
          fontSize: 13, fontWeight: 500, cursor: 'pointer',
        }}>
          Cancel
        </button>
        <button onClick={onConfirm} disabled={!btnEnabled || sending} style={{
          flex: 2, padding: '14px 0', borderRadius: 12,
          background: btnEnabled && !sending ? '#E8312A' : 'rgba(232,49,42,0.3)',
          border: 'none', color: '#fff',
          fontFamily: 'var(--font-sans)', fontSize: 14, fontWeight: 600,
          cursor: btnEnabled && !sending ? 'pointer' : 'not-allowed',
          transition: 'background 0.4s ease',
        }}>
          {sending ? 'Sending…' : btnEnabled ? 'SEND ALERT' : 'Hold on…'}
        </button>
      </div>
    </div>
  );
}

// ─── Live alert map (dark tactical) ──────────────────────────────────────────
// Shows the user's own location, the fan-out zone ring, and responders placed
// at their REAL distance but a randomised (privacy-preserving) bearing. The
// backend never returns responder coordinates — only distance_m.
const ALERT_MAP_DEFAULT = { lat: 23.7450, lng: 90.3718 };  // campus fallback (matches MapScreen)

// Deterministic 0–2π bearing from a stable key so a responder dot keeps its
// direction across polls (only the distance is real; the angle is obfuscated).
function _stableBearing(key) {
  let h = 0;
  const s = String(key || '');
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return (h % 360) * Math.PI / 180;
}

function AlertLiveMap({ eventId, gpsResult, token, onCount }) {
  const mapElRef = _useR(null);
  const mapRef = _useR(null);
  const userLayerRef = _useR(null);
  const zoneRingRef = _useR(null);
  const dotLayersRef = _useR([]);
  const [poll, setPoll] = _useS({ zoneRadiusM: null, responders: [] });
  const [reconnecting, setReconnecting] = _useS(false);

  const hasGps = gpsResult && gpsResult.gps_status === 'ok'
    && typeof gpsResult.lat === 'number' && typeof gpsResult.lng === 'number';
  const center = hasGps ? { lat: gpsResult.lat, lng: gpsResult.lng } : ALERT_MAP_DEFAULT;
  const leafletReady = typeof window !== 'undefined' && window.L;

  // 1) Init map once
  _useE(() => {
    if (!leafletReady || !mapElRef.current || mapRef.current) return;
    const map = L.map(mapElRef.current, {
      center: [center.lat, center.lng],
      zoom: hasGps ? 15 : 13,
      zoomControl: false,
      attributionControl: false,
    });
    // Dark tactical tiles (free, no key)
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      maxZoom: 19, detectRetina: true,
      attribution: '© OpenStreetMap © CARTO',
    }).addTo(map);
    mapRef.current = map;
    // Container mounts inside an already-laid-out view; nudge sizing just in case.
    setTimeout(() => { try { map.invalidateSize(); } catch (_) {} }, 120);

    // User beacon (only when we actually have the user's location)
    if (hasGps) {
      const icon = L.divIcon({
        className: '',
        html: '<div class="alert-beacon"><span class="alert-beacon-ring"></span><span class="alert-beacon-dot"></span></div>',
        iconSize: [22, 22], iconAnchor: [11, 11],
      });
      userLayerRef.current = L.marker([center.lat, center.lng], { icon, interactive: false }).addTo(map);
    }

    return () => {
      if (mapRef.current) { try { mapRef.current.remove(); } catch (_) {} mapRef.current = null; }
      userLayerRef.current = null; zoneRingRef.current = null; dotLayersRef.current = [];
    };
  }, [leafletReady]);

  // 2) Poll responders every 5s while the alert is live
  _useE(() => {
    if (!eventId) return;
    let cancelled = false;
    const tick = async () => {
      try {
        const data = await alertApiGet(`/v1/alerts/${eventId}/responders`, token);
        if (cancelled) return;
        setReconnecting(false);
        setPoll({ zoneRadiusM: data.zone_radius_m ?? null, responders: data.responders || [] });
        if (onCount) onCount(data.responder_count || 0);
      } catch (e) {
        if (cancelled) return;
        setReconnecting(true);  // keep last drawn state, surface a subtle indicator
        console.warn('[AlertMap] responder poll failed:', e.message);
      }
    };
    tick();
    const id = setInterval(tick, 5000);
    return () => { cancelled = true; clearInterval(id); };
  }, [eventId, token]);

  // 3) Draw zone ring + responder dots whenever poll data changes
  _useE(() => {
    const map = mapRef.current;
    if (!map) return;
    const radius = poll.zoneRadiusM || 1000;  // fall back to backend default if no zone

    // Zone ring
    if (zoneRingRef.current) { try { map.removeLayer(zoneRingRef.current); } catch (_) {} zoneRingRef.current = null; }
    if (poll.zoneRadiusM) {
      zoneRingRef.current = L.circle([center.lat, center.lng], {
        radius, color: '#E8312A', fillColor: '#E8312A', fillOpacity: 0.08, weight: 1.5, interactive: false,
      }).addTo(map);
    }

    // Responder dots — clear then redraw
    dotLayersRef.current.forEach(l => { try { map.removeLayer(l); } catch (_) {} });
    dotLayersRef.current = [];
    const cosLat = Math.cos(center.lat * Math.PI / 180) || 1e-9;
    poll.responders.forEach((r, i) => {
      const dist = (typeof r.distance_m === 'number' && r.distance_m >= 0) ? r.distance_m : radius / 2;
      const theta = _stableBearing(r.created_at || String(i));
      const dLat = (dist * Math.cos(theta)) / 111000;
      const dLng = (dist * Math.sin(theta)) / (111000 * cosLat);
      const icon = L.divIcon({
        className: '',
        html: '<div class="responder-dot"></div>',
        iconSize: [14, 14], iconAnchor: [7, 7],
      });
      const m = L.marker([center.lat + dLat, center.lng + dLng], { icon, interactive: false }).addTo(map);
      dotLayersRef.current.push(m);
    });
  }, [JSON.stringify(poll)]);

  if (!leafletReady) {
    return (
      <div style={{
        padding: '18px', borderRadius: 14, textAlign: 'center',
        background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.1)',
        fontSize: 12.5, color: 'rgba(247,243,238,0.6)',
      }}>
        Map unavailable on this device.
      </div>
    );
  }

  const count = poll.responders.length;
  return (
    <div style={{ position: 'relative', borderRadius: 14, overflow: 'hidden', border: '1px solid rgba(232,49,42,0.3)' }}>
      <div ref={mapElRef} style={{ height: 240, background: '#0A0A0C' }}/>

      {/* Count overlay */}
      <div style={{
        position: 'absolute', left: 10, bottom: 10, zIndex: 500,
        display: 'flex', alignItems: 'center', gap: 7,
        padding: '6px 11px', borderRadius: 999,
        background: 'rgba(10,10,12,0.82)', border: '1px solid rgba(232,49,42,0.4)',
        fontSize: 11.5, color: '#FFD9D7', fontFamily: 'var(--font-sans)', fontWeight: 600,
      }}>
        <span style={{ width: 7, height: 7, borderRadius: 999, background: '#E8312A',
          animation: 'statusPulse 1.5s ease-in-out infinite' }}/>
        {count} {count === 1 ? 'person' : 'people'} responding
      </div>

      {/* Location-unavailable banner */}
      {!hasGps && (
        <div style={{
          position: 'absolute', left: 10, right: 10, top: 10, zIndex: 500,
          padding: '7px 11px', borderRadius: 10, textAlign: 'center',
          background: 'rgba(184,137,58,0.18)', border: '1px solid rgba(184,137,58,0.4)',
          fontSize: 11, color: '#E8C57A', fontFamily: 'var(--font-sans)',
        }}>
          Location unavailable — map centered on campus
        </div>
      )}

      {/* Reconnecting indicator */}
      {reconnecting && (
        <div style={{
          position: 'absolute', right: 10, bottom: 10, zIndex: 500,
          padding: '5px 9px', borderRadius: 999,
          background: 'rgba(10,10,12,0.82)', border: '1px solid rgba(255,255,255,0.12)',
          fontSize: 10.5, color: 'rgba(247,243,238,0.6)', fontFamily: 'var(--font-sans)',
        }}>
          reconnecting…
        </div>
      )}
    </div>
  );
}

// ─── During phase ────────────────────────────────────────────────────────────
function AlertDuring({ holding, progress, activated, eventId, gpsResult, token, onDown, onUp, responderCount, onMarkSafe, onNeedMoreHelp, onCount }) {
  const circ = 2 * Math.PI * 102;

  if (activated) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
        {/* Alert sent confirmation */}
        <div style={{
          padding: '20px 18px', borderRadius: 16,
          background: 'rgba(232,49,42,0.1)', border: '1px solid rgba(232,49,42,0.3)',
          display: 'flex', alignItems: 'center', gap: 14,
        }}>
          <div style={{
            width: 40, height: 40, borderRadius: 999, flexShrink: 0,
            background: 'rgba(232,49,42,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <IconShield size={20} stroke="#E8312A"/>
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 14, color: '#FFD9D7' }}>Alert broadcast</div>
            <div style={{ fontSize: 12, color: 'rgba(247,243,238,0.65)', marginTop: 2 }}>
              Proctor and nearby users notified
            </div>
          </div>
        </div>

        {/* Live tactical map — your location, fan-out zone, responders */}
        <AlertLiveMap eventId={eventId} gpsResult={gpsResult} token={token} onCount={onCount}/>

        {/* "Help is coming" banner — appears the moment a nearby user confirms */}
        {responderCount > 0 && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            padding: '12px 14px', borderRadius: 12,
            background: 'rgba(74,107,92,0.18)', border: '1px solid rgba(74,107,92,0.5)',
          }}>
            <div style={{
              width: 30, height: 30, borderRadius: 999, flexShrink: 0,
              background: 'rgba(74,107,92,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <IconCheck size={16} sw={2.6} stroke="#9FCFBD"/>
            </div>
            <div style={{ fontSize: 13.5, fontWeight: 600, color: '#9FCFBD' }}>
              {responderCount === 1
                ? 'Someone is coming to help'
                : `${responderCount} people are coming to help`}
            </div>
          </div>
        )}

        {/* Responder count */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
          padding: '12px 0',
          fontSize: 13, color: 'rgba(247,243,238,0.8)',
        }}>
          <IconUser size={15}/> <strong>{responderCount}</strong>&nbsp;people responding nearby
        </div>

        {/* 24h countdown note */}
        <div style={{
          padding: '10px 14px', borderRadius: 12,
          background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)',
          fontSize: 12, color: 'rgba(247,243,238,0.55)', textAlign: 'center',
        }}>
          Your contacts will be notified for the next 24 hours unless you mark yourself safe.
        </div>

        {/* Actions */}
        <button onClick={onMarkSafe} style={{
          width: '100%', padding: '15px 0', borderRadius: 14,
          background: 'rgba(74,107,92,0.25)', border: '1px solid rgba(74,107,92,0.5)',
          color: '#9FCFBD', fontFamily: 'var(--font-sans)',
          fontSize: 14, fontWeight: 600, cursor: 'pointer',
        }}>
          I am safe
        </button>
        <button onClick={onNeedMoreHelp} style={{
          width: '100%', padding: '15px 0', borderRadius: 14,
          background: '#E8312A', border: 'none',
          color: '#fff', fontFamily: 'var(--font-sans)',
          fontSize: 14, fontWeight: 600, cursor: 'pointer',
        }}>
          Need more help
        </button>

        {/* Emergency number */}
        <div style={{ textAlign: 'center', marginTop: 4 }}>
          <a href="tel:999" style={{
            fontSize: 12.5, color: 'rgba(247,243,238,0.45)',
            textDecoration: 'none', fontFamily: 'var(--font-sans)',
          }}>
            Call 999 (Police) directly
          </a>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 18 }}>
      <button
        onPointerDown={onDown}
        onPointerUp={onUp}
        onPointerLeave={onUp}
        className="hold-btn"
        aria-label="Hold to activate emergency alert">
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
            {holding ? `${Math.ceil((1 - progress) * 4)}…` : 'Hold to alert'}
          </div>
          <div style={{ fontSize: 10.5, letterSpacing: '0.18em', textTransform: 'uppercase', opacity: 0.6 }}>
            4 seconds
          </div>
        </div>
      </button>

      <div style={{
        padding: '8px 14px', borderRadius: 999, border: '1px solid rgba(255,255,255,0.1)',
        background: 'rgba(255,255,255,0.04)', fontSize: 11.5, color: 'rgba(247,243,238,0.75)',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <IconClock size={13}/> 1 alert per day · confirmed once, cannot be undone
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
          <div style={{ fontWeight: 600, color: '#FFD9D7', letterSpacing: '0.04em' }}>10-second video records automatically</div>
          <div style={{ fontSize: 10.5, color: 'rgba(247,243,238,0.55)', marginTop: 1 }}>
            Stays on your device only · never auto-uploaded
          </div>
        </div>
      </div>

      <div style={{ width: '100%', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginTop: 4 }}>
        <div style={{ padding: 12, borderRadius: 12, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
          <div className="eyebrow" style={{ color: 'rgba(247,243,238,0.5)' }}>Will notify</div>
          <div style={{ marginTop: 6, fontSize: 12.5, lineHeight: 1.6, color: 'rgba(247,243,238,0.85)' }}>
            Campus proctor<br/>Users within 1km<br/>Emergency contacts
          </div>
        </div>
        <div style={{ padding: 12, borderRadius: 12, background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.08)' }}>
          <div className="eyebrow" style={{ color: 'rgba(247,243,238,0.5)' }}>Will share</div>
          <div style={{ marginTop: 6, fontSize: 12.5, lineHeight: 1.6, color: 'rgba(247,243,238,0.85)' }}>
            Live GPS (24h link)<br/>Anonymous event ID<br/>Encrypted timestamp
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Before phase ─────────────────────────────────────────────────────────────
function AlertBefore({ token }) {
  const [threatText, setThreatText] = _useS('');
  const [contacts, setContacts] = _useS([
    { name: 'Bappa (Brother)', phone: '+8801712000001', relationship: 'brother' },
    { name: 'Mrs. Akter (Mother)', phone: '+8801819000002', relationship: 'mother' },
  ]);
  const [form, setForm] = _useS({ name: '', phone: '', relationship: '' });
  const [saving, setSaving] = _useS(false);
  const [saved, setSaved] = _useS(false);
  const [zones, setZones] = _useS([]);

  React.useEffect(() => {
    fetch(`${API_BASE}/v1/zones`)
      .then(r => r.json())
      .then(d => setZones(Array.isArray(d) ? d.filter(z => z.status === 'active') : []))
      .catch(() => {});
  }, []);

  const handleAddContact = () => {
    if (!form.name || !form.phone) return;
    setContacts(prev => [...prev, { ...form }]);
    setForm({ name: '', phone: '', relationship: '' });
  };

  const handleRemoveContact = (i) => setContacts(prev => prev.filter((_, idx) => idx !== i));

  const handleSave = async () => {
    setSaving(true);
    try {
      await alertApiPost('/v1/alerts/phase1', {
        threat_description: threatText || null,
        emergency_contacts: contacts.slice(0, 5),
      }, token);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      console.error('[Phase1] Save failed:', e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Risk zone list — live from backend */}
      <div className="card" style={{ background: 'rgba(255,255,255,0.7)' }}>
        <div className="eyebrow" style={{ marginBottom: 8 }}>Around you</div>
        {zones.length === 0 ? (
          <div style={{ fontSize: 12, color: 'var(--ink-2)', padding: '8px 0' }}>
            No active risk zones reported nearby.
          </div>
        ) : zones.slice(0, 3).map((z, i) => (
          <div key={z.id || i} style={{ marginBottom: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{
                width: 8, height: 8, borderRadius: 999, flexShrink: 0,
                background: z.zone_type === 'red_zone' || z.zone_type === 'rape' || z.zone_type === 'murder'
                  ? 'var(--red)' : 'var(--ember)',
              }}/>
              <span style={{ fontSize: 13, color: 'var(--navy)', fontWeight: 500 }}>
                {z.description_public || z.zone_type}
              </span>
            </div>
            <div style={{ fontSize: 11, color: 'var(--muted)', marginLeft: 16, marginTop: 2 }}>
              {z.radius_m ? z.radius_m + 'm radius · ' : ''}{z.status}
            </div>
          </div>
        ))}
        <div style={{ marginTop: 6, fontSize: 12, color: 'var(--ink-2)' }}>
          <strong>{zones.length} risk zone{zones.length !== 1 ? 's' : ''}</strong> active in your area.
        </div>
      </div>

      {/* Threat documentation */}
      <div className="card" style={{ background: 'rgba(255,255,255,0.7)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <IconLock size={14} stroke="var(--navy)"/>
          <div className="eyebrow">Document a threat (encrypted)</div>
        </div>
        <textarea value={threatText} onChange={e => setThreatText(e.target.value)}
          placeholder="Describe any threats or concerns you are aware of…"
          style={{
            width: '100%', minHeight: 80, padding: '10px 12px', borderRadius: 10,
            border: '1px solid var(--mist)', background: 'var(--cream)',
            fontFamily: 'var(--font-sans)', fontSize: 13, color: 'var(--navy)',
            resize: 'vertical', boxSizing: 'border-box',
            outline: 'none',
          }}
        />
      </div>

      {/* Emergency contacts */}
      <div>
        <div className="eyebrow" style={{ marginBottom: 8 }}>Emergency contacts · {contacts.length}</div>
        {contacts.map((c, i) => (
          <div key={i} style={{
            display: 'flex', alignItems: 'center', gap: 10, padding: '10px 12px',
            background: 'rgba(255,255,255,0.6)', border: '1px solid var(--mist)',
            borderRadius: 12, marginBottom: 6,
          }}>
            <div style={{
              width: 32, height: 32, borderRadius: 999,
              background: 'var(--cream-2)', display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: 'var(--navy)',
            }}><IconUser size={15}/></div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13.5, color: 'var(--navy)', fontWeight: 500 }}>{c.name}</div>
              <div className="mono" style={{ fontSize: 10.5, color: 'var(--muted)' }}>
                {c.phone.slice(0, 6)}●●●●●● · {c.relationship}
              </div>
            </div>
            <button onClick={() => handleRemoveContact(i)} style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--muted)', padding: '4px 6px', fontSize: 16,
            }}>×</button>
          </div>
        ))}

        {/* Add contact form */}
        {contacts.length < 5 && (
          <div style={{
            padding: '12px 14px', borderRadius: 12,
            background: 'rgba(255,255,255,0.4)', border: '1px dashed var(--mist)',
            marginTop: 4,
          }}>
            <div className="eyebrow" style={{ marginBottom: 10, color: 'var(--muted)' }}>Add contact</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {[
                { k: 'name', ph: 'Full name', type: 'text' },
                { k: 'phone', ph: '+880…', type: 'tel' },
                { k: 'relationship', ph: 'Relationship (e.g. brother)', type: 'text' },
              ].map(({ k, ph, type }) => (
                <input key={k} type={type} placeholder={ph} value={form[k]}
                  onChange={e => setForm(f => ({ ...f, [k]: e.target.value }))}
                  style={{
                    padding: '9px 12px', borderRadius: 9,
                    border: '1px solid var(--mist)', background: 'var(--cream)',
                    fontFamily: 'var(--font-sans)', fontSize: 13, color: 'var(--navy)',
                    outline: 'none',
                  }}
                />
              ))}
              <button onClick={handleAddContact} className="btn" style={{
                width: '100%', padding: '10px 0', fontSize: 13,
              }}>
                + Add contact
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Save button */}
      <button onClick={handleSave} disabled={saving} className="btn btn-primary" style={{
        width: '100%', padding: '14px 0', fontSize: 14,
        opacity: saving ? 0.7 : 1,
      }}>
        {saving ? 'Saving…' : saved ? '✓ Saved securely' : 'Save phase 1 record (encrypted)'}
      </button>
    </div>
  );
}

// ─── After phase ──────────────────────────────────────────────────────────────
function AlertAfter({ eventId, token, go }) {
  const [mediaType, setMediaType] = _useS('photo');
  const [blobRef, setBlobRef] = _useS('');
  const [uploading, setUploading] = _useS(false);
  const [uploaded, setUploaded] = _useS(false);
  const [history, setHistory] = _useS([]);
  const mediaTypes = ['photo', 'video', 'audio', 'document'];

  React.useEffect(() => {
    if (!token) return;
    alertApiGet('/v1/alerts/me', token)
      .then(d => setHistory(Array.isArray(d) ? d : []))
      .catch(() => {});
  }, [token]);

  const handleUpload = async () => {
    if (!eventId || !blobRef) return;
    setUploading(true);
    try {
      const enc = new TextEncoder();
      const hashBuf = await crypto.subtle.digest('SHA-256', enc.encode(blobRef));
      const hash = Array.from(new Uint8Array(hashBuf)).map(b => b.toString(16).padStart(2, '0')).join('');
      await alertApiPost(`/v1/alerts/${eventId}/evidence`, {
        encrypted_blob_ref: blobRef,
        sha256_hash: hash,
        capture_timestamp: new Date().toISOString(),
        media_type: mediaType,
      }, token);
      setUploaded(true);
      setBlobRef('');
    } catch (e) {
      console.error('[Evidence] Upload failed:', e);
    } finally {
      setUploading(false);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Evidence upload */}
      <div className="card" style={{ background: 'rgba(255,255,255,0.7)', borderColor: 'rgba(74,107,92,0.3)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <IconLock size={16} stroke="var(--sage-2)"/>
          <div className="eyebrow" style={{ color: 'var(--sage-2)' }}>Evidence vault · encrypted</div>
        </div>
        <div className="serif" style={{ marginTop: 4, fontSize: 17, fontWeight: 500, color: 'var(--navy)' }}>
          Upload evidence — timestamped & sealed
        </div>

        {/* Media type selector */}
        <div style={{ display: 'flex', gap: 6, marginTop: 12, flexWrap: 'wrap' }}>
          {mediaTypes.map(t => (
            <button key={t} onClick={() => setMediaType(t)} style={{
              padding: '5px 12px', borderRadius: 999, fontSize: 12,
              background: mediaType === t ? 'var(--navy)' : 'var(--cream)',
              color: mediaType === t ? '#fff' : 'var(--ink-2)',
              border: `1px solid ${mediaType === t ? 'var(--navy)' : 'var(--mist)'}`,
              cursor: 'pointer', fontFamily: 'var(--font-sans)',
              textTransform: 'capitalize',
            }}>
              {t}
            </button>
          ))}
        </div>

        {/* Encrypted blob ref input */}
        <input
          type="text"
          placeholder="Paste encrypted file reference or path…"
          value={blobRef}
          onChange={e => setBlobRef(e.target.value)}
          style={{
            marginTop: 12, width: '100%', padding: '10px 12px', borderRadius: 10,
            border: '1px solid var(--mist)', background: 'var(--cream)',
            fontFamily: 'var(--font-sans)', fontSize: 12, color: 'var(--navy)',
            boxSizing: 'border-box', outline: 'none',
          }}
        />

        <div style={{
          marginTop: 10, padding: '12px 14px', border: '1px dashed var(--mist-2)',
          borderRadius: 12, background: 'var(--cream)', textAlign: 'center',
        }}>
          <IconUpload size={24} stroke="var(--muted)"/>
          <div style={{ marginTop: 6, fontSize: 12.5, color: 'var(--ink-2)' }}>
            Encrypt file client-side, then paste the reference above
          </div>
          <div style={{ marginTop: 2, fontSize: 11, color: 'var(--muted)' }}>
            SHA-256 hashed · server stores reference only · 7-year retention
          </div>
        </div>

        <button onClick={handleUpload} disabled={!blobRef || !eventId || uploading}
          className="btn btn-primary" style={{
            width: '100%', marginTop: 12, padding: '12px 0',
            opacity: !blobRef || !eventId ? 0.4 : 1,
          }}>
          {uploading ? 'Uploading…' : uploaded ? '✓ Evidence recorded' : 'Submit evidence'}
        </button>
      </div>

      {/* Link to formal case */}
      <button onClick={() => go && go('compose')} className="btn btn-ghost" style={{ width: '100%' }}>
        <IconFile size={16}/> Convert to formal complaint or FIR
      </button>

      {/* Previous alerts history — live from backend */}
      <div>
        <div className="eyebrow" style={{ marginBottom: 8 }}>Previous alerts · {history.length}</div>
        {history.length === 0 ? (
          <div style={{ fontSize: 12, color: 'var(--muted)', padding: '8px 0' }}>No previous alerts.</div>
        ) : history.map((a, i) => (
          <div key={a.event_id || i} style={{
            padding: '12px 14px', background: 'rgba(255,255,255,0.6)',
            border: '1px solid var(--mist)', borderRadius: 12, marginBottom: 8,
          }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="mono" style={{ fontSize: 12, color: 'var(--navy)' }}>
                {a.event_id ? a.event_id.slice(0, 8) + '…' : '—'}
              </span>
              <span className="pill">{a.state}</span>
            </div>
            <div className="mono" style={{ fontSize: 10.5, color: 'var(--muted)', marginTop: 4 }}>
              {a.created_at ? new Date(a.created_at).toLocaleString('en-BD') : '—'}
            </div>
            {a.closed_by && (
              <div style={{ fontSize: 12, color: 'var(--ink-2)', marginTop: 4 }}>Closed by: {a.closed_by}</div>
            )}
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
function FeedRowMini({ item, onOpen }) {
  const isApi = !!item.post_number;
  const hasToken = !!localStorage.getItem('anchor_access_token');
  const kicker   = isApi ? (item.category || '').replace(/_/g, ' ').toUpperCase() : item.kicker;
  const headline = isApi ? item.title : item.headline;
  const when     = isApi
    ? new Date(item.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })
    : item.byline?.when;

  const [counts, setCounts] = React.useState({
    corroborate: isApi ? (item.signal_counts?.corroborate || 0) : (item.corr || 0),
    challenge:   isApi ? (item.signal_counts?.challenge   || 0) : (item.chal || 0),
    user_signal: isApi ? (item.signal_counts?.user_signal || null) : null,
  });
  const [busy, setBusy] = React.useState(false);

  async function signal(type) {
    if (!isApi || busy || !localStorage.getItem('anchor_access_token')) return;
    setBusy(true);
    try {
      const data = await apiFetch(`/v1/feed/${item.id}/${type}`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}),
      });
      if (data?.counts) setCounts(data.counts);
    } catch (_) {}
    setBusy(false);
  }

  const userSig = counts.user_signal;

  return (
    <div
      onClick={onOpen || undefined}
      style={{
        padding: '14px 0', borderTop: '1px solid var(--mist)', display: 'flex', gap: 12,
        cursor: onOpen ? 'pointer' : 'default',
      }}
    >
      <div style={{ width: 80, height: 60, borderRadius: 6, overflow: 'hidden', flexShrink: 0, position: 'relative' }}>
        <NewsArt variant={item.art || { incident:'protest', missing_person:'building', road:'road', safety:'court', civic_event:'building' }[item.category] || 'protest'}/>
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="news-kicker" style={{ marginBottom: 3, fontSize: 9 }}>{kicker}</div>
        <div className="serif" style={{ fontSize: 14, fontWeight: 500, lineHeight: 1.15, color: 'var(--navy)' }}>{headline}</div>
        <div style={{ marginTop: 6, display: 'flex', gap: 6, alignItems: 'center', fontSize: 10.5, color: 'var(--muted)' }}>
          <button
            onClick={e => { e.stopPropagation(); signal('corroborate'); }}
            disabled={!isApi || !hasToken || busy}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 3,
              background: userSig === 'corroborate' ? 'var(--sage)' : 'rgba(74,107,92,0.1)',
              color: userSig === 'corroborate' ? 'white' : 'var(--sage-2)',
              border: 'none', borderRadius: 999, padding: '2px 8px',
              fontSize: 10.5, fontWeight: 600, cursor: isApi && hasToken ? 'pointer' : 'default',
            }}
          ><IconCheck size={9} sw={2.4}/> {counts.corroborate}</button>
          <button
            onClick={e => { e.stopPropagation(); signal('challenge'); }}
            disabled={!isApi || !hasToken || busy}
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 3,
              background: userSig === 'challenge' ? 'var(--ember)' : 'rgba(196,69,54,0.08)',
              color: userSig === 'challenge' ? 'white' : 'var(--ember)',
              border: 'none', borderRadius: 999, padding: '2px 8px',
              fontSize: 10.5, fontWeight: 600, cursor: isApi && hasToken ? 'pointer' : 'default',
            }}
          ><IconX size={9} sw={2.4}/> {counts.challenge}</button>
          <span style={{ marginLeft: 'auto' }}>{when}</span>
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

// Built-in offline fallback — mirrors the backend shape so the screen always
// renders even when the API is unreachable.
const RIGHTS_FALLBACK = [
  { category: 'personal_safety', illustration: 'shield', accent: '#C44536',
    citation: 'Penal Code 1860 · §509',
    title_en: 'Right against harassment in public spaces',
    title_bn: 'প্রকাশ্য স্থানে হয়রানির বিরুদ্ধে অধিকার',
    summary_en: 'Insulting the modesty of a woman by word, gesture or act is a criminal offence.',
    summary_bn: 'কথা, অঙ্গভঙ্গি বা কাজের মাধ্যমে নারীর শ্লীলতাহানি একটি ফৌজদারি অপরাধ।',
    full_text_en: 'Any word, gesture, or act intended to insult the modesty of a woman is punishable with imprisonment up to one year, or fine, or both.',
    full_text_bn: 'কোনো নারীর শ্লীলতাহানির উদ্দেশ্যে করা যেকোনো শব্দ, অঙ্গভঙ্গি বা কাজ এক বছর পর্যন্ত কারাদণ্ড, জরিমানা, বা উভয় দণ্ডে দণ্ডনীয়।',
    penalty_en: 'Up to 1 year imprisonment or fine', penalty_bn: '১ বছর পর্যন্ত কারাদণ্ড বা জরিমানা',
    where_to_invoke_en: 'File a GD at the nearest thana, or call 999.',
    where_to_invoke_bn: 'নিকটস্থ থানায় জিডি করুন, অথবা ৯৯৯-এ কল করুন।',
    steps: [] },
  { category: 'cyber', illustration: 'lock', accent: '#3A5A8C',
    citation: 'Cyber Security Act 2023 · §25',
    title_en: 'Right to lodge a cyber-harassment complaint',
    title_bn: 'সাইবার হয়রানির অভিযোগ করার অধিকার',
    summary_en: 'Targeted online harassment is a cognizable offence.',
    summary_bn: 'লক্ষ্যবস্তু করে অনলাইন হয়রানি আমলযোগ্য অপরাধ।',
    full_text_en: 'Online harassment, defamation and publishing private images without consent are punishable. File at the Cyber Police Centre or any thana.',
    full_text_bn: 'অনলাইনে হয়রানি, মানহানি ও সম্মতি ছাড়া ব্যক্তিগত ছবি প্রকাশ শাস্তিযোগ্য। সাইবার পুলিশ সেন্টার বা যেকোনো থানায় অভিযোগ করুন।',
    penalty_en: 'Varies — fines and imprisonment', penalty_bn: 'অপরাধভেদে — জরিমানা ও কারাদণ্ড',
    where_to_invoke_en: 'CID Cyber Police Centre, any thana, or 999.',
    where_to_invoke_bn: 'সিআইডি সাইবার পুলিশ সেন্টার, যেকোনো থানা, অথবা ৯৯৯।',
    steps: [] },
  { category: 'custody', illustration: 'gavel', accent: '#7A5230',
    citation: 'CrPC §60A · Constitution Art. 33',
    title_en: 'Right to inform a relative on arrest',
    title_bn: 'গ্রেপ্তারে আত্মীয়কে জানানোর অধিকার',
    summary_en: 'On arrest you must be told the grounds, allowed a lawyer, and produced before a magistrate within 24 hours.',
    summary_bn: 'গ্রেপ্তারে কারণ জানাতে হবে, আইনজীবী রাখার সুযোগ ও ২৪ ঘণ্টায় ম্যাজিস্ট্রেটের সামনে হাজির করতে হবে।',
    full_text_en: 'On arrest, you must be informed of the grounds, allowed to consult a lawyer of your choice, and produced before a magistrate within twenty-four hours.',
    full_text_bn: 'গ্রেপ্তারে আপনাকে কারণ জানাতে হবে, পছন্দের আইনজীবীর সঙ্গে পরামর্শের সুযোগ দিতে হবে এবং চব্বিশ ঘণ্টার মধ্যে ম্যাজিস্ট্রেটের সামনে হাজির করতে হবে।',
    penalty_en: 'Violation is grounds for High Court relief', penalty_bn: 'লঙ্ঘন হাইকোর্টে প্রতিকারের ভিত্তি',
    where_to_invoke_en: 'Insist on these rights at arrest; a lawyer can file habeas corpus.',
    where_to_invoke_bn: 'গ্রেপ্তারে এই অধিকার দাবি করুন; আইনজীবী হেবিয়াস কর্পাস রিট করতে পারেন।',
    steps: [] },
  { category: 'workplace', illustration: 'building', accent: '#4A6B5C',
    citation: 'High Court Directive 2009',
    title_en: 'Right to a safe workplace',
    title_bn: 'নিরাপদ কর্মস্থলের অধিকার',
    summary_en: 'Every workplace must have a sexual-harassment complaint committee chaired by a woman.',
    summary_bn: 'প্রতিটি কর্মস্থলে নারীর নেতৃত্বে যৌন হয়রানি অভিযোগ কমিটি থাকতে হবে।',
    full_text_en: 'Every workplace, including educational institutions, must have a complaint committee for sexual harassment, chaired by a woman.',
    full_text_bn: 'শিক্ষাপ্রতিষ্ঠানসহ প্রতিটি কর্মস্থলে নারীর সভাপতিত্বে যৌন হয়রানি অভিযোগ কমিটি থাকতে হবে।',
    penalty_en: 'Non-compliance is contempt of the directive', penalty_bn: 'অমান্য করা নির্দেশনা অবমাননা',
    where_to_invoke_en: "Complain to your institution's committee; escalate via a writ.",
    where_to_invoke_bn: 'প্রতিষ্ঠানের কমিটিতে অভিযোগ করুন; উপেক্ষিত হলে রিটে যান।',
    steps: [] },
  { category: 'domestic', illustration: 'heart', accent: '#B0436A',
    citation: 'DV (Prevention & Protection) Act 2010',
    title_en: 'Right to seek a protection order',
    title_bn: 'সুরক্ষা আদেশ চাওয়ার অধিকার',
    summary_en: 'Victims of domestic violence can apply for residence, protection and compensation orders.',
    summary_bn: 'পারিবারিক সহিংসতার শিকার ব্যক্তি বসবাস, সুরক্ষা ও ক্ষতিপূরণ আদেশ চাইতে পারেন।',
    full_text_en: 'Victims of domestic violence may apply to a Court of Magistrate for a residence order, protection order, or compensation.',
    full_text_bn: 'পারিবারিক সহিংসতার শিকার ম্যাজিস্ট্রেট আদালতে বসবাস, সুরক্ষা বা ক্ষতিপূরণ আদেশের জন্য আবেদন করতে পারেন।',
    penalty_en: 'Breach is punishable with jail and fine', penalty_bn: 'লঙ্ঘন কারাদণ্ড ও জরিমানায় দণ্ডনীয়',
    where_to_invoke_en: 'Apply through a Court of Magistrate; an NGO can assist.',
    where_to_invoke_bn: 'ম্যাজিস্ট্রেট আদালতে আবেদন করুন; এনজিও সহায়তা করতে পারে।',
    steps: [] },
  { category: 'privacy', illustration: 'eye', accent: '#5B6770',
    citation: 'Constitution Art. 43',
    title_en: 'Right to privacy and consent',
    title_bn: 'গোপনীয়তা ও সম্মতির অধিকার',
    summary_en: 'Privacy of correspondence and communication is a constitutional right.',
    summary_bn: 'চিঠিপত্র ও যোগাযোগের গোপনীয়তা একটি সাংবিধানিক অধিকার।',
    full_text_en: 'Every citizen has the right to privacy of correspondence and communication. Surveillance without due process is unconstitutional.',
    full_text_bn: 'প্রত্যেক নাগরিকের যোগাযোগের গোপনীয়তার অধিকার রয়েছে। যথাযথ প্রক্রিয়া ছাড়া নজরদারি অসাংবিধানিক।',
    penalty_en: 'Remediable via High Court writ', penalty_bn: 'হাইকোর্ট রিটে প্রতিকারযোগ্য',
    where_to_invoke_en: 'Challenge unlawful surveillance via a writ petition.',
    where_to_invoke_bn: 'বেআইনি নজরদারির বিরুদ্ধে রিট পিটিশন করুন।',
    steps: [] },
];

const RIGHTS_CATEGORY_LABELS = {
  personal_safety: { en: 'Safety',     bn: 'নিরাপত্তা' },
  cyber:           { en: 'Cyber',      bn: 'সাইবার' },
  custody:         { en: 'Custody',    bn: 'আটক' },
  workplace:       { en: 'Workplace',  bn: 'কর্মস্থল' },
  domestic:        { en: 'Domestic',   bn: 'পারিবারিক' },
  privacy:         { en: 'Privacy',    bn: 'গোপনীয়তা' },
  consumer:        { en: 'Consumer',   bn: 'ভোক্তা' },
  rti:             { en: 'Information', bn: 'তথ্য' },
  dowry:           { en: 'Dowry',      bn: 'যৌতুক' },
  child_marriage:  { en: 'Child',      bn: 'শিশু' },
  road:            { en: 'Road',       bn: 'সড়ক' },
  labor:           { en: 'Labour',     bn: 'শ্রম' },
};

function rightsCatLabel(cat, lang) {
  const m = RIGHTS_CATEGORY_LABELS[cat];
  if (!m) return (cat || '').replace(/_/g, ' ');
  return lang === 'BN' ? m.bn : m.en;
}

// Maps an illustration key → an icon component (all defined in icons.jsx).
function RightsGlyph({ kind, size = 26, stroke = '#fff' }) {
  const p = { size, stroke };
  switch (kind) {
    case 'shield':   return <IconShield {...p}/>;
    case 'lock':     return <IconLock {...p}/>;
    case 'gavel':    return <IconGavel {...p}/>;
    case 'building': return <IconBuilding {...p}/>;
    case 'heart':    return <IconHeart {...p}/>;
    case 'book':     return <IconBook {...p}/>;
    case 'eye':      return <IconEyeOff {...p}/>;
    case 'route':    return <IconRoute {...p}/>;
    case 'doc':      return <IconDoc {...p}/>;
    case 'scale':    return <IconScale {...p}/>;
    default:         return <IconScale {...p}/>;
  }
}

// Infographic banner — gradient band keyed by the law's accent + glyph, with a
// decorative SVG motif and the citation chip. Pure SVG/CSS, no image assets.
function RightInfographic({ kind, accent, citation, catLabel }) {
  const dark = accent || '#C44536';
  return (
    <div style={{
      position: 'relative', height: 96, overflow: 'hidden',
      background: `linear-gradient(135deg, ${dark} 0%, ${dark}cc 60%, ${dark}99 100%)`,
    }}>
      {/* decorative concentric arcs */}
      <svg viewBox="0 0 200 96" preserveAspectRatio="xMidYMid slice"
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', opacity: 0.16 }} aria-hidden="true">
        <circle cx="172" cy="20" r="46" fill="none" stroke="#fff" strokeWidth="1.4"/>
        <circle cx="172" cy="20" r="30" fill="none" stroke="#fff" strokeWidth="1.4"/>
        <circle cx="172" cy="20" r="16" fill="none" stroke="#fff" strokeWidth="1.4"/>
        <circle cx="18" cy="84" r="3" fill="#fff"/>
        <circle cx="34" cy="84" r="3" fill="#fff"/>
        <circle cx="50" cy="84" r="3" fill="#fff"/>
      </svg>
      <div style={{ position: 'relative', height: '100%', padding: '14px 16px', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{
            width: 44, height: 44, borderRadius: 12,
            background: 'rgba(255,255,255,0.18)', border: '1px solid rgba(255,255,255,0.3)',
            display: 'flex', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(2px)',
          }}>
            <RightsGlyph kind={kind} size={24} stroke="#fff"/>
          </div>
          <span style={{
            fontFamily: 'var(--font-sans)', fontSize: 10, fontWeight: 700, letterSpacing: '0.08em',
            textTransform: 'uppercase', color: 'rgba(255,255,255,0.92)',
            padding: '4px 9px', borderRadius: 999, background: 'rgba(255,255,255,0.16)',
          }}>{catLabel}</span>
        </div>
        <div className="mono" style={{ fontSize: 10.5, color: 'rgba(255,255,255,0.95)' }}>{citation}</div>
      </div>
    </div>
  );
}

function RightCard({ r, lang, open, onToggle }) {
  const bn = lang === 'BN';
  const pick = (field) => {
    const v = bn ? r[field + '_bn'] : r[field + '_en'];
    return (v && String(v).trim()) ? v : (r[field + '_en'] || '');
  };
  const bnCls = bn ? 'bn' : '';
  const steps = Array.isArray(r.steps) ? r.steps : [];
  const where = pick('where_to_invoke');
  const penalty = pick('penalty');

  return (
    <div style={{
      background: 'rgba(255,255,255,0.78)', border: '1px solid var(--mist)',
      borderRadius: 16, overflow: 'hidden', marginBottom: 12,
    }}>
      <RightInfographic kind={r.illustration} accent={r.accent}
        citation={r.citation} catLabel={rightsCatLabel(r.category, lang)}/>

      <div style={{ padding: '14px 16px 16px' }}>
        <div className={`serif ${bnCls}`} style={{ fontSize: 18, fontWeight: 500, color: 'var(--navy)', lineHeight: 1.18, letterSpacing: '-0.005em' }}>
          {pick('title')}
        </div>
        <p className={bnCls} style={{ margin: '7px 0 0', fontSize: 13, color: 'var(--ink-2)', lineHeight: 1.55 }}>
          {pick('summary')}
        </p>

        {penalty && penalty !== '—' && (
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginTop: 10,
            padding: '5px 10px', borderRadius: 8, background: 'var(--cream-2)', border: '1px solid var(--mist)' }}>
            <span style={{ width: 6, height: 6, borderRadius: 999, background: r.accent || 'var(--ember)' }}/>
            <span className={bnCls} style={{ fontSize: 11.5, color: 'var(--ink-2)', fontWeight: 500 }}>{penalty}</span>
          </div>
        )}

        {open && (
          <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px dashed var(--mist)' }}>
            <p className={bnCls} style={{ margin: 0, fontSize: 13, color: 'var(--ink)', lineHeight: 1.6 }}>
              {pick('full_text')}
            </p>

            {steps.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <div className="eyebrow" style={{ color: 'var(--ember-2)', marginBottom: 6 }}>{bn ? 'যা করবেন' : 'What to do'}</div>
                {steps.map((s, si) => (
                  <div key={si} style={{ display: 'flex', gap: 9, marginBottom: 7, alignItems: 'flex-start' }}>
                    <span style={{
                      flexShrink: 0, width: 18, height: 18, borderRadius: 999, marginTop: 1,
                      background: r.accent || 'var(--ember)', color: '#fff',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 10.5, fontWeight: 700, fontFamily: 'var(--font-sans)',
                    }}>{si + 1}</span>
                    <span className={bnCls} style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.5 }}>
                      {bn ? ((s.bn && String(s.bn).trim()) ? s.bn : s.en) : (s.en || s.bn)}
                    </span>
                  </div>
                ))}
              </div>
            )}

            {where && (
              <div style={{ marginTop: 12, padding: '10px 12px', borderRadius: 10,
                background: 'var(--cream-2)', border: '1px solid var(--mist)', display: 'flex', gap: 9 }}>
                <span style={{ flexShrink: 0, color: r.accent || 'var(--ember)', marginTop: 1 }}>
                  <IconMap size={15} stroke={r.accent || 'var(--ember)'}/>
                </span>
                <div>
                  <div className="eyebrow" style={{ color: 'var(--muted)', marginBottom: 2 }}>{bn ? 'কোথায় যাবেন' : 'Where to invoke'}</div>
                  <div className={bnCls} style={{ fontSize: 12.5, color: 'var(--ink)', lineHeight: 1.5 }}>{where}</div>
                </div>
              </div>
            )}
          </div>
        )}

        <button onClick={onToggle} style={{
          marginTop: 12, width: '100%', padding: '9px 12px', borderRadius: 10,
          background: open ? 'transparent' : 'var(--navy)', color: open ? 'var(--ink-2)' : '#F7F3EE',
          border: open ? '1px solid var(--mist)' : 'none', cursor: 'pointer',
          fontFamily: 'var(--font-sans)', fontSize: 12.5, fontWeight: 500,
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
        }}>
          {open ? (bn ? 'বন্ধ করুন' : 'Show less') : (bn ? 'বিস্তারিত পড়ুন' : 'Read full text')}
          <span style={{ transform: open ? 'rotate(-90deg)' : 'rotate(90deg)', transition: 'transform .15s', display: 'inline-flex' }}>
            <IconChevronRight size={13} stroke={open ? 'var(--ink-2)' : '#F7F3EE'}/>
          </span>
        </button>
      </div>
    </div>
  );
}

function RightsScreen() {
  const { lang: rawLang } = useApp();
  // Legal-rights text is content: "Both" (BI) shows Bangla.
  const lang = (typeof contentLang === 'function') ? contentLang(rawLang)
                                                   : ((rawLang === 'BN' || rawLang === 'BI') ? 'BN' : 'EN');
  const [rights, setRights] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [offline, setOffline] = React.useState(false);
  const [category, setCategory] = React.useState('all');
  const [openId, setOpenId] = React.useState(null);

  React.useEffect(() => {
    let alive = true;
    fetch(`${API_BASE}/v1/legal-rights`)
      .then(r => { if (!r.ok) throw new Error('bad status'); return r.json(); })
      .then(data => {
        if (!alive) return;
        const list = Array.isArray(data) && data.length ? data : RIGHTS_FALLBACK;
        setRights(list);
        setOffline(!(Array.isArray(data) && data.length));
        setLoading(false);
      })
      .catch(() => {
        if (!alive) return;
        setRights(RIGHTS_FALLBACK);
        setOffline(true);
        setLoading(false);
      });
    return () => { alive = false; };
  }, []);

  const bn = lang === 'BN';
  const cats = Array.from(new Set(rights.map(r => r.category)));
  const visible = category === 'all' ? rights : rights.filter(r => r.category === category);
  const keyOf = (r, i) => (r.id || `${r.category}-${i}`);

  return (
    <>
      <Header back title={bn ? 'আপনার অধিকার জানুন' : 'Know your rights'} subtitle={bn ? 'বাংলাদেশ · নাগরিক অধিকার' : 'Bangladesh · Civic rights'}/>

      <div style={{ padding: '12px 20px 2px' }}>
        <div className={bn ? 'bn' : ''} style={{ fontSize: 13, color: 'var(--muted)', fontFamily: bn ? 'var(--font-bn)' : 'var(--font-serif)', fontStyle: bn ? 'normal' : 'italic' }}>
          {bn ? 'দৈনন্দিন জীবনের গুরুত্বপূর্ণ আইনি অধিকার। বিস্তারিত ও কোথায় প্রয়োগ করবেন দেখতে যেকোনো কার্ডে ট্যাপ করুন।'
              : 'The laws that matter most for daily life. Tap any card for the full text and where to invoke it.'}
        </div>
      </div>

      {/* category filter chips */}
      {!loading && cats.length > 1 && (
        <div style={{ display: 'flex', gap: 6, padding: '12px 20px 4px', overflowX: 'auto' }} className="no-scrollbar">
          {['all', ...cats].map((c) => {
            const active = category === c;
            return (
              <span key={c} onClick={() => setCategory(c)} className={bn ? 'bn' : ''} style={{
                padding: '6px 11px', borderRadius: 999, whiteSpace: 'nowrap', cursor: 'pointer',
                background: active ? 'var(--ember)' : 'rgba(255,255,255,0.7)',
                color: active ? '#F7F3EE' : 'var(--ink-2)',
                border: '1px solid ' + (active ? 'var(--ember)' : 'var(--mist)'),
                fontSize: 11.5, fontWeight: 500,
              }}>{c === 'all' ? (bn ? 'সব' : 'All') : rightsCatLabel(c, lang)}</span>
            );
          })}
        </div>
      )}

      <div style={{ padding: '14px 20px 28px' }}>
        {loading && (
          <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--muted)', fontSize: 13, fontFamily: 'var(--font-sans)' }}>
            {bn ? 'লোড হচ্ছে…' : 'Loading rights…'}
          </div>
        )}

        {!loading && offline && (
          <div className={bn ? 'bn' : ''} style={{
            display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12,
            padding: '9px 12px', borderRadius: 10, background: 'var(--cream-2)',
            border: '1px solid var(--mist)', fontSize: 11.5, color: 'var(--muted)', fontFamily: bn ? 'var(--font-bn)' : 'var(--font-sans)',
          }}>
            <span style={{ width: 6, height: 6, borderRadius: 999, background: 'var(--gold)', flexShrink: 0 }}/>
            {bn ? 'অফলাইন — অন্তর্নির্মিত গাইড দেখানো হচ্ছে।' : 'Offline — showing the built-in guide.'}
          </div>
        )}

        {!loading && visible.length === 0 && (
          <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--muted)', fontSize: 13, fontFamily: 'var(--font-sans)' }}>
            {bn ? 'কিছু পাওয়া যায়নি।' : 'Nothing here yet.'}
          </div>
        )}

        {!loading && visible.map((r, i) => {
          const k = keyOf(r, i);
          return (
            <RightCard key={k} r={r} lang={lang}
              open={openId === k} onToggle={() => setOpenId(openId === k ? null : k)}/>
          );
        })}
      </div>
    </>
  );
}

Object.assign(window, {
  NewsArt, FeedRowMini, ComposeScreen, RightsScreen,
});
