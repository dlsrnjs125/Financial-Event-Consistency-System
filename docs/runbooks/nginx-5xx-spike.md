# Nginx 5xx Spike Runbook

## 1. 증상

- Nginx 5xx rate 증가
- upstream response time 증가
- Blue-Green 전환 직후 smoke 실패 가능

## 2. 사용자 영향

외부 금융사 이벤트 수신 실패가 증가할 수 있다. client retry가 발생하면 duplicate storm으로 이어질 수 있으므로 idempotency와 DB 정합성 검증이 함께 필요하다.

## 3. 즉시 확인할 지표

- Nginx 5xx count
- upstream response time
- API `financial_http_errors_total`
- readiness dependency status

## 4. 확인 명령

```bash
make deploy-status
make deploy-smoke
docker compose exec -T nginx nginx -t
```

## 5. 1차 대응

1. active upstream 확인
2. Nginx config test 실행
3. Blue/Green API health 확인
4. 전환 직후 장애라면 rollback 실행
5. rollback 후 smoke와 정합성 검증 실행

## 6. 복구 확인 기준

- Nginx 5xx 증가 중단
- `/health`, `/ready` 200
- deploy-smoke 통과
- duplicated ledger/event count 0

## 7. 재발 방지

- upstream snippet 변경 전후 `nginx -t` 유지
- reload 실패 시 backup restore 유지
- Nginx 내부에서 target API health 확인

## 8. 사후 기록 템플릿

- 발생 시간:
- active color:
- upstream target:
- rollback 여부:
- smoke 결과:
- 정합성 검증 결과:
