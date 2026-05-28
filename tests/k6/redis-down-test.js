import http from 'k6/http';
import { check, sleep } from 'k6';
import {
  API_PATH,
  buildHeaders,
  buildPayload,
  encodeBody,
  isDuplicateScenarioAllowed,
  recordTransactionResult,
  thresholds,
  transactionUrl,
} from './helpers/common.js';

const RUN_ID = __ENV.REDIS_DOWN_RUN_ID || `${Date.now()}`;
const IDEMPOTENCY_KEY = __ENV.REDIS_DOWN_KEY || `idem-redis-down-${RUN_ID}`;
const EXTERNAL_EVENT_ID = __ENV.REDIS_DOWN_EVENT_ID || `BANK-REDIS-DOWN-${RUN_ID}`;
const BODY = encodeBody(
  buildPayload({
    external_event_id: EXTERNAL_EVENT_ID,
    amount: Number(__ENV.REDIS_DOWN_AMOUNT || 10000),
    occurred_at: new Date().toISOString(),
  }),
);

export const options = {
  vus: Number(__ENV.VUS || 50),
  duration: __ENV.DURATION || '30s',
  thresholds: {
    ...thresholds.redisDown,
    unexpected_response_rate: ['rate==0'],
    server_error_rate: ['rate==0'],
  },
  tags: {
    scenario: 'phase9-redis-down',
  },
};

export default function () {
  const headers = buildHeaders(BODY, IDEMPOTENCY_KEY, API_PATH);
  const res = http.post(transactionUrl(), BODY, { headers });

  recordTransactionResult(res, [200, 202, 409]);
  check(res, {
    'status is 200/202/409': (r) => isDuplicateScenarioAllowed(r.status),
    'no 5xx': (r) => r.status < 500,
  });

  sleep(Number(__ENV.SLEEP_SECONDS || 0.05));
}
