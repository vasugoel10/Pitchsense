/**
 * API utility module for PitchSense.
 * 
 * Handles CSRF token management automatically:
 * 1. On first import, fetches /api/csrf/ to set the csrftoken cookie.
 * 2. Reads the cookie and attaches X-CSRFToken header to every POST request.
 * 
 * This eliminates the need for @csrf_exempt on any Django view.
 */

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
  return null;
}

// Fetch the CSRF cookie from Django on module load
let csrfReady = fetch('/api/csrf/', { credentials: 'same-origin' })
  .then(() => true)
  .catch(() => {
    console.warn('Failed to fetch CSRF token. POST requests may fail.');
    return false;
  });

/**
 * Make an API request with automatic CSRF token handling.
 * @param {string} url - API endpoint
 * @param {object} options - fetch options (method, body, etc.)
 * @returns {Promise<object>} Parsed JSON response
 */
export async function apiFetch(url, options = {}) {
  await csrfReady;
  
  const headers = {
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };
  
  // Attach CSRF token for unsafe methods
  const method = (options.method || 'GET').toUpperCase();
  if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    const csrfToken = getCookie('csrftoken');
    if (csrfToken) {
      headers['X-CSRFToken'] = csrfToken;
    }
  }
  
  const response = await fetch(url, {
    ...options,
    headers,
    credentials: 'same-origin', // include cookies
  });
  
  return response.json();
}
