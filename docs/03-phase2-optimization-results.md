# Phase 2: Async + Connection Pool 최적화 실험 결과

## 1. 실험 목표

Phase 1에서 발견한 Connection 생성 오버헤드 병목을 해결하고, 단계별 최적화로 TPS 한계를 측정한다.

---

## 2. 최적화 단계별 결과

### 전체 요약

| 단계 | 방식 | 목표 TPS | 실제 TPS | Latency | CPU | 개선율 |
|------|------|----------|----------|---------|-----|--------|
| Phase 1 | 동기, No Pool | 200 | ~70 | ~15ms | ~35% | 기준 |
| Phase 2 | Async + Pool(50) | 200 | ~175 | ~2.8ms | ~15% | **2.5배** |
| Phase 2-B | 동시 요청 50개 | 500 | ~493 | ~12ms | ~15% | **7배** |
| Phase 2-B | 동시 요청 50개 | 1000 | ~980 | ~14ms | ~30% | **14배** |
| Phase 2-B | 동시 요청 50개 | 2000 | ~1,900 | ~9.5ms | ~34% | **27배** |
| Phase 2-B | 동시 요청 50개 | 4000 | ~3,780 | ~6.5ms | ~40% | **54배** |
| Phase 2-B | 동시 요청 50개 | 8000 | ~5,100 | ~6.3ms | ~51% | 한계 도달 |
| Phase 2-C | Pool(100) + Batch | 8000 | ~7,950 | ~0.21ms | ~24% | **113배** |
| Phase 2-C | Pool(100) + Batch | 10000 | ~9,930 | ~0.26ms | ~28% | **142배** |

---

## 3. 단계별 상세 분석

### 3-1. Phase 1 → Phase 2: Connection Pool 도입

**변경 내용:**
```python
# Phase 1: 매번 새 연결
conn = psycopg2.connect(...)  # 매 요청마다
cur.execute(...)
conn.close()

# Phase 2: Connection Pool
pool = await asyncpg.create_pool(min_size=10, max_size=50)
async with pool.acquire() as conn:  # 풀에서 가져다 씀
    await conn.execute(...)
```

**결과:**
- TPS: 70 → 175 (2.5배 향상)
- Latency: 15ms → 2.8ms (5배 감소)
- CPU: 35% → 15% (절반 감소)

**원리:**
- TCP 3-way handshake 제거
- PostgreSQL 인증 과정 제거  
- Connection 객체 재사용

---

### 3-2. Phase 2 → Phase 2-B: 동시 요청

**변경 내용:**
```python
# Phase 2: 순차 처리
latency = await insert_one()  # 하나 끝나야 다음

# Phase 2-B: 동시 처리
tasks = [insert_one() for _ in range(50)]
results = await asyncio.gather(*tasks)  # 50개 동시
```

**결과 (TPS 500 목표):**
- TPS: 175 → 493 (2.8배 향상)

**결과 (TPS 8000 목표):**
- TPS: ~5,100에서 한계
- CPU: ~51%

**병목 원인:**
- Connection Pool 크기(50) 제한
- 개별 INSERT 네트워크 오버헤드

---

### 3-3. Phase 2-B → Phase 2-C: Pool 확장 + Batch INSERT

**변경 내용:**
```python
# Phase 2-B: 개별 INSERT
await conn.execute("INSERT ... VALUES ($1, $2, $3)")

# Phase 2-C: Batch INSERT
pool = create_pool(max_size=100)  # 50 → 100
await conn.executemany("INSERT ... VALUES ($1, $2, $3)", 
                       [(tx1), (tx2), ..., (tx100)])  # 100건 한번에
```

**결과:**
- TPS: 5,100 → 9,930 (1.9배 향상)
- Latency: 6.3ms → 0.26ms (24배 감소!)
- CPU: 51% → 28% (절반 감소)

**원리:**
- 네트워크 왕복 100번 → 1번
- DB 트랜잭션 오버헤드 감소
- Pool 크기 증가로 동시 처리 확대

---

## 4. 핵심 인사이트

### 4-1. 병목은 단계별로 이동한다
```
Phase 1: Connection 생성 → 해결
     ↓
Phase 2: 순차 처리 → 해결  
     ↓
Phase 2-B: Pool 크기 + 네트워크 왕복 → 해결
     ↓
Phase 2-C: ??? (다음 병목 찾기)
```

### 4-2. 측정 없이 최적화는 불가능

- "Connection Pool 쓰면 빨라진다" (O)
- "얼마나 빨라지는가?" → 측정 필요
- 우리 환경에서: 2.5배 → 7배 → 142배

### 4-3. Batch 처리의 위력

| 방식 | 네트워크 왕복 | TPS |
|------|--------------|-----|
| 개별 INSERT | 5,100회/초 | ~5,100 |
| Batch 100건 | 100회/초 | ~10,000 |

**네트워크가 병목일 때 Batch가 가장 효과적**

---

## 5. 면접 예상 질문

### Q1. Connection Pool이 왜 성능을 개선하나요?

> "매 요청마다 DB 연결을 생성하면 TCP handshake, 인증 과정이 반복됩니다. 
> 우리 실험에서 15ms의 latency 중 약 10ms가 이 오버헤드였습니다.
> Pool을 사용하면 미리 만들어둔 연결을 재사용하므로 latency가 2.8ms로 줄었습니다."

### Q2. 동시 요청을 늘리면 무조건 좋아지나요?

> "아닙니다. Pool 크기가 50인데 동시 요청을 100개 보내면 50개는 대기합니다.
> 또한 DB 서버의 처리 능력, 네트워크 대역폭에도 한계가 있습니다.
> 우리 실험에서 Phase 2-B는 TPS 5,100에서 한계에 도달했습니다."

### Q3. Batch INSERT의 트레이드오프는?

> "장점은 네트워크 왕복을 줄여 TPS를 높이는 것입니다.
> 단점은 Latency가 Batch 크기만큼 지연됩니다.
> 실시간 응답이 중요한 API에는 적합하지 않고,
> 로그 적재, 이벤트 수집 같은 배치성 작업에 적합합니다."

### Q4. 다음 병목은 무엇일까요?

> "현재 TPS 10,000에서 CPU 28%입니다. 아직 여유가 있으므로:
> 1. PostgreSQL의 WAL(Write-Ahead Log) 병목
> 2. Disk I/O 병목
> 3. Python asyncio 이벤트 루프 오버헤드
> 를 의심할 수 있습니다. 다음 단계로 DB 모니터링이 필요합니다."

---

## 6. 기술 스택

| 컴포넌트 | 버전 | 역할 |
|----------|------|------|
| Python | 3.11 | Generator |
| asyncpg | 0.29.0 | Async PostgreSQL Driver |
| PostgreSQL | 15 | Database |
| Docker | - | 컨테이너 환경 |

---

## 7. 메트릭 파일

- `analysis/data/phase1_generator_metrics_final.csv`
- `analysis/data/phase2_generator_metrics.csv` (진행 중)

---

## 8. 최종 성과

**Intel N100 (4코어, 3.4GHz)에서:**

| 지표 | Phase 1 | Phase 2-C | 개선 |
|------|---------|-----------|------|
| TPS | 70 | 9,930 | **142배** |
| Latency | 15ms | 0.26ms | **58배 감소** |
| CPU 효율 | 35% | 28% | 더 효율적 |
