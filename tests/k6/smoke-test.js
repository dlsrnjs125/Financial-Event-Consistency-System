import http from 'k6/http';
import { check, sleep } from 'k6';

// Configuration
const BASE_URL = __ENV.BASE_URL || 'http://localhost:80';
const VIRTUAL_USERS = parseInt(__ENV.VUS || '10');
const DURATION = __ENV.DURATION || '30s';

export const options = {
  vus: VIRTUAL_USERS,
  duration: DURATION,
  thresholds: {
    http_req_duration: ['p(95)<500', 'p(99)<1000'],
    http_req_failed: ['rate<0.05'],
  },
  tags: {
    name: 'smoke-test',
  }
};

export default function() {
  const headers = {
    'Content-Type': 'application/json',
    'Idempotency-Key': `idem-${Date.now()}-${Math.random()}`
  };

  const payload = JSON.stringify({
    external_event_id: `BANK-${Date.now()}-${Math.random()}`,
    account_id: 'ACC-001',
    event_type: 'DEPOSIT',
    amount: 10000,
    currency: 'KRW',
    occurred_at: new Date().toISOString()
  });

  const res = http.post(`${BASE_URL}/api/v1/transaction-events`, payload, { headers });

  check(res, {
    'status is 200 or 409': (r) => r.status === 200 || r.status === 409,
    'response time < 500ms': (r) => r.timings.duration < 500,
    'has event_id': (r) => r.json('event_id') !== undefined,
  });

  sleep(1);
}
