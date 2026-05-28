import http from 'k6/http';
import { check, sleep } from 'k6';
import {
  API_PATH,
  buildHeaders,
  buildPayload,
  encodeBody,
  isSuccessOrProcessing,
  recordTransactionResult,
  thresholds,
  transactionUrl,
  uniqueExternalEventId,
  uniqueIdempotencyKey,
} from './helpers/common.js';

export const options = {
  stages: [
    { duration: __ENV.RAMP_UP || '20s', target: Number(__ENV.PEAK_VUS || 50) },
    { duration: __ENV.STEADY || '1m', target: Number(__ENV.PEAK_VUS || 50) },
    { duration: __ENV.RAMP_DOWN || '20s', target: 0 },
  ],
  thresholds: thresholds.peak,
  tags: {
    scenario: 'phase9-peak-load',
  },
};

export default function () {
  const payload = buildPayload({
    external_event_id: uniqueExternalEventId('BANK-PEAK'),
  });
  const body = encodeBody(payload);
  const headers = buildHeaders(body, uniqueIdempotencyKey('idem-peak'), API_PATH);
  const res = http.post(transactionUrl(), body, { headers });

  recordTransactionResult(res, [200, 202]);
  check(res, {
    'status is 200 or 202': (r) => isSuccessOrProcessing(r.status),
    '500 errors are failures': (r) => r.status !== 500,
    'no 5xx': (r) => r.status < 500,
  });

  sleep(Number(__ENV.SLEEP_SECONDS || 0.1));
}
