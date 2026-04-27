/**
 * MediFlow Auth Helper
 * Handles JWT login, logout, token refresh, and authenticated fetch.
 */

const Auth = (() => {

  const ACCESS_KEY  = 'mf_access';
  const REFRESH_KEY = 'mf_refresh';
  const USER_KEY    = 'mf_user';

  // ── Storage helpers ────────────────────────────────────────────────────────

  function getAccess()  { return localStorage.getItem(ACCESS_KEY); }
  function getRefresh() { return localStorage.getItem(REFRESH_KEY); }
  function getUser()    { try { return JSON.parse(localStorage.getItem(USER_KEY)); } catch { return null; } }

  function saveTokens(access, refresh) {
    localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  }

  function clearSession() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(USER_KEY);
  }

  // ── JWT decode (no library needed) ────────────────────────────────────────

  function decodeJWT(token) {
    try {
      return JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    } catch { return null; }
  }

  function isExpired(token) {
    const payload = decodeJWT(token);
    if (!payload || !payload.exp) return true;
    return Date.now() >= payload.exp * 1000 - 30000; // 30s buffer
  }

  // ── Token refresh ──────────────────────────────────────────────────────────

  async function refreshAccessToken() {
    const refresh = getRefresh();
    if (!refresh) return null;
    try {
      const res = await fetch('/api/auth/token/refresh/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh }),
      });
      if (!res.ok) { clearSession(); return null; }
      const data = await res.json();
      saveTokens(data.access, data.refresh || refresh);
      return data.access;
    } catch {
      return null;
    }
  }

  // ── Get a valid access token (refresh if needed) ───────────────────────────

  async function getValidToken() {
    let access = getAccess();
    if (!access) return null;
    if (isExpired(access)) {
      access = await refreshAccessToken();
    }
    return access;
  }

  // ── Authenticated fetch ────────────────────────────────────────────────────
  // Drop-in replacement for fetch() — adds Authorization header automatically.
  // Redirects to /login/ on 401.

  async function apiFetch(url, options = {}) {
    const token = await getValidToken();
    if (!token) { redirectToLogin(); return null; }

    const headers = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
      ...(options.headers || {}),
    };

    const res = await fetch(url, { ...options, headers });

    if (res.status === 401) {
      // Try one refresh then retry
      const newToken = await refreshAccessToken();
      if (!newToken) { redirectToLogin(); return null; }
      const retryHeaders = { ...headers, 'Authorization': `Bearer ${newToken}` };
      return fetch(url, { ...options, headers: retryHeaders });
    }

    return res;
  }

  // ── Login ──────────────────────────────────────────────────────────────────

  async function login(username, password) {
    const res = await fetch('/api/auth/token/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || 'Invalid username or password');
    }

    const data = await res.json();
    saveTokens(data.access, data.refresh);

    // Decode and store user info
    const payload = decodeJWT(data.access);
    if (payload) {
      localStorage.setItem(USER_KEY, JSON.stringify({
        id: payload.user_id,
        username: payload.username || username,
      }));
    }

    return data;
  }

  // ── Logout ─────────────────────────────────────────────────────────────────

  function logout() {
    clearSession();
    window.location.href = '/login/';
  }

  // ── Guard — call on every protected page ──────────────────────────────────

  function requireAuth() {
    const token = getAccess();
    if (!token) { redirectToLogin(); return false; }
    if (isExpired(token)) {
      // Try refresh in background; redirect if it fails
      refreshAccessToken().then(t => { if (!t) redirectToLogin(); });
    }
    return true;
  }

  function redirectToLogin() {
    if (window.location.pathname !== '/login/') {
      window.location.href = '/login/';
    }
  }

  // ── Init navbar ───────────────────────────────────────────────────────────

  function initNavbar() {
    const user = getUser();
    const el = document.getElementById('nav-username');
    if (el && user?.username) el.textContent = user.username;
  }

  return { login, logout, requireAuth, apiFetch, getUser, initNavbar, getAccess };

})();
