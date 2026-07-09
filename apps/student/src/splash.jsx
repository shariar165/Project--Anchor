// Anchor — Splash screens (Splash1 = dark, Splash2 = color-matched)

const { useEffect: _sEffect, useState: _sState } = React;

function SplashWordmark({ size = 96, color = '#F7F3EE', accent }) {
  return (
    <span className="serif" style={{
      fontWeight: 500, fontSize: size, letterSpacing: '-0.035em',
      color, lineHeight: 1, fontOpticalSizing: 'auto',
    }}>
      Anchor<span style={{ color: accent, fontStyle: 'italic' }}>.</span>
    </span>
  );
}

function SmallAnchorGlyph({ size = 38, color = '#F7F3EE' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="5" r="2"/>
      <path d="M12 7v15"/>
      <path d="M5 12h14"/>
      <path d="M3 16a9 9 0 0 0 18 0"/>
    </svg>
  );
}

// ───────────────────────────────────────────────────────────
// Splash 1 — dark "grayist black"
// ───────────────────────────────────────────────────────────
function Splash1({ onAdvance }) {
  _sEffect(() => {
    const t = setTimeout(onAdvance, 2400);
    return () => clearTimeout(t);
  }, [onAdvance]);

  return (
    <div onClick={onAdvance} data-splash="1" style={{
      position: 'absolute', inset: 0, background: '#0E0E0F',
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      cursor: 'pointer', overflow: 'hidden',
    }}>
      {/* Subtle radial wash */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'radial-gradient(420px 320px at 50% 38%, rgba(247,243,238,0.07), transparent 70%)',
      }}/>
      {/* Top grain */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none', opacity: 0.5,
        backgroundImage: "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.06 0'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>\")",
      }}/>

      <div style={{
        position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column',
        alignItems: 'center', gap: 14, animation: 'splash1In 700ms cubic-bezier(.2,.7,.2,1) both',
      }}>
        <div style={{
          width: 64, height: 64, borderRadius: 16,
          background: 'rgba(247,243,238,0.05)',
          border: '1px solid rgba(247,243,238,0.12)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginBottom: 8,
        }}>
          <SmallAnchorGlyph size={32} color="#F7F3EE"/>
        </div>
        <SplashWordmark size={88} color="#F7F3EE" accent="#C44536"/>
      </div>

      {/* Created by AiVion */}
      <div style={{
        position: 'absolute', left: 0, right: 0, bottom: 64, textAlign: 'center', zIndex: 1,
        animation: 'splashFootIn 900ms 300ms ease-out both',
      }}>
        <div style={{
          fontFamily: 'var(--font-sans)', fontSize: 9.5, fontWeight: 600,
          color: 'rgba(247,243,238,0.45)', letterSpacing: '0.32em',
          textTransform: 'uppercase', marginBottom: 6,
        }}>Created by</div>
        <div className="serif" style={{
          fontStyle: 'italic', fontWeight: 500, fontSize: 22,
          color: '#F7F3EE', letterSpacing: '-0.005em',
        }}>
          Team AiVion
        </div>
        <div style={{
          marginTop: 6, fontFamily: 'var(--font-sans)', fontSize: 9.5,
          color: 'rgba(247,243,238,0.4)', letterSpacing: '0.22em', textTransform: 'uppercase',
        }}>Daffodil International University</div>
      </div>

      {/* Progress dot */}
      <div style={{
        position: 'absolute', bottom: 24, left: '50%', transform: 'translateX(-50%)',
        width: 4, height: 4, borderRadius: 999, background: 'rgba(247,243,238,0.4)',
        animation: 'splashDot 1.4s ease-in-out infinite',
      }}/>
    </div>
  );
}

// ───────────────────────────────────────────────────────────
// Splash 2 — color-matched (cream/navy with sage→ember tinted glow)
// ───────────────────────────────────────────────────────────
function Splash2({ onAdvance }) {
  _sEffect(() => {
    const t = setTimeout(onAdvance, 2600);
    return () => clearTimeout(t);
  }, [onAdvance]);

  return (
    <div onClick={onAdvance} style={{
      position: 'absolute', inset: 0, background: 'var(--cream)',
      display: 'flex', flexDirection: 'column', cursor: 'pointer', overflow: 'hidden',
    }}>
      {/* Soft sage→ember wash representing C2C */}
      <div style={{
        position: 'absolute', inset: 0,
        background:
          'radial-gradient(380px 280px at 15% 10%, rgba(74,120,160,0.18), transparent 60%),' +
          'radial-gradient(420px 320px at 95% 90%, rgba(196,69,54,0.16), transparent 60%)',
      }}/>
      {/* Grain */}
      <div style={{
        position: 'absolute', inset: 0, pointerEvents: 'none', opacity: 0.5, mixBlendMode: 'multiply',
        backgroundImage: "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 0.06 0'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>\")",
      }}/>

      {/* Top brand row */}
      <div style={{
        position: 'relative', zIndex: 1,
        padding: '70px 28px 0',
        display: 'flex', alignItems: 'center', gap: 10,
        animation: 'splashFootIn 600ms ease-out both',
      }}>
        <div style={{
          width: 34, height: 34, borderRadius: 10, background: 'var(--navy)',
          color: '#F7F3EE', display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <SmallAnchorGlyph size={18} color="#F7F3EE"/>
        </div>
        <SplashWordmark size={22} color="var(--navy)" accent="var(--ember)"/>
      </div>

      {/* Big italic headline */}
      <div style={{
        position: 'relative', zIndex: 1, padding: '0 28px', marginTop: 'auto', marginBottom: 'auto',
        animation: 'splashLineIn 900ms 200ms cubic-bezier(.2,.7,.2,1) both',
      }}>
        <div className="eyebrow" style={{ marginBottom: 14, color: 'var(--gold)' }}>
          Anchor · a promise
        </div>
        <div className="serif" style={{
          fontWeight: 400, fontStyle: 'italic',
          fontSize: 46, lineHeight: 1.02, letterSpacing: '-0.025em',
          color: 'var(--navy)',
        }}>
          We worked for
          <br/>
          your <span style={{ color: 'var(--ember-2)', fontWeight: 500 }}>safety</span>
          <span className="serif" style={{ color: 'var(--ember-2)', fontStyle: 'normal', fontWeight: 500 }}>.</span>
        </div>
        <div style={{
          marginTop: 18, fontFamily: 'var(--font-serif)', fontStyle: 'italic',
          fontSize: 15, lineHeight: 1.45, color: 'var(--ink-2)',
          maxWidth: 320,
        }}>
          A two-tier civic platform from <strong style={{ fontStyle: 'normal', fontWeight: 600, color: 'var(--navy)' }}>campus to country</strong> — built so every student and citizen has a voice that's heard.
        </div>
      </div>

      {/* Footer */}
      <div style={{
        position: 'relative', zIndex: 1, padding: '0 28px 56px',
        animation: 'splashFootIn 900ms 500ms ease-out both',
      }}>
        <div style={{ height: 1, background: 'var(--mist-2)', margin: '0 0 14px' }}/>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{
            width: 28, height: 28, borderRadius: 999,
            background: 'linear-gradient(135deg, var(--sage), var(--ember-2))',
          }}/>
          <div>
            <div className="eyebrow" style={{ fontSize: 9 }}>From Campus to Country</div>
            <div className="serif" style={{
              fontStyle: 'italic', fontSize: 13, color: 'var(--navy)', marginTop: 2,
            }}>
              Tap anywhere to continue
            </div>
          </div>
          <div style={{ flex: 1 }}/>
          <button onClick={(e) => { e.stopPropagation(); onAdvance(); }} style={{
            padding: '8px 14px', borderRadius: 999, background: 'var(--navy)', color: '#F7F3EE',
            border: 'none', cursor: 'pointer', fontFamily: 'var(--font-sans)',
            fontSize: 12, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase',
          }}>Enter</button>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { Splash1, Splash2 });
