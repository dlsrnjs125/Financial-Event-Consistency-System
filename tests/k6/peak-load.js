import http from 'k6/http';
import { check, sleep } from 'k6';

// Configuration
const BASE_URL = __ENV.BASE_URL || 'http://localhost:80';

export const options = {
  stages: [
    { duration: '10s', target: 20 },   // Ramp up
    { duration: '30s', target: 50 },   // Sustain peak
    { duration: '10s', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],
    http_req_failed: ['rate<0.05'],
  },
  tags: {
    name: 'peak-load-test',
  }
};

export default function() {
  const headers = {
    'Content-Type': 'application/json',
    'Idempotency-Key': `idem-peak-${Date.now()}-${Math.random()}`
  };

  const payload = JSON.stringify({
    external_event_id: `BANK-PEAK-${Date.now()}-${Math.random()}`,
    account_id: 'ACC-001',
    event_type: 'DEPOSIT',
    amount: Math.floor(Math.random() * 100000),
    currency: 'KRW',
    occurred_at: new Date().toISOString()
  });

  const res = http.post(`${BASE_URL}/api/v1/transaction-events`, payload, { headers });

  check(res, {
    'status is 200 or 409': (r) => r.status === 200 || r.status === 409,
    'no 500 errors': (r) => r.status !== 500,
  });

  sleep(0.5);
}
