import http from 'k6/http';
import { check, sleep } from 'k6';
import {
  API_PATH,
  buildHeaders,
  buildPayload,
  encodeBody,
  isAllowedTransactionStatus,
  recordTransactionResult,
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
  vus: Number(__ENV.VUS || 100),
  duration: __ENV.DURATION || '30s',
  thresholds: {
    ...thresholds.duplicate,
    duplicate_processing_rate: ['rate==0'],
  },
  tags: {
    scenario: 'phase9-duplicate-storm',
  },
};

export default function () {
  const headers = buildHeaders(DUPLICATE_BODY, DUPLICATE_KEY, API_PATH);
  const res = http.post(transactionUrl(), DUPLICATE_BODY, { headers });

  recordTransactionResult(res);
  const duplicated = safeDuplicatedFlag(res);

  check(res, {
    'status is 200/202/409': (r) => isAllowedTransactionStatus(r.status),
    'same-key different-body conflict is not expected': (r) => r.status !== 409,
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
