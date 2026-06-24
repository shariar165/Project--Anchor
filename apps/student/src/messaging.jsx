// ═══════════════════════════════════════════════════════════════
//  MESSAGING — E2EE user ↔ lawyer chat + "Apply as a Lawyer"
//  Distinct from the AI chat (chat-pro.jsx). Uses global E2EE helper
//  (e2ee.jsx) and apiFetch (applications.jsx). Server stores ciphertext only.
// ═══════════════════════════════════════════════════════════════
const _MSG_API = window.ANCHOR_API_URL || 'http://localhost:8000';

function fmtTime(ts) {
  if (!ts) return '';
  try {
    return new Date(ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch (e) { return ''; }
}

// ── Conversations list ─────────────────────────────────────────
function ConversationsScreen() {
  const { go } = useApp();
  const [convs, setConvs] = React.useState([]);
  const [loading, setLoading] = React.useState(true);
  const [error, setError] = React.useState('');

  React.useEffect(() => {
    let alive = true;
    (async () => {
      try {
        if (window.E2EE) { try { await E2EE.ensureKeyPair(); } catch (e) {} }
        const data = await apiFetch('/v1/conversations');
        if (alive) { setConvs(data); setLoading(false); }
      } catch (e) {
        if (alive) { setError('Could not load messages.'); setLoading(false); }
      }
    })();
    return () => { alive = false; };
  }, []);

  return (
    <>
      <Header back title="Messages" subtitle="End-to-end encrypted"/>
      <div style={{ padding: '14px 20px 28px' }}>
        {loading && <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--muted)', fontSize: 13, fontFamily: 'var(--font-sans)' }}>Loading…</div>}
        {error && <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--red)', fontSize: 13, fontFamily: 'var(--font-sans)' }}>{error}</div>}
        {!loading && !error && convs.length === 0 && (
          <div style={{ textAlign: 'center', padding: '48px 16px', color: 'var(--muted)', fontSize: 13, fontFamily: 'var(--font-sans)' }}>
            <IconLock size={22} stroke="var(--mist-2)"/>
            <div style={{ marginTop: 10 }}>No conversations yet.</div>
            <div style={{ marginTop: 4, fontSize: 12 }}>Start an encrypted chat from Find a Lawyer.</div>
          </div>
        )}
        {convs.map((c) => (
          <button key={c.id} onClick={() => go('chat-thread', { conv: c })} style={{
            width: '100%', textAlign: 'left', cursor: 'pointer',
            padding: 14, background: 'var(--surface)',
            border: '1px solid var(--mist)', borderRadius: 14, marginBottom: 10,
            display: 'flex', alignItems: 'center', gap: 12,
          }}>
            <div style={{
              width: 46, height: 46, borderRadius: 12, flexShrink: 0,
              background: 'linear-gradient(135deg, var(--brand), #1c3a5e)', color: '#F7F3EE',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: 'var(--font-serif)', fontWeight: 500, fontSize: 16,
            }}>{(c.counterpart_name || '?').slice(0, 1).toUpperCase()}</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div className="serif" style={{ fontSize: 15, fontWeight: 500, color: 'var(--navy)' }}>{c.counterpart_name}</div>
                {c.counterpart_role === 'lawyer' && (
                  <span title="Verified lawyer" style={{ width: 14, height: 14, borderRadius: 999, background: 'var(--gold)', color: '#fff', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><IconCheck size={9} sw={3.2}/></span>
                )}
              </div>
              <div style={{ fontSize: 11.5, color: 'var(--muted)', marginTop: 2, fontFamily: 'var(--font-sans)' }}>
                {c.last_message_at ? fmtTime(c.last_message_at) : 'No messages yet'}
              </div>
            </div>
            {c.unread_count > 0 && (
              <span style={{ minWidth: 20, height: 20, padding: '0 6px', borderRadius: 999, background: 'var(--ember)', color: '#fff', fontSize: 11, fontWeight: 600, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>{c.unread_count}</span>
            )}
          </button>
        ))}
      </div>
    </>
  );
}

// ── Single encrypted thread ────────────────────────────────────
function ChatThreadScreen({ params }) {
  const { auth } = useApp();
  const conv = (params && params.conv) || {};
  const myId = auth && auth.user ? String(auth.user.id) : null;

  const [messages, setMessages] = React.useState([]);
  const [text, setText] = React.useState('');
  const [keyReady, setKeyReady] = React.useState(false);
  const [keyMissing, setKeyMissing] = React.useState(false);
  const [sending, setSending] = React.useState(false);
  const keyRef = React.useRef(null);
  const seenRef = React.useRef(new Set());
  const scrollRef = React.useRef(null);

  const appendDecrypted = React.useCallback(async (raw) => {
    if (!raw || !raw.id || seenRef.current.has(raw.id)) return;
    seenRef.current.add(raw.id);
    let body = '🔒 encrypted';
    if (keyRef.current) body = await E2EE.decrypt(keyRef.current, raw.ciphertext, raw.iv);
    setMessages(prev => [...prev, {
      id: raw.id,
      mine: String(raw.sender_id) === myId,
      text: body,
      created_at: raw.created_at,
    }].sort((a, b) => new Date(a.created_at) - new Date(b.created_at)));
  }, [myId]);

  // Set up the shared key, load history, open the live stream.
  React.useEffect(() => {
    let alive = true;
    let es = null;
    (async () => {
      try {
        if (window.E2EE) await E2EE.ensureKeyPair();
        // Resolve the counterpart public key (from the conv payload or by fetching).
        let pubKey = conv.counterpart_public_key;
        if (!pubKey && conv.counterpart_user_id) {
          try {
            const k = await apiFetch('/v1/e2ee/keys/' + conv.counterpart_user_id);
            pubKey = k.public_key_jwk;
          } catch (e) { /* 404 — counterpart has no key yet */ }
        }
        if (pubKey) {
          keyRef.current = await E2EE.deriveKey(pubKey);
          if (alive) setKeyReady(true);
        } else if (alive) {
          setKeyMissing(true);
        }

        const history = await apiFetch('/v1/conversations/' + conv.id + '/messages');
        for (const m of history) await appendDecrypted(m);
        try { await apiFetch('/v1/conversations/' + conv.id + '/read', { method: 'POST' }); } catch (e) {}

        // Live updates via SSE (token in query — EventSource can't set headers).
        const tok = localStorage.getItem('anchor_access_token');
        es = new EventSource(_MSG_API + '/v1/conversations/' + conv.id + '/stream?token=' + encodeURIComponent(tok || ''));
        es.onmessage = (ev) => {
          if (!ev.data || ev.data.startsWith(':')) return;
          try { appendDecrypted(JSON.parse(ev.data)); } catch (e) {}
        };
      } catch (e) { /* surface nothing fatal */ }
    })();
    return () => { alive = false; if (es) es.close(); };
  }, [conv.id]);

  React.useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  const send = async () => {
    const body = text.trim();
    if (!body || sending) return;
    if (!keyRef.current) { setKeyMissing(true); return; }
    setSending(true);
    try {
      const enc = await E2EE.encrypt(keyRef.current, body);
      const msg = await apiFetch('/v1/conversations/' + conv.id + '/messages', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(enc),
      });
      setText('');
      await appendDecrypted(msg);
    } catch (e) {
      /* keep the text so the user can retry */
    } finally {
      setSending(false);
    }
  };

  return (
    <>
      <Header back title={conv.counterpart_name || 'Chat'} subtitle="🔒 End-to-end encrypted"/>
      <div ref={scrollRef} style={{ padding: '14px 16px 8px', overflowY: 'auto', flex: 1 }}>
        {keyMissing && (
          <div style={{ margin: '0 0 12px', padding: '10px 12px', borderRadius: 10, background: 'rgba(184,137,58,0.08)', border: '1px solid rgba(184,137,58,0.3)', fontSize: 12, color: 'var(--ink-2)', fontFamily: 'var(--font-sans)' }}>
            Waiting for {conv.counterpart_name || 'the other person'} to set up encryption. They need to open the app once before messages can be sent.
          </div>
        )}
        {messages.map((m) => (
          <div key={m.id} style={{ display: 'flex', justifyContent: m.mine ? 'flex-end' : 'flex-start', marginBottom: 8 }}>
            <div style={{
              maxWidth: '78%', padding: '9px 12px', borderRadius: 14,
              background: m.mine ? 'var(--brand)' : 'var(--surface)',
              color: m.mine ? '#F7F3EE' : 'var(--ink)',
              border: m.mine ? 'none' : '1px solid var(--mist)',
              fontSize: 14, fontFamily: 'var(--font-sans)', lineHeight: 1.4,
              borderBottomRightRadius: m.mine ? 4 : 14, borderBottomLeftRadius: m.mine ? 14 : 4,
            }}>
              <div style={{ whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{m.text}</div>
              <div style={{ marginTop: 3, fontSize: 9.5, opacity: 0.6, textAlign: 'right' }}>{fmtTime(m.created_at)}</div>
            </div>
          </div>
        ))}
        {messages.length === 0 && !keyMissing && (
          <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--muted)', fontSize: 12.5, fontFamily: 'var(--font-sans)' }}>
            No messages yet. Say hello — only the two of you can read this.
          </div>
        )}
      </div>
      <div style={{ padding: '8px 14px 16px', borderTop: '1px solid var(--mist)', display: 'flex', gap: 8, alignItems: 'flex-end', background: 'var(--cream)' }}>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
          placeholder="Type a message…"
          rows={1}
          style={{
            flex: 1, resize: 'none', maxHeight: 100, padding: '10px 13px', borderRadius: 12,
            border: '1px solid var(--mist-2)', background: 'var(--surface-solid)', outline: 'none',
            fontFamily: 'var(--font-sans)', fontSize: 14, color: 'var(--navy)',
          }}
        />
        <button onClick={send} disabled={sending || !text.trim()} style={{
          width: 42, height: 42, borderRadius: 12, flexShrink: 0, border: 'none',
          background: text.trim() ? 'var(--brand)' : 'var(--mist)', color: '#F7F3EE',
          cursor: text.trim() ? 'pointer' : 'default', display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}><IconSend size={17}/></button>
      </div>
    </>
  );
}

// ── Apply as a Lawyer ──────────────────────────────────────────
const _SPECIALIZATIONS = ['Criminal', 'Civil', 'Family', 'Constitutional', 'Cyber', 'DV Act', 'Labour', 'Property'];

function ApplyLawyerScreen() {
  const { go } = useApp();
  const [profile, setProfile] = React.useState(undefined); // undefined=loading, null=none
  const [bar, setBar] = React.useState('');
  const [district, setDistrict] = React.useState('');
  const [specs, setSpecs] = React.useState([]);
  const [bio, setBio] = React.useState('');
  const [busy, setBusy] = React.useState(false);
  const [error, setError] = React.useState('');

  const load = React.useCallback(async () => {
    try {
      const p = await apiFetch('/v1/lawyers/me');
      setProfile(p);
    } catch (e) {
      setProfile(null);
    }
  }, []);
  React.useEffect(() => { load(); }, [load]);

  const toggleSpec = (s) => setSpecs(prev => prev.includes(s) ? prev.filter(x => x !== s) : [...prev, s]);

  const submit = async () => {
    setError('');
    if (bar.trim().length < 2 || district.trim().length < 2) {
      setError('Bar number and district are required.');
      return;
    }
    setBusy(true);
    try {
      await apiFetch('/v1/lawyers/apply', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          bar_number: bar.trim(), district: district.trim(),
          specializations: specs, bio: bio.trim() || null,
        }),
      });
      await load();
    } catch (e) {
      setError(e.message || 'Could not submit application.');
    } finally {
      setBusy(false);
    }
  };

  const field = {
    width: '100%', padding: '10px 13px', borderRadius: 10, border: '1px solid var(--mist-2)',
    background: 'var(--surface-solid)', fontFamily: 'var(--font-sans)', fontSize: 14, color: 'var(--navy)',
    outline: 'none', boxSizing: 'border-box',
  };

  const StatusBanner = ({ tone, title, body }) => (
    <div style={{
      padding: 16, borderRadius: 14, marginBottom: 16,
      background: tone === 'green' ? 'rgba(74,107,92,0.08)' : tone === 'red' ? 'rgba(232,49,42,0.07)' : 'rgba(184,137,58,0.08)',
      border: '1px solid ' + (tone === 'green' ? 'rgba(74,107,92,0.3)' : tone === 'red' ? 'rgba(232,49,42,0.22)' : 'rgba(184,137,58,0.3)'),
    }}>
      <div className="serif" style={{ fontSize: 16, fontWeight: 500, color: 'var(--navy)' }}>{title}</div>
      <div style={{ marginTop: 6, fontSize: 13, color: 'var(--ink-2)', fontFamily: 'var(--font-sans)', lineHeight: 1.5 }}>{body}</div>
    </div>
  );

  return (
    <>
      <Header back title="Lawyer Verification" subtitle="Reviewed by Anchor super-admin"/>
      <div style={{ padding: '16px 20px 28px' }}>
        {profile === undefined && (
          <div style={{ textAlign: 'center', padding: '40px 0', color: 'var(--muted)', fontSize: 13, fontFamily: 'var(--font-sans)' }}>Loading…</div>
        )}

        {profile && profile.status === 'verified' && (
          <StatusBanner tone="green" title="✓ You're a verified lawyer"
            body="Your profile is live in the national Find-a-Lawyer directory. Citizens can now start end-to-end encrypted chats with you — check Messages." />
        )}
        {profile && profile.status === 'pending' && (
          <StatusBanner tone="gold" title="Application under review"
            body="A super-admin is verifying your bar credentials. You'll appear in the directory once approved." />
        )}
        {profile && profile.status === 'rejected' && (
          <>
            <StatusBanner tone="red" title="Application not approved"
              body={profile.rejection_reason || 'Your credentials could not be verified. You may correct your details and resubmit below.'} />
          </>
        )}

        {(profile === null || (profile && profile.status === 'rejected')) && (
          <div style={{ background: 'var(--surface)', border: '1px solid var(--mist)', borderRadius: 16, padding: 16 }}>
            <div style={{ fontSize: 13.5, color: 'var(--ink-2)', fontFamily: 'var(--font-sans)', marginBottom: 16, lineHeight: 1.5 }}>
              Are you a practising lawyer? Submit your Bar Council credentials. Once a super-admin verifies you, you'll be listed in Find-a-Lawyer and citizens can reach you over encrypted chat.
            </div>

            <div style={{ marginBottom: 12 }}>
              <div className="eyebrow" style={{ marginBottom: 5 }}>Bar Council number *</div>
              <input style={field} value={bar} onChange={e => setBar(e.target.value)} placeholder="e.g. BAR-DHK-12345"/>
            </div>
            <div style={{ marginBottom: 12 }}>
              <div className="eyebrow" style={{ marginBottom: 5 }}>District *</div>
              <input style={field} value={district} onChange={e => setDistrict(e.target.value)} placeholder="e.g. Dhaka"/>
            </div>
            <div style={{ marginBottom: 12 }}>
              <div className="eyebrow" style={{ marginBottom: 7 }}>Specializations</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {_SPECIALIZATIONS.map(s => {
                  const on = specs.includes(s);
                  return (
                    <span key={s} onClick={() => toggleSpec(s)} style={{
                      padding: '6px 11px', borderRadius: 999, cursor: 'pointer', fontSize: 12, fontWeight: 500,
                      background: on ? 'var(--brand)' : 'var(--surface)', color: on ? '#F7F3EE' : 'var(--ink-2)',
                      border: '1px solid ' + (on ? 'var(--navy)' : 'var(--mist)'),
                    }}>{s}</span>
                  );
                })}
              </div>
            </div>
            <div style={{ marginBottom: 14 }}>
              <div className="eyebrow" style={{ marginBottom: 5 }}>Short bio</div>
              <textarea style={{ ...field, minHeight: 80, resize: 'vertical' }} value={bio} onChange={e => setBio(e.target.value)} placeholder="Years of practice, areas of focus…"/>
            </div>

            {error && (
              <div style={{ marginBottom: 12, padding: '9px 12px', borderRadius: 10, background: 'rgba(232,49,42,0.07)', border: '1px solid rgba(232,49,42,0.2)', fontSize: 12.5, color: 'var(--red)', fontFamily: 'var(--font-sans)' }}>{error}</div>
            )}

            <button onClick={submit} disabled={busy} className="btn btn-primary" style={{ width: '100%', height: 44, borderRadius: 12, fontSize: 14.5 }}>
              {busy ? 'Submitting…' : 'Submit for verification'}
            </button>
          </div>
        )}
      </div>
    </>
  );
}

window.ConversationsScreen = ConversationsScreen;
window.ChatThreadScreen = ChatThreadScreen;
window.ApplyLawyerScreen = ApplyLawyerScreen;
