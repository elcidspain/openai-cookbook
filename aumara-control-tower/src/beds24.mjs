const API_BASE = 'https://api.beds24.com/v2';
export const DEFAULT_MESSAGE_MAX_AGE = 999;
const ERROR_SNIPPET_LIMIT = 300;
const MAX_MESSAGE_LENGTH = 5000;

export class Beds24ApiError extends Error {
  constructor(message, status, details = null) {
    super(message);
    this.name = 'Beds24ApiError';
    this.status = Number(status) || 0;
    this.details = details;
  }
}

function normalizeCredential(value) {
  return String(value || '').trim();
}

function credential(name) {
  const value = normalizeCredential(process.env[name]);
  if (!value) throw new Error(`Missing env: ${name}`);
  return value;
}

function buildPath(path, params = {}) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params || {})) {
    if (value === undefined || value === null) continue;
    const raw = String(value).trim();
    if (!raw) continue;
    query.set(key, raw);
  }
  const suffix = query.toString();
  return suffix ? `${path}?${suffix}` : path;
}

async function requestBeds24({ method, path, headers = {}, body }) {
  const finalHeaders = {
    accept: 'application/json',
    ...headers
  };
  const options = {
    method,
    headers: finalHeaders
  };
  if (body !== undefined) {
    options.body = JSON.stringify(body);
    finalHeaders['content-type'] = 'application/json';
  }

  const response = await fetch(`${API_BASE}${path}`, options);
  const raw = await response.text();
  let parsed = {};
  if (raw) {
    try {
      parsed = JSON.parse(raw);
    } catch {
      // Keep error payload small to avoid echoing large upstream responses.
      parsed = { raw: raw.slice(0, ERROR_SNIPPET_LIMIT) };
    }
  }

  if (!response.ok) {
    throw new Beds24ApiError(
      `Beds24 ${method} ${path} failed with HTTP ${response.status}`,
      response.status,
      parsed
    );
  }
  return parsed;
}

function rows(response, label) {
  if (!response || typeof response !== 'object' || !Array.isArray(response.data)) {
    throw new Error(`${label} response did not contain a data array`);
  }
  return response.data;
}

function readToken() {
  return credential('BEDS24_TOKEN_CREDENTIAL');
}

async function writeAccessToken() {
  const refreshToken = credential('BEDS24_REFRESH_TOKEN');
  const response = await requestBeds24({
    method: 'GET',
    path: '/authentication/token',
    headers: { refreshToken }
  });
  const token = normalizeCredential(response?.token);
  if (!token) throw new Error('Beds24 token exchange returned no access token');
  return token;
}

export async function listBookings(params = {}) {
  const response = await requestBeds24({
    method: 'GET',
    path: buildPath('/bookings', params),
    headers: { token: readToken() }
  });
  return rows(response, 'Booking');
}

export async function listBookingMessages({ bookingId, maxAge = DEFAULT_MESSAGE_MAX_AGE }) {
  const id = Number(bookingId);
  if (!Number.isFinite(id) || id <= 0) throw new Error('bookingId must be a positive number');
  const response = await requestBeds24({
    method: 'GET',
    path: buildPath('/bookings/messages', { bookingId: id, maxAge }),
    headers: { token: readToken() }
  });
  return rows(response, 'Message');
}

function normalizeText(value) {
  return String(value || '').replace(/\s+/g, ' ').trim().toLowerCase();
}

function hasDuplicateHostMessage(messages, message) {
  const expected = normalizeText(message);
  if (!expected) return false;
  for (const item of messages) {
    const source = String(item?.source || '').toLowerCase();
    const text = item?.message || item?.text || item?.body;
    if (source === 'host' && normalizeText(text) === expected) return true;
  }
  return false;
}

export async function sendGuestMessage({ bookingId, message, dedupe = true }) {
  const id = Number(bookingId);
  if (!Number.isFinite(id) || id <= 0) throw new Error('bookingId must be a positive number');
  const text = String(message || '').trim();
  if (!text) throw new Error('message is required');
  if (text.length > MAX_MESSAGE_LENGTH) {
    throw new Error(`message must be ${MAX_MESSAGE_LENGTH} characters or less`);
  }

  if (dedupe) {
    const messages = await listBookingMessages({ bookingId: id, maxAge: DEFAULT_MESSAGE_MAX_AGE });
    if (hasDuplicateHostMessage(messages, text)) {
      return {
        sent: false,
        duplicate: true,
        bookingId: id
      };
    }
  }

  const token = await writeAccessToken();
  const response = await requestBeds24({
    method: 'POST',
    path: '/bookings/messages',
    headers: { token },
    // Beds24 expects an array of message objects, even for one message.
    body: [{ bookingId: id, message: text }]
  });
  return {
    sent: true,
    duplicate: false,
    bookingId: id,
    response
  };
}
