import crypto from 'k6/crypto';
import { Counter, Rate, Trend } from 'k6/metrics';

export const BASE_URL = (__ENV.BASE_URL || 'http://localhost:8080').replace(/\/+$/, '');
export const CLIENT_ID = __ENV.CLIENT_ID || 'bank-a';
export const CLIENT_SECRET = __ENV.CLIENT_SECRET || 'change-me-secret';
export const API_PATH = '/api/v1/transaction-events';
export const DEFAULT_ACCOUNT_NO = __ENV.ACCOUNT_NO || 'ACC-001';

export const thresholds = {
  smoke: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'],
    http_req_failed: ['rate<0.01'],
    unexpected_response_rate: ['rate==0'],
    server_error_rate: ['rate==0'],
  },
  normal: {
    http_req_duration: ['p(50)<100', 'p(95)<300', 'p(99)<1000'],
    http_req_failed: ['rate<0.01'],
    unexpected_response_rate: ['rate==0'],
    server_error_rate: ['rate==0'],
  },
  peak: {
    http_req_duration: ['p(95)<800', 'p(99)<1500'],
    http_req_failed: ['rate<0.03'],
    unexpected_response_rate: ['rate==0'],
    server_error_rate: ['rate==0'],
  },
  duplicate: {
    http_req_duration: ['p(95)<1000', 'p(99)<2000'],
    http_req_failed: ['rate<0.05'],
  },
  redisDown: {
    http_req_duration: ['p(95)<1500', 'p(99)<3000'],
    http_req_failed: ['rate<0.05'],
  },
};

export const summaryTrendStats = ['avg', 'min', 'med', 'max', 'p(90)', 'p(95)', 'p(99)'];

export const acceptedStatusCodes = {
  completed: [200],
  processing: [202],
  conflict: [409],
  domainRejected: [422],
};

export const transactionRequests = new Counter('transaction_requests_total');
export const transactionCompleted = new Counter('transaction_completed_total');
export const transactionProcessing = new Counter('transaction_processing_total');
export const transactionConflicts = new Counter('transaction_conflicts_total');
export const transactionFailures = new Counter('transaction_failures_total');
export const duplicateResponses = new Counter('duplicate_responses_total');
export const unexpectedResponseRate = new Rate('unexpected_response_rate');
export const serverErrorRate = new Rate('server_error_rate');
export const apiDuration = new Trend('transaction_api_duration_ms');

export function uniqueSuffix(prefix = 'k6') {
  const vu = typeof __VU === 'undefined' ? 'init' : __VU;
  const iter = typeof __ITER === 'undefined' ? 'init' : __ITER;
  return `${prefix}-${Date.now()}-${vu}-${iter}-${randomHex(8)}`;
}

export function uniqueExternalEventId(prefix = 'BANK-K6') {
  return `${prefix}-${uniqueSuffix('event')}`;
}

export function uniqueIdempotencyKey(prefix = 'idem-k6') {
  return `${prefix}-${uniqueSuffix('key')}`;
}

export function buildPayload(overrides = {}) {
  const payload = {
    external_event_id: overrides.external_event_id || uniqueExternalEventId(),
    account_no: overrides.account_no || DEFAULT_ACCOUNT_NO,
    event_type: overrides.event_type || 'DEPOSIT',
    amount: overrides.amount || randomAmount(),
    currency: overrides.currency || 'KRW',
    occurred_at: overrides.occurred_at || new Date().toISOString(),
  };

  if (overrides.original_external_event_id) {
    payload.original_external_event_id = overrides.original_external_event_id;
  }

  if (payload.event_type !== 'CANCEL') {
    delete payload.original_external_event_id;
  }

  return payload;
}

export function encodeBody(payload) {
  return canonicalJson(payload);
}

export function canonicalJson(value) {
  if (value === null || typeof value !== 'object') {
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) {
    return `[${value.map((item) => canonicalJson(item)).join(',')}]`;
  }

  return `{${Object.keys(value)
    .sort()
    .map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`)
    .join(',')}}`;
}

export function bodyHash(rawBody) {
  return crypto.sha256(rawBody, 'hex');
}

export function signatureBaseString(method, path, timestamp, rawBody) {
  return [method.toUpperCase(), path, timestamp, bodyHash(rawBody)].join('\n');
}

export function signRequest(method, path, timestamp, rawBody, secret = CLIENT_SECRET) {
  return crypto.hmac('sha256', secret, signatureBaseString(method, path, timestamp, rawBody), 'hex');
}

export function buildHeaders(rawBody, idempotencyKey, path = API_PATH) {
  const timestamp = new Date().toISOString();
  return {
    'Content-Type': 'application/json',
    'Idempotency-Key': idempotencyKey,
    'X-Client-Id': CLIENT_ID,
    'X-Timestamp': timestamp,
    'X-Signature': signRequest('POST', path, timestamp, rawBody),
  };
}

export function transactionUrl(path = API_PATH) {
  return `${BASE_URL}${path}`;
}

export function isSuccessOrProcessing(status) {
  return [200, 202].includes(status);
}

export function isDuplicateScenarioAllowed(status) {
  return [200, 202, 409].includes(status);
}

export function recordTransactionResult(res, allowedStatuses = [200, 202]) {
  transactionRequests.add(1);
  apiDuration.add(res.timings.duration);
  unexpectedResponseRate.add(!allowedStatuses.includes(res.status));
  serverErrorRate.add(res.status >= 500);

  if (res.status === 200) {
    transactionCompleted.add(1);
    const duplicated = safeJsonValue(res, 'duplicated');
    duplicateResponses.add(duplicated === true ? 1 : 0);
    return;
  }
  if (res.status === 202) {
    transactionProcessing.add(1);
    return;
  }
  if (res.status === 409) {
    transactionConflicts.add(1);
    return;
  }

  transactionFailures.add(1);
}

export function safeJsonValue(res, selector) {
  try {
    return res.json(selector);
  } catch (_) {
    return undefined;
  }
}

function randomAmount() {
  return Math.floor(Math.random() * 9000) + 1000;
}

function randomHex(length) {
  let value = '';
  while (value.length < length) {
    value += Math.floor(Math.random() * 16).toString(16);
  }
  return value.slice(0, length);
}
