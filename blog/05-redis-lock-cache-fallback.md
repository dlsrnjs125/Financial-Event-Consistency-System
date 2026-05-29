# 5편. Redis Lock/Cache를 어디까지 믿어야 할까?

## 들어가며

PostgreSQL만으로도 정합성을 보장할 수 있다면, **왜 Redis를 쓸까요?**

이 편에서는 Redis의 역할, 한계, 그리고 장애 대응을 다룹니다.

---

## Redis를 사용하는 이유

### 문제
```
동일 external_event_id로 100개의 동시 요청
  ↓
모두 PostgreSQL로 직진
  ↓
DB Connection Pool 고갈, Lock 경합, 성능 저하
```

### 해결책
```
Redis Lock으로 동시 요청 1개만 DB 진입 허용
  ↓
나머지 99개는 대기 또는 기존 결과 반환
  ↓
DB 부하 감소, 성능 향상
```

---

## Redis Key 설계

### 1. Lock Key (중복 요청 방지 잠금)
```python
key = f"lock:idempotency:{idempotency_key}"
ttl = 10  # 초

# Lock 획득 시도
result = redis.set(key, "locked", nx=True, ex=ttl)

if result:
    # Lock 획득 성공
    process_transaction()
else:
    # Lock 획득 실패 (이미 처리 중)
    return 202 Accepted
```

### 2. Idempotency Cache (이미 처리된 요청 결과)
```python
key = f"cache:idempotency:{idempotency_key}"
ttl = 3600  # 1시간

# 캐시 저장
redis.setex(key, ttl, json.dumps(response))

# 캐시 조회
cached = redis.get(key)
if cached:
    return json.loads(cached)
```

### 3. Rate Limit Counter (외부 시스템당 요청 제한)
```python
key = f"rate-limit:external-system:{client_id}"
ttl = 60  # 1분

count = redis.incr(key)
if count == 1:
    redis.expire(key, ttl)

if count > MAX_REQUESTS_PER_MINUTE:
    return 429 Too Many Requests
```

---

## Redis 처리 흐름

### 정상 시나리오
```
[요청 1] Redis Lock 획득 (OK)
          ↓
         DB 처리
          ↓
         Redis Cache 저장
          ↓
         응답 반환
         ↓
[요청 2] Redis Lock 획득 실패
          ↓
         Redis Cache 조회 (HIT)
          ↓
         기존 응답 즉시 반환 ✅

결과: 높은 응답 속도, DB 부하 감소
```

### Redis 장애 시나리오
```
[요청 1] Redis Lock 획득 실패 (장애)
          ↓
         Warning 로그 기록
          ↓
         PostgreSQL Transaction으로 처리
          ↓
         응답 반환
         ↓
[요청 2] Redis Cache 조회 실패 (장애)
          ↓
         Warning 로그 기록
          ↓
         PostgreSQL 조회
          ↓
         기존 결과 반환 ✅

결과: 정합성은 깨지지 않음, 응답 속도만 감소
```

---

## Redis 장애 Fallback 코드 (Python)

```python
import logging
from typing import Optional, Dict, Any

from redis.exceptions import ConnectionError, RedisError, TimeoutError

logger = logging.getLogger(__name__)

def mask_idempotency_key(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return f"{value[:4]}...{value[-4:]}"

class IdempotencyManager:
    def __init__(self, redis_client, db_session):
        self.redis = redis_client
        self.db = db_session
    
    def acquire_lock(self, idempotency_key: str) -> bool:
        """
        Redis Lock 획득 시도
        
        Returns:
            True if lock acquired, False otherwise
        """
        try:
            key = f"lock:idempotency:{idempotency_key}"
            result = self.redis.set(key, "locked", nx=True, ex=10)
            return bool(result)
        except (ConnectionError, TimeoutError, RedisError) as exc:
            logger.warning(
                "redis_lock_fallback",
                extra={
                    "dependency": "redis",
                    "operation": "lock_acquire",
                    "fallback_used": True,
                    "error_type": type(exc).__name__,
                    "idempotency_key_masked": mask_idempotency_key(idempotency_key),
                },
            )
            # Redis 장애 → PostgreSQL로 처리
            return None  # None = fallback to DB
    
    def get_cached_result(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """
        Redis Cache 조회
        """
        try:
            key = f"cache:idempotency:{idempotency_key}"
            cached = self.redis.get(key)
            if cached:
                logger.info(
                    "idempotency_cache_hit",
                    extra={
                        "dependency": "redis",
                        "operation": "cache_get",
                        "idempotency_key_masked": mask_idempotency_key(idempotency_key),
                    },
                )
                return json.loads(cached)
        except (ConnectionError, TimeoutError, RedisError) as exc:
            logger.warning(
                "redis_cache_get_fallback",
                extra={
                    "dependency": "redis",
                    "operation": "cache_get",
                    "fallback_used": True,
                    "error_type": type(exc).__name__,
                    "idempotency_key_masked": mask_idempotency_key(idempotency_key),
                },
            )
            # Redis 장애 → DB 조회로 fallback
        
        return None
    
    def cache_result(self, idempotency_key: str, result: Dict[str, Any]) -> bool:
        """
        Redis에 결과 캐시 저장
        """
        try:
            key = f"cache:idempotency:{idempotency_key}"
            self.redis.setex(key, 3600, json.dumps(result))
            return True
        except (ConnectionError, TimeoutError, RedisError) as exc:
            logger.warning(
                "redis_cache_set_fallback",
                extra={
                    "dependency": "redis",
                    "operation": "cache_set",
                    "fallback_used": True,
                    "error_type": type(exc).__name__,
                    "idempotency_key_masked": mask_idempotency_key(idempotency_key),
                },
            )
            # Redis 장애 → 무시하고 진행
            return False
    
    def handle_idempotent_request(
        self,
        idempotency_key: str,
        request_body: Dict[str, Any],
        process_func
    ) -> Dict[str, Any]:
        """
        멱등성 요청 처리
        
        Args:
            idempotency_key: 멱등성 키
            request_body: 요청 본문
            process_func: 실제 처리 함수
        
        Returns:
            처리 결과
        """
        
        # 1. Redis Cache 확인
        cached_result = self.get_cached_result(idempotency_key)
        if cached_result:
            return cached_result
        
        # 2. PostgreSQL에서 멱등성 기록 확인
        db_record = self.db.query(IdempotencyRecord).filter(
            IdempotencyRecord.idempotency_key == idempotency_key
        ).with_for_update().first()
        
        if db_record:
            # 기존 기록 발견
            if db_record.request_hash != compute_hash(request_body):
                raise DuplicateIdempotencyKeyError("Different body for same key")
            
            if db_record.status == 'COMPLETED':
                result = db_record.response_body
                # Redis에 캐시 저장 (장애면 무시)
                self.cache_result(idempotency_key, result)
                return result
            else:
                return 202  # Processing
        
        # 3. Redis Lock 시도
        lock_acquired = self.acquire_lock(idempotency_key)
        
        # lock_acquired가 None이면 Redis 장애 → DB로 처리
        # lock_acquired가 False면 이미 처리 중 → 대기 또는 폴링
        
        if lock_acquired is False:
            # Lock 획득 실패 (처리 중)
            logger.info(
                "redis_lock_not_acquired",
                extra={
                    "dependency": "redis",
                    "operation": "lock_acquire",
                    "result": "rejected",
                    "reason": "lock_not_acquired",
                    "idempotency_key_masked": mask_idempotency_key(idempotency_key),
                },
            )
            return 202  # Accepted
        
        try:
            # 4. 실제 처리 실행
            result = process_func()
            
            # 5. Redis 캐시 저장 시도
            self.cache_result(idempotency_key, result)
            
            return result
            
        except TransactionProcessingError as exc:
            logger.error(
                "transaction_processing_failed",
                extra={
                    "error_type": type(exc).__name__,
                    "idempotency_key_masked": mask_idempotency_key(idempotency_key),
                },
            )
            raise
```

---

## 테스트: Redis 장애 시나리오

### 테스트 1: Redis Lock 실패해도 정합성 유지
```python
def test_duplicate_prevention_when_redis_lock_fails():
    """Redis Lock이 안 되어도 중복 처리를 방지하는가?"""
    
    # Redis Lock 시뮬레이션 실패
    def mock_redis_lock_fail(*args, **kwargs):
        raise ConnectionError("Redis connection failed")
    
    redis.set = mock_redis_lock_fail
    
    account = create_account()
    
    # 같은 요청을 동시에 100번 (Redis Lock 불가능)
    responses = concurrent.run(
        lambda: client.post(
            "/api/v1/transaction-events",
            json={
                "external_event_id": "BANK-003",
                "account_id": account.id,
                "event_type": "DEPOSIT",
                "amount": 5000
            },
            headers={"Idempotency-Key": "idem-003"}
        ),
        times=100
    )
    
    # 검증: PostgreSQL Unique Constraint로 1개만 처리
    assert db.count(ledger_entries) == 1  # ✅
    assert account.balance == 5000        # ✅
```

### 테스트 2: Redis Cache 미스해도 DB에서 조회
```python
def test_result_retrieval_when_redis_cache_misses():
    """Redis Cache가 없어도 DB에서 결과를 조회하는가?"""
    
    account = create_account()
    
    # 첫 번째 요청 (처리 + 캐시)
    resp1 = client.post(
        "/api/v1/transaction-events",
        json={
            "external_event_id": "BANK-004",
            "account_id": account.id,
            "event_type": "DEPOSIT",
            "amount": 7000
        },
        headers={"Idempotency-Key": "idem-004"}
    )
    
    event_id_1 = resp1.json()["event_id"]
    
    # Redis 캐시 지우기
    redis.flushdb()
    
    # 두 번째 요청 (캐시 미스, DB 조회)
    resp2 = client.post(
        "/api/v1/transaction-events",
        json={
            "external_event_id": "BANK-004",
            "account_id": account.id,
            "event_type": "DEPOSIT",
            "amount": 7000
        },
        headers={"Idempotency-Key": "idem-004"}
    )
    
    event_id_2 = resp2.json()["event_id"]
    
    # 검증: 같은 event_id 반환, 거래는 1건만
    assert event_id_1 == event_id_2  # ✅
    assert db.count(ledger_entries) == 1  # ✅
```

---

## 핵심 메시지

> **Redis는 성능 최적화 도구이지, 정합성 보장 도구가 아니다.**
>
> **Redis 장애가 발생하면 응답 속도는 느려지지만, 정합성은 PostgreSQL에 의해 여전히 보장된다.**

---

## Redis 도입 전후 비교

비교 대상:

1. PostgreSQL Unique Constraint only
2. Redis Lock + PostgreSQL Unique Constraint
3. Redis Cache + PostgreSQL Unique Constraint

측정 지표:

- p95 latency
- p99 latency
- DB transaction count
- cache hit ratio
- `financial_redis_lock_acquire_failed_total`
- duplicate processing rate

해석 기준:

Redis Lock과 Cache는 DB 부하와 중복 요청 응답시간을 줄이는 데 기여해야 한다.
하지만 Redis가 없어도 duplicate processing rate는 0%여야 한다.

---


## 개발 중 실제로 발견한 문제와 수정

처음에는 Redis lock/cache를 중복 요청 완화 계층으로 붙였기 때문에, Redis가 내려가면 성능은 떨어지더라도 DB unique constraint가 최종 방어선을 해줄 것이라고 봤다. Phase 9 Redis Down 실행에서 실제로 중복 Ledger는 0건이었다. 하지만 일부 5xx가 발생했다. 이 결과는 "정합성은 유지됐지만 Redis 장애가 API 가용성으로 번졌다"는 의미였다.

이후 수정한 기준은 세 가지였다.

1. Redis connection error/timeout은 fallback 대상이다. 요청 처리는 DB transaction과 idempotency record 기준으로 계속한다.
2. Redis lock 미획득은 장애가 아니다. 같은 key가 이미 처리 중이라는 신호이므로 `rejected`, `lock_not_acquired`로 기록한다.
3. Redis cache miss는 failure가 아니다. Redis get 자체가 성공했고 값이 없을 뿐이므로 cache result metric으로 분리한다.

이 구분을 하지 않으면 Grafana에서 duplicate storm을 Redis 장애처럼 해석하거나, cache miss가 많은 정상 상황을 장애로 오해할 수 있다.

검증은 다음 흐름으로 했다.

```bash
make failure-redis-down
make phase10-redis-down-check
make failure-redis-up
make k6-verify
```

최종 판단 기준은 HTTP 200 비율만이 아니었다. Redis가 없어도 PostgreSQL 기준 duplicate ledger/event count가 0건인지, 그리고 Redis 장애 단독으로 5xx가 확산되지 않는지를 함께 봤다.

남은 한계도 있다. 로컬 단일 Redis 컨테이너의 down/up은 운영 Redis cluster의 failover, network partition, replication lag를 모두 설명하지 못한다. 다만 이 프로젝트에서는 Redis가 실패해도 최종 정합성이 DB에 남는 구조를 먼저 고정했다.
