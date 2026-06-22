// ═══════════════════════════════════════════════════════════════
//  E2EE — client-side end-to-end encryption for user ↔ lawyer chat
//  ECDH (P-256) key agreement → AES-GCM message encryption.
//  Private keys never leave the browser; the server only ever sees
//  ciphertext. Depends on global apiFetch() from applications.jsx.
// ═══════════════════════════════════════════════════════════════
const E2EE = (function () {
  const PRIV_KEY = 'anchor_e2ee_priv';
  const PUB_KEY  = 'anchor_e2ee_pub';
  const subtle = (window.crypto && window.crypto.subtle) || null;

  function b64(buf) {
    return btoa(String.fromCharCode.apply(null, new Uint8Array(buf)));
  }
  function unb64(str) {
    return Uint8Array.from(atob(str), c => c.charCodeAt(0));
  }

  async function fingerprint(jwk) {
    const data = new TextEncoder().encode(JSON.stringify(jwk));
    const hash = await subtle.digest('SHA-256', data);
    return b64(hash).slice(0, 43);
  }

  // Generate-or-load this device's keypair and publish the public key. Idempotent.
  async function ensureKeyPair() {
    if (!subtle) throw new Error('WebCrypto unavailable (needs HTTPS or localhost)');
    let pubJwk  = JSON.parse(localStorage.getItem(PUB_KEY)  || 'null');
    let privJwk = JSON.parse(localStorage.getItem(PRIV_KEY) || 'null');
    if (!pubJwk || !privJwk) {
      const kp = await subtle.generateKey(
        { name: 'ECDH', namedCurve: 'P-256' }, true, ['deriveKey', 'deriveBits']
      );
      pubJwk  = await subtle.exportKey('jwk', kp.publicKey);
      privJwk = await subtle.exportKey('jwk', kp.privateKey);
      localStorage.setItem(PUB_KEY,  JSON.stringify(pubJwk));
      localStorage.setItem(PRIV_KEY, JSON.stringify(privJwk));
    }
    try {
      await apiFetch('/v1/e2ee/keys', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          public_key_jwk: JSON.stringify(pubJwk),
          key_fingerprint: await fingerprint(pubJwk),
        }),
      });
    } catch (e) { /* upload is best-effort; encryption still works locally */ }
    return pubJwk;
  }

  async function _importPriv(jwk) {
    return subtle.importKey('jwk', jwk, { name: 'ECDH', namedCurve: 'P-256' }, false, ['deriveKey']);
  }
  async function _importPub(jwk) {
    return subtle.importKey('jwk', jwk, { name: 'ECDH', namedCurve: 'P-256' }, false, []);
  }

  // Derive the shared AES-GCM key for a counterpart's public key (JWK string or object).
  async function deriveKey(theirPubJwk) {
    if (!subtle) throw new Error('WebCrypto unavailable');
    const privJwk = JSON.parse(localStorage.getItem(PRIV_KEY) || 'null');
    if (!privJwk) throw new Error('No local key — call ensureKeyPair first');
    const priv = await _importPriv(privJwk);
    const pubObj = typeof theirPubJwk === 'string' ? JSON.parse(theirPubJwk) : theirPubJwk;
    const pub = await _importPub(pubObj);
    return subtle.deriveKey(
      { name: 'ECDH', public: pub }, priv,
      { name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt']
    );
  }

  async function encrypt(key, text) {
    const iv = window.crypto.getRandomValues(new Uint8Array(12));
    const ct = await subtle.encrypt({ name: 'AES-GCM', iv }, key, new TextEncoder().encode(text));
    return { ciphertext: b64(ct), iv: b64(iv) };
  }

  async function decrypt(key, ciphertext, ivb64) {
    try {
      const pt = await subtle.decrypt({ name: 'AES-GCM', iv: unb64(ivb64) }, key, unb64(ciphertext));
      return new TextDecoder().decode(pt);
    } catch (e) {
      return '🔒 unable to decrypt';
    }
  }

  return { ensureKeyPair, deriveKey, encrypt, decrypt, supported: !!subtle };
})();

window.E2EE = E2EE;
