# Phase 3: Redis Buffer + Consumer 구현

## 1. 목표

Phase 2에서 PostgreSQL 직접 INSERT의 한계(TPS 17,500)를 확인했다.
Phase 3에서는 Redis를 버퍼로 사용하여 안정적인 비동기 처리 파이프라인을 구축한다.

---

## 2. 아키텍처

### Phase 2 (이전)
```
Generator → PostgreSQL (직접 INSERT)
문제: DB 장애 시 데이터 유실, 스파이크 대응 불가
```

### Phase 3 (현재)
```
Generator → Redis Queue → Consumer → PostgreSQL
장점: 버퍼 역할, 데이터 유실 방지, 독립적 스케일링
```

---

## 3. 구현 내용

### 3-1. Generator 수정

**Redis로 데이터 푸시:**
```python
async def push_batch():
    transactions = [generate_transaction() for _ in range(batch_size)]
    pipe = redis_client.pipeline()
    for tx in transactions:
        pipe.lpush("tx_queue", json.dumps(tx))
    await pipe.execute()
```

**현실적인 데이터 생성:**
- 500명 사용자 풀 (VIP 2%, Premium 13%, Normal 85%)
- 10개 카테고리 (편의점, 커피, 식당, 배달, 온라인쇼핑 등)
- 영업시간 반영 (백화점 10~21시, 편의점 24시간)
- 금액 분포 (소액 70%, 중액 25%, 고액 5%)

### 3-2. Consumer 구현

**Redis → FDS 검사 → PostgreSQL:**
```python
async def run_consumer():
    while True:
        # Redis에서 배치로 가져오기
        results = await pipe.execute()  # RPOP * batch_size
        
        # FDS 룰 적용
        for tx in transactions:
            is_fraud, fraud_rules = fds_engine.check(tx)
            tx['is_fraud'] = is_fraud
            tx['fraud_rules'] = fraud_rules
        
        # PostgreSQL에 Batch INSERT
        await conn.executemany(INSERT_QUERY, processed_txs)
```

### 3-3. FDS 룰 엔진

| 룰 | 조건 | 탐지 대상 |
|----|------|----------|
| Velocity | 1분 내 5회 이상 결제 | 카드 도용 |
| Amount Spike | 평소의 10배 이상 금액 | 비정상 결제 |
| Dawn High Amount | 새벽 시간 + 500만원 이상 | 시간대 이상 |
| Unusual Category | 일반등급 + 명품 1천만원 이상 | 카테고리 이상 |

---

## 4. 실험 결과

### 4-1. Generator 10,000 TPS + Consumer

| 지표 | Generator | Consumer |
|------|-----------|----------|
| TPS | ~9,900 | ~5,000 |
| Queue | 계속 증가 | - |
| 상태 | ❌ 불균형 | - |

**문제:** Consumer가 Generator를 못 따라감 → Queue 무한 증가

### 4-2. Generator 5,000 TPS + Consumer (균형)

| 지표 | Generator | Consumer |
|------|-----------|----------|
| TPS | ~4,970 | ~4,990 |
| Queue | 0~500 (안정) | - |
| E2E Latency | - | ~80ms |
| CPU | ~30% | ~30% |
| 상태 | ✅ 균형 | ✅ 균형 |

**결과:** 안정적인 파이프라인 동작

---

## 5. Redis 버퍼의 역할

### 왜 Redis를 사용하는가?
```
상황 1: 정상
Generator (5,000 TPS) → Redis (Queue: 500) → Consumer (5,000 TPS)
결과: 균형 유지

상황 2: 트래픽 스파이크
Generator (10,000 TPS) → Redis (Queue: 증가) → Consumer (5,000 TPS)
결과: Queue에 쌓이지만 데이터 유실 없음

상황 3: DB 장애 (1분)
Generator (5,000 TPS) → Redis (Queue: 300,000) → Consumer (중단)
복구 후: Consumer가 Queue 처리 → 데이터 유실 없음
```

### Redis 없이는?
```
Generator (10,000 TPS) → PostgreSQL (5,000 TPS 한계)
결과: 타임아웃, 데이터 유실, 서비스 장애
```

---

## 6. 핵심 인사이트

### 6-1. 버퍼의 중요성

- Producer와 Consumer의 속도 차이를 흡수
- 스파이크 트래픽 대응 가능
- 장애 복구 시 데이터 유실 방지

### 6-2. 배압(Backpressure) 관리

- Queue 길이 모니터링 필수
- Queue가 무한히 쌓이면 메모리 문제
- Generator 속도 조절 또는 Consumer 스케일 아웃 필요

### 6-3. E2E Latency vs Throughput

- 직접 INSERT: Latency 낮음 (0.3ms), Throughput 한계 (17,500 TPS)
- Redis 버퍼: Latency 높음 (80ms), 안정성 높음

---

## 7. 면접 예상 질문

### Q1. Redis를 왜 사용했나요?

> "Generator와 Consumer의 처리 속도 차이를 흡수하기 위해 버퍼로 사용했습니다.
> 트래픽 스파이크 시에도 데이터 유실 없이 순차 처리가 가능하고,
> DB 장애 시에도 Queue에 데이터가 보관되어 복구 후 처리할 수 있습니다."

### Q2. Queue가 계속 쌓이면 어떻게 하나요?

> "두 가지 방법이 있습니다:
> 1. Consumer 스케일 아웃 - 여러 Consumer 인스턴스 실행
> 2. Generator 속도 조절 - Backpressure 적용
> 실험에서 Generator TPS를 10,000에서 5,000으로 낮춰 균형을 맞췄습니다."

### Q3. E2E Latency가 80ms인데 괜찮나요?

> "FDS는 실시간 응답이 필요한 API가 아니라 배치 처리 성격입니다.
> 결제 승인은 별도 시스템에서 처리하고, FDS는 사후 분석 및 알림 용도입니다.
> 80ms는 충분히 빠른 수준이며, 필요시 Consumer를 늘려 개선할 수 있습니다."

---

## 8. 다음 단계

- [ ] Part B: Airflow SLA 모니터링
- [ ] Consumer 스케일 아웃 테스트
- [ ] 데이터 분석 & 시각화
