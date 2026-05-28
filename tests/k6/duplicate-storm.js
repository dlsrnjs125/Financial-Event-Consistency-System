import http from 'k6/http';
import { check, sleep } from 'k6';
import {
  API_PATH,
  buildHeaders,
  buildPayload,
  encodeBody,
  isDuplicateScenarioAllowed,
  recordTransactionResult,
  summaryTrendStats,
  thresholds,
  transactionUrl,
} from './helpers/common.js';

const STORM_ID = __ENV.STORM_ID || `${Date.now()}`;
const DUPLICATE_KEY = __ENV.DUPLICATE_KEY || `idem-duplicate-storm-${STORM_ID}`;
const DUPLICATE_EVENT_ID = __ENV.DUPLICATE_EVENT_ID || `BANK-DUPLICATE-STORM-${STORM_ID}`;
const DUPLICATE_OCCURRED_AT = new Date().toISOString();
const DUPLICATE_BODY = encodeBody(
  buildPayload({
    external_event_id: DUPLICATE_EVENT_ID,
    amount: Number(__ENV.DUPLICATE_AMOUNT || 10000),
    occurred_at: DUPLICATE_OCCURRED_AT,
  }),
);

export const options = {
  vus: Number(__ENV.VUS || 50),
  duration: __ENV.DURATION || '15s',
  summaryTrendStats,
  thresholds: {
    ...thresholds.duplicate,
    unexpected_response_rate: ['rate==0'],
    server_error_rate: ['rate==0'],
  },
  tags: {
    scenario: 'phase9-duplicate-storm',
  },
};

export default function () {
  const headers = buildHeaders(DUPLICATE_BODY, DUPLICATE_KEY, API_PATH);
  const res = http.post(transactionUrl(), DUPLICATE_BODY, { headers });

  recordTransactionResult(res, [200, 202, 409]);
  const duplicated = safeDuplicatedFlag(res);

  check(res, {
    'status is 200/202/409': (r) => isDuplicateScenarioAllowed(r.status),
    'no 5xx': (r) => r.status < 500,
    '200 response is original or replay': (r) => r.status !== 200 || duplicated === true || duplicated === false,
  });

  sleep(Number(__ENV.SLEEP_SECONDS || 0.05));
}

function safeDuplicatedFlag(res) {
  try {
    return res.json('duplicated');
  } catch (_) {
    return undefined;
  }
}
