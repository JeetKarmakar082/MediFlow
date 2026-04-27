/**
 * MediFlow API Helper
 * Simple fetch wrapper that adds CSRF token for mutating requests.
 * Works with Django session authentication — no JWT needed.
 */

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
  return null;
}

async function apiFetch(url, options = {}) {
  const method = (options.method || 'GET').toUpperCase();
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };

  // CSRF token required for all mutating requests
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    headers['X-CSRFToken'] = getCookie('csrftoken');
  }

  const res = await fetch(url, { ...options, headers });

  // Session expired or not logged in
  if (res.status === 403 || res.status === 401) {
    window.location.href = '/login/';
    return null;
  }

  return res;
}
