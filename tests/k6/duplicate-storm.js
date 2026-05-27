import http from 'k6/http';
import { check, sleep, Counter } from 'k6';

// Configuration
const BASE_URL = __ENV.BASE_URL || 'http://localhost:80';
const DUPLICATE_KEY = 'idem-duplicate-storm-001';
const DUPLICATE_EVENT_ID = 'BANK-DUPLICATE-STORM-001';

// Counters
const duplicateCounter = new Counter('duplicate_requests');
const successCounter = new Counter('success_requests');
const conflictCounter = new Counter('conflict_requests');

export const options = {
  vus: 100,
  duration: '30s',
  thresholds: {
    http_req_duration: ['p(95)<1000'],
    http_req_failed: ['rate<0.05'],
  },
  tags: {
    name: 'duplicate-storm-test',
  }
};

export default function() {
  const headers = {
    'Content-Type': 'application/json',
    'Idempotency-Key': DUPLICATE_KEY  // All VUs use same key
  };

  const payload = JSON.stringify({
    external_event_id: DUPLICATE_EVENT_ID,  // All VUs use same event_id
    account_id: 'ACC-001',
    event_type: 'DEPOSIT',
    amount: 10000,
    currency: 'KRW',
    occurred_at: new Date().toISOString()
  });

  const res = http.post(`${BASE_URL}/api/v1/transaction-events`, payload, { headers });

  if (res.status === 200) {
    successCounter.add(1);
  } else if (res.status === 409) {
    conflictCounter.add(1);
  } else {
    duplicateCounter.add(1);
  }

  check(res, {
    'status is 200 or 409': (r) => r.status === 200 || r.status === 409,
    'no 500 errors': (r) => r.status !== 500,
  });

  sleep(0.1);
}

export function teardown(data) {
  console.log(`
    ===== Duplicate Storm Test Results =====
    Success (200): ${successCounter.value()}
    Conflict (409): ${conflictCounter.value()}
    Errors: ${duplicateCounter.value()}
    Total: ${successCounter.value() + conflictCounter.value() + duplicateCounter.value()}
    =====================================
  `);
}
