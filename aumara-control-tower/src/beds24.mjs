const API_BASE = 'https://beds24.com/api/v2';
const TOKEN_ENV = 'BEDS24_TOKEN_CREDENTIAL';

function getToken() {
  const token = String(process.env[TOKEN_ENV] || '').trim();
  if (!token) throw new Error(`Missing ${TOKEN_ENV}`);
  return token;
}

function buildUrl(pathname, params = {}) {
  const url = new URL(`${API_BASE}${pathname}`);
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue;
    url.searchParams.set(key, String(value));
  }
  return url;
}

async function beds24Get(pathname, params = {}) {
  const response = await fetch(buildUrl(pathname, params), {
    method: 'GET',
    headers: {
      accept: 'application/json',
      token: getToken()
    }
  });

  const raw = await response.text();