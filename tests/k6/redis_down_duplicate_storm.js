import http from 'k6/http';
import { check, sleep } from 'k6';
import {
  API_PATH,
  buildHeaders,
  buildPayload,
  encodeBody,
  recordTransactionResult,
  safeJsonValue,
  summaryTrendStats,
  thresholds,
  transactionUrl,
} from './helpers/common.js';

const RUN_ID = __ENV.REDIS_DOWN_STORM_ID || `${Date.now()}`;
const IDEMPOTENCY_KEY = __ENV.REDIS_DOWN_KEY || `idem-rd-storm-${RUN_ID}`;
const EXTERNAL_EVENT_ID = __ENV.REDIS_DOWN_EVENT_ID || `BANK-REDIS-DOWN-STORM-${RUN_ID}`;
const OCCURRED_AT = new Date().toISOString();
const BODY = encodeBody(
  buildPayload({
    external_event_id: EXTERNAL_EVENT_ID,
    amount: Number(__ENV.REDIS_DOWN_AMOUNT ?? 10000),
    occurred_at: OCCURRED_AT,
  }),
);

const allowedStatuses = [200, 201, 202, 409];

export const options = {
  vus: Number(__ENV.VUS || 80),
  duration: __ENV.DURATION || '30s',
  summaryTrendStats,
  thresholds: {
    ...thresholds.redisDown,
    unexpected_response_rate: ['rate==0'],
    server_error_rate: [__ENV.SERVER_ERROR_THRESHOLD || 'rate<0.01'],
  },
  tags: {
    scenario: 'phase10-redis-down-duplicate-storm',
  },
};

export default function () {
  const headers = buildHeaders(BODY, IDEMPOTENCY_KEY, API_PATH);
  const res = http.post(transactionUrl(), BODY, { headers });

  recordTransactionResult(res, allowedStatuses);
  check(res, {
    'status is 200/201/202/409': (r) => allowedStatuses.includes(r.status),
    '5xx ratio remains below threshold input': (r) => r.status < 500,
    'body has event or idempotency tracking': hasTrackingField,
  });

  sleep(Number(__ENV.SLEEP_SECONDS || 0.03));
}

function hasTrackingField(res) {
  if (res.status >= 500) {
    return false;
  }
  return (
    safeJsonValue(res, 'event_id') !== undefined ||
    safeJsonValue(res, 'idempotency_key_status') !== undefined ||
    safeJsonValue(res, 'error.code') === 'IdempotencyConflict'
  );
}
