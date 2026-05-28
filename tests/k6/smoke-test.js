import http from 'k6/http';
import { check, sleep } from 'k6';
import {
  BASE_URL,
  API_PATH,
  buildHeaders,
  buildPayload,
  encodeBody,
  isAllowedTransactionStatus,
  recordTransactionResult,
  thresholds,
  transactionUrl,
  uniqueExternalEventId,
  uniqueIdempotencyKey,
} from './helpers/common.js';

export const options = {
  vus: Number(__ENV.VUS || 1),
  iterations: Number(__ENV.ITERATIONS || 3),
  thresholds: thresholds.smoke,
  tags: {
    scenario: 'phase9-smoke',
  },
};

export default function () {
  const health = http.get(`${BASE_URL}/health`);
  check(health, {
    'health returns 200': (r) => r.status === 200,
  });

  const payload = buildPayload({
    external_event_id: uniqueExternalEventId('BANK-SMOKE'),
    amount: 1000,
  });
  const body = encodeBody(payload);
  const headers = buildHeaders(body, uniqueIdempotencyKey('idem-smoke'), API_PATH);
  const res = http.post(transactionUrl(), body, { headers });

  recordTransactionResult(res);
  check(res, {
    'transaction status is allowed': (r) => isAllowedTransactionStatus(r.status),
    'transaction has no 5xx': (r) => r.status < 500,
    'completed response has event_id': (r) => r.status !== 200 || r.json('event_id') !== undefined,
  });

  sleep(1);
}
