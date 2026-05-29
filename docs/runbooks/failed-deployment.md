# Failed Deployment Runbook

## 1. 증상

- Green `/health` 또는 `/ready` 실패
- Nginx config test 실패
- 전환 후 deploy-smoke 실패
- Nginx 5xx 증가

## 2. 사용자 영향

Green 전환 전 실패라면 사용자 영향은 없어야 한다. 전환 후 실패라면 즉시 Blue로 traffic rollback하고 정합성 검증을 수행한다.

## 3. 즉시 확인할 지표

- active upstream color
- Green health/readiness
- Nginx 5xx
- deploy-smoke 결과
- duplicate ledger/event count

## 4. 확인 명령

```bash
make deploy-status
make deploy-smoke
make deploy-rollback
make deploy-verify
```

## 5. 1차 대응

1. Green 검증 실패면 전환하지 않는다.
2. 전환 후 smoke 실패면 rollback 실행
3. rollback 후 Blue `/ready`와 smoke 확인
4. DB rollback은 자동 수행하지 않는다.
5. ledger/account 정합성 검증 실행

## 6. 복구 확인 기준

- active upstream이 Blue로 복구
- `/health`, `/ready` 200
- deploy-smoke 통과
- duplicate ledger/event count 0

## 7. 재발 방지

- Green 검증 항목 강화
- Nginx reload 실패 시 backup restore 유지
- host port와 container port 혼동 방지
- migration은 backward-compatible 원칙 유지

## 8. 사후 기록 템플릿

- 발생 시간:
- 실패 단계:
- active color:
- rollback 여부:
- 정합성 검증 결과:
