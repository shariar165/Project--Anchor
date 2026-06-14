// Anchor — Screens part 2: Cases, CaseDetail, Map, Feed, Lawyers, Notices, Profile

// ═══════════════════════════════════════════════════════════════
//  CASES SCREEN
// ═══════════════════════════════════════════════════════════════
function CasesScreen() {
  const { go, mode } = useApp();
  const [tab, setTab] = React.useState('all');
  const inMode = ACTIVE_CASES.filter(c => c.scope === mode);
  const filtered = inMode.filter(c =>
    tab === 'all' ? true :
    tab === 'active' ? c.status !== 'resolved' :
    /* resolved */ c.status === 'resolved'
  );

  return (
    <>
      <Header back/>
      <div style={{ padding: '4px 20px 0' }}>
        <div className="eyebrow">{mode === 'campus' ? 'Campus' : 'National'} · my cases</div>
        <h1 className="h-display" style={{ margin: '4px 0 4px', fontSize: 26, lineHeight: 1.05 }}>My Cases</h1>
        <div style={{ fontSize: 13, color: 'var(--muted)', fontFamily: 'var(--font-serif)', fontStyle: 'italic' }}>
          {mode === 'campus' ? 'Filed within Daffodil — routed through the campus hierarchy.' : 'Filed across Bangladesh — routed through legal channels.'}
        </div>
      </div>

      <div style={{ padding: '14px 20px 8px' }}>
        <div className="tabbar">
          {[['all', `All · ${inMode.length}`], ['active', `Active · ${inMode.filter(c => c.status !== 'resolved').length}`], ['resolved', `Resolved · ${inMode.filter(c => c.status === 'resolved').length}`]].map(([k, l]) => (
            <button key={k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{l}</button>
          ))}
        </div>
      </div>

      <div style={{ padding: '8px 20px 28px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {filtered.map(c => <CaseCard key={c.id} c={c} onOpen={() => go('case', { id: c.id })}/>)}
        {filtered.length === 0 && (
          <div style={{ padding: '60px 20px', textAlign: 'center' }}>
            <div className="serif" style={{ fontSize: 20, color: 'var(--navy)' }}>No cases here yet.</div>
            <div style={{ marginTop: 6, fontSize: 13, color: 'var(--muted)', fontFamily: 'var(--font-serif)', fontStyle: 'italic' }}>
              When you file a complaint or draft a GD, it appears here.
            </div>
            <button onClick={() => go('compose')} className="btn btn-primary" style={{ marginTop: 14 }}>
              <IconSparkles size={14}/> Start a new one
            </button>
          </div>
        )}
      </div>
    </>
  );
}

function CaseCard({ c, onOpen }) {
  return (
    <button onClick={onOpen} style={{
      textAlign: 'left', background: 'rgba(255,255,255,0.7)', border: '1px solid var(--mist)',
      borderRadius: 16, padding: 16, cursor: 'pointer',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="mono" style={{ fontSize: 11, color: 'var(--muted)' }}>{c.id}</span>
          {c.anon && <span className="anon"><IconEyeOff size={12}/> Anonymous</span>}
        </div>
        <StatusPill status={c.status}/>
      </div>
      <div className="serif" style={{ fontSize: 16, fontWeight: 500, lineHeight: 1.2, color: 'var(--navy)', marginBottom: 10 }}>
        {c.title}
      </div>
      <Stepper status={c.status}/>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 12 }}>
        <div style={{ fontSize: 11.5, color: 'var(--ink-2)' }}>{c.routed}</div>
        <div className="serif" style={{ fontSize: 11.5, color: 'var(--muted)', fontStyle: 'italic' }}>{c.updated}</div>
      </div>
    </button>
  );
}

// ═══════════════════════════════════════════════════════════════
//  CASE DETAIL
// ═══════════════════════════════════════════════════════════════
function CaseDetailScreen({ params }) {
  const { mode } = useApp();
  const c = ACTIVE_CASES.find(x => x.id === params.id) ||
            ACTIVE_CASES.find(x => x.scope === mode) || ACTIVE_CASES[0];
  const currentLevel = c.timeline.findIndex(t => t.active);

  return (
    <>
      <Header back/>

      <div style={{ padding: '4px 20px 14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <span className="mono" style={{ fontSize: 11, color: 'var(--muted)' }}>{c.id}</span>
          {c.anon && <span className="anon"><IconEyeOff size={12}/> Anonymous</span>}
          <span style={{ flex: 1 }}/>
          <StatusPill status={c.status}/>
        </div>
        <h1 className="h-display" style={{ fontSize: 24, margin: 0, lineHeight: 1.1 }}>{c.title}</h1>
        <div style={{ marginTop: 8, fontSize: 12.5, color: 'var(--ink-2)', fontStyle: 'italic', fontFamily: 'var(--font-serif)' }}>
          {c.routed} · last updated {c.updated}
        </div>
      </div>

      {/* Routing hierarchy */}
      <div style={{ padding: '0 20px 14px' }}>
        <div className="eyebrow" style={{ marginBottom: 10 }}>Routing hierarchy</div>
        <div style={{
          padding: 14, borderRadius: 14, background: 'rgba(255,255,255,0.65)', border: '1px solid var(--mist)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {c.routing.map((step, i) => {
              const isCurr = i === Math.min(currentLevel >= 0 ? currentLevel : 0, c.routing.length - 1);
              const isPast = i < (currentLevel >= 0 ? currentLevel : 0);
              return (
                <React.Fragment key={i}>
                  <div style={{ flex: 1, textAlign: 'center' }}>
                    <div style={{
                      width: 28, height: 28, borderRadius: 999, margin: '0 auto',
                      background: isCurr ? 'var(--gold)' : isPast ? 'var(--sage)' : 'var(--mist)',
                      color: isCurr || isPast ? '#fff' : 'var(--muted)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontFamily: 'var(--font-serif)', fontSize: 12, fontWeight: 500,
                      boxShadow: isCurr ? '0 0 0 5px rgba(184,137,58,0.18)' : 'none',
                    }}>
                      {isPast ? <IconCheck size={12} sw={3}/> : i + 1}
                    </div>
                    <div style={{
                      marginTop: 6, fontSize: 10, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase',
                      color: isCurr ? 'var(--navy)' : 'var(--muted)', lineHeight: 1.2,
                    }}>{step}</div>
                  </div>
                  {i < c.routing.length - 1 && <span style={{ flex: 0.3, height: 1, background: isPast ? 'var(--sage)' : 'var(--mist-2)' }}/>}
                </React.Fragment>
              );
            })}
          </div>
        </div>
      </div>

      {/* Timeline */}
      <div style={{ padding: '4px 20px 14px' }}>
        <div className="eyebrow" style={{ marginBottom: 6 }}>Timeline</div>
        <div>
          {c.timeline.map((t, i) => (
            <div key={i} className="tl-step">
              <span className={`tl-dot ${t.done ? 'done' : t.active ? 'active' : ''}`}/>
              <div style={{ flex: 1 }}>
                <div style={{
                  fontSize: 13.5, fontWeight: 500,
                  color: t.done || t.active ? 'var(--navy)' : 'var(--muted)',
                }}>{t.t}</div>
                <div className="mono" style={{ fontSize: 10.5, color: 'var(--muted)', marginTop: 1 }}>{t.d}</div>
              </div>
              {t.active && <span className="pill pill-review"><span className="dot pulse"/> Now</span>}
            </div>
          ))}
        </div>
      </div>

      {/* Original text */}
      <div style={{ padding: '4px 20px 14px' }}>
        <div className="eyebrow" style={{ marginBottom: 6 }}>Original complaint</div>
        <div className="card" style={{ background: 'rgba(255,255,255,0.7)' }}>
          {c.anon ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
              <IconEyeOff size={14} stroke="var(--muted)"/>
              <div className="mono" style={{ fontSize: 11, color: 'var(--muted)' }}>From: S***** A***** (verified DIU)</div>
            </div>
          ) : null}
          <p className="serif" style={{ margin: 0, fontSize: 14, lineHeight: 1.55, color: 'var(--ink)' }}>
            “{c.desc}”
          </p>
        </div>
      </div>

      {/* Evidence */}
      <div style={{ padding: '4px 20px 14px' }}>
        <div className="eyebrow" style={{ marginBottom: 8 }}>Evidence · 3 items</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
          {[1,2,3].map(i => (
            <div key={i} style={{
              aspectRatio: '1', borderRadius: 10, background: `linear-gradient(135deg, var(--mist) 30%, var(--mist-2))`,
              border: '1px solid var(--mist-2)', position: 'relative', overflow: 'hidden',
            }}>
              <div style={{
                position: 'absolute', bottom: 6, left: 6, right: 6,
                background: 'rgba(11,29,53,0.75)', color: '#F7F3EE',
                padding: '4px 6px', borderRadius: 6,
                fontSize: 9, fontFamily: 'var(--font-mono)', lineHeight: 1.3,
              }}>
                IMG-00{i}<br/>23.78°N 90.41°E
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Dead Man's Switch — for national cases that enabled it */}
      {c.deadMan && (
        <div style={{ padding: '4px 20px 14px' }}>
          <div style={{
            padding: 14, borderRadius: 14, background: 'rgba(232,49,42,0.06)',
            border: '1px solid rgba(232,49,42,0.25)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <IconShield size={16} stroke="var(--ember)"/>
              <div className="eyebrow" style={{ color: 'var(--ember-2)' }}>Dead Man's Switch · Active</div>
            </div>
            <div style={{ fontSize: 13, color: 'var(--ink)', lineHeight: 1.4 }}>
              If you don't check in within <strong>48 hours</strong>, evidence and contacts will be released to your designated lawyer automatically.
            </div>
          </div>
        </div>
      )}

      {/* Actions */}
      <div style={{ padding: '4px 20px 28px', display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        <button className="btn btn-primary"><IconPlus size={15}/> Add update</button>
        <button className="btn btn-ghost"><IconArrowUp size={15}/> Escalate</button>
      </div>
    </>
  );
}

// ═══════════════════════════════════════════════════════════════
//  MAP SCREEN
// ═══════════════════════════════════════════════════════════════
function MapScreen() {
  const [filter, setFilter] = React.useState('all');
  const [selected, setSelected] = React.useState(null);

  const zones = [
    { id: 1, type: 'black', x: 32, y: 38, r: 48, status: 'investigating', label: 'Dhanmondi-15', summary: 'Reported sexual assault, May 2026.', date: 'May 20, 2026' },
    { id: 2, type: 'red',   x: 58, y: 28, r: 42, status: 'active', label: 'Mohammadpur-7', summary: 'Murder case under investigation.', date: 'May 18, 2026' },
    { id: 3, type: 'black', x: 70, y: 55, r: 55, status: 'active', label: 'Mirpur-10 Circle', summary: 'Multiple reports of harassment after dusk.', date: 'May 14, 2026' },
    { id: 4, type: 'red',   x: 22, y: 64, r: 38, status: 'resolved', label: 'Hazaribagh', summary: 'Closed — suspect convicted Feb 2026.', date: 'Feb 2026' },
    { id: 5, type: 'black', x: 48, y: 72, r: 45, status: 'investigating', label: 'New Market', summary: 'Two reports of theft + assault. April 2026.', date: 'Apr 2026' },
  ];
  const visible = zones.filter(z => filter === 'all' || z.status === filter);

  return (
    <>
      <Header back/>
      <div style={{ padding: '4px 20px 12px' }}>
        <div className="eyebrow">Red Zone Map · Dhaka</div>
        <h1 className="h-display" style={{ fontSize: 24, margin: '4px 0 0', lineHeight: 1.1 }}>
          {visible.length} marked zones nearby
        </h1>
        <div style={{ marginTop: 6, fontSize: 12.5, color: 'var(--muted)', fontFamily: 'var(--font-serif)', fontStyle: 'italic' }}>
          Black = sexual assault · Red = homicide. Radius is approximate.
        </div>
      </div>

      <div style={{ padding: '0 20px 10px', display: 'flex', gap: 6, overflowX: 'auto' }} className="no-scrollbar">
        {[['all', 'All'], ['active', 'Active'], ['investigating', 'Under investigation'], ['resolved', 'Resolved']].map(([k, l]) => (
          <button key={k} onClick={() => setFilter(k)} style={{
            padding: '7px 12px', borderRadius: 999, whiteSpace: 'nowrap',
            background: filter === k ? 'var(--navy)' : 'rgba(255,255,255,0.7)',
            color: filter === k ? '#F7F3EE' : 'var(--ink-2)',
            border: '1px solid ' + (filter === k ? 'var(--navy)' : 'var(--mist)'),
            fontSize: 11.5, fontWeight: 500, cursor: 'pointer',
          }}>{l}</button>
        ))}
      </div>

      {/* Map */}
      <div style={{ padding: '0 20px 14px' }}>
        <div style={{
          position: 'relative', height: 420, borderRadius: 16, overflow: 'hidden',
          border: '1px solid var(--mist)',
          background: 'linear-gradient(135deg, #E8E2D6, #D8D0BE)',
        }}>
          {/* Stylized roads/blocks */}
          <svg width="100%" height="100%" viewBox="0 0 360 420" preserveAspectRatio="none" style={{ position: 'absolute', inset: 0 }}>
            {/* River */}
            <path d="M-20 360 Q60 320 140 340 T280 320 T400 350 L400 460 L-20 460 Z" fill="rgba(74,107,92,0.18)"/>
            {/* Park */}
            <path d="M180 60 Q230 70 240 110 T200 170 Q160 160 170 110 Z" fill="rgba(74,107,92,0.15)"/>
            {/* Roads */}
            <g stroke="rgba(11,29,53,0.12)" strokeWidth="1.5" fill="none">
              <path d="M0 90 Q140 80 240 95 T360 100"/>
              <path d="M0 200 L360 210"/>
              <path d="M80 0 L100 420"/>
              <path d="M220 0 L240 420"/>
              <path d="M300 0 L320 420"/>
            </g>
            {/* Block labels */}
            <g fontFamily="var(--font-serif)" fontStyle="italic" fill="rgba(11,29,53,0.35)" fontSize="9">
              <text x="40" y="55">Dhanmondi</text>
              <text x="200" y="55">Mohammadpur</text>
              <text x="40" y="220">Hazaribagh</text>
              <text x="240" y="190">Mirpur</text>
              <text x="160" y="310">New Market</text>
              <text x="50" y="395" fill="rgba(74,107,92,0.7)">Buriganga River</text>
            </g>
          </svg>

          {/* Zones */}
          {visible.map(z => (
            <div key={z.id}
              className={`zone-circle ${z.type === 'black' ? 'zone-black' : 'zone-red'}`}
              style={{ left: `${z.x}%`, top: `${z.y}%`, width: z.r * 1.8, height: z.r * 1.8 }}
              onClick={() => setSelected(z)}
              title={z.label}/>
          ))}

          {/* User pin */}
          <div style={{
            position: 'absolute', left: '46%', top: '46%', transform: 'translate(-50%,-50%)',
          }}>
            <div style={{
              width: 14, height: 14, borderRadius: 999, background: 'var(--navy)',
              border: '3px solid #fff', boxShadow: '0 2px 8px rgba(11,29,53,0.4)',
            }}/>
            <div style={{
              position: 'absolute', top: 18, left: '50%', transform: 'translateX(-50%)',
              fontSize: 9.5, color: 'var(--navy)', fontWeight: 600, letterSpacing: '0.08em',
              textTransform: 'uppercase', whiteSpace: 'nowrap',
            }}>You · Sobhanbag</div>
          </div>

          {/* Legend */}
          <div style={{
            position: 'absolute', bottom: 10, left: 10,
            background: 'rgba(247,243,238,0.92)', backdropFilter: 'blur(8px)',
            border: '1px solid var(--mist)', borderRadius: 10, padding: '8px 10px',
            fontSize: 10.5,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
              <span style={{ width: 12, height: 12, borderRadius: 999, background: 'rgba(20,20,20,0.4)', border: '1px solid rgba(20,20,20,0.7)' }}/>
              <span style={{ color: 'var(--ink-2)' }}>Sexual assault</span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ width: 12, height: 12, borderRadius: 999, background: 'rgba(232,49,42,0.35)', border: '1px solid rgba(232,49,42,0.8)' }}/>
              <span style={{ color: 'var(--ink-2)' }}>Homicide</span>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom sheet for selection */}
      {selected && (
        <div style={{ padding: '4px 20px 28px' }}>
          <div className="card" style={{ background: 'rgba(255,255,255,0.85)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span className={`pill ${selected.status === 'resolved' ? 'pill-resolved' : selected.status === 'active' ? 'pill-escalated' : 'pill-review'}`}>
                <span className="dot"/> {selected.status === 'investigating' ? 'Under investigation' : selected.status[0].toUpperCase() + selected.status.slice(1)}
              </span>
              <span style={{ flex: 1 }}/>
              <button onClick={() => setSelected(null)} style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--muted)' }}><IconX size={16}/></button>
            </div>
            <div className="serif" style={{ fontSize: 18, fontWeight: 500, color: 'var(--navy)', lineHeight: 1.15 }}>{selected.label}</div>
            <div className="mono" style={{ fontSize: 10.5, color: 'var(--muted)', marginTop: 4 }}>{selected.date}</div>
            <div style={{ marginTop: 8, fontSize: 13, color: 'var(--ink-2)', lineHeight: 1.45 }}>{selected.summary}</div>
          </div>
        </div>
      )}
    </>
  );
}

// ═══════════════════════════════════════════════════════════════
//  FEED SCREEN — newspaper layout, mode-filtered
// ═══════════════════════════════════════════════════════════════
function FeedScreen() {
  const { mode } = useApp();
  const [tab, setTab] = React.useState('top');
  const items = FEED.filter(f => f.scope === mode);
  const today = new Date().toLocaleDateString('en-GB', { weekday: 'long', day: '2-digit', month: 'long', year: 'numeric' });

  const visible = items.filter(it => {
    if (tab === 'top')      return it.trusted || it.corr > 100;
    if (tab === 'recent')   return true;
    if (tab === 'trusted')  return it.trusted;
    return true;
  });
  const [hero, ...rest] = visible;

  return (
    <>
      <Header back/>

      {/* Masthead */}
      <div style={{ padding: '4px 20px 0' }}>
        <div className="masthead">
          <div>
            <div className="nameplate">
              The Anchor <em>Verified</em>
            </div>
            <div className="issue" style={{ marginTop: 2 }}>
              {mode === 'campus' ? 'Campus edition · Daffodil' : 'National edition · Bangladesh'} · {today}
            </div>
          </div>
          <div style={{ textAlign: 'right', flexShrink: 0, paddingLeft: 10 }}>
            <div className="eyebrow" style={{ fontSize: 9 }}>Vol. 1 · 042</div>
            <div className="serif" style={{ fontStyle: 'italic', fontSize: 10.5, color: 'var(--muted)', marginTop: 2 }}>
              Human-moderated
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="tabbar" style={{ marginBottom: 4 }}>
          {[['top', 'Top stories'], ['recent', 'Latest'], ['trusted', 'Trusted only']].map(([k, l]) => (
            <button key={k} className={tab === k ? 'on' : ''} onClick={() => setTab(k)}>{l}</button>
          ))}
        </div>
      </div>

      <div style={{ padding: '14px 20px 28px' }}>
        {/* Hero story */}
        {hero && <NewsFeature item={hero}/>}

        {/* Section rule */}
        {rest.length > 0 && (
          <div className="news-rule">More from this edition</div>
        )}

        {/* Two-column-ish stack of rest */}
        {rest.map(it => <NewsCard key={it.id} item={it}/>)}

        {visible.length === 0 && (
          <div style={{ padding: '60px 20px', textAlign: 'center' }}>
            <div className="serif" style={{ fontSize: 20, color: 'var(--navy)' }}>Nothing in this section yet.</div>
            <div style={{ marginTop: 6, fontSize: 13, color: 'var(--muted)', fontFamily: 'var(--font-serif)', fontStyle: 'italic' }}>
              Switch tab to see other stories.
            </div>
          </div>
        )}

        <div className="rule-fancy" style={{ marginTop: 22 }}>End of edition · {items.length} verified items</div>
      </div>
    </>
  );
}

function NewsFeature({ item }) {
  // Split kicker into "Section · Story": use as a teaser line
  const stripParts = [
    item.scope === 'campus' ? 'Anchor verified · Campus edition' : 'Anchor verified · National edition',
    item.byline.when,
    'Human-moderated',
  ];

  // Build a tabloid headline — italic display with mixed sizes
  return (
    <article className="news-feature">
      {/* Promotional red strap */}
      <div className="news-strap">
        <span className="label">{stripParts[0]}</span>
        <span className="label" style={{ flex: 'none' }}>{stripParts[1].toUpperCase()}</span>
      </div>

      {/* Big photo, framed */}
      <div className="news-photo">
        <div className="news-photo-frame">
          <NewsArt variant={item.art}/>
        </div>
        <div className="news-photo-caption">
          <strong>Photo —</strong> {photoCaption(item)}
        </div>
      </div>

      {/* Decorative italic headline */}
      <div className="news-decor">
        <span className="pre">{item.kicker}:</span>
        <span className="title" dangerouslySetInnerHTML={{ __html: decorateHeadline(item.headline) }}/>
      </div>

      {/* Byline */}
      <div className="news-byline">
        by <strong>{item.byline.author}</strong> · {item.byline.source}
      </div>

      {/* Drop-cap lead */}
      <p className="news-lead-drop">{item.lead}</p>

      {/* Trust badges */}
      <div style={{ display: 'flex', gap: 6, marginTop: 12, flexWrap: 'wrap' }}>
        {item.trusted && <span className="pill" style={{ color: 'var(--gold)', borderColor: 'rgba(184,137,58,0.35)', background: 'rgba(184,137,58,0.08)' }}><IconBadge size={9}/> Trusted source</span>}
        <span className="pill pill-resolved"><IconCheck size={9} sw={3}/> Reviewed & published</span>
      </div>

      <div className="news-actions">
        <button className="news-act corr"><IconThumbUp size={13}/> Corroborate · {item.corr}</button>
        <button className="news-act chal"><IconThumbDown size={13}/> Challenge · {item.chal}</button>
      </div>
    </article>
  );
}

function NewsCard({ item }) {
  return (
    <article className="news-card">
      <div className="news-photo">
        <div className="news-photo-frame">
          <NewsArt variant={item.art}/>
        </div>
        <div className="news-photo-caption">
          <strong>Photo —</strong> {photoCaption(item)}
        </div>
      </div>
      <div className="news-kicker">{item.kicker}</div>
      <h3 className="news-headline lg">{item.headline}</h3>
      <div className="news-byline">
        by <strong>{item.byline.author}</strong> · {item.byline.source} · {item.byline.when}
      </div>
      <p style={{ margin: 0, fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.55 }}>{item.lead}</p>
      <div style={{ display: 'flex', gap: 6, marginTop: 10 }}>
        {item.trusted && <span className="pill" style={{ color: 'var(--gold)', borderColor: 'rgba(184,137,58,0.35)', background: 'rgba(184,137,58,0.08)' }}><IconBadge size={9}/> Trusted</span>}
        <span className="pill pill-resolved"><IconCheck size={9} sw={3}/> Reviewed</span>
      </div>
      <div className="news-actions">
        <button className="news-act corr"><IconThumbUp size={13}/> Corroborate · {item.corr}</button>
        <button className="news-act chal"><IconThumbDown size={13}/> Challenge · {item.chal}</button>
      </div>
    </article>
  );
}

// Helper: photo captions matching the news art variant
function photoCaption(item) {
  const captions = {
    protest:  'crowd footage at the cordon, cross-checked against ministry briefing.',
    traffic:  'live view of the Mirpur-10 intersection during the disruption window.',
    court:    'the Cyber Tribunal building, where new fast-track hearings will be held.',
    road:     'street near the closed file location, marked on the Anchor red zone map.',
    building: 'campus administrative block — registration notice was issued from here.',
    library:  'the affected reading sections, photographed two days before closure.',
    mess:     'a recent meal at the Block C mess, used as evidence in the audit.',
  };
  return captions[item.art] || 'verified imagery from the Anchor newsroom.';
}

// Helper: wrap ampersands and em-dashes in italic spans so the display headline
// renders with mixed sizes the way a classic tabloid headline would
function decorateHeadline(text) {
  return text
    .replace(/&/g, '<span class="amp">&amp;</span>')
    .replace(/ — /g, '<span class="amp"> — </span>');
}

// ═══════════════════════════════════════════════════════════════
//  LAWYERS SCREEN
// ═══════════════════════════════════════════════════════════════
function LawyersScreen() {
  const lawyers = [
    { n: 'Adv. Farzana Kabir', spec: ['Criminal', 'Cyber'], lang: 'BN · EN', rate: 4.9, count: 312, bar: 'BC-2014-DH-04812', avail: 'Available now', initials: 'FK', color: '#4A6B5C' },
    { n: 'Adv. Tanvir Hossain', spec: ['Civil', 'Constitutional'], lang: 'BN · EN', rate: 4.7, count: 198, bar: 'BC-2011-DH-02144', avail: 'Replies in 1h', initials: 'TH', color: '#0B1D35' },
    { n: 'Adv. Mahbuba Akter', spec: ['Family', 'DV Act'], lang: 'BN', rate: 4.8, count: 240, bar: 'BC-2016-DH-06721', avail: 'Available tomorrow', initials: 'MA', color: '#B8893A' },
    { n: 'Adv. Rifat Chowdhury', spec: ['Cyber', 'Criminal'], lang: 'BN · EN · HI', rate: 4.6, count: 154, bar: 'BC-2018-DH-07810', avail: 'Available now', initials: 'RC', color: '#C44536' },
  ];

  return (
    <>
      <Header back title="Find a Lawyer" subtitle="Verified · Bar-Council certified"/>

      <div style={{ padding: '14px 20px 6px' }}>
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px',
          background: 'rgba(255,255,255,0.7)', border: '1px solid var(--mist-2)', borderRadius: 999,
        }}>
          <IconSearch size={15} stroke="var(--muted)"/>
          <input placeholder="Search by name, specialty, location…" style={{
            flex: 1, border: 'none', outline: 'none', background: 'transparent',
            fontFamily: 'var(--font-sans)', fontSize: 13.5, color: 'var(--ink)',
          }}/>
        </div>

        <div style={{ display: 'flex', gap: 6, marginTop: 10, overflowX: 'auto' }} className="no-scrollbar">
          {['All', 'Criminal', 'Civil', 'Family', 'Constitutional', 'Cyber', 'DV Act'].map((f, i) => (
            <span key={f} style={{
              padding: '6px 11px', borderRadius: 999, whiteSpace: 'nowrap',
              background: i === 0 ? 'var(--navy)' : 'rgba(255,255,255,0.7)',
              color: i === 0 ? '#F7F3EE' : 'var(--ink-2)',
              border: '1px solid ' + (i === 0 ? 'var(--navy)' : 'var(--mist)'),
              fontSize: 11.5, fontWeight: 500, cursor: 'pointer',
            }}>{f}</span>
          ))}
        </div>
      </div>

      <div style={{ padding: '12px 20px 28px' }}>
        {lawyers.map((l, i) => (
          <div key={i} style={{
            padding: 14, background: 'rgba(255,255,255,0.7)',
            border: '1px solid var(--mist)', borderRadius: 14, marginBottom: 10,
          }}>
            <div style={{ display: 'flex', gap: 12 }}>
              <div style={{
                width: 52, height: 52, borderRadius: 12, flexShrink: 0,
                background: `linear-gradient(135deg, ${l.color}, ${l.color}cc)`,
                color: '#F7F3EE',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: 'var(--font-serif)', fontWeight: 500, fontSize: 18,
                border: '1px solid rgba(11,29,53,0.08)',
              }}>{l.initials}</div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div className="serif" style={{ fontSize: 15.5, fontWeight: 500, color: 'var(--navy)' }}>{l.n}</div>
                  <span title="Verified bar-council ID" style={{
                    width: 14, height: 14, borderRadius: 999, background: 'var(--gold)', color: '#fff',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                  }}><IconCheck size={9} sw={3.2}/></span>
                </div>
                <div className="mono" style={{ fontSize: 10.5, color: 'var(--muted)', marginTop: 1 }}>{l.bar}</div>
                <div style={{ display: 'flex', gap: 4, marginTop: 6, flexWrap: 'wrap' }}>
                  {l.spec.map(s => (
                    <span key={s} style={{
                      padding: '2px 7px', borderRadius: 6, background: 'var(--cream-2)',
                      border: '1px solid var(--mist)', fontSize: 10, color: 'var(--ink-2)',
                    }}>{s}</span>
                  ))}
                </div>
                <div style={{ marginTop: 6, display: 'flex', alignItems: 'center', gap: 10, fontSize: 11, color: 'var(--muted)' }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}><IconStar size={11} stroke="var(--gold)" fill="var(--gold)"/> {l.rate} <span style={{ color: 'var(--mist-2)' }}>·</span> {l.count}</span>
                  <span>{l.lang}</span>
                </div>
              </div>
            </div>
            <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px dashed var(--mist)', display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, color: 'var(--sage-2)' }}>
                <span style={{ width: 6, height: 6, borderRadius: 999, background: 'var(--sage)' }}/> {l.avail}
              </span>
              <span style={{ flex: 1 }}/>
              <button style={{
                padding: '8px 12px', borderRadius: 10, background: 'var(--navy)', color: '#F7F3EE',
                border: 'none', fontSize: 12, fontWeight: 500, cursor: 'pointer',
                display: 'inline-flex', alignItems: 'center', gap: 6,
              }}>
                <IconLock size={12}/> Start E2EE chat
              </button>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

// ═══════════════════════════════════════════════════════════════
//  NOTICES SCREEN
// ═══════════════════════════════════════════════════════════════
function NoticesScreen() {
  const notices = [
    { tag: 'University-wide', date: 'May 23, 2026', title: 'Summer 2026 mid-term examination schedule released',
      bn: 'গ্রীষ্ম ২০২৬ মিড-টার্ম পরীক্ষার সময়সূচি প্রকাশিত',
      summary: 'Mid-terms for all departments will commence on June 8. Detailed routine attached. Students must collect admit cards from departmental offices by June 3.' },
    { tag: 'Department · SWE', date: 'May 22, 2026', title: 'SWE-3rd year industrial visit — registration open',
      bn: 'SWE-৩য় বর্ষের ইন্ডাস্ট্রিয়াল ভিজিটের রেজিস্ট্রেশন চলছে',
      summary: 'Two-day visit to Robi Axiata and BJIT. Limited to 60 students. Selection on merit + first-come basis.' },
    { tag: 'Batch · 2024', date: 'May 21, 2026', title: 'Tuition fee installment reminder — 2nd cycle',
      bn: '২৪ ব্যাচ — টিউশন ফি ২য় কিস্তির রিমাইন্ডার',
      summary: 'Final date to pay 2nd installment is May 31. Late payment incurs 5% surcharge.' },
    { tag: 'University-wide', date: 'May 19, 2026', title: 'Library inter-section renovation — temporary access changes',
      bn: 'লাইব্রেরি সেকশনের সংস্কার — সাময়িক প্রবেশ পরিবর্তন',
      summary: 'Sections A and B will be closed from May 25 to June 12. Students may access digital library and reading room C as usual.' },
  ];
  const [showBn, setShowBn] = React.useState(false);

  return (
    <>
      <Header back title="Notices" subtitle="University · Department · Batch"/>

      <div style={{ padding: '12px 20px 4px', display: 'flex', alignItems: 'center', gap: 8 }}>
        <div className="tabbar" style={{ flex: 1 }}>
          {['All', 'University', 'Department', 'Batch'].map((t, i) => (
            <button key={t} className={i === 0 ? 'on' : ''}>{t}</button>
          ))}
        </div>
      </div>

      <div style={{ padding: '8px 20px 4px', display: 'flex', justifyContent: 'flex-end' }}>
        <button onClick={() => setShowBn(v => !v)} style={{
          padding: '6px 10px', borderRadius: 999, background: 'transparent',
          border: '1px solid var(--mist-2)', fontSize: 11, fontWeight: 600,
          letterSpacing: '0.06em', color: 'var(--ink-2)', cursor: 'pointer',
          display: 'inline-flex', alignItems: 'center', gap: 5,
        }}>
          <IconSparkles size={12} stroke="var(--gold)"/> AI summary · {showBn ? 'বাংলা' : 'English'}
        </button>
      </div>

      <div style={{ padding: '8px 20px 28px' }}>
        {notices.map((n, i) => (
          <div key={i} style={{
            padding: '18px 0', borderBottom: '1px solid var(--mist)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
              <span className="eyebrow">{n.tag}</span>
              <span style={{ width: 3, height: 3, borderRadius: 999, background: 'var(--mist-2)' }}/>
              <span className="mono" style={{ fontSize: 10.5, color: 'var(--muted)' }}>{n.date}</span>
            </div>
            <div className={showBn ? 'serif bn' : 'serif'} style={{
              fontSize: showBn ? 18 : 19, fontWeight: 500,
              lineHeight: 1.2, color: 'var(--navy)', letterSpacing: '-0.005em',
            }}>
              {showBn ? n.bn : n.title}
            </div>
            <div style={{ marginTop: 8, padding: '10px 12px', background: 'rgba(184,137,58,0.06)', border: '1px solid rgba(184,137,58,0.18)', borderRadius: 10 }}>
              <div className="eyebrow" style={{ color: 'var(--gold)', marginBottom: 4, fontSize: 9.5 }}>
                <IconSparkles size={10} stroke="var(--gold)"/> AI summary
              </div>
              <div style={{ fontSize: 12.5, color: 'var(--ink-2)', lineHeight: 1.45 }}>{n.summary}</div>
            </div>
          </div>
        ))}
      </div>
    </>
  );
}

// ═══════════════════════════════════════════════════════════════
//  PROFILE SCREEN
// ═══════════════════════════════════════════════════════════════
function ProfileScreen() {
  return (
    <>
      <Header back/>
      <div style={{ padding: '16px 20px 8px' }}>
        <div style={{
          padding: 18, borderRadius: 18, background: 'linear-gradient(180deg, rgba(255,255,255,0.85), rgba(255,255,255,0.55))',
          border: '1px solid var(--mist)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
            <div style={{
              width: 56, height: 56, borderRadius: 999, position: 'relative',
              background: 'linear-gradient(135deg, #C9B7A2, #8E7A60)',
              color: '#F7F3EE', display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: 'var(--font-serif)', fontWeight: 500, fontSize: 22,
            }}>
              SA
              <span style={{
                position: 'absolute', bottom: -2, right: -2, width: 20, height: 20, borderRadius: 999,
                background: 'var(--gold)', color: '#fff', display: 'flex',
                alignItems: 'center', justifyContent: 'center', border: '2.5px solid var(--cream)',
              }}><IconCheck size={11} sw={3}/></span>
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="serif" style={{ fontSize: 19, fontWeight: 500, color: 'var(--navy)', lineHeight: 1.1 }}>Sadia Akter</div>
              <div style={{ marginTop: 4, fontSize: 12.5, color: 'var(--ink-2)' }}>
                SWE · 4th year · Daffodil International University
              </div>
              <div style={{ marginTop: 6, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                <span className="pill" style={{ color: 'var(--gold)', borderColor: 'rgba(184,137,58,0.35)', background: 'rgba(184,137,58,0.08)' }}><IconCheck size={9} sw={3}/> Verified DIU</span>
                <span className="pill"><IconClock size={10}/> Since Jan 2024</span>
              </div>
            </div>
          </div>

          {/* Stats */}
          <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px dashed var(--mist)', display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
            {[
              { l: 'Cases filed', v: '7' },
              { l: 'Resolved', v: '4' },
              { l: 'Trust score', v: '92' },
            ].map(s => (
              <div key={s.l} style={{ textAlign: 'center' }}>
                <div className="serif" style={{ fontSize: 22, fontWeight: 500, color: 'var(--navy)', letterSpacing: '-0.02em' }}>{s.v}</div>
                <div className="eyebrow" style={{ marginTop: 2, fontSize: 9.5 }}>{s.l}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Settings sections */}
      <div style={{ padding: '14px 20px 0' }}>
        <SettingsGroup title="Preferences" items={[
          { label: 'Language',            value: 'English · বাংলা', Icon: IconGlobe },
          { label: 'Notifications',       value: 'On · selective',  Icon: IconBell },
          { label: 'Default anonymity',   value: 'Always ask',       Icon: IconEyeOff },
        ]}/>
        <SettingsGroup title="Safety" items={[
          { label: "Dead Man's Switch",   value: 'Active · 48h',     Icon: IconShield, accent: 'var(--ember)' },
          { label: 'Two-factor auth',     value: 'TOTP · enabled',   Icon: IconLock },
          { label: 'Trusted contacts',    value: '3 set',             Icon: IconPhone },
        ]}/>
        <SettingsGroup title="Data" items={[
          { label: 'Export my data',      value: 'JSON · PDF',       Icon: IconUpload },
          { label: 'Delete account',      value: 'Permanent',         Icon: IconX, danger: true },
        ]}/>
      </div>

      <div style={{ padding: '6px 20px 32px', textAlign: 'center' }}>
        <div className="serif" style={{ fontStyle: 'italic', fontSize: 12, color: 'var(--muted)' }}>
          Anchor AI v0.4 · build 2026-05-23
        </div>
        <div style={{ marginTop: 4, fontSize: 10.5, color: 'var(--muted)', letterSpacing: '0.06em' }}>
          Built by Team AiVion · Daffodil International University
        </div>
      </div>
    </>
  );
}

function SettingsGroup({ title, items }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div className="eyebrow" style={{ marginBottom: 8 }}>{title}</div>
      <div style={{
        background: 'rgba(255,255,255,0.7)', border: '1px solid var(--mist)',
        borderRadius: 14, overflow: 'hidden',
      }}>
        {items.map((it, i) => {
          const Ico = it.Icon;
          return (
            <div key={i} style={{
              display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px',
              borderBottom: i < items.length - 1 ? '1px solid var(--mist)' : 'none',
            }}>
              <div style={{
                width: 30, height: 30, borderRadius: 8,
                background: it.danger ? 'rgba(232,49,42,0.08)' : 'var(--cream-2)',
                color: it.danger ? 'var(--red)' : (it.accent || 'var(--navy)'),
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                border: '1px solid ' + (it.danger ? 'rgba(232,49,42,0.2)' : 'var(--mist)'),
              }}><Ico size={15}/></div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 500, color: it.danger ? 'var(--red)' : 'var(--navy)' }}>{it.label}</div>
                <div style={{ fontSize: 11.5, color: 'var(--muted)' }}>{it.value}</div>
              </div>
              <IconChevronRight size={14} stroke="var(--mist-2)"/>
            </div>
          );
        })}
      </div>
    </div>
  );
}

Object.assign(window, {
  CasesScreen, CaseDetailScreen, MapScreen, FeedScreen,
  LawyersScreen, NoticesScreen, ProfileScreen,
});
