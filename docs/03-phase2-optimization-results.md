# Phase 2: Async + Connection Pool 최적화 실험 결과

## 1. 실험 목표

Phase 1에서 발견한 Connection 생성 오버헤드 병목을 해결하고, 단계별 최적화로 TPS 한계를 측정한다.

---

## 2. 최적화 단계별 결과

| 단계 | 방식 | Pool | Batch | TPS | Latency | CPU | 개선율 |
|------|------|------|-------|-----|---------|-----|--------|
| Phase 1 | 동기, No Pool | - | 1 | 70 | 15ms | 35% | 기준 |
| Phase 2 | Async + Pool | 50 | 1 | 175 | 2.8ms | 15% | 2.5배 |
| Phase 2-B | 동시 요청 | 50 | 1 | 5,100 | 6.3ms | 51% | 73배 |
| Phase 2-C | Pool + Batch | 100 | 100 | 17,400 | 0.26ms | 28% | 248배 |
| **Phase 2-D** | **Max Pool + Large Batch** | **200** | **500** | **17,500** | **0.30ms** | **44%** | **250배** |

---

## 3. 단계별 최적화 기법

### Phase 1 → Phase 2: Connection Pool
```python
# Before: 매번 새 연결
conn = psycopg2.connect(...)
cur.execute(...)
conn.close()

# After: Pool에서 재사용
pool = await asyncpg.create_pool(min_size=10, max_size=50)
async with pool.acquire() as conn:
    await conn.execute(...)
```

**효과:** TPS 70 → 175 (2.5배)

---

### Phase 2 → Phase 2-B: 동시 요청
```python
# Before: 순차 처리
latency = await insert_one()

# After: 동시 처리
tasks = [insert_one() for _ in range(50)]
results = await asyncio.gather(*tasks)
```

**효과:** TPS 175 → 5,100 (29배)

---

### Phase 2-B → Phase 2-C: Batch INSERT
```python
# Before: 개별 INSERT
await conn.execute("INSERT ... VALUES ($1, $2)")

# After: Batch INSERT
await conn.executemany("INSERT ... VALUES ($1, $2)", 
                       [(data1), (data2), ..., (data100)])
```

**효과:** TPS 5,100 → 17,400 (3.4배)

---

### Phase 2-C → Phase 2-D: Pool + Batch 극대화
```python
# Pool: 100 → 200
# Batch: 100 → 500
pool = await asyncpg.create_pool(min_size=50, max_size=200)
batch_size = 500
```

**효과:** TPS 17,400 → 17,500 (한계 도달)

---

## 4. 한계점 분석

### TPS ~17,500에서 더 이상 안 올라가는 이유

| 가능성 | 분석 | 결론 |
|--------|------|------|
| CPU | 44%로 여유 있음 | ❌ 원인 아님 |
| Connection Pool | 200개 중 일부만 사용 | ❌ 원인 아님 |
| **PostgreSQL 처리 한계** | WAL, Disk I/O | ⭐ 주 원인 |

### PostgreSQL 병목 상세

1. **WAL (Write-Ahead Log):** 모든 INSERT가 WAL에 기록됨
2. **Disk I/O:** NVMe SSD지만 쓰기 속도 한계 존재
3. **Lock Contention:** 동시 INSERT 시 테이블/인덱스 락 경쟁

---

## 5. 핵심 인사이트

### 병목은 단계별로 이동한다
```
Phase 1: Connection 생성 병목
    ↓ (Pool 도입)
Phase 2: 순차 처리 병목
    ↓ (동시 요청)
Phase 2-B: 네트워크 왕복 병목
    ↓ (Batch INSERT)
Phase 2-C/D: PostgreSQL 자체 한계
    ↓ (더 이상 Application 레벨 최적화 불가)
```

### 다음 단계 최적화 방향

Application 레벨 한계 도달 → DB 레벨 최적화 필요:

1. PostgreSQL 튜닝 (`synchronous_commit = off`)
2. 파티셔닝
3. 읽기/쓰기 분리 (Read Replica)
4. 다른 DB 사용 (TimescaleDB, ClickHouse)

---

## 6. 면접 예상 질문

### Q1. 최종 TPS가 17,500인데, 더 올리려면 어떻게 해야 하나요?

> "Application 레벨에서는 Connection Pool, 동시 요청, Batch INSERT 모두 적용했습니다.
> 더 올리려면 DB 레벨 최적화가 필요합니다:
> 1. synchronous_commit = off로 WAL 동기화 끄기 (데이터 손실 위험)
> 2. 테이블 파티셔닝으로 Lock 경쟁 줄이기
> 3. TimescaleDB 같은 시계열 DB 사용"

### Q2. Batch INSERT의 단점은?

> "Latency가 Batch 크기만큼 지연됩니다.
> Batch 500이면 500건이 모여야 INSERT됩니다.
> 실시간 응답이 중요한 API에는 부적합하고,
> 로그 수집, 이벤트 적재 같은 배치성 작업에 적합합니다."

### Q3. Pool 크기를 어떻게 정하나요?

> "CPU 코어 수와 DB 연결 한계를 고려합니다.
> PostgreSQL 기본 max_connections는 100입니다.
> 우리 실험에서 Pool 100 → 200으로 늘려도 TPS 차이가 없었습니다.
> 이미 병목이 Pool이 아닌 DB 처리 속도였기 때문입니다."

---

## 7. 최종 성과

**Intel N100 (4코어, 16GB RAM)에서:**

| 지표 | Phase 1 | Phase 2-D | 개선 |
|------|---------|-----------|------|
| TPS | 70 | 17,500 | **250배** |
| Latency | 15ms | 0.30ms | **50배 감소** |

---

## 8. 기술 스택

| 컴포넌트 | 역할 |
|----------|------|
| Python 3.11 | Generator |
| asyncpg | Async PostgreSQL Driver |
| asyncio.gather | 동시 요청 처리 |
| executemany | Batch INSERT |
| PostgreSQL 15 | Database |
