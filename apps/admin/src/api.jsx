// Anchor AI Admin — API client
const AnchorAPI = (() => {
  const BASE = 'http://localhost:8000';
  const K = {
    access: 'anchor_admin_access_token',
    refresh: 'anchor_admin_refresh_token',
    user: 'anchor_admin_user',
  };

  function getAccessToken() { return localStorage.getItem(K.access); }
  function getRefreshToken() { return localStorage.getItem(K.refresh); }

  function setTokens(access, refresh) {
    localStorage.setItem(K.access, access);
    if (refresh) localStorage.setItem(K.refresh, refresh);
  }

  function getStoredUser() {
    try { return JSON.parse(localStorage.getItem(K.user) || 'null'); } catch { return null; }
  }

  function setStoredUser(user) {
    localStorage.setItem(K.user, JSON.stringify(user));
  }

  function clearAuth() {
    Object.values(K).forEach(k => localStorage.removeItem(k));
  }

  // Attempt a silent token refresh. Returns true on success, false if session is dead.
  let _refreshing = null; // deduplicate concurrent refresh attempts
  async function _tryRefresh() {
    if (_refreshing) return _refreshing;
    const rt = getRefreshToken();
    if (!rt) return false;
    _refreshing = (async () => {
      try {
        const res = await fetch(BASE + '/auth/refresh', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: rt }),
        });
        if (!res.ok) { clearAuth(); return false; }
        const data = await res.json();
        setTokens(data.access_token, data.refresh_token);
        return true;
      } catch {
        return false;
      } finally {
        _refreshing = null;
      }
    })();
    return _refreshing;
  }

  function _authHeaders(extra = {}) {
    const tok = getAccessToken();
    const headers = { ...extra };
    if (tok) headers['Authorization'] = 'Bearer ' + tok;
    return headers;
  }

  // Shared fetch-with-auto-refresh logic
  async function _fetch(buildReq, retried = false) {
    const [url, init] = buildReq();
    const res = await fetch(url, init);
    if (res.status === 401 && !retried) {
      const ok = await _tryRefresh();
      if (ok) return _fetch(buildReq, true);
      clearAuth();
      throw new Error('Session expired — please log in again');
    }
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Request failed');
    return data;
  }

  async function apiPost(path, body) {
    const res = await fetch(BASE + path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Request failed');
    return data;
  }

  async function apiGet(path) {
    return _fetch(() => [BASE + path, { headers: _authHeaders() }]);
  }

  async function apiPostAuth(path, body) {
    return _fetch(() => [BASE + path, {
      method: 'POST',
      headers: _authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(body),
    }]);
  }

  async function apiPatch(path, body) {
    return _fetch(() => [BASE + path, {
      method: 'PATCH',
      headers: _authHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(body),
    }]);
  }

  async function apiDelete(path) {
    return _fetch(() => [BASE + path, {
      method: 'DELETE',
      headers: _authHeaders(),
    }]);
  }

  return { getAccessToken, getRefreshToken, setTokens, getStoredUser, setStoredUser, clearAuth, apiPost, apiGet, apiPostAuth, apiPatch, apiDelete };
})();

Object.assign(window, { AnchorAPI });
