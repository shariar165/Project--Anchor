// officer-scorecards.jsx — National-mode police accountability scorecard.
// Depends on: icons.jsx, app.jsx (useApp, Header), applications.jsx (apiFetch global).
// Routes: officer-scorecard (directory), police-station (detail), rate-station (rating form)

const { useState: _osS, useEffect: _osE } = React;

const OS_BASE = window.ANCHOR_API_URL || 'http://localhost:8000';

const osFetch = (typeof apiFetch === 'function')
  ? apiFetch
  : async (path, opts = {}) => {
      const res = await fetch(OS_BASE + path, {
        ...opts,
        headers: { 'Authorization': 'Bearer ' + (localStorage.getItem('anchor_access_token') || ''), ...(opts.headers || {}) },
      });
      if (!res.ok) { let d = 'Request failed'; try { d = (await res.json()).detail || d; } catch {} throw new Error(d); }
      return res.status === 204 ? null : res.json();
    };

function Stars({ value, size = 13 }) {
  const v = value || 0;
  return (
    <span style={{ display: 'inline-flex', gap: 1, color: 'var(--gold)', fontSize: size, lineHeight: 1 }}>
      {[1, 2, 3, 4, 5].map(i => (
        <span key={i} style={{ opacity: i <= Math.round(v) ? 1 : 0.25 }}>★</span>
      ))}
    </span>
  );
}

function ScoreBar({ label, value }) {
  const pct = value ? (value / 5) * 100 : 0;
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11.5, marginBottom: 4 }}>
        <span style={{ color: 'var(--muted)', fontWeight: 600 }}>{label}</span>
        <span className="mono" style={{ color: 'var(--navy)' }}>{value != null ? value.toFixed(1) : '—'}</span>
      </div>
      <div style={{ height: 6, borderRadius: 999, background: 'var(--mist)', overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: 'var(--ember)', borderRadius: 999 }}/>
      </div>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// OfficerScorecardScreen — station directory
// ────────────────────────────────────────────────────────────────────────────

function OfficerScorecardScreen() {
  const { go } = useApp();
  const [stations, setStations] = _osS([]);
  const [loading, setLoading] = _osS(true);
  const [error, setError] = _osS(null);
  const [q, setQ] = _osS('');

  _osE(() => {
    setLoading(true);
    osFetch('/v1/officer-scorecards/stations')
      .then(setStations).catch(e => setError(e.message)).finally(() => setLoading(false));
  }, []);

  const filtered = stations.filter(s =>
    !q.trim() || s.name.toLowerCase().includes(q.toLowerCase()) || s.district.toLowerCase().includes(q.toLowerCase()));

  return (
    <>
      <Header title="Officer scorecard" subtitle="Public accountability" back/>
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 20px 100px' }}>
        <div style={{ background: 'rgba(196,69,54,0.06)', border: '1px solid rgba(196,69,54,0.18)', borderRadius: 12, padding: '11px 14px', marginBottom: 14, fontSize: 12, color: 'var(--ink-2)', lineHeight: 1.55 }}>
          Community ratings of police stations and officers. Submissions are <strong>reviewed before</strong> they count toward a station's public score.
        </div>

        <input value={q} onChange={e => setQ(e.target.value)} placeholder="Search thana or district…" style={{
          width: '100%', padding: '10px 14px', borderRadius: 12, boxSizing: 'border-box', marginBottom: 14,
          border: '1px solid var(--mist)', background: 'rgba(255,255,255,0.85)', fontFamily: 'var(--font-sans)', fontSize: 13, color: 'var(--navy)', outline: 'none',
        }}/>

        {loading && <div style={{ textAlign: 'center', padding: 40, color: 'var(--muted)', fontSize: 13 }}>Loading…</div>}
        {!loading && error && <div style={{ padding: 16, background: 'rgba(232,49,42,0.06)', borderRadius: 12, color: 'var(--red)', fontSize: 13, textAlign: 'center' }}>{error}</div>}
        {!loading && !error && filtered.length === 0 && <div style={{ textAlign: 'center', padding: 40, color: 'var(--muted)', fontSize: 13 }}>No stations found.</div>}

        {!loading && !error && filtered.map(s => (
          <button key={s.id} onClick={() => go('police-station', { id: s.id })} style={{
            width: '100%', textAlign: 'left', background: 'rgba(255,255,255,0.7)', border: '1px solid var(--mist)',
            borderRadius: 14, padding: 14, marginBottom: 10, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 12,
          }}>
            <div style={{ width: 38, height: 38, borderRadius: 10, flexShrink: 0, background: 'rgba(196,69,54,0.12)', border: '1px solid rgba(196,69,54,0.25)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--ember)' }}>
              <IconBadge size={17}/>
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="serif" style={{ fontSize: 15, fontWeight: 500, color: 'var(--navy)', lineHeight: 1.2 }}>{s.name}</div>
              <div style={{ fontSize: 11.5, color: 'var(--muted)', marginTop: 3 }}>{s.district}{s.division ? ` · ${s.division}` : ''}</div>
            </div>
            <div style={{ textAlign: 'right', flexShrink: 0 }}>
              <Stars value={s.avg_overall}/>
              <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 3 }}>
                {s.total_count > 0 ? `${s.avg_overall.toFixed(1)} · ${s.total_count} rating${s.total_count === 1 ? '' : 's'}` : 'No ratings'}
              </div>
            </div>
          </button>
        ))}
      </div>
    </>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// StationDetailScreen
// ────────────────────────────────────────────────────────────────────────────

function StationDetailScreen({ params = {} }) {
  const { go, back } = useApp();
  const [s, setS] = _osS(null);
  const [loading, setLoading] = _osS(true);
  const [error, setError] = _osS(null);

  _osE(() => {
    setLoading(true);
    osFetch(`/v1/officer-scorecards/stations/${params.id}`)
      .then(setS).catch(e => setError(e.message)).finally(() => setLoading(false));
  }, [params.id]);

  if (loading) return <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--cream)', color: 'var(--muted)', fontSize: 13 }}>Loading…</div>;
  if (error || !s) return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 14, alignItems: 'center', justifyContent: 'center', background: 'var(--cream)' }}>
      <div style={{ color: 'var(--red)', fontSize: 13 }}>{error || 'Station not found'}</div>
      <button onClick={back} className="btn btn-ghost" style={{ fontSize: 12 }}>Go back</button>
    </div>
  );

  const maxHist = Math.max(1, ...Object.values(s.histogram || {}));

  return (
    <>
      <Header title={s.name} subtitle={`${s.district}${s.division ? ' · ' + s.division : ''}`} back/>
      <div style={{ flex: 1, overflowY: 'auto', padding: '14px 20px 20px' }}>
        {/* Overall */}
        <div style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid var(--mist)', borderRadius: 14, padding: '18px 16px', marginBottom: 14, textAlign: 'center' }}>
          <div className="serif" style={{ fontSize: 40, fontWeight: 600, color: 'var(--navy)', lineHeight: 1 }}>{s.avg_overall != null ? s.avg_overall.toFixed(1) : '—'}</div>
          <div style={{ margin: '8px 0 4px' }}><Stars value={s.avg_overall} size={18}/></div>
          <div style={{ fontSize: 12, color: 'var(--muted)' }}>{s.total_count} approved rating{s.total_count === 1 ? '' : 's'}</div>
        </div>

        {/* Dimension bars */}
        <div style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid var(--mist)', borderRadius: 14, padding: '14px 16px', marginBottom: 14 }}>
          <div className="eyebrow" style={{ marginBottom: 12 }}>Breakdown</div>
          <ScoreBar label="Responsiveness" value={s.avg_responsiveness}/>
          <ScoreBar label="Conduct & courtesy" value={s.avg_conduct}/>
          <ScoreBar label="Integrity (bribery-free)" value={s.avg_integrity}/>
        </div>

        {/* Histogram */}
        {s.total_count > 0 && (
          <div style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid var(--mist)', borderRadius: 14, padding: '14px 16px', marginBottom: 14 }}>
            <div className="eyebrow" style={{ marginBottom: 12 }}>Rating distribution</div>
            {[5, 4, 3, 2, 1].map(star => (
              <div key={star} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <span style={{ fontSize: 11, color: 'var(--muted)', width: 28 }}>{star}★</span>
                <div style={{ flex: 1, height: 8, borderRadius: 999, background: 'var(--mist)', overflow: 'hidden' }}>
                  <div style={{ width: `${((s.histogram[String(star)] || 0) / maxHist) * 100}%`, height: '100%', background: 'var(--gold)' }}/>
                </div>
                <span className="mono" style={{ fontSize: 10.5, color: 'var(--muted)', width: 20, textAlign: 'right' }}>{s.histogram[String(star)] || 0}</span>
              </div>
            ))}
          </div>
        )}

        {/* Officers */}
        {s.officers && s.officers.length > 0 && (
          <div style={{ marginBottom: 14 }}>
            <div className="eyebrow" style={{ marginBottom: 10 }}>Officers at this station</div>
            {s.officers.map(o => (
              <button key={o.id} onClick={() => go('rate-station', { stationId: s.id, stationName: s.name, officerId: o.id, officerName: o.name })} style={{
                width: '100%', textAlign: 'left', background: 'rgba(255,255,255,0.7)', border: '1px solid var(--mist)',
                borderRadius: 12, padding: 12, marginBottom: 8, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 10,
              }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--navy)' }}>{o.name}</div>
                  <div style={{ fontSize: 11, color: 'var(--muted)', marginTop: 2 }}>{o.rank || 'Officer'}{o.badge_no ? ` · #${o.badge_no}` : ''}</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <Stars value={o.avg_overall}/>
                  <div style={{ fontSize: 10, color: 'var(--muted)', marginTop: 2 }}>{o.total_count > 0 ? `${o.avg_overall.toFixed(1)} · ${o.total_count}` : 'No ratings'}</div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      <div style={{ padding: '12px 20px 24px', borderTop: '1px solid var(--mist)', background: 'var(--cream)', flexShrink: 0 }}>
        <button onClick={() => go('rate-station', { stationId: s.id, stationName: s.name })} className="btn btn-primary" style={{ width: '100%' }}>
          Rate this station
        </button>
      </div>
    </>
  );
}

// ────────────────────────────────────────────────────────────────────────────
// RateStationScreen
// ────────────────────────────────────────────────────────────────────────────

function StarPicker({ value, onChange }) {
  return (
    <div style={{ display: 'flex', gap: 6 }}>
      {[1, 2, 3, 4, 5].map(i => (
        <button key={i} onClick={() => onChange(i)} style={{
          background: 'none', border: 'none', cursor: 'pointer', padding: 2, fontSize: 28, lineHeight: 1,
          color: i <= value ? 'var(--gold)' : 'var(--mist-2)',
        }}>★</button>
      ))}
    </div>
  );
}

function RateStationScreen({ params = {} }) {
  const { go, back } = useApp();
  const [scores, setScores] = _osS({ responsiveness: 0, conduct: 0, integrity: 0, overall: 0 });
  const [comment, setComment] = _osS('');
  const [anonymous, setAnonymous] = _osS(true);
  const [submitting, setSubmitting] = _osS(false);
  const [done, setDone] = _osS(false);
  const [err, setErr] = _osS(null);

  const setScore = (k, v) => setScores(s => ({ ...s, [k]: v }));
  const ready = scores.responsiveness && scores.conduct && scores.integrity && scores.overall;

  const submit = async () => {
    if (!ready) { setErr('Please rate all four areas.'); return; }
    setSubmitting(true); setErr(null);
    try {
      await osFetch('/v1/officer-scorecards/ratings', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          station_id: params.stationId, officer_id: params.officerId || null,
          ...scores, comment: comment.trim() || null, anonymous,
        }),
      });
      setDone(true);
    } catch (e) {
      setErr(e.message);
    } finally {
      setSubmitting(false);
    }
  };

  if (done) return (
    <>
      <Header title="Submitted" back={false}/>
      <div style={{ padding: '40px 20px 100px', textAlign: 'center' }}>
        <div style={{ width: 64, height: 64, borderRadius: 18, background: 'rgba(184,137,58,0.14)', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 18px', color: 'var(--gold)' }}>
          <IconCheck size={30} sw={2.5}/>
        </div>
        <div className="serif" style={{ fontSize: 21, fontWeight: 600, color: 'var(--navy)', marginBottom: 8 }}>Thanks — under review</div>
        <div style={{ fontSize: 13.5, color: 'var(--muted)', lineHeight: 1.6, marginBottom: 26 }}>
          Your rating was submitted. A moderator will review it before it counts toward {params.stationName || 'the station'}'s public score.
        </div>
        <button onClick={() => go('police-station', { id: params.stationId })} className="btn btn-primary" style={{ width: '100%', marginBottom: 10 }}>Back to station</button>
        <button onClick={() => go('officer-scorecard')} style={{ background: 'none', border: 'none', color: 'var(--muted)', fontSize: 12, cursor: 'pointer', width: '100%' }}>All stations</button>
      </div>
    </>
  );

  const dims = [
    ['responsiveness', 'Responsiveness', 'Speed and willingness to help'],
    ['conduct', 'Conduct & courtesy', 'Respectful, professional behaviour'],
    ['integrity', 'Integrity', 'Free from bribery / corruption'],
    ['overall', 'Overall', 'Your overall experience'],
  ];

  return (
    <>
      <Header title={`Rate ${params.officerName || params.stationName || 'station'}`} subtitle={params.officerName ? params.stationName : 'Anonymous & moderated'} back/>
      <div style={{ flex: 1, overflowY: 'auto', padding: '14px 20px 120px' }}>
        {err && <div style={{ color: 'var(--red)', fontSize: 12.5, background: 'rgba(232,49,42,0.07)', borderRadius: 10, padding: '9px 13px', marginBottom: 12 }}>{err}</div>}

        {dims.map(([k, label, hint]) => (
          <div key={k} style={{ background: 'rgba(255,255,255,0.7)', border: '1px solid var(--mist)', borderRadius: 14, padding: '14px 16px', marginBottom: 10 }}>
            <div style={{ fontSize: 13.5, fontWeight: 600, color: 'var(--navy)' }}>{label}</div>
            <div style={{ fontSize: 11.5, color: 'var(--muted)', marginBottom: 10 }}>{hint}</div>
            <StarPicker value={scores[k]} onChange={v => setScore(k, v)}/>
          </div>
        ))}

        <div style={{ marginTop: 4, marginBottom: 12 }}>
          <div style={{ fontSize: 10.5, fontWeight: 700, color: 'var(--muted)', textTransform: 'uppercase', letterSpacing: '0.12em', marginBottom: 6 }}>Comment (optional)</div>
          <textarea value={comment} onChange={e => setComment(e.target.value)} maxLength={2000} placeholder="Describe your experience. Avoid naming uninvolved people." style={{
            width: '100%', minHeight: 90, padding: '10px 12px', borderRadius: 10, boxSizing: 'border-box',
            border: '1px solid var(--mist)', background: 'rgba(255,255,255,0.85)', fontFamily: 'var(--font-sans)', fontSize: 13, color: 'var(--navy)', resize: 'vertical', outline: 'none',
          }}/>
        </div>

        <label style={{ display: 'flex', alignItems: 'center', gap: 10, fontSize: 13, color: 'var(--ink-2)', cursor: 'pointer' }}>
          <input type="checkbox" checked={anonymous} onChange={e => setAnonymous(e.target.checked)}/>
          Submit anonymously (your name is hidden from the public)
        </label>
      </div>
      <div style={{ padding: '12px 20px 24px', borderTop: '1px solid var(--mist)', background: 'var(--cream)' }}>
        <button onClick={submit} disabled={submitting} className="btn btn-primary" style={{ width: '100%', opacity: ready ? 1 : 0.6 }}>
          {submitting ? 'Submitting…' : 'Submit rating'}
        </button>
      </div>
    </>
  );
}
